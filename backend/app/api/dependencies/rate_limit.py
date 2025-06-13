"""Rate limiting dependencies for FastAPI routes"""

import logging
from fastapi import Request, HTTPException, Depends, status
from typing import Callable, Optional

from app.core.redis.rate_limit import check_rate_limit
from app.core.redis_init import redis_client

logger = logging.getLogger(__name__)

def rate_limiter(
    limit: int = 100,
    window: int = 60,
    key_func: Optional[Callable[[Request], str]] = None
):
    """
    Rate limiting dependency for FastAPI routes
    
    Args:
        limit: Maximum number of requests allowed within window
        window: Time window in seconds
        key_func: Optional function to generate custom keys (default: IP + endpoint)
        
    Usage:
        @app.post("/login")
        async def login(
            request: Request,
            _: None = Depends(rate_limiter(limit=5, window=60))
        ):
            # Login logic...
    """
    async def get_rate_limit_key(request: Request) -> str:
        """Generate a rate limit key from the request"""
        if key_func:
            return key_func(request)
        
        # Default: IP + Path
        client_ip = request.client.host if request.client else "unknown"
        return f"ratelimit:{client_ip}:{request.url.path}"
    
    async def check_rate_limit_dependency(request: Request):
        # Skip if Redis is not available
        if not redis_client:
            logger.warning("Redis not available, skipping rate limiting")
            return
            
        # Get rate limit key
        key = await get_rate_limit_key(request)
        
        # Check rate limit
        allowed = await check_rate_limit(key, limit, window, redis_client=redis_client)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
    
    return check_rate_limit_dependency