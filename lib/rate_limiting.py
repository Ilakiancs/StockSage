"""
Rate limiting middleware and utilities for the Stock Tracker API
"""

import time
import logging
from typing import Dict, Tuple
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from fastapi.responses import Response
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter implementation
    """
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in the time window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is allowed for the given identifier
        
        Args:
            identifier: Unique identifier (e.g., IP address, user ID)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        async with self.lock:
            now = time.time()
            
            # Clean old requests outside the window
            request_times = self.requests[identifier]
            while request_times and request_times[0] <= now - self.window_seconds:
                request_times.popleft()
            
            # Check if under limit
            current_requests = len(request_times)
            is_allowed = current_requests < self.max_requests
            
            if is_allowed:
                request_times.append(now)
            
            # Calculate reset time
            reset_time = int(now + self.window_seconds) if request_times else int(now)
            
            # Calculate remaining requests
            remaining = max(0, self.max_requests - current_requests - (1 if is_allowed else 0))
            
            rate_info = {
                'limit': self.max_requests,
                'remaining': remaining,
                'reset': reset_time,
                'reset_time': datetime.fromtimestamp(reset_time).isoformat()
            }
            
            logger.debug(f"Rate limit check for {identifier}: {current_requests}/{self.max_requests}")
            
            return is_allowed, rate_info


class IPRateLimiter(RateLimiter):
    """Rate limiter based on IP address"""
    
    def get_identifier(self, request: Request) -> str:
        """Get IP address as identifier"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Use first IP in X-Forwarded-For header
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class TwilioRateLimiter(RateLimiter):
    """Rate limiter for Twilio webhook requests"""
    
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        # More restrictive for SMS webhooks
        super().__init__(max_requests, window_seconds)
    
    def get_identifier(self, request: Request) -> str:
        """Get phone number as identifier from Twilio request"""
        # This would be called after form parsing
        return "twilio_webhook"  # Single identifier for all Twilio requests


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on system load
    """
    
    def __init__(self, base_limit: int = 60, window_seconds: int = 60):
        self.base_limit = base_limit
        self.window_seconds = window_seconds
        self.current_multiplier = 1.0
        self.load_samples = deque(maxlen=10)
        self.last_adjustment = time.time()
        self.rate_limiter = RateLimiter(base_limit, window_seconds)
    
    def update_system_load(self, cpu_percent: float, memory_percent: float):
        """Update system load metrics"""
        load_score = (cpu_percent + memory_percent) / 2
        self.load_samples.append(load_score)
        
        # Adjust rate limiting every 30 seconds
        now = time.time()
        if now - self.last_adjustment > 30:
            self._adjust_rate_limit()
            self.last_adjustment = now
    
    def _adjust_rate_limit(self):
        """Adjust rate limit based on system load"""
        if not self.load_samples:
            return
        
        avg_load = sum(self.load_samples) / len(self.load_samples)
        
        if avg_load > 80:  # High load
            self.current_multiplier = max(0.5, self.current_multiplier * 0.8)
        elif avg_load < 40:  # Low load
            self.current_multiplier = min(2.0, self.current_multiplier * 1.1)
        
        new_limit = int(self.base_limit * self.current_multiplier)
        self.rate_limiter.max_requests = new_limit
        
        logger.info(f"Adjusted rate limit to {new_limit} (multiplier: {self.current_multiplier:.2f}, load: {avg_load:.1f}%)")


# Global rate limiters
ip_rate_limiter = IPRateLimiter(max_requests=100, window_seconds=60)  # 100 requests per minute per IP
twilio_rate_limiter = TwilioRateLimiter(max_requests=30, window_seconds=60)  # 30 SMS per minute
adaptive_limiter = AdaptiveRateLimiter(base_limit=200, window_seconds=60)  # Global adaptive limit


async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI middleware for rate limiting
    """
    try:
        # Get appropriate rate limiter based on endpoint
        if request.url.path == "/receive-message":
            limiter = twilio_rate_limiter
            identifier = "twilio_webhook"
        else:
            limiter = ip_rate_limiter
            identifier = limiter.get_identifier(request)
        
        # Check rate limit
        is_allowed, rate_info = await limiter.is_allowed(identifier)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {identifier} on {request.url.path}")
            
            response = Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rate_info['limit']),
                    "X-RateLimit-Remaining": str(rate_info['remaining']),
                    "X-RateLimit-Reset": str(rate_info['reset']),
                    "Retry-After": str(limiter.window_seconds)
                }
            )
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info['limit'])
        response.headers["X-RateLimit-Remaining"] = str(rate_info['remaining'])
        response.headers["X-RateLimit-Reset"] = str(rate_info['reset'])
        
        return response
        
    except Exception as e:
        logger.error(f"Error in rate limiting middleware: {e}")
        # Continue processing request if rate limiting fails
        return await call_next(request)


class RateLimitConfig:
    """Configuration for different rate limiting scenarios"""
    
    # Different rate limits for different endpoints
    ENDPOINTS = {
        "/receive-message": {
            "max_requests": 30,
            "window_seconds": 60,
            "description": "Twilio webhook rate limit"
        },
        "/health": {
            "max_requests": 200,
            "window_seconds": 60,
            "description": "Health check rate limit"
        },
        "default": {
            "max_requests": 100,
            "window_seconds": 60,
            "description": "Default API rate limit"
        }
    }
    
    # Rate limits by user type (if authentication is added later)
    USER_TYPES = {
        "admin": {
            "max_requests": 1000,
            "window_seconds": 60
        },
        "user": {
            "max_requests": 100,
            "window_seconds": 60
        },
        "guest": {
            "max_requests": 20,
            "window_seconds": 60
        }
    }


async def get_system_metrics():
    """Get system metrics for adaptive rate limiting"""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        return cpu_percent, memory_percent
    except ImportError:
        logger.warning("psutil not available, using dummy metrics")
        return 50.0, 50.0  # Default values


async def monitor_system_load():
    """Background task to monitor system load and adjust rate limits"""
    while True:
        try:
            cpu, memory = await get_system_metrics()
            adaptive_limiter.update_system_load(cpu, memory)
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Error monitoring system load: {e}")
            await asyncio.sleep(60)  # Wait longer on error


def create_rate_limited_endpoint(max_requests: int = 60, window_seconds: int = 60):
    """
    Decorator to create rate-limited endpoints
    
    Usage:
    @create_rate_limited_endpoint(max_requests=10, window_seconds=60)
    async def my_endpoint():
        pass
    """
    def decorator(func):
        limiter = RateLimiter(max_requests, window_seconds)
        
        async def wrapper(request: Request, *args, **kwargs):
            identifier = request.client.host if request.client else "unknown"
            is_allowed, rate_info = await limiter.is_allowed(identifier)
            
            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(rate_info['limit']),
                        "X-RateLimit-Remaining": str(rate_info['remaining']),
                        "X-RateLimit-Reset": str(rate_info['reset'])
                    }
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator
