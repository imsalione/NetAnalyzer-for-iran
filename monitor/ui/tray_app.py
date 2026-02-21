"""
System Tray Application - Responsive real-time monitoring.

Key improvements:
- Persistent PlatformMonitor (preserves classifier history across checks)
- Adaptive fast re-check: when a significant state change is detected,
  immediately schedules a confirmation check (instead of waiting for the
  normal 30-second timer).
- Async VPN check correctly scheduled via asyncio.ensure_future.
- Complete Persian status translations.
"""

import asyncio
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QAction
from loguru import logger

from monitor.core.platform_monitor import PlatformMonitor, MonitorResult
from monitor.core.settings import Settings
from monitor.core.statistics import Statistics
from monitor.ui.minimal_window import MinimalWindow


def create_colored_icon(rgb: tuple, size: int = 64) -> QIcon:
    r, g, b = rgb
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(r, g, b)))
    painter.setPen(QPen(QColor(255, 255, 255), 2))
    margin = 6
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pixmap)


class TrayApplication(QWidget):
    """Main tray application with adaptive real-time monitoring."""

    status_updated = pyqtSignal(object)   # MonitorResult

    # Delay before the fast follow-up check (ms).
    # Short enough to feel instant, long enough to avoid hammering.
    _FAST_RECHECK_DELAY_MS = 1500

    def __init__(self):
        super().__init__()
        logger.info("=== Initializing TrayApplication ===")

        self.settings = Settings()
        self.stats    = Statistics()

        self.current_result = None
        self.current_color  = (158, 158, 158)
        self.window_visible = False
        self._is_checking   = False

        # ── Persistent monitor ───────────────────────────────────────────
        # One monitor instance lives for the whole session.
        # The classifier's smoothing history and the circuit-breaker state
        # are preserved between checks, which is essential for fast detection.
        self._monitor: PlatformMonitor    = PlatformMonitor(timeout=5.0, max_concurrent=5)
        self._monitor_session_open: bool  = False

        # Register callback so the monitor can request a fast follow-up check
        self._monitor.on_state_changed = self._on_monitor_state_changed

        # ── Fast re-check timer ──────────────────────────────────────────
        # Fires once after a significant state change is detected.
        self._fast_check_timer = QTimer()
        self._fast_check_timer.setSingleShot(True)
        self._fast_check_timer.timeout.connect(self._schedule_check)

        # ── Tray icon ────────────────────────────────────────────────────
        self.tray_icon = QSystemTrayIcon(self)
        self._update_icon(self.current_color)
        self.tray_icon.setToolTip("پایش اتصال اینترنت\nدر حال بارگذاری...")

        self._create_menu()

        # ── UI window ────────────────────────────────────────────────────
        self.minimal_window = MinimalWindow()

        # ── Signal connections ───────────────────────────────────────────
        self.tray_icon.activated.connect(self._on_tray_clicked)
        self.status_updated.connect(self._on_status_updated)
        self.minimal_window.vpn_check_requested.connect(
            lambda name: asyncio.ensure_future(self._check_vpn_platform(name))
        )

        self.tray_icon.show()

        # ── Periodic check timer ─────────────────────────────────────────
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._schedule_check)
        interval = self.settings.get('check_interval', 30) * 1000
        self.check_timer.start(interval)

        # First check immediately
        self._schedule_check()

        # Restore saved VPN platform
        saved = self.settings.get('vpn_platform')
        if saved:
            self.minimal_window.set_vpn_platform(saved)
            self._update_vpn_menu_checkmarks(saved)

        logger.info("=== TrayApplication initialized ===")

    # ──────────────────────────────────────────────────────────────────
    # Adaptive re-check
    # ──────────────────────────────────────────────────────────────────

    def _on_monitor_state_changed(self):
        """
        Called by PlatformMonitor when a significant state change is detected.
        Schedules a fast confirmation check so the UI updates within ~1.5s.
        """
        if not self._fast_check_timer.isActive():
            logger.debug(f"Fast re-check scheduled in {self._FAST_RECHECK_DELAY_MS}ms")
            self._fast_check_timer.start(self._FAST_RECHECK_DELAY_MS)

    # ──────────────────────────────────────────────────────────────────
    # Icon
    # ──────────────────────────────────────────────────────────────────

    def _update_icon(self, rgb: tuple):
        if rgb != self.current_color:
            logger.info(f"Icon: {self.current_color} → {rgb}")
            self.current_color = rgb
        self.tray_icon.setIcon(create_colored_icon(rgb))
        self.tray_icon.hide()
        self.tray_icon.show()

    # ──────────────────────────────────────────────────────────────────
    # Menu
    # ──────────────────────────────────────────────────────────────────

    def _create_menu(self):
        menu = QMenu()

        toggle_action = QAction("نمایش/مخفی پنجره", self)
        toggle_action.triggered.connect(self._toggle_window)
        menu.addAction(toggle_action)
        menu.addSeparator()

        check_action = QAction("بررسی اکنون", self)
        check_action.triggered.connect(self._schedule_check)
        menu.addAction(check_action)
        menu.addSeparator()

        interval_menu = menu.addMenu("بازه بررسی")
        for label, seconds in [("۵ ثانیه", 5), ("۱۰ ثانیه", 10), ("۳۰ ثانیه", 30), ("۱ دقیقه", 60)]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, s=seconds: self._set_interval(s))
            interval_menu.addAction(action)

        vpn_menu = menu.addMenu("🛡️ پایش VPN")
        self.vpn_platform_actions = {}
        for display, name in [("اینستاگرام", "Instagram"), ("تلگرام", "Telegram"), ("توییتر", "Twitter")]:
            action = QAction(display, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, p=name: self._select_vpn_platform(p))
            vpn_menu.addAction(action)
            self.vpn_platform_actions[name] = action

        vpn_menu.addSeparator()
        disable_action = QAction("❌ غیرفعال", self)
        disable_action.triggered.connect(lambda: self._select_vpn_platform(None))
        vpn_menu.addAction(disable_action)
        menu.addSeparator()

        self.notif_action = QAction("اعلان‌ها", self)
        self.notif_action.setCheckable(True)
        self.notif_action.setChecked(self.settings.get('notifications_enabled', True))
        self.notif_action.triggered.connect(self._toggle_notifications)
        menu.addAction(self.notif_action)
        menu.addSeparator()

        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self._exit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)

    # ──────────────────────────────────────────────────────────────────
    # VPN platform selection
    # ──────────────────────────────────────────────────────────────────

    def _select_vpn_platform(self, platform_name):
        self.settings.set('vpn_platform', platform_name)
        self.minimal_window.set_vpn_platform(platform_name)
        self._update_vpn_menu_checkmarks(platform_name)
        status = "فعال" if platform_name else "غیرفعال"
        self.tray_icon.showMessage(
            "پایش VPN",
            f"پایش VPN {status} شد" + (f" - {platform_name}" if platform_name else ""),
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _update_vpn_menu_checkmarks(self, selected):
        for name, action in self.vpn_platform_actions.items():
            action.setChecked(name == selected)

    async def _check_vpn_platform(self, platform_name: str):
        if not platform_name or self._is_checking:
            return
        try:
            platform = next((p for p in PlatformMonitor.PLATFORMS if p.name == platform_name), None)
            if not platform:
                return
            if not self._monitor_session_open:
                await self._monitor.__aenter__()
                self._monitor_session_open = True
            session = await self._monitor._get_session()
            result  = await self._monitor.checker.check(platform, session)
            self.minimal_window.update_vpn_status(result.is_accessible)
        except Exception as e:
            logger.error(f"VPN check failed for {platform_name}: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Tray interactions
    # ──────────────────────────────────────────────────────────────────

    def _on_tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self):
        if self.window_visible:
            self.minimal_window.hide()
            self.window_visible = False
        else:
            if self.current_result:
                self.minimal_window.update_status(
                    self.current_result,
                    {'uptime': self.stats.get_uptime_today(),
                     'disconnections': self.stats.get_disconnections_today()},
                )
            self.minimal_window.show()
            self.minimal_window.raise_()
            self.minimal_window.activateWindow()
            self.window_visible = True

    # ──────────────────────────────────────────────────────────────────
    # Check scheduling
    # ──────────────────────────────────────────────────────────────────

    def _schedule_check(self):
        if self._is_checking:
            logger.debug("Check already in progress, skipping")
            return
        asyncio.ensure_future(self._check_connection())

    async def _check_connection(self):
        if self._is_checking:
            return
        self._is_checking = True
        try:
            if not self._monitor_session_open:
                await self._monitor.__aenter__()
                self._monitor_session_open = True

            result = await self._monitor.check_all()
            self.current_result = result

            is_online = result.internet_status != "No Internet Access"
            self.stats.add_check(is_online)

            self.status_updated.emit(result)

        except Exception as e:
            logger.error(f"Check failed: {e}", exc_info=True)
        finally:
            self._is_checking = False

    # ──────────────────────────────────────────────────────────────────
    # UI update
    # ──────────────────────────────────────────────────────────────────

    def _on_status_updated(self, result: MonitorResult):
        quality_color = MinimalWindow.QUALITY_COLORS.get(result.quality, QColor(158, 158, 158))
        rgb = (quality_color.red(), quality_color.green(), quality_color.blue())
        self._update_icon(rgb)

        accessible     = result.get_accessible_platforms()
        accessible_str = ', '.join(accessible[:3]) + ("..." if len(accessible) > 3 else "")

        tooltip  = f"{self._translate_status(result.internet_status)}\n"
        tooltip += f"کیفیت: {self._translate_quality(result.quality)}\n"
        if accessible_str:
            tooltip += f"فعال: {accessible_str}"
        self.tray_icon.setToolTip(tooltip)

        if self.window_visible:
            self.minimal_window.update_status(
                result,
                {'uptime': self.stats.get_uptime_today(),
                 'disconnections': self.stats.get_disconnections_today()},
            )

    # ──────────────────────────────────────────────────────────────────
    # Translations
    # ──────────────────────────────────────────────────────────────────

    def _translate_status(self, status: str) -> str:
        return {
            'Full Internet Access':              'اتصال کامل',
            'Social Media Blocked':              'فیلتر شبکه‌های اجتماعی',
            'International Internet Restricted': 'محدودیت بین‌الملل',
            'Iran-Only Network':                 'اینترنت ملی',
            'VPN Active':                        'VPN فعال',
            'VPN Active (Social Still Blocked)': 'VPN فعال - شبکه‌های اجتماعی همچنان فیلتر',
            'DPI Interference Suspected':        'اختلال DPI',
            'Unstable Connection':               'اتصال ناپایدار',
            'No Internet Access':                'بدون اینترنت',
        }.get(status, status)

    def _translate_quality(self, quality: str) -> str:
        return {
            'Excellent': 'عالی',
            'Good':      'خوب',
            'Average':   'متوسط',
            'Poor':      'ضعیف',
            'Very Poor': 'بسیار ضعیف',
            'Unknown':   'نامشخص',
        }.get(quality, quality)

    # ──────────────────────────────────────────────────────────────────
    # Settings
    # ──────────────────────────────────────────────────────────────────

    def _set_interval(self, seconds: int):
        self.settings.set('check_interval', seconds)
        self.check_timer.setInterval(seconds * 1000)
        self.tray_icon.showMessage(
            "تنظیمات",
            f"بازه بررسی به {seconds} ثانیه تغییر کرد",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _toggle_notifications(self):
        enabled = self.notif_action.isChecked()
        self.settings.set('notifications_enabled', enabled)
        self.tray_icon.showMessage(
            "اعلان‌ها",
            f"اعلان‌ها {'فعال' if enabled else 'غیرفعال'} شدند",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    # ──────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────

    def _exit(self):
        logger.info("Exiting")
        self.check_timer.stop()
        self._fast_check_timer.stop()
        self.tray_icon.hide()
        if self.minimal_window:
            self.minimal_window.close()
        asyncio.ensure_future(self._cleanup_monitor())
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    async def _cleanup_monitor(self):
        try:
            if self._monitor_session_open:
                await self._monitor.__aexit__(None, None, None)
                self._monitor_session_open = False
        except Exception as e:
            logger.debug(f"Monitor cleanup: {e}")

    def closeEvent(self, a0: QEvent):
        self.check_timer.stop()
        self._fast_check_timer.stop()
        a0.accept()
