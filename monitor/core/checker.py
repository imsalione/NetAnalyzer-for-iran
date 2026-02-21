"""
Multi-layer network checker for a single platform.
Performs DNS, TCP, and HTTP checks concurrently with optimized resource usage.
Supports HTTP and SOCKS5 proxy (v2rayN, Clash, Shadowsocks, etc.)
"""

import asyncio
import time
import socket
from datetime import datetime
from typing import Optional

import aiohttp
from loguru import logger

from .models import Platform, DetailedCheckResult, PlatformStatus


class PlatformChecker:
    """Performs three-layer check for a single platform with minimal resource usage."""

    def __init__(
        self,
        timeout: float = 5.0,
        semaphore: asyncio.Semaphore = None,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.semaphore = semaphore or asyncio.Semaphore(5)
        self.proxy = proxy  # e.g. "http://127.0.0.1:10809" or "socks5://127.0.0.1:10808"
        # DNS cache to reduce lookups
        self._dns_cache: dict = {}
        self._cache_ttl = 300  # 5 minutes

    def update_proxy(self, proxy: Optional[str]):
        """Update proxy settings at runtime (called when proxy changes)."""
        if self.proxy != proxy:
            logger.info(f"Proxy updated: {self.proxy!r} → {proxy!r}")
            self.proxy = proxy

    async def check(self, platform: Platform, session: aiohttp.ClientSession) -> DetailedCheckResult:
        """Run all checks concurrently and return aggregated result."""
        start = time.monotonic()

        async with self.semaphore:
            # When a proxy is active, DNS and TCP checks behave differently:
            # - DNS resolution is handled by the proxy server, not locally
            # - TCP connections go through the proxy tunnel
            # We still run local DNS/TCP checks so we can detect DPI patterns,
            # but the HTTP check is the authoritative signal when proxy is active.
            dns_task = self._check_dns(platform.url)
            tcp_task = self._check_tcp(platform.url)
            http_task = self._check_http(platform, session)

            results = await asyncio.gather(
                dns_task, tcp_task, http_task, return_exceptions=True
            )

            dns_ok, tcp_ok, http_result = results

        # Parse DNS result
        dns_success = isinstance(dns_ok, bool) and dns_ok
        if not dns_success:
            logger.debug(f"DNS failed for {platform.name}: {dns_ok!r}")

        # Parse TCP result
        tcp_success = isinstance(tcp_ok, bool) and tcp_ok
        if not tcp_success:
            logger.debug(f"TCP failed for {platform.name}: {tcp_ok!r}")

        # Parse HTTP result
        http_success = False
        ping_ms = 0
        error = None

        if isinstance(http_result, tuple) and len(http_result) == 2:
            http_success, latency = http_result
            if http_success:
                ping_ms = latency * 1000
                logger.debug(f"HTTP success for {platform.name}: {ping_ms:.0f}ms"
                             + (f" [via proxy]" if self.proxy else ""))
            else:
                error = "http_failed"
                logger.debug(f"HTTP failed for {platform.name}")
        elif isinstance(http_result, Exception):
            error = type(http_result).__name__
            logger.debug(f"HTTP exception for {platform.name}: {error}")
        else:
            error = "unknown"

        # ---------------------------------------------------------------
        # Status determination
        # When a proxy is active, HTTP is the only reliable signal because:
        # - DNS may resolve locally but the site is blocked without proxy
        # - TCP may fail (handshake intercepted) without proxy
        # We must trust the HTTP result above DNS/TCP when proxy is in use.
        # ---------------------------------------------------------------
        if http_success:
            status = PlatformStatus.ONLINE if ping_ms < 500 else PlatformStatus.SLOW
        else:
            status = PlatformStatus.BLOCKED

        return DetailedCheckResult(
            platform=platform,
            status=status,
            ping_ms=ping_ms,
            timestamp=datetime.now(),
            dns_success=dns_success,
            tcp_success=tcp_success,
            http_success=http_success,
            error_type=error,
        )

    async def _check_dns(self, url: str) -> bool:
        """Resolve domain using asyncio.getaddrinfo with caching."""
        try:
            host = self._extract_host(url)

            now = time.time()
            if host in self._dns_cache:
                cached_time, cached_result = self._dns_cache[host]
                if now - cached_time < self._cache_ttl:
                    return cached_result

            loop = asyncio.get_running_loop()
            try:
                await asyncio.wait_for(
                    loop.getaddrinfo(host, 443, family=socket.AF_UNSPEC),
                    timeout=self.timeout,
                )
                result = True
            except asyncio.TimeoutError:
                result = False

            self._dns_cache[host] = (now, result)
            return result

        except Exception:
            return False

    async def _check_tcp(self, url: str) -> bool:
        """Attempt TCP connection to port 443 with timeout."""
        try:
            host = self._extract_host(url)

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, 443),
                timeout=self.timeout,
            )
            writer.close()
            await writer.wait_closed()
            return True

        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    async def _check_http(self, platform: Platform, session: aiohttp.ClientSession):
        """
        Perform HTTP GET request with proxy support.

        When self.proxy is set, requests are routed through the proxy so that
        connections blocked by ISP (Instagram, Twitter, Telegram, etc.) are
        reached correctly through VPN tunnels.
        """
        try:
            start = time.monotonic()

            timeout = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=self.timeout / 2,
                sock_read=self.timeout,
            )

            request_kwargs: dict = dict(
                ssl=True,
                timeout=timeout,
                allow_redirects=True,
                max_redirects=3,
            )

            # Attach proxy if configured
            if self.proxy:
                request_kwargs["proxy"] = self.proxy

            async with session.request(
                "GET",
                platform.url,
                **request_kwargs,
            ) as response:
                # Read minimal content (1 KB) to confirm connectivity
                await response.content.read(1024)
                latency = time.monotonic() - start
                success = 200 <= response.status < 400
                return success, latency

        except asyncio.TimeoutError:
            return False, 0
        except aiohttp.ClientProxyConnectionError as e:
            # Proxy itself is unreachable — surface this distinctly
            logger.warning(f"Proxy connection error for {platform.url}: {e}")
            return e
        except aiohttp.ClientError as e:
            return e
        except Exception as e:
            return e

    def _extract_host(self, url: str) -> str:
        """Extract hostname from URL."""
        if "://" in url:
            return url.split("://")[1].split("/")[0]
        return url.split("/")[0]

    def clear_dns_cache(self):
        """Clear DNS cache manually if needed."""
        self._dns_cache.clear()
