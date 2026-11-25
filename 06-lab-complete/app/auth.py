"""
API Key authentication (tiêu chí 6).

Client gửi header  X-API-Key: <key>; key phải trùng biến môi trường AGENT_API_KEY.
Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422), nên dùng auto_error=False
rồi tự trả lỗi. Nếu AGENT_API_KEY chưa cấu hình thì từ chối mọi request (fail closed).
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    expected = settings.agent_api_key
    # compare_digest: so sánh thời gian hằng số, tránh lộ key qua timing
    if not api_key or not expected or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Send header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
