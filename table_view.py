"""
table_view.py — Hostmaster alternative table view

A premium, intentional table listing all listening processes.
Designed to the same visual standard as the lattice view — not an afterthought.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import ServerNode
from theme import (
    ThemeMode,
    font_body,
    font_label,
    font_micro,
    font_mono,
    theme_manager,
)

# Column index constants
_COL_PROCESS = 0
_COL_PORT = 1
_COL_IP = 2
_COL_PID = 3
_COL_COMMAND = 4
_COL_COUNT = 5

_HEADERS = ["PROCESS", "PORT", "IP ADDRESS", "PID", "COMMAND"]

# Maximum characters shown in the COMMAND column
_CMD_MAX_CHARS = 80


class AlternativeTableView(QWidget):
    """
    Clean, themed table listing every listening process.

    Signals
    -------
    node_selected(ServerNode)
        Emitted when the user selects a row with a valid attached ServerNode.
    selection_cleared()
        Emitted when the selection becomes empty.
    """

    node_selected = Signal(object)   # emits ServerNode
    selection_cleared = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Table setup ----------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(_COL_COUNT)
        self.table.setHorizontalHeaderLabels(_HEADERS)

        # Row sizing
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)

        # Column sizing
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(_COL_PROCESS, QHeaderView.Stretch)
        h.setSectionResizeMode(_COL_PORT, QHeaderView.Fixed)
        h.setSectionResizeMode(_COL_IP, QHeaderView.Fixed)
        h.setSectionResizeMode(_COL_PID, QHeaderView.Fixed)
        h.setSectionResizeMode(_COL_COMMAND, QHeaderView.Stretch)
        self.table.setColumnWidth(_COL_PORT, 70)
        self.table.setColumnWidth(_COL_IP, 120)
        self.table.setColumnWidth(_COL_PID, 60)

        # Header text alignment — all left/vcenter
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setHighlightSections(False)

        # Behaviour
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        # Scroll — minimal/hidden chrome
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Connections
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.table)

        # Apply initial styling, then track theme changes
        self.update_style()
        theme_manager.theme_changed.connect(self.update_style)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_table(self, nodes: list[ServerNode]) -> None:
        """
        Replace the table contents with the given list of ServerNode objects.

        Preserves existing selection by port/pid key where possible.
        """
        # Block selection signals while repopulating to avoid spurious emissions
        self.table.blockSignals(True)
        self.table.setRowCount(len(nodes))

        for row, node in enumerate(nodes):
            # PROCESS — clean_name, stores full node for retrieval
            item_process = QTableWidgetItem(node.clean_name)
            item_process.setData(Qt.UserRole, node)
            item_process.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_process.setFont(font_body())

            # PORT — right-aligned mono
            item_port = QTableWidgetItem(str(node.port))
            item_port.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_port.setFont(font_mono())

            # IP ADDRESS
            item_ip = QTableWidgetItem(node.ip)
            item_ip.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_ip.setFont(font_mono())

            # PID — right-aligned mono
            item_pid = QTableWidgetItem(str(node.pid))
            item_pid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pid.setFont(font_mono())

            # COMMAND — truncated cmdline, fallback to process_name
            cmd_text = (node.cmdline[:_CMD_MAX_CHARS] if node.cmdline
                        else node.process_name)
            item_command = QTableWidgetItem(cmd_text)
            item_command.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_command.setFont(font_label())

            self.table.setItem(row, _COL_PROCESS, item_process)
            self.table.setItem(row, _COL_PORT, item_port)
            self.table.setItem(row, _COL_IP, item_ip)
            self.table.setItem(row, _COL_PID, item_pid)
            self.table.setItem(row, _COL_COMMAND, item_command)

        self.table.blockSignals(False)
        
        # Re-apply fading based on current selection
        selected = self.table.selectedItems()
        self._apply_row_fading(selected[0].row() if selected else -1)

    # ------------------------------------------------------------------
    # Selection UX (Fading)
    # ------------------------------------------------------------------

    def _apply_row_fading(self, selected_row: int) -> None:
        """Fade out unselected rows to highlight the active selection."""
        t = theme_manager.tokens
        from PySide6.QtGui import QBrush, QColor
        
        has_selection = selected_row >= 0
        primary_brush = QBrush(t.text_primary)
        
        # High-end fade effect: drop opacity significantly
        dim_color = QColor(t.text_primary)
        dim_color.setAlphaF(0.20)
        dim_brush = QBrush(dim_color)

        for row in range(self.table.rowCount()):
            brush = dim_brush if (has_selection and row != selected_row) else primary_brush
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setForeground(brush)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def on_selection_changed(self) -> None:
        """Emit node_selected or selection_cleared based on current row."""
        selected = self.table.selectedItems()
        if not selected:
            self._apply_row_fading(-1)
            self.selection_cleared.emit()
            return

        row = selected[0].row()
        self._apply_row_fading(row)
        
        item = self.table.item(row, _COL_PROCESS)
        if item is None:
            self.selection_cleared.emit()
            return

        node = item.data(Qt.UserRole)
        if isinstance(node, ServerNode):
            self.node_selected.emit(node)
        else:
            self.selection_cleared.emit()

    def update_style(self, mode: Optional[ThemeMode] = None) -> None:
        """
        Re-apply the full stylesheet from current theme tokens.

        Called at init and whenever theme_manager emits theme_changed.
        The `mode` argument is accepted but ignored — tokens are always
        fetched live from theme_manager.tokens.
        """
        t = theme_manager.tokens
        H = t.hex  # static method: ColorTokens.hex(color) -> "#RRGGBB"

        bg_base       = H(t.bg_base)
        bg_raised     = H(t.bg_raised)
        text_primary  = H(t.text_primary)
        text_muted    = H(t.text_muted)
        border_hl     = H(t.border_hairline)
        border_def    = H(t.border_default)
        accent_dim    = H(t.accent_dim)

        # font_micro size for header (10px)
        hdr_font = font_micro()
        hdr_px   = hdr_font.pixelSize()

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_base};
                alternate-background-color: {bg_raised};
                color: {text_primary};
                border: none;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {bg_raised};
                color: {text_muted};
                font-size: {hdr_px}px;
                font-weight: 500;
                padding: 0px 12px;
                border: none;
                border-bottom: 1px solid {border_hl};
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QTableWidget::item {{
                padding: 0px 12px;
                border-bottom: 1px solid {border_hl};
            }}
            QTableWidget::item:selected {{
                background-color: {accent_dim};
                color: {text_primary};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {border_def};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Re-apply row fading to update hardcoded QBrush foregrounds to the new theme colors
        selected = self.table.selectedItems()
        self._apply_row_fading(selected[0].row() if selected else -1)
