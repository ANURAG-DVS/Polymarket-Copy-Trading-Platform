import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: dict) -> None:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add log level
        log_record['level'] = record.levelname
        
        # Add logger name
        log_record['logger'] = record.name
        
        # Add service info
        log_record['service'] = 'polymarket-copy-trading'
        
        # Add environment
        from app.core.config import settings
        log_record['environment'] = settings.NODE_ENV
        
        # Add extra context if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        
        if hasattr(record, 'trade_id'):
            log_record['trade_id'] = record.trade_id
        
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

def setup_logging():
    """Configure structured logging for the application"""
    
    # Create logger
    logger = logging.getLogger()
    
    # Get log level from environment
    from app.core.config import settings
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    logger.setLevel(log_level)
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # JSON formatter
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

# Create logger instance
logger = setup_logging()

class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for adding context to logs"""
    
    def process(self, msg, kwargs):
        # Add extra context from adapter
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra'].update(self.extra)
        return msg, kwargs

def get_logger(name: str, **context) -> LoggerAdapter:
    """Get logger with context"""
    base_logger = logging.getLogger(name)
    return LoggerAdapter(base_logger, context)

# Usage examples:
# logger.info("Trade executed successfully", extra={"trade_id": 123, "user_id": 456})
# logger.error("Database connection failed", extra={"error": str(e)}, exc_info=True)
# logger.warning("High queue backlog", extra={"queue_depth": 1500})
