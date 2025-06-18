"""
Valkey initialization and connection management for FastAPI application.
Uses the valkey_core module for robust connection handling and resilience.
"""
import asyncio
import logging
from typing import Optional

from app.core.valkey_core.client import ValkeyClient, get_valkey_client
from app.core.valkey_core.config import ValkeyConfig

# Import the metrics directly
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# Global client instance for application-wide usage
_valkey_client: Optional[ValkeyClient] = None

# Define Prometheus metrics
# These will be automatically exported via the /metrics endpoint
CACHE_SIZE = Gauge(
    "valkey_cache_size_bytes",
    "Total memory used by Valkey/Redis cache in bytes"
)
CACHE_ITEMS = Gauge(
    "valkey_cache_items",
    "Total number of keys in Valkey/Redis cache"
)

def update_cache_size(size_bytes: int) -> None:
    """Update the cache size metric"""
    CACHE_SIZE.set(size_bytes)

def update_cache_items(num_items: int) -> None:
    """Update the cache items metric"""
    CACHE_ITEMS.set(num_items)

async def update_cache_metrics():
    """Background task to update cache metrics periodically"""
    while True:
        try:
            if _valkey_client and await _valkey_client.is_healthy():
                # Use aconn() to get the raw connection
                redis = await _valkey_client.aconn()
                info = await redis.info()
                update_cache_size(info.get("used_memory", 0))
                # Get DB info, assuming client holds the db number or defaults to 0
                db_key = f"db{ValkeyConfig.VALKEY_DB}"
                db_info = info.get(db_key, {})
                update_cache_items(db_info.get("keys", 0))
        except Exception as e:
            logger.error(f"Error updating cache metrics: {e}")

        # Update every 60 seconds
        await asyncio.sleep(60)

async def init_valkey():
    """
    Initialize Valkey connection on app startup.
    Called by FastAPI startup event handler.
    """
    global _valkey_client
    
    logger.info("Initializing Valkey connection...")
    _valkey_client = get_valkey_client()
    
    # Test connection
    try:
        if await _valkey_client.is_healthy():
            logger.info("Valkey connection established successfully")
            
            # Start background task for metrics collection
            # Use create_task to run in background without blocking
            asyncio.create_task(update_cache_metrics())
        else:
            logger.warning("Failed to establish Valkey connection. Some features may not work properly.")
    except Exception as e:
        logger.error(f"Error initializing Valkey connection: {e}")
    
    return _valkey_client


async def close_valkey():
    """
    Close Valkey connection on app shutdown.
    Called by FastAPI shutdown event handler.
    """
    global _valkey_client
    
    if _valkey_client:
        logger.info("Closing Valkey connection...")
        try:
            await _valkey_client.shutdown()
            logger.info("Valkey connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing Valkey connection: {e}")


def get_valkey():
    """
    Get the current Valkey client instance.
    Returns the global instance if initialized, or creates a new one.
    """
    global _valkey_client
    
    if _valkey_client is None:
        logger.warning("Valkey client accessed before initialization. Creating new instance.")
        _valkey_client = get_valkey_client()
        
    return _valkey_client