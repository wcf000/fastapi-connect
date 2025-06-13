"""Caching dependencies for FastAPI routes"""

import functools
import logging
import json
from typing import Any, Callable

from app.core.redis_init import redis_cache

logger = logging.getLogger(__name__)

def cache_response(ttl: int = 300, key_prefix: str = "api:"):
    """
    Cache expensive API responses with Redis
    
    Args:
        ttl: Cache TTL in seconds (default: 5 minutes)
        key_prefix: Prefix for cache keys
        
    Usage:
        @cache_response(ttl=600, key_prefix="users:")
        async def get_user_data(user_id: int):
            # Expensive database query...
            return result
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip caching if Redis is not available
            if not redis_cache:
                return await func(*args, **kwargs)
                
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}{func.__name__}"
            
            # Add arguments to key
            if args:
                cache_key += f":{':'.join(str(arg) for arg in args)}"
            
            # Add keyword arguments to key
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                cache_key += f":{':'.join(f'{k}={v}' for k, v in sorted_kwargs)}"
            
            try:
                # Try to get from cache
                cached_result = await redis_cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_result
                    
                # Cache miss, execute function
                logger.debug(f"Cache miss for {cache_key}")
                result = await func(*args, **kwargs)
                
                # Cache the result
                await redis_cache.set(cache_key, result, ttl=ttl)
                return result
                
            except Exception as e:
                # On error, fall back to the original function
                logger.warning(f"Cache operation failed: {str(e)}. Falling back to uncached operation.")
                return await func(*args, **kwargs)
                
        return wrapper
    return decorator