import redis.asyncio as redis
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_redis():
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.redis_url,
            decode_responses=True
        )
    return _client


async def cache_get(key: str):
    try:
        r = get_redis()
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
        return None


async def cache_set(key: str, value, ttl_seconds: int = 300):
    try:
        r = get_redis()
        await r.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")


async def cache_delete(key: str):
    try:
        r = get_redis()
        await r.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")


async def check_cache_connection() -> bool:
    try:
        r = get_redis()
        await r.ping()
        logger.info("Redis connection OK")
        return True
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return False