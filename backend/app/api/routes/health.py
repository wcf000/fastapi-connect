import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.valkey_init import get_valkey
from app.core.telemetry.health_check import check_telemetry_health
from app.core.telemetry.telemetry import get_telemetry

# Import the proper config objects
from app.core.prometheus.config import get_prometheus_config
from app.core.grafana.config import GrafanaConfig
from app.core.pulsar.health_check import pulsar_health

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    valkey: bool
    prometheus: bool
    grafana: bool
    telemetry: bool
    pulsar: bool
    details: dict = {}


@router.get("/health", response_model=HealthStatus, tags=["health"])
async def health_check():
    """
    Health check endpoint for the application.
    Checks if Valkey, Prometheus, Grafana, and Telemetry are available.
    """
    valkey_client = get_valkey()
    valkey_healthy = False
    prometheus_healthy = False
    grafana_healthy = False
    pulsar_healthy = False
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

    # 4. Check Telemetry health with improved detection
    telemetry_client = get_telemetry()
    telemetry_health = check_telemetry_health(telemetry_client)
    telemetry_healthy = telemetry_health["status"] in ["healthy", "degraded"]  # Consider degraded as "working"

    # Add more detailed telemetry information
    details["telemetry"] = {
        "status": telemetry_health["status"],
        "circuit_breaker": telemetry_health.get("circuit_breaker", "unknown"),
    }

    # Add any error reason
    if "reason" in telemetry_health:
        details["telemetry"]["reason"] = telemetry_health["reason"]

    # Add exporter details if available
    if "exporters" in telemetry_health:
        details["telemetry"]["exporters"] = telemetry_health["exporters"]
        
    # 5. Check Pulsar health
    try:
        pulsar_health_status = await pulsar_health.get_health_status()
        pulsar_data = pulsar_health_status.body.decode('utf-8')
        import json
        pulsar_json = json.loads(pulsar_data)
        pulsar_healthy = pulsar_json.get("healthy", False)
        details["pulsar"] = {
            "status": "connected" if pulsar_healthy else "disconnected",
            "connection": pulsar_json.get("details", {}).get("connection", False),
            "producer": pulsar_json.get("details", {}).get("producer", False),
            "consumer": pulsar_json.get("details", {}).get("consumer", False),
        }
    except Exception as e:
        pulsar_healthy = False
        details["pulsar_error"] = str(e)
        details["pulsar"] = {"status": "disconnected"}

    # Determine overall status with more nuanced approach
    if valkey_healthy and prometheus_healthy and grafana_healthy and telemetry_health["status"] == "healthy" and pulsar_healthy:
        overall_status = "healthy"
    elif valkey_healthy:
        # Core service is up, but monitoring systems may be degraded
        if telemetry_health["status"] == "degraded" or not pulsar_healthy:
            overall_status = "degraded"
            degradation_reason = []
            if telemetry_health["status"] == "degraded":
                degradation_reason.append("Telemetry system degraded but operational")
            if not pulsar_healthy:
                degradation_reason.append("Pulsar messaging system degraded or unavailable")
            details["degraded_reason"] = "; ".join(degradation_reason)
        elif not prometheus_healthy or not grafana_healthy:
            overall_status = "degraded"
            details["degraded_reason"] = "Monitoring systems partially unavailable"
        else:
            overall_status = "degraded"
    else:
        overall_status = "unhealthy"
        details["unhealthy_reason"] = "Critical service (Valkey) is down"

    response = HealthStatus(
        status=overall_status,
        valkey=valkey_healthy,
        prometheus=prometheus_healthy,
        grafana=grafana_healthy,
        telemetry=telemetry_healthy,
        pulsar=pulsar_healthy,
        details=details,
    )

    # Only raise an exception if the critical service (Valkey) is down
    if not valkey_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response.model_dump()
        )

    return response