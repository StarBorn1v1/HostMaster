"""
sidebar.py — Hostmaster Sidebar

Premium inspector panel. Structured as discrete inner-section classes,
each self-styling via theme_manager tokens. Aesthetic: Linear / Vercel.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models import ServerNode, SystemStats
from theme import (
    ThemeMode,
    font_body,
    font_display,
    font_heading,
    font_label,
    font_micro,
    font_mono,
    font_ui,
    theme_manager,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SIDEBAR_WIDTH = 320
_MAX_INNER_WIDTH = _SIDEBAR_WIDTH - 24  # label overflow guard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _section_divider_label(text: str) -> QLabel:
    """10px micro uppercase section header label."""
    lbl = QLabel(text.upper())
    lbl.setFont(font_micro())
    lbl.setWordWrap(False)
    lbl.setMaximumWidth(_MAX_INNER_WIDTH)
    return lbl


def _value_label(text: str, mono: bool = True, wrap: bool = False) -> QLabel:
    """Monospace (or body) value label."""
    lbl = QLabel(text)
    lbl.setFont(font_mono() if mono else font_body())
    lbl.setWordWrap(wrap)
    if not wrap:
        lbl.setMaximumWidth(_MAX_INNER_WIDTH)
    return lbl


# ---------------------------------------------------------------------------
# Section 1 — _AppHeader
# ---------------------------------------------------------------------------


class _AppHeader(QFrame):
    """App name + theme toggle. 52px fixed height."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppHeader")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(8)

        self._logo = QLabel()
        from PySide6.QtGui import QPixmap
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "hostmaster_app_icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            self._logo.setPixmap(pix.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # Fallback path if run from inside the folder directly
            pix = QPixmap("assets/hostmaster_app_icon.png")
            self._logo.setPixmap(pix.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
        layout.addWidget(self._logo)

        self._title = QLabel("Host Master")
        self._title.setFont(font_heading())
        self._title.setWordWrap(False)
        layout.addWidget(self._title)

        layout.addStretch()

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex

        self.setStyleSheet(f"""
            QFrame#AppHeader {{
                background-color: transparent;
                border-bottom: 1px solid {th(t.border_hairline)};
            }}
        """)
        self._title.setStyleSheet(f"color: {th(t.text_max)};")


# ---------------------------------------------------------------------------
# Section 2 — _MetricsBar
# ---------------------------------------------------------------------------


class _MetricChip(QFrame):
    """A single metric chip: value on top, label below."""

    def __init__(self, value: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricChip")

        inner = QVBoxLayout(self)
        inner.setContentsMargins(8, 6, 8, 6)
        inner.setSpacing(2)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._val = QLabel(value)
        self._val.setFont(font_display())
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setWordWrap(False)

        self._key = QLabel(label.upper())
        self._key.setFont(font_micro())
        self._key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key.setWordWrap(False)

        inner.addWidget(self._val)
        inner.addWidget(self._key)

    def set_value(self, text: str) -> None:
        self._val.setText(text)

    def apply_style(self, t) -> None:
        th = t.hex
        self.setStyleSheet(f"""
            QFrame#MetricChip {{
                background-color: transparent;
                border: none;
            }}
        """)
        self._val.setStyleSheet(f"color: {th(t.text_primary)};")
        self._key.setStyleSheet(f"color: {th(t.text_muted)};")


class _MetricsBar(QFrame):
    """Three stat chips: PORTS, CPU, RAM. 76px fixed height."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricsBar")
        self.setFixedHeight(76)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._chip_ports = _MetricChip("0", "Ports")
        self._chip_cpu = _MetricChip("0%", "CPU")
        self._chip_ram = _MetricChip("0%", "RAM")

        for chip in (self._chip_ports, self._chip_cpu, self._chip_ram):
            layout.addWidget(chip)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    def update_metrics(self, stats: SystemStats) -> None:
        self._chip_ports.set_value(str(stats.active_ports_count))
        self._chip_cpu.set_value(f"{stats.cpu_percent:.0f}%")
        self._chip_ram.set_value(f"{stats.ram_percent:.0f}%")

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex
        self.setStyleSheet(f"""
            QFrame#MetricsBar {{
                background-color: transparent;
                border-bottom: 1px solid {th(t.border_hairline)};
            }}
        """)
        for chip in (self._chip_ports, self._chip_cpu, self._chip_ram):
            chip.apply_style(t)


# ---------------------------------------------------------------------------
# Section 3 — _SearchField
# ---------------------------------------------------------------------------


class _SearchField(QFrame):
    """Filter input. 52px fixed height. Emits text_changed(str)."""

    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchSection")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Filter by name or port\u2026")
        self._edit.setFont(font_body())
        self._edit.setFixedHeight(32)
        self._edit.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self._edit)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex
        self.setStyleSheet(f"""
            QFrame#SearchSection {{
                background-color: transparent;
                border-bottom: 1px solid {th(t.border_hairline)};
            }}
            QLineEdit {{
                background-color: {th(t.bg_control)};
                color: {th(t.text_primary)};
                border: 1px solid {th(t.border_hairline)};
                border-radius: 4px;
                padding: 0px 10px;
                outline: none;
            }}
            QLineEdit:focus {{
                border: 1px solid {th(t.border_focus)};
            }}
        """)


# ---------------------------------------------------------------------------
# Section 4 — _InspectorPanel
# ---------------------------------------------------------------------------


class _EmptyState(QWidget):
    """State 0: graceful empty placeholder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl = QLabel("Select a node\nto inspect")
        self._lbl.setFont(font_label())
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl)

    def apply_style(self, t) -> None:
        self._lbl.setStyleSheet(f"color: {t.hex(t.text_muted)};")


