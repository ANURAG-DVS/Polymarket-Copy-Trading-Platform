from datadog import initialize, statsd
from app.core.config import settings
import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Initialize DataDog if API key is present
if settings.DATADOG_API_KEY:
    options = {
        'api_key': settings.DATADOG_API_KEY,
        'app_key': settings.DATADOG_APP_KEY,
    }
    initialize(**options)
    logger.info("DataDog initialized")

class Metrics:
    """Metrics collection wrapper"""
    
    @staticmethod
    def increment(metric_name: str, value: int = 1, tags: list = None):
        """Increment a counter metric"""
        if settings.DATADOG_API_KEY:
            statsd.increment(metric_name, value, tags=tags or [])
    
    @staticmethod
    def gauge(metric_name: str, value: float, tags: list = None):
        """Set a gauge metric"""
        if settings.DATADOG_API_KEY:
            statsd.gauge(metric_name, value, tags=tags or [])
    
    @staticmethod
    def histogram(metric_name: str, value: float, tags: list = None):
        """Record a histogram metric"""
        if settings.DATADOG_API_KEY:
            statsd.histogram(metric_name, value, tags=tags or [])
    
    @staticmethod
    def timing(metric_name: str, value: float, tags: list = None):
        """Record a timing metric"""
        if settings.DATADOG_API_KEY:
            statsd.timing(metric_name, value, tags=tags or [])

def track_execution_time(metric_name: str):
    """Decorator to track execution time of functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                Metrics.timing(metric_name, duration_ms, tags=['status:success'])
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                Metrics.timing(metric_name, duration_ms, tags=['status:error'])
                Metrics.increment(f'{metric_name}.error')
                raise
        return wrapper
    return decorator

# Usage examples:
# Metrics.increment('trade.executed', tags=['trader_id:123', 'outcome:yes'])
# Metrics.gauge('queue.depth', 150, tags=['queue_name:trades'])
# Metrics.histogram('api.response_time', 45.3, tags=['endpoint:/traders'])

# @track_execution_time('trade.execution.time')
# async def execute_trade(...):
#     ...
