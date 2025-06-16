"""
Valkey initialization and connection management for FastAPI application.
Uses the valkey_core module for robust connection handling and resilience.
"""
import logging
from typing import Optional

from app.core.valkey_core.client import ValkeyClient, get_valkey_client
from app.core.valkey_core.config import ValkeyConfig

logger = logging.getLogger(__name__)

# Global client instance for application-wide usage
_valkey_client: Optional[ValkeyClient] = None


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