class _ServerState(QWidget):
    """State 1: ServerNode inspector."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Process name heading
        self._lbl_name = QLabel("")
        self._lbl_name.setFont(font_heading())
        self._lbl_name.setWordWrap(False)
        self._lbl_name.setMaximumWidth(_MAX_INNER_WIDTH)
        layout.addWidget(self._lbl_name)
        layout.addSpacing(12)

        # PORT
        self._sec_port = _section_divider_label("Port")
        self._val_port = _value_label("")
        layout.addWidget(self._sec_port)
        layout.addSpacing(2)
        layout.addWidget(self._val_port)
        layout.addSpacing(10)

        # IP
        self._sec_ip = _section_divider_label("IP")
        self._val_ip = _value_label("")
        layout.addWidget(self._sec_ip)
        layout.addSpacing(2)
        layout.addWidget(self._val_ip)
        layout.addSpacing(10)

        # PID
        self._sec_pid = _section_divider_label("PID")
        self._val_pid = _value_label("")
        layout.addWidget(self._sec_pid)
        layout.addSpacing(2)
        layout.addWidget(self._val_pid)
        layout.addSpacing(10)

        # COMMAND
        self._sec_cmd = _section_divider_label("Command")
        self._val_cmd = _value_label("", mono=True, wrap=True)
        layout.addWidget(self._sec_cmd)
        layout.addSpacing(2)
        layout.addWidget(self._val_cmd)

        # Copy Button
        layout.addSpacing(16)
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setFont(font_ui())
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(self._copy_btn)

        layout.addStretch()

    def _copy_to_clipboard(self) -> None:
        from PySide6.QtGui import QClipboard
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        info = (
            f"Process: {self._lbl_name.text()}\n"
            f"Port: {self._val_port.text()}\n"
            f"IP: {self._val_ip.text()}\n"
            f"PID: {self._val_pid.text()}\n"
            f"Command: {self._val_cmd.text()}"
        )
        QApplication.clipboard().setText(info)
        
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy to Clipboard"))

    def populate(self, node: ServerNode) -> None:
        self._lbl_name.setText(node.clean_name or node.process_name)
        self._val_port.setText(f":{node.port}")
        self._val_ip.setText(node.ip)
        self._val_pid.setText(str(node.pid))
        cmd = node.cmdline if node.cmdline else node.process_name
        self._val_cmd.setText(cmd[:120])

    def apply_style(self, t) -> None:
        th = t.hex
        self._lbl_name.setStyleSheet(f"color: {th(t.text_max)};")
        for sec in (self._sec_port, self._sec_ip, self._sec_pid, self._sec_cmd):
            sec.setStyleSheet(f"color: {th(t.text_muted)};")
        self._val_port.setStyleSheet(f"color: {th(t.text_primary)};")
        self._val_ip.setStyleSheet(f"color: {th(t.text_secondary)};")
        self._val_pid.setStyleSheet(f"color: {th(t.text_secondary)};")
        self._val_cmd.setStyleSheet(f"color: {th(t.text_muted)};")
        self._copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {th(t.bg_control)};
                color: {th(t.text_secondary)};
                border: 1px solid {th(t.border_default)};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {th(t.bg_overlay)};
                color: {th(t.text_primary)};
                border: 1px solid {th(t.border_focus)};
            }}
        """)


