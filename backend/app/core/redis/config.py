"""
Redis configuration settings with timeout and performance parameters.
"""

from redis.exceptions import ConnectionError, ResponseError, TimeoutError

# Import settings
from app.core.config import settings


class RedisConfig:
    # Sharding configuration
    REDIS_SHARD_SIZE = 25 * 1024 * 1024 * 1024  # 25GB
    REDIS_SHARD_OPS_LIMIT = 25000  # ops/second
    REDIS_SHARD_NODES = [
        {"host": "localhost", "port": 6379},
    ]
    # Redis connection settings
    REDIS_HOST = getattr(settings, "REDIS_HOST", "127.0.0.1")
    REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
    REDIS_DB = getattr(settings, "REDIS_DB", 0)
    REDIS_PASSWORD = getattr(settings, "REDIS_PASSWORD", None)
    REDIS_CLUSTER = getattr(settings, "REDIS_CLUSTER", False)

    # Circuit breaker settings
    REDIS_FAILURE_THRESHOLD = getattr(settings, "REDIS_FAILURE_THRESHOLD", 3)
    REDIS_RECOVERY_TIMEOUT = getattr(settings, "REDIS_RECOVERY_TIMEOUT", 30)

    # Connection pooling settings
    REDIS_MAX_CONNECTIONS = getattr(settings, "REDIS_MAX_CONNECTIONS", 10)
    REDIS_SOCKET_TIMEOUT = getattr(settings, "REDIS_SOCKET_TIMEOUT", 5.0)
    REDIS_SOCKET_CONNECT_TIMEOUT = getattr(
        settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 2.0
    )
    # Connection timeout in seconds (float)
    REDIS_TIMEOUT = 5.0

    # Circuit breaker settings
    CIRCUIT_BREAKER = {
        "failure_threshold": 3,  # Failures before opening
        "recovery_timeout": 30,  # Seconds to wait before attempting recovery
        "expected_exceptions": (ConnectionError, TimeoutError, ResponseError),
    }

    # Monitoring settings
    METRICS_UPDATE_INTERVAL = 60  # Seconds between metrics updates

    # Connection pool settings
    REDIS_MAX_CONNECTIONS = 100
    REDIS_IDLE_TIMEOUT = 300  # seconds

    # Performance tuning
    REDIS_SOCKET_TIMEOUT = 10.0
    REDIS_SOCKET_CONNECT_TIMEOUT = 5.0

    # Retry configuration
    REDIS_RETRY_ATTEMPTS = 3
    REDIS_RETRY_DELAY = 0.1  # seconds

    # Health check interval in seconds
    REDIS_HEALTH_CHECK_INTERVAL = 60

    # Cache-specific settings
    REDIS_CACHE_TTL = 3600  # Default TTL in seconds (1 hour)
    REDIS_CACHE_PREFIX = "lead_ignite:"

    # Rate limiting settings
    REDIS_RATE_LIMIT_WINDOW = 60  # seconds
    REDIS_RATE_LIMIT_MAX_REQUESTS = 100

    # SSL/TLS
    REDIS_SSL = getattr(settings, "REDIS_SSL", False)
    REDIS_SSL_CERT_REQS = getattr(
        settings, "REDIS_SSL_CERT_REQS", None
    )  # e.g., 'required', 'optional', 'none'
    REDIS_SSL_CA_CERTS = getattr(settings, "REDIS_SSL_CA_CERTS", None)
    REDIS_SSL_KEYFILE = getattr(settings, "REDIS_SSL_KEYFILE", None)
    REDIS_SSL_CERTFILE = getattr(settings, "REDIS_SSL_CERTFILE", None)
    # RESP3
    REDIS_PROTOCOL = getattr(settings, "REDIS_PROTOCOL", 2)  # 2 or 3
    # Advanced Auth
    REDIS_USERNAME = getattr(settings, "REDIS_USERNAME", None)
    # URL-based config
    REDIS_URL = getattr(settings, "REDIS_URL", None)
