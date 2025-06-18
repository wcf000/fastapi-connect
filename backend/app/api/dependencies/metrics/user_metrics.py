from prometheus_client import Counter, Histogram, Gauge

# User registration metrics
USER_REGISTRATIONS = Counter(
    "app_user_registrations_total",
    "Total number of user registrations",
    ["status"]  # success, failure
)

# User login metrics
USER_LOGINS = Counter(
    "app_user_logins_total",
    "Total number of user login attempts",
    ["status"]  # success, failure
)

# Active users gauge
ACTIVE_USERS = Gauge(
    "app_active_users",
    "Number of currently active users"
)

# User operations metrics
USER_OPERATIONS = Counter(
    "app_user_operations_total",
    "Total count of user-related operations",
    ["operation", "status"]  # operation: create, update, delete, read; status: success, failure
)

# Database query duration for user operations
DB_QUERY_DURATION = Histogram(
    "app_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
)

# Helper functions for recording metrics
def record_user_registration(status: str):
    """Record a user registration event"""
    USER_REGISTRATIONS.labels(status=status).inc()

def record_user_login(status: str):
    """Record a user login event"""
    USER_LOGINS.labels(status=status).inc()

def record_user_operation(operation: str, status: str):
    """Record a user operation"""
    USER_OPERATIONS.labels(operation=operation, status=status).inc()

def time_db_query(operation: str, table: str):
    """Context manager for timing database queries"""
    return DB_QUERY_DURATION.labels(operation=operation, table=table).time()