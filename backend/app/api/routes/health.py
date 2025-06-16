from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.valkey_init import get_valkey

router = APIRouter()

class HealthStatus(BaseModel):
    status: str
    valkey: bool
    details: dict = {}

@router.get("/health", response_model=HealthStatus, tags=["health"])
async def health_check():
    """
    Health check endpoint for the application.
    Checks if Valkey is available.
    """
    valkey_client = get_valkey()
    valkey_healthy = False
    details = {}
    
    try:
        valkey_healthy = await valkey_client.is_healthy()
        details["valkey"] = "connected" if valkey_healthy else "disconnected"
    except Exception as e:
        details["valkey_error"] = str(e)
    
    status = "healthy" if valkey_healthy else "unhealthy"
    
    response = HealthStatus(
        status=status,
        valkey=valkey_healthy,
        details=details
    )
    
    if not valkey_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    
    return response