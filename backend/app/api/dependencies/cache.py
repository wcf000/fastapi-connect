"""
Valkey cache utilities for the FastAPI application.
Provides simple caching operations and decorators.
"""
import functools
import json
import logging
import random
import asyncio
from typing import Any, Callable, Optional, TypeVar

from app.core.valkey_init import get_valkey

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ValkeyCache:
    """Wrapper for Valkey cache operations."""
    
    @staticmethod
    async def get(key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        client = get_valkey()
        if not client:
            logger.warning(f"Valkey client not initialized. Cannot get key: {key}")
            return default
            
        try:
            value = await client.get(key)
            if value is None:
                return default
            return value
        except Exception as e:
            logger.error(f"Error getting value from Valkey: {e}")
            return default
    
    @staticmethod
    async def set(key: str, value: Any, ttl: int = 3600) -> bool:
        """Set a value in the cache with optional TTL."""
        client = get_valkey()
        if not client:
            logger.warning(f"Valkey client not initialized. Cannot set key: {key}")
            return False
            
        try:
            return await client.set(key, value, ex=ttl)
        except Exception as e:
            logger.error(f"Error setting value in Valkey: {e}")
            return False
    
    @staticmethod
    async def delete(key: str) -> bool:
        """Delete a key from the cache."""
        client = get_valkey()
        if not client:
            logger.warning(f"Valkey client not initialized. Cannot delete key: {key}")
            return False
            
        try:
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting key from Valkey: {e}")
            return False
        
    @staticmethod
    async def exists(key: str) -> bool:
        """Check if a key exists in the cache."""
        client = get_valkey()
        if not client:
            logger.warning(f"Valkey client not initialized. Cannot check key: {key}")
            return False
            
        try:
            return await client.exists(key)
        except Exception as e:
            logger.error(f"Error checking key existence in Valkey: {e}")
            return False


def valkey_cache(ttl: int = 3600, key_prefix: str = "cache:"):
    """
    Decorator for caching function results in Valkey.
    
    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for the cache key
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate a cache key
            key_parts = [key_prefix, func.__module__, func.__name__]
            if args:
                key_parts.extend([str(arg) for arg in args])
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}:{v}")
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached = await ValkeyCache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key}")
                if isinstance(cached, str) and cached.startswith("{"):
                    try:
                        return json.loads(cached)
                    except json.JSONDecodeError:
                        pass
                return cached
            
            # Cache miss, execute function
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            try:
                if isinstance(result, (dict, list)):
                    await ValkeyCache.set(cache_key, json.dumps(result), ttl)
                else:
                    await ValkeyCache.set(cache_key, result, ttl)
            except Exception as e:
                logger.error(f"Error caching result: {e}")
                
            return result
        
        return wrapper
    
    return decorator


async def invalidate_cache_keys(*keys: str):
    """Invalidate multiple cache keys."""
    client = get_valkey()
    if not client:
        logger.warning("Valkey client not initialized. Cannot invalidate cache keys.")
        return False
        
    try:
        result = await client.delete(*keys)
        logger.debug(f"Invalidated {result} cache keys")
        return result > 0
    except Exception as e:
        logger.error(f"Error invalidating cache keys: {e}")
        return False


def invalidate_cache(*keys: str):
    """
    Decorator to invalidate cache keys after function execution.
    
    Args:
        keys: Cache keys to invalidate
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await invalidate_cache_keys(*keys)
            return result
        
        return wrapper
    
    return decorator