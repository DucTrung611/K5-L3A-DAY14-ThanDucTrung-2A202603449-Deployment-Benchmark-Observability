"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

redis.from_url() chỉ tạo client, KHÔNG kết nối: app vẫn khởi động được khi Redis chưa sẵn sàng.
Kết nối thật chỉ xảy ra ở lệnh đầu tiên (ping trong /ready, hoặc lệnh trong /ask).
"""
import redis

from app.config import settings

r = (
    redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    if settings.redis_url
    else None
)


def get_redis() -> "redis.Redis":
    if r is None:
        raise redis.exceptions.ConnectionError("REDIS_URL is not configured")
    return r


def redis_healthy() -> bool:
    """Dùng cho GET /ready: không kết nối được Redis thì trả False."""
    try:
        return bool(get_redis().ping())
    except redis.exceptions.RedisError:
        return False
