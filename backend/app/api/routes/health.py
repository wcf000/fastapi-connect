import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.valkey_init import get_valkey

# Import the proper config objects
from app.core.prometheus.config import get_prometheus_config
from app.core.grafana.config import GrafanaConfig

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    valkey: bool
    prometheus: bool
    grafana: bool
    details: dict = {}


@router.get("/health", response_model=HealthStatus, tags=["health"])
async def health_check():
    """
    Health check endpoint for the application.
    Checks if Valkey, Prometheus, and Grafana are available.
    """
    valkey_client = get_valkey()
    valkey_healthy = False
    prometheus_healthy = False
    grafana_healthy = False
    details = {}

    # Get configuration objects
    prometheus_config = get_prometheus_config()

    # 1. Check Valkey health (existing check)
    try:
        valkey_healthy = await valkey_client.is_healthy()
        details["valkey"] = "connected" if valkey_healthy else "disconnected"
    except Exception as e:
        details["valkey_error"] = str(e)

    # 2. Check Prometheus health
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Use the proper configuration object for Prometheus
            response = await client.get(f"{prometheus_config.SERVICE_URL}/-/healthy")
            prometheus_healthy = response.status_code == 200
        details["prometheus"] = "connected" if prometheus_healthy else "disconnected"
    except Exception as e:
        details["prometheus_error"] = str(e)

    # 3. Check Grafana health
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Use the proper configuration path for Grafana
            response = await client.get(f"{GrafanaConfig.SERVICE_URL}/api/health")
            grafana_healthy = response.status_code == 200
        details["grafana"] = "connected" if grafana_healthy else "disconnected"
    except Exception as e:
        details["grafana_error"] = str(e)

    # Determine overall status
    # Valkey is critical, others are for monitoring
    if valkey_healthy and prometheus_healthy and grafana_healthy:
        overall_status = "healthy"
    elif valkey_healthy:
        overall_status = "degraded"  # Core service is up, but monitoring is down
    else:
        overall_status = "unhealthy"  # Critical service is down

    response = HealthStatus(
        status=overall_status,
        valkey=valkey_healthy,
        prometheus=prometheus_healthy,
        grafana=grafana_healthy,
        details=details,
    )

    # Only raise an exception if the critical service (Valkey) is down
    if not valkey_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response.model_dump()
        )

    return response