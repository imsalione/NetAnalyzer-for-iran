"""
Minimal Status Window - Final Design
Quality-based color synchronization with status description below chart
"""

from collections import deque
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QMenu, QApplication, QPushButton, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QPointF, QTimer, QByteArray, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QAction, QCursor
from PyQt6.QtSvg import QSvgRenderer
import weakref
import os
import sys


def get_base_path() -> str:
    """Get the base path for the application (works for both dev and frozen exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class SvgIconButton(QPushButton):
    """Custom button that displays SVG icons with color customization."""

    def __init__(self, platform_name: str = None, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.is_connected = False
        self.svg_renderer = None
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton { border: none; padding: 0px; margin: 0px; background-color: transparent; }
            QPushButton:hover { background-color: transparent; }
            QPushButton:pressed { background-color: transparent; }
        """)
        self._load_svg()

    def _get_svg_path(self) -> str:
        base_path = get_base_path()
        icons_dir = os.path.join(base_path, 'icons')
        svg_files = {
            'Instagram': os.path.join(icons_dir, 'instagram.svg'),
            'Telegram':  os.path.join(icons_dir, 'telegram.svg'),
            'Twitter':   os.path.join(icons_dir, 'twitter.svg'),
        }
        if self.platform_name and self.platform_name in svg_files:
            path = svg_files[self.platform_name]
            if os.path.exists(path):
                return path
        return None

    def _get_default_svg(self) -> str:
        default_svgs = {
            'Instagram': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zM5.838 12a6.162 6.162 0 1112.324 0 6.162 6.162 0 01-12.324 0zM12 16a4 4 0 110-8 4 4 0 010 8zm4.965-10.405a1.44 1.44 0 112.881.001 1.44 1.44 0 01-2.881-.001z"/>
            </svg>''',
            'Telegram': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
            </svg>''',
            'Twitter': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
                <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.104c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 0021.775-3.374 13.5 13.5 0 002.163-7.253c0-.207-.005-.415-.015-.622a9.48 9.48 0 002.306-2.394z"/>
            </svg>''',
            None: '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
                <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
            </svg>'''
        }
        return default_svgs.get(self.platform_name, default_svgs[None])

    def _load_svg(self):
        svg_path = self._get_svg_path()
        if svg_path and os.path.exists(svg_path):
            try:
                with open(svg_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                self.svg_renderer = QSvgRenderer(QByteArray(svg_content.encode()))
                return
            except Exception as e:
                print(f"Error loading SVG from {svg_path}: {e}")
        svg_content = self._get_default_svg()
        self.svg_renderer = QSvgRenderer(QByteArray(svg_content.encode()))

    def set_platform(self, platform_name: str):
        self.platform_name = platform_name
        self._load_svg()
        self.update()

    def set_connected(self, connected: bool):
        self.is_connected = connected
        self.update()

    def get_background_color(self) -> QColor:
        if self.is_connected and self.platform_name:
            return QColor(76, 175, 80)
        elif not self.is_connected and self.platform_name:
            return QColor(244, 67, 54)
        else:
            return QColor(158, 158, 158)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rect = self.rect()
        center = rect.center()
        circle_radius = int(min(rect.width(), rect.height()) * 0.4)
        bg_color = self.get_background_color()
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, circle_radius, circle_radius)
        if self.svg_renderer and self.svg_renderer.isValid():
            icon_size = int(circle_radius * 1.4)
            icon_x = center.x() - icon_size // 2
            icon_y = center.y() - icon_size // 2
            icon_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
            self.svg_renderer.render(painter, icon_rect)
        painter.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def sizeHint(self):
        return self.size()

    def minimumSizeHint(self):
        return self.size()


