import os
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.main import api_router
from app.core.config import settings
from app.core.telemetry.telemetry import setup_telemetry
from app.core.valkey_init import init_valkey, close_valkey
from app.api.dependencies.metrics import setup_api_info, track_requests_middleware
from app.core.prometheus.middleware import PrometheusMiddleware


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate a unique ID for a route, handling routes without tags."""
    if route.tags and len(route.tags) > 0:
        return f"{route.tags[0]}-{route.name}"
    else:
        return f"api-{route.name}"  # Fallback for routes without tags


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Setup OpenTelemetry - add this before any other middleware or route registration
telemetry_client = setup_telemetry(app)

# Set up Prometheus metrics
setup_api_info(settings.PROJECT_NAME, "1.0.0")

# Add middlewares
app.add_middleware(PrometheusMiddleware)  # Use the middleware from app.core.prometheus
app.middleware("http")(track_requests_middleware())

# Create metrics endpoint
metrics_app = make_asgi_app()
app.mount("/api/v1/metrics", metrics_app)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Valkey startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    await init_valkey()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_valkey()

# Get host and port from environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
