"""
Rate limiting utilities for Notion API calls.

Provides token bucket rate limiter and retry logic for handling 429 errors.
"""

import threading
import time


# Rate limiting configuration
MAX_REQUESTS_PER_SECOND = 3.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


class NotionTokenBucketRateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, rate=3.0, capacity=5):
        """
        Args:
            rate: Tokens added per second (requests per second)
            capacity: Maximum tokens in bucket (burst capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens=1):
        """Acquire tokens, blocking if necessary."""
        with self.lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update
                
                # Add tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                # Calculate wait time for next token
                wait_time = (tokens - self.tokens) / self.rate
                time.sleep(wait_time)


# Global rate limiter instance
rate_limiter = NotionTokenBucketRateLimiter(rate=MAX_REQUESTS_PER_SECOND, capacity=5)


def retry_on_429(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Retry a function if it raises a 429 error.
    
    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func call
    """
    for attempt in range(max_retries + 1):
        try:
            rate_limiter.acquire()
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a 429 rate limit error
            if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
                if attempt < max_retries:
                    wait_time = RETRY_BACKOFF_BASE ** attempt
                    time.sleep(wait_time)
                    continue
            # Re-raise if not a 429 or out of retries
            raise
    return None
