# In app/api/routes/health.py
from fastapi import APIRouter, Depends
from app.core.redis.client import client as redis_client

# Change the prefix to match your API structure
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/redis")
async def check_redis_health():
    """
    Redis health check endpoint
    """
    try:
        # Test Redis connection
        is_connected = await redis_client.is_healthy()
        
        # Basic Redis info
        info = {
            "status": "healthy" if is_connected else "unhealthy",
            "connected": is_connected,
        }
        
        # Add additional diagnostics if connected
        if is_connected:
            # Get Redis client stats
            stats = {}  # You can add more detailed stats here
            info["stats"] = stats
            
        return info
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }