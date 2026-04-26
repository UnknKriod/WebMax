import asyncio
import time

class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_requests_per_second: float = 20.0):
        self.max_requests = max_requests_per_second
        self.tokens = max_requests_per_second
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.max_requests, self.tokens + elapsed * self.max_requests)
            self.last_update = now
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.max_requests
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1