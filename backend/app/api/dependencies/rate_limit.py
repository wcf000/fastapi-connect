"""
Rate limiting utilities using Valkey.
Provides functions and decorators for API rate limiting.
"""
import logging
import time
from fastapi import HTTPException, Request, status
from typing import Callable, Optional

from app.core.valkey_init import get_valkey
from app.core.valkey_core.limiting.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

async def rate_limit_request(
    request: Request,
    limit: int = 100,
    window: int = 60,
    key_func: Optional[Callable] = None,
):
    """
    Rate limiting function for FastAPI requests.
    
    Args:
        request: The FastAPI request
        limit: Maximum number of requests allowed within the window
        window: Time window in seconds
        key_func: Function to generate the rate limit key (defaults to IP address)
    
    Raises:
        HTTPException: If rate limit is exceeded
    """
    client = get_valkey()
    if not client:
        # Fail open if Valkey is not available
        logger.warning("Valkey client not initialized. Skipping rate limiting.")
        return
    
    # Get identifier (IP by default)
    identifier = key_func(request) if key_func else request.client.host
    
    # Create rate limit key
    endpoint = request.url.path
    key = f"rate:{endpoint}:{identifier}"
    
    # Check rate limit
    allowed = await check_rate_limit(client, key, limit, window)
    
    if not allowed:
        # Get remaining time until window resets
        ttl = await client.ttl(key)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
            headers={"Retry-After": str(ttl)}
        )


def rate_limiter(limit: int = 100, window: int = 60, key_func: Optional[Callable] = None):
    """
    Decorator for rate limiting FastAPI endpoints.
    
    Args:
        limit: Maximum number of requests allowed within the window
        window: Time window in seconds
        key_func: Function to generate the rate limit key (defaults to IP address)
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            await rate_limit_request(request, limit, window, key_func)
            return await func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator