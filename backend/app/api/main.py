from fastapi import APIRouter

# Import Pulsar configuration override first
from app.core.pulsar.config_override import *

from app.api.routes import items, login, private, users, utils, health, messaging, mcp
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(health.router)
api_router.include_router(messaging.router)
api_router.include_router(mcp.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
