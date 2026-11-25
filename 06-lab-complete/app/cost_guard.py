"""
Cost guard (tiêu chí 8).

Cộng dồn chi phí LLM (tính theo token) vào Redis, theo từng ngày (UTC).
Tổng chi phí trong ngày >= DAILY_BUDGET_USD → HTTP 402.

Lưu ý: check_budget() chạy TRƯỚC khi gọi LLM còn record_cost() chạy SAU, nên request
cuối cùng có thể làm tổng vượt ngân sách một chút trước khi request kế tiếp bị chặn.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_KEY_TTL_SECONDS = 2 * 24 * 3600  # key của ngày cũ tự biến mất


def _budget_key() -> str:
    return "cost:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def estimate_tokens(text: str) -> int:
    """Ước lượng thô: 2 token cho mỗi từ (mock LLM không trả số token thật)."""
    return max(1, len(text.split()) * 2)


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    spent = float(get_redis().get(_budget_key()) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail=f"Daily budget exceeded: ${spent:.6f} of ${settings.daily_budget_usd} used. Resets at 00:00 UTC.",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    r = get_redis()
    key = _budget_key()
    pipe = r.pipeline()
    pipe.incrbyfloat(key, cost)  # nguyên tử: nhiều worker cộng cùng lúc không mất số
    pipe.expire(key, _KEY_TTL_SECONDS)
    pipe.execute()
    return cost
