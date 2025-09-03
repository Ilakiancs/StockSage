import logging
import logging.handlers
import os
from datetime import datetime

def setup_logging(log_level=logging.INFO, log_file="logs/app.log"):
    """
    Setup comprehensive logging configuration
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: logs/app.log)
    """
    
    # Ensure logs directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    
    # Error file handler (separate file for errors)
    error_file_handler = logging.handlers.RotatingFileHandler(
        log_file.replace('.log', '_errors.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    
    # Configure root logger
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_file_handler)
    
    # Configure specific loggers
    setup_module_loggers()
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info(f"Stock Tracker Application Started - {datetime.now()}")
    logger.info("=" * 50)

def setup_module_loggers():
    """Configure specific loggers for different modules"""
    
    # Stock tracking logger
    stock_logger = logging.getLogger('lib.stock_checker')
    stock_logger.setLevel(logging.INFO)
    
    # SMS logger
    sms_logger = logging.getLogger('lib.sms')
    sms_logger.setLevel(logging.INFO)
    
    # Agent logger
    agent_logger = logging.getLogger('lib.agent')
    agent_logger.setLevel(logging.INFO)
    
    # Tracker logger
    tracker_logger = logging.getLogger('lib.tracker')
    tracker_logger.setLevel(logging.INFO)
    
    # FastAPI logger
    fastapi_logger = logging.getLogger('uvicorn')
    fastapi_logger.setLevel(logging.WARNING)  # Reduce uvicorn verbosity
    
    # Scheduler logger
    scheduler_logger = logging.getLogger('apscheduler')
    scheduler_logger.setLevel(logging.WARNING)  # Reduce scheduler verbosity

def log_system_info():
    """Log system and environment information"""
    logger = logging.getLogger(__name__)
    
    try:
        import platform
        import sys
        
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Architecture: {platform.architecture()}")
        
        # Log environment variables (without sensitive data)
        env_vars = [
            "HOST", "PORT", "TWILIO_PHONE_NUMBER", 
            "TARGET_PHONE_NUMBER", "WEBHOOK_URL"
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                # Mask phone numbers for privacy
                if "PHONE" in var:
                    masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "*" * len(value)
                    logger.info(f"Environment {var}: {masked_value}")
                else:
                    logger.info(f"Environment {var}: {value}")
            else:
                logger.warning(f"Environment {var}: NOT SET")
                
    except Exception as e:
        logger.error(f"Error logging system info: {e}")

class RequestLogger:
    """Middleware-style request logger for FastAPI"""
    
    def __init__(self):
        self.logger = logging.getLogger('requests')
    
    def log_request(self, method: str, url: str, headers: dict = None):
        """Log incoming request"""
        self.logger.info(f"REQUEST: {method} {url}")
        
        if headers:
            # Log relevant headers (excluding sensitive ones)
            safe_headers = {k: v for k, v in headers.items() 
                          if k.lower() not in ['authorization', 'x-twilio-signature']}
            self.logger.debug(f"Headers: {safe_headers}")
    
    def log_response(self, status_code: int, response_time: float = None):
        """Log outgoing response"""
        self.logger.info(f"RESPONSE: {status_code}" + 
                        (f" ({response_time:.3f}s)" if response_time else ""))

class StockTrackingLogger:
    """Specialized logger for stock tracking operations"""
    
    def __init__(self):
        self.logger = logging.getLogger('stock_tracking')
    
    def log_price_check(self, symbol: str, current_price: float, previous_close: float):
        """Log stock price check"""
        change_percent = (current_price - previous_close) / previous_close * 100
        self.logger.info(f"PRICE_CHECK: {symbol} ${current_price:.2f} "
                        f"({change_percent:+.2f}%) prev: ${previous_close:.2f}")
    
    def log_alert_triggered(self, symbol: str, change_percent: float):
        """Log when an alert is triggered"""
        self.logger.warning(f"ALERT_TRIGGERED: {symbol} moved {change_percent:+.2f}%")
    
    def log_alert_sent(self, symbol: str, message: str):
        """Log when an alert SMS is sent"""
        self.logger.info(f"ALERT_SENT: {symbol} - {message[:50]}...")
    
    def log_duplicate_alert_prevented(self, symbol: str):
        """Log when duplicate alert is prevented"""
        self.logger.info(f"DUPLICATE_PREVENTED: {symbol} already alerted today")

# Performance logging decorator
def log_performance(func_name: str = None):
    """Decorator to log function performance"""
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger('performance')
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"PERFORMANCE: {name} completed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"PERFORMANCE: {name} failed in {execution_time:.3f}s - {e}")
                raise
                
        return wrapper
    return decorator
