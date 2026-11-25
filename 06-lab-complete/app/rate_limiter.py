"""
Rate limiting (tiêu chí 7) — sliding window 60 giây, state lưu trong Redis.

Mỗi API key có một sorted set: member = một request, score = thời điểm của request.
Lưu trong Redis (không phải dict trong RAM) nên mọi worker / instance dùng chung bộ đếm
và bộ đếm vẫn còn sau khi restart agent.
"""
import hashlib
import math
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Tối đa RATE_LIMIT_PER_MINUTE request / 60 giây cho mỗi key; vượt → 429 + Retry-After."""
    limit = settings.rate_limit_per_minute
    r = get_redis()
    now = time.time()
    # Không lưu API key thật trong Redis, chỉ lưu bản băm rút gọn
    redis_key = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    member = f"{now}:{uuid.uuid4().hex[:8]}"

    # Thêm request này rồi đếm, trong một giao dịch (MULTI/EXEC) → hai worker không thể
    # cùng thấy "còn chỗ" rồi cùng vượt giới hạn.
    pipe = r.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - WINDOW_SECONDS)
    pipe.zadd(redis_key, {member: now})
    pipe.zcard(redis_key)
    pipe.expire(redis_key, WINDOW_SECONDS + 1)
    _, _, count, _ = pipe.execute()

    if count > limit:
        r.zrem(redis_key, member)  # request bị từ chối không chiếm chỗ trong cửa sổ
        oldest = r.zrange(redis_key, 0, 0, withscores=True)
        retry_after = WINDOW_SECONDS
        if oldest:
            retry_after = max(1, min(WINDOW_SECONDS, math.ceil(oldest[0][1] + WINDOW_SECONDS - now)))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} requests per {WINDOW_SECONDS}s. Retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
