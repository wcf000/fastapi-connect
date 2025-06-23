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
from app.core.pulsar.client import PulsarClient
from app.core.pulsar.background import start_background_processors
from app.core.pulsar.config_override import *  # Add this import at the top, before other imports


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

# Initialize Pulsar client
pulsar_client = PulsarClient()

# Database startup event - initialize either PostgreSQL or Supabase
@app.on_event("startup")
async def startup_database():
    import os
    from app.core.db_utils.db_selector import get_db_client
    
    # Check if we're using Supabase
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    
    if supabase_url.strip() and supabase_key.strip():
        print("Using Supabase as the database backend")
        # No additional initialization needed for Supabase
    else:
        print("Using PostgreSQL as the database backend")
        # Initialize PostgreSQL
        from app.core.db import init_db
        init_db()

# Valkey startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    await init_valkey()

# Pulsar startup event
@app.on_event("startup")
async def startup_pulsar_client():
    # The client is already initialized as a global instance
    # Just log that it's started
    app.state.pulsar_client = pulsar_client
    print("Pulsar client initialized")
    
    # Start background processors for Pulsar message consumption
    app.state.background_tasks = await start_background_processors()
    print("Pulsar background processors started")

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_valkey()
    
# Pulsar shutdown event
@app.on_event("shutdown")
async def shutdown_pulsar_client():
    if hasattr(app.state, "pulsar_client"):
        await app.state.pulsar_client.close()
        print("Pulsar client closed")
    
    # Cancel background tasks
    if hasattr(app.state, "background_tasks"):
        for task in app.state.background_tasks:
            task.cancel()
        print("Pulsar background processors stopped")

# Get host and port from environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