class _HubState(QWidget):
    """State 2: Hub / This Machine inspector."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Hostname heading
        self._lbl_host = QLabel("")
        self._lbl_host.setFont(font_heading())
        self._lbl_host.setWordWrap(False)
        self._lbl_host.setMaximumWidth(_MAX_INNER_WIDTH)
        layout.addWidget(self._lbl_host)
        layout.addSpacing(12)

        # CPU
        self._sec_cpu = _section_divider_label("CPU")
        self._val_cpu = _value_label("")
        layout.addWidget(self._sec_cpu)
        layout.addSpacing(2)
        layout.addWidget(self._val_cpu)
        layout.addSpacing(10)

        # MEMORY
        self._sec_mem = _section_divider_label("Memory")
        self._val_mem = _value_label("")
        self._val_mem_pct = _value_label("")
        layout.addWidget(self._sec_mem)
        layout.addSpacing(2)
        layout.addWidget(self._val_mem)
        layout.addSpacing(1)
        layout.addWidget(self._val_mem_pct)
        layout.addSpacing(10)

        # DISK I/O
        self._sec_disk = _section_divider_label("Disk I/O")
        self._val_disk = _value_label("")
        layout.addWidget(self._sec_disk)
        layout.addSpacing(2)
        layout.addWidget(self._val_disk)
        layout.addSpacing(10)

        # PORTS
        self._sec_ports = _section_divider_label("Ports")
        self._val_ports = _value_label("", mono=False)
        layout.addWidget(self._sec_ports)
        layout.addSpacing(2)
        layout.addWidget(self._val_ports)

        layout.addStretch()

    def populate(self, stats: SystemStats) -> None:
        self._lbl_host.setText(stats.hostname)
        self._val_cpu.setText(f"{stats.cpu_percent:.0f}%  ({stats.cpu_cores} cores)")
        self._val_mem.setText(f"{stats.ram_used_gb:.1f} / {stats.ram_total_gb:.1f} GB")
        self._val_mem_pct.setText(f"{stats.ram_percent:.0f}% used")
        self._val_disk.setText(
            f"R: {stats.disk_read_mb:.1f} MB  W: {stats.disk_write_mb:.1f} MB"
        )
        self._val_ports.setText(f"{stats.active_ports_count} active listeners")

    def apply_style(self, t) -> None:
        th = t.hex
        self._lbl_host.setStyleSheet(f"color: {th(t.text_max)};")
        for sec in (self._sec_cpu, self._sec_mem, self._sec_disk, self._sec_ports):
            sec.setStyleSheet(f"color: {th(t.text_muted)};")
        for val in (self._val_cpu, self._val_mem):
            val.setStyleSheet(f"color: {th(t.text_primary)};")
        for val in (self._val_mem_pct, self._val_disk):
            val.setStyleSheet(f"color: {th(t.text_secondary)};")
        self._val_ports.setStyleSheet(f"color: {th(t.text_secondary)};")


class _InspectorPanel(QFrame):
    """
    Contextual inspector. Three states via QStackedWidget:
      0 — empty (no selection)
      1 — ServerNode selected
      2 — Hub (This Machine) selected
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self._empty = _EmptyState()
        self._server = _ServerState()
        self._hub = _HubState()

        self.stack.addWidget(self._empty)   # index 0
        self.stack.addWidget(self._server)  # index 1
        self.stack.addWidget(self._hub)     # index 2

        self.stack.setCurrentIndex(0)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    # ------------------------------------------------------------------
    # Public state API
    # ------------------------------------------------------------------

    def set_node(self, node: ServerNode | None) -> None:
        if node is None:
            self.stack.setCurrentIndex(0)
            return
        self._server.populate(node)
        self._apply_style()
        self.stack.setCurrentIndex(1)

    def set_system_stats(self, stats: SystemStats | None) -> None:
        if stats is None:
            self.stack.setCurrentIndex(0)
            return
        self._hub.populate(stats)
        self._apply_style()
        self.stack.setCurrentIndex(2)

    def clear(self) -> None:
        self.stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex
        self.setStyleSheet(f"""
            QFrame#InspectorPanel {{
                background-color: transparent;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QWidget {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {th(t.border_default)};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._empty.apply_style(t)
        self._server.apply_style(t)
        self._hub.apply_style(t)


# ---------------------------------------------------------------------------
# Section 5 — _ActionBar
# ---------------------------------------------------------------------------


class _ActionBar(QFrame):
    """Kill button + secondary action buttons."""

    kill_clicked = Signal()
    refresh_clicked = Signal()
    recenter_clicked = Signal()
    toggle_view_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActionBar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # --- Kill button (primary destructive) ---
        self.kill_btn = QPushButton("Terminate Process")
        self.kill_btn.setFixedHeight(44)
        self.kill_btn.setFont(font_ui())
        self.kill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.kill_btn.setEnabled(False)
        self.kill_btn.clicked.connect(self.kill_clicked)
        layout.addWidget(self.kill_btn)

        # --- Secondary row: Refresh + Recenter ---
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedHeight(40)
        self.refresh_btn.setFont(font_ui())
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)

        self.recenter_btn = QPushButton("Recenter")
        self.recenter_btn.setFixedHeight(40)
        self.recenter_btn.setFont(font_ui())
        self.recenter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recenter_btn.clicked.connect(self.recenter_clicked)

        row1.addWidget(self.refresh_btn)
        row1.addWidget(self.recenter_btn)
        layout.addLayout(row1)

        # --- Third row: View Mode + Theme ---
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)

        self.view_btn = QPushButton("Switch to Grid")
        self.view_btn.setFixedHeight(40)
        self.view_btn.setFont(font_ui())
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.clicked.connect(self.toggle_view_clicked)

        self.theme_btn = QPushButton()
        self.theme_btn.setFixedHeight(40)
        self.theme_btn.setFont(font_ui())
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(theme_manager.toggle_mode)

        row2.addWidget(self.view_btn)
        row2.addWidget(self.theme_btn)
        layout.addLayout(row2)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    def _on_refresh_clicked(self) -> None:
        self.refresh_btn.setText("Refreshing...")
        self.refresh_btn.setEnabled(False)
        self.refresh_clicked.emit()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(600, lambda: [self.refresh_btn.setText("Refresh"), self.refresh_btn.setEnabled(True)])

    def set_view_label(self, is_lattice: bool) -> None:
        self.view_btn.setText("Switch to Grid" if is_lattice else "Switch to Lattice")

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex

        is_dark = theme_manager.mode == ThemeMode.DARK
        self.theme_btn.setText("Light" if is_dark else "Dark")

        self.setStyleSheet(f"""
            QFrame#ActionBar {{
                background-color: transparent;
                border-top: 1px solid {th(t.border_hairline)};
            }}
        """)

        self.kill_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {th(t.destructive)};
                border: 1px solid {th(t.destructive)};
                border-radius: 4px;
            }}
            QPushButton:hover:enabled {{
                background-color: {th(t.destructive_dim)};
                color: {th(t.destructive_text)};
                border: 1px solid {th(t.destructive)};
            }}
            QPushButton:disabled {{
                background-color: {th(t.bg_control)};
                color: {th(t.text_muted)};
                border: 1px solid {th(t.border_hairline)};
            }}
        """)

        sec = f"""
            QPushButton {{
                background-color: transparent;
                color: {th(t.text_secondary)};
                border: 1px solid {th(t.border_default)};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {th(t.bg_control)};
                color: {th(t.text_primary)};
            }}
        """
        for btn in (self.refresh_btn, self.recenter_btn, self.view_btn, self.theme_btn):
            btn.setStyleSheet(sec)


