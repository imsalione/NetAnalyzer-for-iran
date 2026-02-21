"""
Smart classifier with instant state-change detection.

Key improvement over previous version:
- INSTANT update when a significant change is detected (VPN on/off, internet lost/gained)
- Smoothing only applies to minor/ambiguous fluctuations
- No more 90-second delays waiting for majority voting
"""

from typing import Dict, List, Optional
from collections import Counter
from loguru import logger

from .models import CheckResult, PlatformStatus


# Groups for quick "significance" comparison
_CONNECTED_STATES = frozenset({
    "Full Internet Access",
    "VPN Active",
    "VPN Active (Social Still Blocked)",
})
_RESTRICTED_STATES = frozenset({
    "Social Media Blocked",
    "DPI Interference Suspected",
    "International Internet Restricted",
    "Iran-Only Network",
    "Unstable Connection",
})
_OFFLINE_STATES = frozenset({
    "No Internet Access",
})


def _state_group(state: str) -> str:
    if state in _CONNECTED_STATES:
        return "connected"
    if state in _RESTRICTED_STATES:
        return "restricted"
    return "offline"


class ConnectionClassifier:
    """
    Classifies internet state from aggregated platform results.

    Smoothing strategy:
      - INSTANT update when the new raw state is in a DIFFERENT group
        than the current smoothed state (e.g. restricted → connected,
        or connected → offline).  History is also reset so the new
        state takes effect immediately.
      - SMOOTHED update (majority of last N results) when the new raw
        state is in the SAME group — prevents flickering between e.g.
        "VPN Active" and "Full Internet Access".
    """

    CATEGORY_IRAN          = "iran"
    CATEGORY_INTERNATIONAL = "international"
    CATEGORY_SOCIAL        = "social"

    def __init__(self, smoothing_window: int = 3):
        self.smoothing_window = smoothing_window
        self._history: List[str]   = []
        self._current_state: str   = ""
        self._proxy_active: bool   = False
        self._proxy_url: Optional[str] = None

    # ------------------------------------------------------------------
    # Proxy status (set by PlatformMonitor)
    # ------------------------------------------------------------------

    def set_proxy_status(self, proxy_url: Optional[str]):
        changed = (proxy_url is not None) != self._proxy_active
        self._proxy_active = proxy_url is not None
        self._proxy_url    = proxy_url
        if changed:
            # Proxy appeared or disappeared → reset history so next
            # classification takes effect without waiting for majority.
            logger.debug("Proxy status changed — resetting classifier history")
            self.reset_smoothing()

    # ------------------------------------------------------------------
    # Main classify
    # ------------------------------------------------------------------

    def classify(self, platforms: Dict[str, CheckResult]) -> str:
        if not platforms:
            return "No Internet Access"

        accessible = {n: r for n, r in platforms.items() if r.is_accessible}
        blocked    = {n: r for n, r in platforms.items() if not r.is_accessible}

        cat_iran          = [r for r in accessible.values() if r.platform.category == self.CATEGORY_IRAN]
        cat_international = [r for r in accessible.values() if r.platform.category == self.CATEGORY_INTERNATIONAL]
        cat_social        = [r for r in accessible.values() if r.platform.category == self.CATEGORY_SOCIAL]

        iran_ok          = len(cat_iran)          > 0
        international_ok = len(cat_international) > 0
        social_ok        = len(cat_social)        > 0

        # ── No connectivity ──────────────────────────────────────────────
        if not iran_ok and not international_ok and not social_ok:
            return "No Internet Access"

        # ── National network only ────────────────────────────────────────
        if iran_ok and not international_ok and not social_ok:
            return "Iran-Only Network"

        # ── Social reachable → VPN is bypassing filters ──────────────────
        if social_ok:
            if self._proxy_active or international_ok:
                return "VPN Active"
            return "VPN Active"   # TUN-mode VPN with no proxy port

        # ── International OK, social blocked ────────────────────────────
        if international_ok and not social_ok:
            if self._proxy_active:
                return "VPN Active (Social Still Blocked)"
            if self._check_dpi_interference(blocked):
                return "DPI Interference Suspected"
            return "Social Media Blocked"

        # ── International OK but Iran not ───────────────────────────────
        if international_ok and not iran_ok:
            return "VPN Active"

        return "Unstable Connection"

    # ------------------------------------------------------------------
    # Smart smoothing
    # ------------------------------------------------------------------

    def smooth(self, new_state: str) -> str:
        """
        Return the state to display, applying smart smoothing:
        - Cross-group change  → instant update + history reset
        - Same-group change   → majority vote over last N results
        """
        current_group = _state_group(self._current_state) if self._current_state else None
        new_group     = _state_group(new_state)

        # Significant change: different group → instant
        if current_group is not None and current_group != new_group:
            logger.info(
                f"Significant state change: '{self._current_state}' ({current_group}) "
                f"→ '{new_state}' ({new_group}) — instant update"
            )
            self._history = [new_state]
            self._current_state = new_state
            return new_state

        # Same group → apply smoothing to avoid flicker
        self._history.append(new_state)
        if len(self._history) > self.smoothing_window:
            self._history.pop(0)

        smoothed = Counter(self._history).most_common(1)[0][0]
        self._current_state = smoothed
        return smoothed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_dpi_interference(self, blocked: Dict[str, CheckResult]) -> bool:
        if not blocked:
            return False
        dpi_count     = 0
        total_checked = 0
        for result in blocked.values():
            if not (hasattr(result, "dns_success") and
                    hasattr(result, "tcp_success") and
                    hasattr(result, "http_success")):
                continue
            total_checked += 1
            if result.dns_success and result.tcp_success and not result.http_success:
                dpi_count += 1
        if total_checked == 0:
            return False
        return dpi_count >= 2 or (dpi_count / total_checked) >= 0.5

    def _avg_latency(self, platforms: List[CheckResult]) -> float:
        valid = [p.ping_ms for p in platforms if p.ping_ms > 0]
        return sum(valid) / len(valid) if valid else 0.0

    def reset_smoothing(self):
        self._history.clear()
        # Keep _current_state so next smooth() can detect a group change

    def get_classification_confidence(self) -> float:
        if not self._history:
            return 0.0
        counter = Counter(self._history)
        return counter.most_common(1)[0][1] / len(self._history)
