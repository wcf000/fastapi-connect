from prometheus_client import Counter, Histogram, Info
from typing import Callable
from fastapi import Request, Response
import time

# API Request metrics
REQUEST_COUNT = Counter(
    "app_api_requests_total", 
    "Total count of API requests", 
    ["method", "endpoint", "status"]
)

# Request latency metrics
REQUEST_LATENCY = Histogram(
    "app_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10]
)

# Server info
API_INFO = Info("app_info", "API information")

def setup_api_info(app_name: str, version: str):
    """Set up API information metric"""
    API_INFO.info({
        "app_name": app_name,
        "version": version
    })

def track_requests_middleware() -> Callable:
    """Middleware factory to track request count and latency"""
    async def middleware(request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Record metrics after the request is processed
        duration = time.time() - start_time
        status_code = response.status_code
        endpoint = request.url.path
        method = request.method
        
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
        
        return response
    
    return middleware

# Endpoint-specific metrics wrapper for tracking specific endpoints
def track_endpoint_performance(endpoint_name: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            response = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Extract status code from response if it's a Response object
            status_code = response.status_code if isinstance(response, Response) else "200"
            
            REQUEST_COUNT.labels(method="ENDPOINT", endpoint=endpoint_name, status=status_code).inc()
            REQUEST_LATENCY.labels(method="ENDPOINT", endpoint=endpoint_name).observe(duration)
            
            return response
        return wrapper
    return decorator