"""
Platform Monitor - Responsive real-time monitoring.

Key improvements:
- Circuit breaker cooldown reduced: 300s → 45s (so blocked platforms
  are re-checked quickly when VPN activates).
- Circuit breaker is fully reset when proxy/connection state changes.
- Proxy rescan interval reduced: 15s → 5s for faster VPN detection.
- Adaptive re-check: if a significant state change is detected,
  immediately schedules a confirmation check.
- Proxy fallback: if proxy causes all checks to fail but direct TCP
  works, clears proxy and retries direct.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
import time

import aiohttp
from loguru import logger

from .models import Platform, MonitorResult, DetailedCheckResult, PlatformStatus
from .checker import PlatformChecker
from .circuit_breaker import CircuitBreaker
from .latency_window import LatencyWindow
from .classifier import ConnectionClassifier
from .proxy_detector import detect_proxy, is_socks5_proxy, check_socks5_support


class PlatformMonitor:
    """Monitor platform accessibility with instant state-change detection."""

    PLATFORMS = [
        Platform("Instagram",  "📷", "https://www.instagram.com",         "social"),
        Platform("Telegram",   "✈️", "https://web.telegram.org",           "social"),
        Platform("X",    "🐦", "https://x.com",                "social"),
        Platform("Google",     "🌍", "https://www.google.com/generate_204","international"),
        Platform("Cloudflare", "☁️", "https://cloudflare.com/cdn-cgi/trace","international"),
        Platform("Microsoft",  "Ⓜ️", "https://www.microsoft.com",           "international"),
        Platform("IRNA",       "📰", "https://www.irna.ir",                "iran"),
        Platform("ISNA",       "📰", "https://www.isna.ir",                "iran"),
        Platform("Digikala",   "🛒", "https://www.digikala.com",           "iran"),
    ]

    _PROXY_RESCAN_INTERVAL = 5    # seconds — fast enough to catch VPN toggle

    def __init__(self, timeout: float = 5.0, max_concurrent: int = 5):
        self.timeout        = timeout
        self.max_concurrent = max_concurrent

        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self.semaphore     = asyncio.Semaphore(max_concurrent)

        self._current_proxy: Optional[str] = None
        self._last_proxy_scan: float       = 0.0
        self._last_known_status: str       = ""

        # Circuit breaker: 3 failures → 45s cooldown (was 300s)
        # 45s is short enough to re-check quickly when VPN activates.
        self.checker         = PlatformChecker(timeout=timeout, semaphore=self.semaphore)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=45)
        self.latency_window  = LatencyWindow(maxlen=20)
        self.classifier      = ConnectionClassifier(smoothing_window=3)

        self._last_check_duration = 0.0

        # Callback that TrayApplication sets to trigger an extra fast check
        self.on_state_changed = None   # Optional[Callable[[], None]]

    # ──────────────────────────────────────────────────────────────────
    # Proxy management
    # ──────────────────────────────────────────────────────────────────

    async def _refresh_proxy(self) -> Optional[str]:
        """
        Re-detect proxy every _PROXY_RESCAN_INTERVAL seconds.
        When the proxy state changes, resets circuit breakers so previously
        blocked platforms are re-checked immediately.
        """
        now = time.monotonic()
        if now - self._last_proxy_scan < self._PROXY_RESCAN_INTERVAL:
            return self._current_proxy

        self._last_proxy_scan = now
        loop     = asyncio.get_running_loop()
        detected = await loop.run_in_executor(None, detect_proxy)

        if detected and is_socks5_proxy(detected) and not check_socks5_support():
            logger.warning(
                f"SOCKS5 proxy detected ({detected}) but 'aiohttp-socks' not installed. "
                "Falling back to direct connection."
            )
            detected = None

        if detected != self._current_proxy:
            old = self._current_proxy
            self._current_proxy = detected
            self.checker.update_proxy(detected)
            self.classifier.set_proxy_status(detected)

            if detected:
                logger.info(f"Proxy activated: {detected}")
            else:
                logger.info(f"Proxy removed (was: {old}) — direct connection")

            # Reset circuit breakers so all platforms are checked fresh.
            # This is critical: without this, platforms that hit their failure
            # threshold before VPN was activated stay in cooldown for 45s.
            self._reset_circuit_breakers()
            await self._close_session()

        return self._current_proxy

    def _reset_circuit_breakers(self):
        """Clear all circuit-breaker state so every platform is checked next cycle."""
        self.circuit_breaker._failures.clear()
        self.circuit_breaker._open_until.clear()
        logger.debug("Circuit breakers reset (proxy state change)")

    def _force_clear_proxy(self):
        """Clear proxy immediately (called when proxy breaks all checks)."""
        if self._current_proxy:
            logger.warning(
                f"Proxy {self._current_proxy} caused all checks to fail — "
                "clearing and retrying direct."
            )
        self._current_proxy = None
        self._last_proxy_scan = 0.0
        self.checker.update_proxy(None)
        self.classifier.set_proxy_status(None)
        self._reset_circuit_breakers()

    # ──────────────────────────────────────────────────────────────────
    # Session management
    # ──────────────────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=self.max_concurrent,
                    limit_per_host=2,
                    ttl_dns_cache=60,   # shorter cache so DNS changes apply faster
                    force_close=True,
                )
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(
                        total=self.timeout,
                        connect=self.timeout / 2,
                        sock_read=self.timeout,
                    ),
                    connector=connector,
                    headers={"User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )},
                )
            return self._session

    async def _close_session(self):
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                await asyncio.sleep(0.1)
                self._session = None

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()

    # ──────────────────────────────────────────────────────────────────
    # Quick connectivity check
    # ──────────────────────────────────────────────────────────────────

    async def quick_ping(self) -> bool:
        """Direct TCP to 1.1.1.1:53 — bypasses any proxy."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("1.1.1.1", 53), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────────
    # Main check
    # ──────────────────────────────────────────────────────────────────

    async def check_all(self) -> MonitorResult:
        """
        Full platform check with proxy auto-detection and fallback.

        Flow:
          1. Direct TCP ping → if fails, report No Internet Access
          2. Refresh proxy detection (every 5s)
          3. Run all platform checks (via proxy if active)
          4. If proxy caused all-fail → clear proxy, retry direct
          5. Detect significant state change → notify TrayApp for fast re-check
        """
        t0 = time.monotonic()

        try:
            # ── 1. Direct connectivity ──────────────────────────────────
            has_internet = await self.quick_ping()
            if not has_internet:
                logger.info("Direct ping failed → No Internet Access")
                result = self._create_disconnected_result()
                self._notify_if_changed(result.internet_status)
                return result

            # ── 2. Proxy refresh ────────────────────────────────────────
            await self._refresh_proxy()

            # ── 3. Platform checks ──────────────────────────────────────
            session = await self._get_session()
            result  = await self._run_checks(session)

            # ── 4. Proxy fallback ───────────────────────────────────────
            if self._current_proxy and result.internet_status == "No Internet Access":
                logger.warning("Proxy broke all checks — retrying direct")
                self._force_clear_proxy()
                await self._close_session()
                session = await self._get_session()
                result  = await self._run_checks(session)

            self._last_check_duration = time.monotonic() - t0
            logger.info(
                f"check_all {self._last_check_duration:.2f}s → "
                f"{result.internet_status} | {result.quality}"
                + (f" [via {self._current_proxy}]" if self._current_proxy else " [direct]")
            )

            # ── 5. Notify on significant change ─────────────────────────
            self._notify_if_changed(result.internet_status)
            return result

        except Exception as e:
            logger.error(f"check_all error: {e}", exc_info=True)
            return self._create_disconnected_result()

    def _notify_if_changed(self, new_status: str):
        """
        If the status group changed (e.g. restricted → connected),
        call the callback so TrayApplication schedules a fast follow-up check.
        """
        if not self._last_known_status:
            self._last_known_status = new_status
            return

        from .classifier import _state_group
        if _state_group(new_status) != _state_group(self._last_known_status):
            logger.debug(
                f"State group changed: '{self._last_known_status}' → '{new_status}'"
                " — requesting fast follow-up check"
            )
            if self.on_state_changed:
                self.on_state_changed()

        self._last_known_status = new_status

    # ──────────────────────────────────────────────────────────────────
    # Platform checks
    # ──────────────────────────────────────────────────────────────────

    async def _run_checks(self, session: aiohttp.ClientSession) -> MonitorResult:
        tasks = []
        for platform in self.PLATFORMS:
            if self.circuit_breaker.is_allowed(platform.name):
                tasks.append(self._check_safe(platform, session))
            else:
                tasks.append(self._blocked_result(platform, "circuit_open"))

        raw = await asyncio.gather(*tasks, return_exceptions=True)

        platforms: Dict[str, DetailedCheckResult] = {}
        for platform, res in zip(self.PLATFORMS, raw):
            if isinstance(res, DetailedCheckResult):
                platforms[platform.name] = res
                if res.is_accessible:
                    self.circuit_breaker.record_success(platform.name)
                    if res.ping_ms > 0:
                        self.latency_window.add(platform.name, res.ping_ms)
                else:
                    self.circuit_breaker.record_failure(platform.name)
            else:
                logger.error(f"Unexpected result for {platform.name}: {res}")
                platforms[platform.name] = await self._blocked_result(platform, "unexpected_error")

        return self._compute_result(platforms)

    async def _check_safe(self, platform: Platform, session: aiohttp.ClientSession) -> DetailedCheckResult:
        try:
            return await self.checker.check(platform, session)
        except Exception as e:
            logger.error(f"Error checking {platform.name}: {e}")
            return await self._blocked_result(platform, "check_exception")

    async def _blocked_result(self, platform: Platform, reason: str) -> DetailedCheckResult:
        return DetailedCheckResult(
            platform=platform,
            status=PlatformStatus.BLOCKED,
            ping_ms=0,
            timestamp=datetime.now(),
            dns_success=False,
            tcp_success=False,
            http_success=False,
            error_type=reason,
        )

    def _create_disconnected_result(self) -> MonitorResult:
        return MonitorResult(
            platforms={},
            timestamp=datetime.now(),
            internet_status="No Internet Access",
            quality="Unknown",
            international_ping=0,
            iran_ping=0,
        )

    def _compute_result(self, platforms: Dict[str, DetailedCheckResult]) -> MonitorResult:
        international = [r for r in platforms.values()
                         if r.platform.category == "international" and r.is_accessible]
        iran          = [r for r in platforms.values()
                         if r.platform.category == "iran"          and r.is_accessible]

        int_ping  = sum(r.ping_ms for r in international) / len(international) if international else 0
        iran_ping = sum(r.ping_ms for r in iran)          / len(iran)          if iran          else 0

        raw_state       = self.classifier.classify(platforms)
        internet_status = self.classifier.smooth(raw_state)

        avg_ping = ((int_ping + iran_ping) / 2
                    if (int_ping > 0 and iran_ping > 0)
                    else max(int_ping, iran_ping))

        if   avg_ping == 0:     quality = "Unknown"
        elif avg_ping < 100:    quality = "Excellent"
        elif avg_ping < 300:    quality = "Good"
        elif avg_ping < 600:    quality = "Average"
        elif avg_ping < 1000:   quality = "Poor"
        else:                   quality = "Very Poor"

        return MonitorResult(
            platforms=platforms,
            timestamp=datetime.now(),
            internet_status=internet_status,
            quality=quality,
            international_ping=int_ping,
            iran_ping=iran_ping,
        )

    async def cleanup(self):
        await self._close_session()

    def __del__(self):
        try:
            if self._session and not self._session.closed:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_session())
        except Exception:
            pass