# ---------------------------------------------------------------------------
# Section 6 — _Footer
# ---------------------------------------------------------------------------


class _Footer(QFrame):
    """Status line. 36px fixed height."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Footer")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._lbl = QLabel("Refreshing every 2.5s")
        self._lbl.setFont(font_micro())
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setWordWrap(False)
        layout.addWidget(self._lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex
        self.setStyleSheet(f"""
            QFrame#Footer {{
                background-color: transparent;
                border-top: 1px solid {th(t.border_hairline)};
            }}
        """)
        self._lbl.setStyleSheet(f"color: {th(t.text_muted)};")


# ---------------------------------------------------------------------------
# Sidebar — root widget
# ---------------------------------------------------------------------------


class Sidebar(QWidget):
    """
    Premium inspector sidebar. 280px fixed width.

    Signals
    -------
    kill_requested        — user pressed Terminate Process
    refresh_requested     — user pressed Refresh
    center_view_requested — user pressed Recenter
    toggle_view_requested — user toggled grid / lattice view
    filter_changed(str)   — search field text changed
    """

    kill_requested = Signal()
    refresh_requested = Signal()
    center_view_requested = Signal()
    toggle_view_requested = Signal()
    filter_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(_SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Header
        self._header = _AppHeader()
        layout.addWidget(self._header)

        # 2. Metrics bar
        self._metrics = _MetricsBar()
        layout.addWidget(self._metrics)

        # 3. Search
        self._search = _SearchField()
        self._search.text_changed.connect(self.filter_changed.emit)
        layout.addWidget(self._search)

        # 4. Inspector panel — expands
        self._inspector = _InspectorPanel()
        layout.addWidget(self._inspector, stretch=1)

        # 5. Action bar
        self._actions = _ActionBar()
        self._actions.kill_clicked.connect(self.kill_requested.emit)
        self._actions.refresh_clicked.connect(self.refresh_requested.emit)
        self._actions.recenter_clicked.connect(self.center_view_requested.emit)
        self._actions.toggle_view_clicked.connect(self.toggle_view_requested.emit)
        layout.addWidget(self._actions)

        # 6. Footer
        self._footer = _Footer()
        layout.addWidget(self._footer)

        self._apply_style()
        theme_manager.theme_changed.connect(self._apply_style)

    # ------------------------------------------------------------------
    # Outer style
    # ------------------------------------------------------------------

    def _apply_style(self, _mode: ThemeMode | None = None) -> None:
        t = theme_manager.tokens
        th = t.hex
        self.setStyleSheet(f"""
            QWidget#Sidebar {{
                background-color: {th(t.bg_raised)};
                border-right: 1px solid {th(t.border_hairline)};
            }}
        """)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_system_stats(self, stats: SystemStats) -> None:
        """Push live metrics into the metrics bar."""
        self._metrics.update_metrics(stats)

    def update_selected_node(self, node: ServerNode | None) -> None:
        """Show ServerNode details in the inspector."""
        self._inspector.set_node(node)
        self._actions.kill_btn.setEnabled(node is not None)

    def update_selected_hub(self, stats: SystemStats | None) -> None:
        """Show hub/machine details in the inspector."""
        self._inspector.set_system_stats(stats)
        self._actions.kill_btn.setEnabled(False)

    def clear_selection(self) -> None:
        """Reset inspector to empty state."""
        self._inspector.clear()
        self._actions.kill_btn.setEnabled(False)