class QualityChart(QWidget):
    """Compact speed chart with quality-based coloring."""

    MODE_BOTH = 0
    MODE_INTERNATIONAL = 1
    MODE_IRAN = 2
    MODE_COMBINED = 3

    modeChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window_ref = None
        if parent:
            widget = parent
            while widget and not isinstance(widget, QDialog):
                widget = widget.parentWidget()
            if widget:
                self.main_window_ref = weakref.ref(widget)

        settings = QSettings("InternetMonitor", "ChartSettings")
        saved_mode = settings.value("chart_mode", self.MODE_BOTH, type=int)

        self.setFixedHeight(55)
        self.setFixedWidth(170)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.int_data = deque(maxlen=40)
        self.iran_data = deque(maxlen=40)
        self.mode = saved_mode
        self.quality_color = QColor(158, 158, 158)

        for _ in range(40):
            self.int_data.append(0)
            self.iran_data.append(0)

    def set_quality_color(self, color: QColor):
        self.quality_color = color
        self.update()

    def add_data(self, int_ping: float, iran_ping: float):
        self.int_data.append(int_ping)
        self.iran_data.append(iran_ping)
        self.update()

    def set_mode(self, mode: int):
        self.mode = mode
        settings = QSettings("InternetMonitor", "ChartSettings")
        settings.setValue("chart_mode", mode)
        self.modeChanged.emit(mode)
        self.update()

    def show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1e1e24; border: 1px solid #3a3a45; border-radius: 6px; padding: 6px; }
            QMenu::item { color: #e0e0e0; padding: 6px 20px; border-radius: 4px; font-family: 'Segoe UI'; font-size: 9pt; }
            QMenu::item:selected { background-color: #2a5caa; }
            QMenu::item:checked { background-color: #2a5caa; color: white; }
        """)
        modes = [
            ("نمایش هر دو", self.MODE_BOTH),
            ("فقط بین‌المللی", self.MODE_INTERNATIONAL),
            ("فقط داخلی", self.MODE_IRAN),
            ("نمایش ترکیبی", self.MODE_COMBINED),
        ]
        for label, mode_value in modes:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, m=mode_value: self.set_mode(m))
            action.setCheckable(True)
            action.setChecked(self.mode == mode_value)
            menu.addAction(action)
        menu.exec(self.mapToGlobal(position))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(26, 26, 31))
        width = self.width()
        height = self.height()
        padding = 4
        painter.setPen(QPen(QColor(50, 50, 50, 80), 0.5, Qt.PenStyle.DotLine))
        for i in range(1, 3):
            y = height * i / 3
            painter.drawLine(padding, int(y), width - padding, int(y))

        if self.mode == self.MODE_COMBINED:
            combined = [(i + r) / 2 if (i > 0 or r > 0) else 0
                        for i, r in zip(self.int_data, self.iran_data)]
            max_val = max(combined) if max(combined) > 0 else 100
        else:
            all_values = []
            if self.mode in [self.MODE_BOTH, self.MODE_INTERNATIONAL]:
                all_values.extend(self.int_data)
            if self.mode in [self.MODE_BOTH, self.MODE_IRAN]:
                all_values.extend(self.iran_data)
            max_val = max(all_values) if all_values and max(all_values) > 0 else 100

        max_val = max(max_val, 100)

        if self.mode == self.MODE_COMBINED:
            self._draw_line(painter, combined, max_val, self.quality_color, width, height, padding, fill=True)
        elif self.mode == self.MODE_BOTH:
            iran_color = QColor(self.quality_color)
            iran_color.setAlpha(180)
            self._draw_line(painter, self.iran_data, max_val, iran_color, width, height, padding, offset=1)
            int_color = QColor(self.quality_color)
            self._draw_line(painter, self.int_data, max_val, int_color, width, height, padding, offset=-1)
        else:
            data = self.iran_data if self.mode == self.MODE_IRAN else self.int_data
            self._draw_line(painter, data, max_val, self.quality_color, width, height, padding, fill=True)

    def _draw_line(self, painter, data, max_val, color, width, height, padding, fill=False, offset=0):
        if not any(data):
            return
        path = QPainterPath()
        points = []
        for i, val in enumerate(data):
            x = padding + (width - 2 * padding) * i / (len(data) - 1) if len(data) > 1 else padding
            y = height - padding - ((height - 2 * padding) * val / max_val) + offset
            points.append(QPointF(x, y))
        if not points:
            return
        path.moveTo(points[0])
        for i in range(1, len(points)):
            path.lineTo(points[i])
        if fill:
            fill_path = QPainterPath(path)
            fill_path.lineTo(QPointF(points[-1].x(), height - padding))
            fill_path.lineTo(QPointF(points[0].x(), height - padding))
            fill_path.closeSubpath()
            fill_color = QColor(color)
            fill_color.setAlpha(40)
            painter.fillPath(fill_path, QBrush(fill_color))
        pen = QPen(color, 2.5, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)


class MinimalWindow(QDialog):
    """Minimal window with quality-based color synchronization."""

    QUALITY_COLORS = {
        'Excellent': QColor(76, 175, 80),
        'Good':      QColor(139, 195, 74),
        'Average':   QColor(255, 193, 7),
        'Poor':      QColor(255, 152, 0),
        'Very Poor': QColor(244, 67, 54),
        'Unknown':   QColor(158, 158, 158),
    }
    GRAY_COLOR = QColor(158, 158, 158)

    vpn_check_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_pos = None
        self.vpn_platform = None
        self.current_quality_color = self.GRAY_COLOR
        self._vpn_check_pending = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 110)

        self.vpn_check_timer = QTimer()
        self.vpn_check_timer.setInterval(5000)
        self.vpn_check_timer.timeout.connect(self._request_vpn_check)

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        from monitor.ui.minimal_window import GridWidget
        container = GridWidget(self)
        container.setObjectName("container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(4)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        left_widget = QWidget()
        left_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        ping_row_widget = QWidget()
        ping_row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        ping_row_layout = QHBoxLayout(ping_row_widget)
        ping_row_layout.setContentsMargins(0, 0, 0, 0)
        ping_row_layout.setSpacing(6)

        ping_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)

        # International ping
        int_container = QWidget()
        int_container.setObjectName("pingContainer")
        int_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        int_layout = QHBoxLayout(int_container)
        int_layout.setContentsMargins(6, 4, 6, 4)
        int_layout.setSpacing(6)
        int_icon = QLabel("🌍")
        int_icon.setStyleSheet("font-size: 11pt; background: transparent; color: #9e9e9e;")
        int_layout.addWidget(int_icon)
        self.int_ping_label = QLabel("--")
        self.int_ping_label.setObjectName("pingLabel")
        self.int_ping_label.setFont(ping_font)
        self.int_ping_label.setStyleSheet("color: #9e9e9e; background: transparent; font-weight: 700;")
        int_layout.addWidget(self.int_ping_label)
        int_layout.addStretch()
        ping_row_layout.addWidget(int_container)

        # Iran ping
        iran_container = QWidget()
        iran_container.setObjectName("pingContainer")
        iran_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        iran_layout = QHBoxLayout(iran_container)
        iran_layout.setContentsMargins(6, 4, 6, 4)
        iran_layout.setSpacing(6)
        iran_icon = QLabel("🏠")
        iran_icon.setStyleSheet("font-size: 11pt; background: transparent; color: #9e9e9e;")
        iran_layout.addWidget(iran_icon)
        self.iran_ping_label = QLabel("--")
        self.iran_ping_label.setObjectName("pingLabel")
        self.iran_ping_label.setFont(ping_font)
        self.iran_ping_label.setStyleSheet("color: #9e9e9e; background: transparent; font-weight: 700;")
        iran_layout.addWidget(self.iran_ping_label)
        iran_layout.addStretch()
        ping_row_layout.addWidget(iran_container)

        left_layout.addWidget(ping_row_widget)

        self.quality_label = QLabel("کیفیت: --")
        self.quality_label.setObjectName("qualityLabel")
        quality_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self.quality_label.setFont(quality_font)
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.quality_label)
        left_layout.addStretch()

        top_layout.addWidget(left_widget)

        self.chart = QualityChart(container)
        self.chart.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        top_layout.addWidget(self.chart)

        container_layout.addLayout(top_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(2)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("در حال بررسی...")
        self.status_label.setObjectName("statusLabel")
        status_font = QFont("Segoe UI", 8, QFont.Weight.Medium)
        self.status_label.setFont(status_font)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setWordWrap(False)
        self.status_label.setStyleSheet(
            "color: #9e9e9e; background: transparent; font-weight: 500; padding: 0px; margin: 0px;"
        )
        bottom_layout.addWidget(self.status_label, 1)

        self.vpn_button = SvgIconButton()
        self.vpn_button.clicked.connect(self._on_vpn_button_clicked)
        bottom_layout.addWidget(self.vpn_button)
        bottom_layout.addStretch(0)

        container_layout.addLayout(bottom_layout)

        main_layout.addWidget(container)
        self.chart.main_window_ref = weakref.ref(self)
        self._apply_style()

    def _on_vpn_button_clicked(self):
        if self.vpn_platform:
            platform_display = {
                'Instagram': 'اینستاگرام',
                'Telegram':  'تلگرام',
                'Twitter':   'توییتر',
            }.get(self.vpn_platform, self.vpn_platform)
            status_text = "✅ متصل" if self.vpn_button.is_connected else "❌ قطع"
            color_text  = "سبز"    if self.vpn_button.is_connected else "قرمز"
            tooltip = (
                f"🛡️ وضعیت VPN برای {platform_display}\n"
                f"وضعیت: {status_text}\n"
                f"دایره {color_text} نشان‌دهنده وضعیت اتصال است\n"
                f"برای تغییر پلتفرم از منوی سینی استفاده کنید"
            )
        else:
            tooltip = (
                "🛡️ پایش VPN فعال نیست\n"
                "برای فعال‌سازی، از منوی سینی یک پلتفرم انتخاب کنید"
            )
        QToolTip.showText(QCursor.pos(), tooltip, self.vpn_button)

    def update_status(self, result, stats=None):
        """Update display with monitoring result."""
        self.current_quality_color = self.QUALITY_COLORS.get(result.quality, self.GRAY_COLOR)
        color_hex = self.current_quality_color.name()
        rgb = (
            self.current_quality_color.red(),
            self.current_quality_color.green(),
            self.current_quality_color.blue(),
        )

        self.chart.set_quality_color(self.current_quality_color)

        if result.international_ping > 0:
            self.int_ping_label.setText(f"{result.international_ping:.0f}")
        else:
            self.int_ping_label.setText("--")

        if result.iran_ping > 0:
            self.iran_ping_label.setText(f"{result.iran_ping:.0f}")
        else:
            self.iran_ping_label.setText("--")

        quality_fa = self._translate_quality(result.quality)
        self.quality_label.setText(f"کیفیت: {quality_fa}")
        self.quality_label.setStyleSheet(f"""
            color: {color_hex};
            background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.15);
            border-radius: 6px;
            padding: 5px 10px;
            font-weight: 700;
        """)

        status_description = self._get_status_description(result.internet_status)
        self.status_label.setText(status_description)

        self.chart.add_data(result.international_ping, result.iran_ping)

        if self.vpn_platform and result.platforms:
            platform_result = result.platforms.get(self.vpn_platform)
            if platform_result:
                self.update_vpn_status(platform_result.is_accessible)

    def update_vpn_status(self, is_accessible: bool):
        self.vpn_button.set_connected(is_accessible)
        if self.vpn_platform:
            platform_display = {
                'Instagram': 'اینستاگرام',
                'Telegram':  'تلگرام',
                'Twitter':   'توییتر',
            }.get(self.vpn_platform, self.vpn_platform)
            tooltip = (
                f"🛡️ VPN برای {platform_display} فعال است"
                if is_accessible
                else f"🛡️ VPN برای {platform_display} غیرفعال است"
            )
            self.vpn_button.setToolTip(tooltip)

    def set_vpn_platform(self, platform_name: str):
        self.vpn_platform = platform_name
        self.vpn_button.set_platform(platform_name)
        if platform_name:
            display_name = {
                'Instagram': 'اینستاگرام',
                'Telegram':  'تلگرام',
                'Twitter':   'توییتر',
            }.get(platform_name, platform_name)
            self.vpn_check_timer.start()
            self.vpn_button.setToolTip(
                f"🛡️ پایش {display_name} برای تشخیص VPN\n"
                f"دایره سبز = متصل | دایره قرمز = قطع"
            )
        else:
            self.vpn_check_timer.stop()
            self.vpn_button.set_connected(False)
            self.vpn_button.setToolTip(
                "🛡️ پایش VPN فعال نیست\nبرای فعال‌سازی از منوی نرم افزار استفاده کنید"
            )

    def _request_vpn_check(self):
        if self.vpn_platform and not self._vpn_check_pending:
            self._vpn_check_pending = True
            self.vpn_check_requested.emit(self.vpn_platform)
            QTimer.singleShot(1000, self._reset_vpn_check_pending)

    def _reset_vpn_check_pending(self):
        self._vpn_check_pending = False

    def _get_status_description(self, status: str) -> str:
        """Get descriptive Persian text for status."""
        descriptions = {
            'Full Internet Access':              'اتصال کامل - دسترسی آزاد به تمام سرویس‌ها',
            'Social Media Blocked':              'فیلتر شبکه‌های اجتماعی - سایر سرویس‌ها فعال',
            'International Internet Restricted': 'محدودیت دسترسی بین‌المللی',
            'Iran-Only Network':                 'اینترنت ملی - فقط دسترسی به سرویس‌های داخلی',
            'VPN Active':                        'فیلترشکن فعال - اتصال امن برقرار است',
            # BUG FIX #4: new state must have its own description
            'VPN Active (Social Still Blocked)': 'فیلترشکن فعال - شبکه‌های اجتماعی همچنان فیلتر',
            'DPI Interference Suspected':        'احتمال اختلال DPI - ممکن است فیلترینگ وجود داشته باشد',
            'Unstable Connection':               'اتصال ناپایدار - ممکن است قطعی‌های موقت رخ دهد',
            'No Internet Access':                'عدم دسترسی به اینترنت',
        }
        return descriptions.get(status, 'در حال بررسی وضعیت اتصال...')

    def _translate_quality(self, quality: str) -> str:
        translations = {
            'Excellent': 'عالی',
            'Good':      'خوب',
            'Average':   'متوسط',
            'Poor':      'ضعیف',
            'Very Poor': 'بسیار ضعیف',
            'Unknown':   'نامشخص',
        }
        return translations.get(quality, quality)

    def wheelEvent(self, event):
        if event.buttons() & Qt.MouseButton.MiddleButton:
            delta = event.angleDelta().y()
            if delta > 0:
                new_opacity = min(1.0, self.windowOpacity() + 0.05)
            elif delta < 0:
                new_opacity = max(0.2, self.windowOpacity() - 0.05)
            else:
                return
            self.setWindowOpacity(new_opacity)
            self._save_opacity()
            event.accept()
        else:
            super().wheelEvent(event)

    def _load_settings(self):
        try:
            settings = QSettings("InternetMonitor", "WindowSettings")
            if settings.contains("pos_x"):
                self.move(settings.value("pos_x", type=int), settings.value("pos_y", type=int))
            else:
                screen = QApplication.primaryScreen().geometry()
                self.move(screen.width() - 380, 10)
            if settings.contains("vpn_platform"):
                self.vpn_platform = settings.value("vpn_platform", type=str)
            if settings.contains("opacity"):
                self.setWindowOpacity(settings.value("opacity", type=float))
            else:
                self.setWindowOpacity(1.0)
        except Exception:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.width() - 380, 10)
            self.setWindowOpacity(1.0)

    def _save_settings(self):
        try:
            settings = QSettings("InternetMonitor", "WindowSettings")
            settings.setValue("pos_x", self.x())
            settings.setValue("pos_y", self.y())
            if self.vpn_platform:
                settings.setValue("vpn_platform", self.vpn_platform)
        except Exception:
            pass

    def _save_opacity(self):
        try:
            settings = QSettings("InternetMonitor", "WindowSettings")
            settings.setValue("opacity", self.windowOpacity())
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = None
            self._save_settings()

    def _apply_style(self):
        self.setStyleSheet("""
            #container {
                background-color: #1a1a1f;
                border: 1px solid #2a2a35;
                border-radius: 12px;
                min-width: 360px; max-width: 360px;
                min-height: 110px; max-height: 110px;
            }
            #pingContainer {
                background-color: #25252d;
                border: 1px solid #353540;
                border-radius: 6px;
                min-width: 80px; max-width: 80px;
            }
            #pingLabel    { font-size: 8pt; }
            #qualityLabel { font-size: 8pt; min-height: 20px; border: 1px solid rgba(255,255,255,0.05); margin: 0px; padding: 2px 5px; }
            #statusLabel  { font-size: 8pt; padding: 5px; margin: 5px; border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; }
            QLabel { font-family: 'Segoe UI'; }
        """)


class GridWidget(QWidget):
    """Widget that draws a subtle grid background."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(QBrush(QColor(26, 26, 31)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        painter.setClipRect(rect)
        painter.setClipping(True)
        grid_pen = QPen(QColor(60, 60, 70, 40), 0.5, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, rect.width(), 20):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 15):
            painter.drawLine(0, y, rect.width(), y)
        painter.setClipping(False)
        border_pen = QPen(QColor(42, 42, 53), 1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 11, 11)
        painter.end()
