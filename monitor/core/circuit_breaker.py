"""
Circuit breaker to temporarily disable failing platforms.
"""

import time
from typing import Dict, Optional


class CircuitBreaker:
    """Tracks failures and opens circuit after threshold."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: Dict[str, int] = {}
        self._open_until: Dict[str, float] = {}

    def record_failure(self, platform_name: str):
        """Increment failure count for a platform."""
        now = time.time()
        # if already in cooldown, don't count further
        if platform_name in self._open_until and now < self._open_until[platform_name]:
            return

        count = self._failures.get(platform_name, 0) + 1
        self._failures[platform_name] = count

        if count >= self.failure_threshold:
            self._open_until[platform_name] = now + self.cooldown_seconds
            self._failures.pop(platform_name, None)

    def record_success(self, platform_name: str):
        """Reset failure count on success."""
        self._failures.pop(platform_name, None)
        # also remove from cooldown if it was there
        self._open_until.pop(platform_name, None)

    def is_allowed(self, platform_name: str) -> bool:
        """Check if platform can be checked."""
        now = time.time()
        if platform_name in self._open_until:
            if now < self._open_until[platform_name]:
                return False
            else:
                # cooldown expired
                self._open_until.pop(platform_name, None)
        return True