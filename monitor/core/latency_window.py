"""
Sliding window for latency tracking and smoothing.
"""

from collections import deque
from typing import Dict, Optional


class LatencyWindow:
    """Maintains a fixed-size deque of latencies per platform."""

    def __init__(self, maxlen: int = 20):
        self.maxlen = maxlen
        self._windows: Dict[str, deque] = {}

    def add(self, platform_name: str, latency_ms: float):
        """Add a latency value for a platform."""
        if platform_name not in self._windows:
            self._windows[platform_name] = deque(maxlen=self.maxlen)
        self._windows[platform_name].append(latency_ms)

    def get_average(self, platform_name: str) -> Optional[float]:
        """Return average latency if enough samples exist."""
        if platform_name not in self._windows or len(self._windows[platform_name]) == 0:
            return None
        values = [v for v in self._windows[platform_name] if v > 0]
        if not values:
            return None
        return sum(values) / len(values)

    def get_all_averages(self) -> Dict[str, float]:
        """Return averages for all platforms."""
        return {name: self.get_average(name) for name in self._windows}