"""Redis initialization for FastAPI application"""

import logging
from app.core.redis import RedisClient, RedisCache

logger = logging.getLogger(__name__)

# Global instances
redis_client = None
redis_cache = None

async def init_redis():
    """Initialize Redis client and cache on application startup"""
    global redis_client, redis_cache
    
    try:
        client = RedisClient()
        redis_client = await client.get_client()
        redis_cache = RedisCache(redis_client)
        
        # Test connection
        is_connected = await client.is_healthy()
        if is_connected:
            logger.info("✅ Redis connection established successfully")
        else:
            logger.warning("⚠️ Redis connection test failed")
        
        return redis_client, redis_cache
    except Exception as e:
        logger.error(f"❌ Failed to initialize Redis: {str(e)}")
        raise

async def close_redis():
    """Close Redis connections on application shutdown"""
    global redis_client
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis connections closed")