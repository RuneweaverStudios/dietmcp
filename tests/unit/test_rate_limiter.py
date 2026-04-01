"""Tests for rate limiter."""

from __future__ import annotations

import asyncio
import time

from dietmcp.security.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_initialization(self):
        """Test rate limiter initializes with correct parameters."""
        limiter = RateLimiter(rate_limit=10, period=5.0)
        assert limiter.rate_limit == 10
        assert limiter.period == 5.0
        assert len(limiter.requests) == 0

    async def test_single_request(self):
        """Test single request passes through immediately."""
        limiter = RateLimiter(rate_limit=10, period=1.0)

        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should complete immediately
        assert elapsed < 0.1
        assert len(limiter.requests) == 1

    async def test_requests_within_limit(self):
        """Test multiple requests within limit don't block."""
        limiter = RateLimiter(rate_limit=10, period=1.0)

        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        # Should complete immediately (under limit)
        assert elapsed < 0.1
        assert len(limiter.requests) == 5

    async def test_rate_limit_blocks(self):
        """Test that exceeding rate limit causes blocking."""
        limiter = RateLimiter(rate_limit=3, period=1.0)

        # First 3 requests should be immediate
        start = time.time()
        for _ in range(3):
            await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be fast
        assert len(limiter.requests) == 3

        # 4th request should block until oldest expires
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should have waited at least 1 second
        assert elapsed >= 0.9  # Allow small timing margin
        assert len(limiter.requests) == 4

    async def test_sliding_window(self):
        """Test that old requests expire from the window."""
        limiter = RateLimiter(rate_limit=2, period=0.5)

        # First 2 requests
        await limiter.acquire()
        await limiter.acquire()

        # Wait for window to slide
        await asyncio.sleep(0.6)

        # Should be able to make 2 more requests immediately
        start = time.time()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should be immediate (old requests expired)
        assert elapsed < 0.1

    async def test_concurrent_requests(self):
        """Test that concurrent requests are handled correctly."""
        limiter = RateLimiter(rate_limit=5, period=1.0)

        # Launch concurrent requests
        tasks = [limiter.acquire() for _ in range(5)]
        start = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # All should complete quickly
        assert elapsed < 0.2
        assert len(limiter.requests) == 5

    async def test_default_parameters(self):
        """Test rate limiter with default parameters."""
        limiter = RateLimiter()  # Should use defaults

        assert limiter.rate_limit == 60
        assert limiter.period == 60.0

        # Should handle 60 requests in a row
        for _ in range(60):
            await limiter.acquire()

        assert len(limiter.requests) == 60

    async def test_exact_boundary(self):
        """Test behavior exactly at rate limit boundary."""
        limiter = RateLimiter(rate_limit=2, period=1.0)

        # Exactly at limit - should pass
        await limiter.acquire()
        await limiter.acquire()

        # One over limit - should block
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.9  # Should wait for window to slide
