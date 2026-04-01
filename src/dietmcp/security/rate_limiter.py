"""Rate limiter to prevent DoS and API abuse."""

from __future__ import annotations

import asyncio
from collections import deque
from time import time


class RateLimiter:
    """Token bucket rate limiter.

    Implements a sliding window rate limiter using a token bucket algorithm.
    Ensures that requests are rate-limited to prevent API abuse and DoS attacks.

    Example:
        Rate limit to 60 requests per minute:
        limiter = RateLimiter(rate_limit=60, period=60.0)
        await limiter.acquire()  # Will block if limit exceeded
    """

    def __init__(
        self,
        rate_limit: int = 60,
        period: float = 60.0,
    ) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests allowed in the time period
            period: Time period in seconds (default: 60.0)
        """
        self.rate_limit = rate_limit
        self.period = period
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a request token, blocking if rate limit exceeded.

        This method will:
        1. Clean up expired request timestamps outside the window
        2. Check if the rate limit would be exceeded
        3. Sleep until a token is available if limit exceeded
        4. Record the current request timestamp

        This is thread-safe and async-safe due to the internal lock.
        """
        async with self._lock:
            now = time()

            # Remove requests outside the time window
            while self.requests and self.requests[0] <= now - self.period:
                self.requests.popleft()

            # Check if rate limit would be exceeded
            if len(self.requests) >= self.rate_limit:
                # Calculate wait time for oldest request to expire
                sleep_time = self.requests[0] + self.period - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Refresh time after sleep
                    now = time()

            # Record this request
            self.requests.append(now)
