from prometheus_client import Counter, Histogram, Gauge

# Cache operation counts
CACHE_OPERATIONS = Counter(
    "app_cache_operations_total",
    "Total number of cache operations",
    ["operation", "status"]  # operation: get, set, delete; status: success, failure
)

# Cache hit/miss counts
CACHE_HITS = Counter(
    "app_cache_hits_total",
    "Total number of cache hits"
)

CACHE_MISSES = Counter(
    "app_cache_misses_total",
    "Total number of cache misses"
)

# Cache operation latency
CACHE_OPERATION_DURATION = Histogram(
    "app_cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

# Cache size metrics
CACHE_SIZE = Gauge(
    "app_cache_size_bytes",
    "Current cache size in bytes"
)

CACHE_ITEMS = Gauge(
    "app_cache_items",
    "Current number of items in cache"
)

# Helper functions
def record_cache_operation(operation: str, status: str):
    """Record a cache operation"""
    CACHE_OPERATIONS.labels(operation=operation, status=status).inc()

def record_cache_hit():
    """Record a cache hit"""
    CACHE_HITS.inc()

def record_cache_miss():
    """Record a cache miss"""
    CACHE_MISSES.inc()

def time_cache_operation(operation: str):
    """Context manager for timing cache operations"""
    return CACHE_OPERATION_DURATION.labels(operation=operation).time()

def update_cache_size(size_bytes: int):
    """Update the cache size gauge"""
    CACHE_SIZE.set(size_bytes)

def update_cache_items(items_count: int):
    """Update the cache items gauge"""
    CACHE_ITEMS.set(items_count)