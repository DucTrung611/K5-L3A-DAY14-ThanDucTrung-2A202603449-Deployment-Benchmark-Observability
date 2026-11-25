"""
Production AI Agent — Part 6 Final Project

Chạy:   uvicorn app.main:app --workers 2
Kiểm tra: python check_production_ready.py

Luồng của POST /ask:
    verify_api_key (401) → check_rate_limit (429) → check_budget (402) → LLM → record_cost
"""
# Phải import và gọi setup_logging() TRƯỚC mọi thứ khác của app, để định dạng JSON không bị
# đoạn code nào khác ghi đè (xem app/logging_config.py).
from app.logging_config import log_event, setup_logging

setup_logging()

import logging
import time
from contextlib import asynccontextmanager

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import get_redis, redis_healthy
from utils.mock_llm import ask as llm_ask

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Graceful shutdown: uvicorn nhận SIGTERM, ngừng nhận kết nối mới, chờ request đang chạy
    xong rồi mới chạy phần sau `yield`. Không tự đăng ký handler SIGTERM để khỏi chặn uvicorn."""
    log_event("startup", environment=settings.environment, port=settings.port,
              rate_limit_per_minute=settings.rate_limit_per_minute,
              daily_budget_usd=settings.daily_budget_usd,
              api_key_configured=bool(settings.agent_api_key))
    yield
    log_event("shutdown")
    try:
        get_redis().close()
    except redis.exceptions.RedisError:
        pass


app = FastAPI(
    title="Production AI Agent",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v


class AskResponse(BaseModel):
    question: str
    answer: str
    cost_usd: float


# ─────────────────────────────────────────────────────────
# Middleware + xử lý lỗi (không lộ stack trace cho client)
# ─────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if request.url.path != "/health":  # HEALTHCHECK gọi liên tục, không log để đỡ nhiễu
            log_event("request", method=request.method, path=request.url.path, status=status,
                      ms=round((time.perf_counter() - start) * 1000, 1))


@app.exception_handler(redis.exceptions.RedisError)
async def redis_error_handler(request: Request, exc: redis.exceptions.RedisError):
    log_event("redis_error", level=logging.ERROR, path=request.url.path, error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable (Redis)."})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    problems = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
                for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Invalid request body", "errors": problems})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log_event("unhandled_error", level=logging.ERROR, path=request.url.path,
              error=type(exc).__name__, message=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy, KHÔNG phụ thuộc Redis.
    Nếu phụ thuộc Redis, mất Redis sẽ khiến platform restart agent oan mà không sửa được gì."""
    return {"status": "ok", "environment": settings.environment,
            "uptime_seconds": round(time.time() - START_TIME, 1)}


@app.get("/ready")
def ready():
    """Readiness: 200 khi nhận traffic được, 503 khi Redis không kết nối được (LB sẽ bỏ qua instance này)."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is not reachable")
    return {"ready": True}


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    cost = record_cost(estimate_tokens(body.question), estimate_tokens(answer))
    log_event("ask", user_id=body.user_id, question_chars=len(body.question),
              answer_chars=len(answer), cost_usd=round(cost, 8))
    return AskResponse(question=body.question, answer=answer, cost_usd=round(cost, 8))
