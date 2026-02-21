"""
Proxy Detector - Auto-detects VPN proxy settings.

Only scans ports that are specifically used by VPN/proxy applications.
Generic ports (8080, 8888, 9090) are intentionally excluded because they
are commonly used by Fiddler, local dev servers, WSL, etc. and cause
false positives that break direct internet detection.

Verification uses TWO checks:
  1. TCP port is open
  2. An actual HTTP request through the proxy succeeds to a known URL

This prevents stale TIME_WAIT ports and non-proxy services from being
mistakenly treated as VPN proxies.
"""

import os
import socket
import sys
import urllib.request
import urllib.error
from typing import Optional, Tuple, List
from loguru import logger


# ONLY well-known VPN/proxy application ports.
# Generic ports (8080, 8888, 9090) deliberately excluded.
KNOWN_PROXY_PORTS: List[Tuple[str, str, int, str]] = [
    ("http",   "127.0.0.1", 10809, "v2rayN HTTP"),
    ("socks5", "127.0.0.1", 10808, "v2rayN SOCKS5"),
    ("http",   "127.0.0.1",  7890, "Clash / ClashX HTTP"),
    ("socks5", "127.0.0.1",  7891, "Clash / ClashX SOCKS5"),
    ("http",   "127.0.0.1",  1087, "Shadowsocks HTTP"),
    ("socks5", "127.0.0.1",  1086, "Shadowsocks SOCKS5"),
    ("socks5", "127.0.0.1",  1080, "Generic SOCKS5"),
    ("http",   "127.0.0.1", 20171, "Outline HTTP"),
    ("http",   "127.0.0.1",  8118, "Privoxy HTTP"),
    ("http",   "127.0.0.1",  3128, "Squid / HTTP proxy"),
]

# URL used to verify proxy actually forwards traffic.
# Using Cloudflare's captive portal — no TLS, tiny response, globally reachable.
_VERIFY_URL     = "http://cp.cloudflare.com/"
_VERIFY_TIMEOUT = 3.0


def _is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """Quick TCP check — does NOT confirm the port is actually a proxy."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _verify_http_proxy(proxy_url: str, timeout: float = _VERIFY_TIMEOUT) -> bool:
    """
    Confirm a proxy URL actually forwards HTTP traffic to the internet.

    Sends a real GET request through the proxy using stdlib urllib (no deps).
    Returns True only if we get a valid HTTP response (status < 500).

    Handles the TIME_WAIT false-positive: a port left in TIME_WAIT after
    VPN shutdown accepts TCP but rejects or drops HTTP — this returns False.
    """
    try:
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener  = urllib.request.build_opener(handler)
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        with opener.open(_VERIFY_URL, timeout=timeout) as resp:
            ok = resp.status in (200, 204)
            if ok:
                logger.debug(f"Proxy verified: {proxy_url} → HTTP {resp.status}")
            return ok
    except urllib.error.HTTPError as e:
        # Proxy understood and replied — it's alive even if the status is odd
        alive = e.code < 500
        logger.debug(f"Proxy HTTP error {e.code} for {proxy_url} — {'alive' if alive else 'dead'}")
        return alive
    except Exception as e:
        logger.debug(f"Proxy verification failed [{type(e).__name__}]: {proxy_url}")
        return False


def _get_env_proxy() -> Optional[str]:
    """Read proxy from standard environment variables."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var, "").strip()
        if val:
            logger.debug(f"Proxy from env {var}: {val}")
            return val
    return None


def _get_windows_proxy() -> Optional[str]:
    """Read proxy from Windows Internet Settings registry (Windows only)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not proxy_enable:
            winreg.CloseKey(key)
            return None
        proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not proxy_server:
            return None
        # Format may be "host:port" or "http=h:p;https=h:p"
        if "=" in proxy_server:
            for entry in proxy_server.split(";"):
                if entry.startswith("https="):
                    return f"http://{entry[6:]}"
                if entry.startswith("http="):
                    return f"http://{entry[5:]}"
        else:
            return f"http://{proxy_server}"
    except Exception:
        pass
    return None


def _scan_local_ports() -> Optional[Tuple[str, str]]:
    """
    Scan VPN-specific ports, verify each HTTP candidate, return first working one.
    Prefers HTTP proxies (natively supported by aiohttp without extra packages).
    """
    open_ports = [(s, h, p, n) for s, h, p, n in KNOWN_PROXY_PORTS if _is_port_open(h, p)]

    if not open_ports:
        return None

    # Verify HTTP candidates first
    for scheme, host, port, name in open_ports:
        if scheme != "http":
            continue
        url = f"http://{host}:{port}"
        if _verify_http_proxy(url):
            return url, name
        logger.debug(f"Skipping {name} ({url}): port open but proxy not responding")

    # Fall back to SOCKS5 (harder to verify cheaply — trust open port)
    for scheme, host, port, name in open_ports:
        if scheme == "socks5":
            url = f"socks5://{host}:{port}"
            logger.debug(f"SOCKS5 detected (unverified): {name} ({url})")
            return url, name

    return None


def detect_proxy() -> Optional[str]:
    """
    Detect an active, working VPN/proxy from all sources.

    Priority: env vars → Windows registry → port scan.
    Returns a proxy URL string or None if no working proxy found.
    """
    proxy = _get_env_proxy()
    if proxy:
        return proxy

    proxy = _get_windows_proxy()
    if proxy:
        return proxy

    result = _scan_local_ports()
    if result:
        proxy_url, app_name = result
        logger.info(f"Working proxy detected: {app_name} → {proxy_url}")
        return proxy_url

    return None


def is_socks5_proxy(proxy_url: str) -> bool:
    return proxy_url.lower().startswith("socks5://")


def check_socks5_support() -> bool:
    try:
        import aiohttp_socks  # noqa: F401
        return True
    except ImportError:
        return False
