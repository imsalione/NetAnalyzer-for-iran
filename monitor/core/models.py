"""
Shared data models for the core monitoring engine.
All dataclasses are frozen to make them hashable.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class PlatformStatus(Enum):
    """Platform connection status."""
    ONLINE = "online"
    SLOW = "slow"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Platform:
    """Platform definition."""
    name: str
    emoji: str
    url: str
    category: str  # 'social', 'international', 'iran'


@dataclass(frozen=True)
class CheckResult:
    """Single platform check result (base)."""
    platform: Platform
    status: PlatformStatus
    ping_ms: float
    timestamp: datetime

    @property
    def is_accessible(self) -> bool:
        return self.status != PlatformStatus.BLOCKED


@dataclass(frozen=True)
class DetailedCheckResult(CheckResult):
    """Extended check result with detailed layer info."""
    dns_success: bool = False
    tcp_success: bool = False
    http_success: bool = False
    error_type: Optional[str] = None


@dataclass(frozen=True)
class MonitorResult:
    """Complete monitoring result."""
    platforms: Dict[str, CheckResult]
    timestamp: datetime
    internet_status: str
    quality: str
    international_ping: float
    iran_ping: float

    def get_accessible_platforms(self) -> List[str]:
        return [name for name, r in self.platforms.items() if r.is_accessible]

    def get_blocked_platforms(self) -> List[str]:
        return [name for name, r in self.platforms.items() if not r.is_accessible]

    def get_status_color(self) -> str:
        color_map = {
            'Full Internet Access': 'green',
            'Social Media Blocked': 'yellow',
            'International Internet Restricted': 'orange',
            'Iran-Only Network': 'orange',
            'VPN Active': 'purple',
            'DPI Interference Suspected': 'yellow',
            'Unstable Connection': 'gray',
            'No Internet Access': 'red',
        }
        return color_map.get(self.internet_status, 'gray')