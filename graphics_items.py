"""
graphics_items.py — Hostmaster visual elements.

Three QGraphicsItem subclasses:
  · MachineHubItem   — Central "this machine" node (132×68, radius 8)
  · LatticeEdgeItem  — Animated edge connecting hub to a server node
  · ServerNodeItem   — Per-process/port card (120×60, radius 6)

Designed for the Hostmaster Design System: clinical, legible, no decoration.
"""

from __future__ import annotations

import math
import socket
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QStyleOptionGraphicsItem,
    QWidget,
)

from models import (
    ServerNode,
    SystemStats,
    clean_process_name,
    process_icon_initial,
    port_accent_index,
)
from theme import (
    theme_manager,
    ThemeMode,
    font_body,
    font_heading,
    font_label,
    font_mono,
)

# ---------------------------------------------------------------------------
# Accent palette — 6 hues for pulse / avatar differentiation
# ---------------------------------------------------------------------------

# Pulse colors (70% opacity, used for traveling dots on edges)
_PULSE_ACCENTS: list[tuple[int, int, int]] = [
    (96, 165, 250),   # 0 — blue
    (167, 139, 250),  # 1 — violet
    (52, 211, 153),   # 2 — emerald
    (251, 191, 36),   # 3 — amber
    (251, 113, 133),  # 4 — rose
    (94, 234, 212),   # 5 — teal
]

# Avatar badge backgrounds (dark variants, 180 alpha)
_AVATAR_BG_DARK: list[tuple[int, int, int, int]] = [
    (29, 52, 97, 180),    # 0 — dark blue
    (46, 33, 92, 180),    # 1 — dark violet
    (6, 55, 38, 180),     # 2 — dark emerald
    (66, 45, 0, 180),     # 3 — dark amber
    (74, 13, 32, 180),    # 4 — dark rose
    (4, 55, 51, 180),     # 5 — dark teal
]


def _avatar_bg(accent_idx: int) -> QColor:
    """Return avatar badge background color appropriate for current theme."""
    r, g, b, a = _AVATAR_BG_DARK[accent_idx % 6]
    if theme_manager.mode == ThemeMode.LIGHT:
        r = min(255, r + 50)
        g = min(255, g + 50)
        b = min(255, b + 50)
    return QColor(r, g, b, a)


def _pulse_color(accent_idx: int) -> QColor:
    """Return pulse dot color at 70% opacity."""
    r, g, b = _PULSE_ACCENTS[accent_idx % 6]
    return QColor(r, g, b, int(255 * 0.70))


def _smoothstep(x: float) -> float:
    """Smoothstep: t = x²(3-2x). Clamps x to [0, 1]."""
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


# ---------------------------------------------------------------------------
# MachineHubItem
# ---------------------------------------------------------------------------

class MachineHubItem(QGraphicsObject):
    """
    Central hub node representing the local machine.

    Geometry: 132 × 68 px, corner radius 8 px.
    Origin is at the item's visual center.
    """

    W: int = 132
    H: int = 68
    RADIUS: int = 8

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)

        self.is_hovered: bool = False
        self.is_selected: bool = False
        self.hostname: str = socket.gethostname() or "Local Machine"
        self.stats: Optional[SystemStats] = None

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(10)
        self._rebuild_tooltip()

        # Premium soft shadow
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(QColor(15, 23, 42, 15))
        shadow.setBlurRadius(15)
        shadow.setYOffset(3)
        shadow.setXOffset(0)
        self.setGraphicsEffect(shadow)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_stats(self, stats: SystemStats) -> None:
        """Update system statistics and repaint."""
        self.stats = stats
        self.hostname = stats.hostname
        self._rebuild_tooltip()
        self.update()

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rebuild_tooltip(self) -> None:
        lines = [
            f"Machine: {self.hostname}",
            "IP: 127.0.0.1 (localhost)",
        ]
        if self.stats:
            lines.append(
                f"CPU: {self.stats.cpu_percent:.1f}%  ({self.stats.cpu_cores} cores)"
            )
            lines.append(
                f"RAM: {self.stats.ram_used_gb:.1f} / {self.stats.ram_total_gb:.1f} GB"
                f"  ({self.stats.ram_percent:.1f}%)"
            )
        self.setToolTip("\n".join(lines))

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        # 6 px margin covers glow rect (3 px) + pen overshoot
        margin = 6
        return QRectF(
            -self.W / 2 - margin,
            -self.H / 2 - margin,
            self.W + margin * 2,
            self.H + margin * 2,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        t = theme_manager.tokens

        rect = QRectF(-self.W / 2, -self.H / 2, self.W, self.H)

        # --- Outer glow / halo (hover or selected) ----------------------
        if self.is_selected or self.is_hovered:
            glow_rect = rect.adjusted(-2, -2, 2, 2)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, self.RADIUS + 2, self.RADIUS + 2)
            if self.is_selected:
                glow_c = QColor(t.accent_dim)
                glow_c.setAlphaF(0.40)
            else:
                glow_c = QColor(t.node_halo)
                glow_c.setAlphaF(0.25)
            painter.fillPath(glow_path, glow_c)

        # --- Card body --------------------------------------------------
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.fillPath(card_path, QBrush(QColor(t.bg_node)))

        # --- Border -----------------------------------------------------
        if self.is_selected:
            pen = QPen(QColor(t.accent_solid), 1.25)
        elif self.is_hovered:
            pen = QPen(QColor(t.border_focus), 1.25)
        else:
            # Soft borderline with drop shadow
            pen = QPen(QColor(t.border_default), 1.0)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(card_path)

        # --- Status dot (positive / green) — 5 px diameter --------------
        # Left of hostname row, vertically centered in upper text area
        dot_x = -self.W / 2 + 14.0
        dot_y = -self.H / 2 + 18.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(t.positive)))
        painter.drawEllipse(QPointF(dot_x, dot_y), 2.5, 2.5)

        # --- Hostname ---------------------------------------------------
        # Text area starts after dot (24 px from left edge), 12 px right margin
        text_x = -self.W / 2 + 24.0
        text_w = self.W - 24.0 - 12.0

        if text_w > 0 and self.hostname:
            hostname_font = font_heading()
            painter.setFont(hostname_font)
            painter.setPen(QPen(QColor(t.text_max)))

            hostname_rect = QRectF(text_x, -self.H / 2 + 8.0, text_w, 22.0)
            fm = painter.fontMetrics()
            elided = fm.elidedText(self.hostname, Qt.ElideRight, int(hostname_rect.width()))
            painter.drawText(hostname_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

        # --- Subtitle: "Local Machine" ----------------------------------
        if text_w > 0:
            sub_font = font_label()
            painter.setFont(sub_font)
            painter.setPen(QPen(QColor(t.text_secondary)))

            sub_rect = QRectF(text_x, -self.H / 2 + 30.0, text_w, 18.0)
            painter.drawText(sub_rect, Qt.AlignLeft | Qt.AlignVCenter, "Local Machine")

        # --- Stats line (CPU · RAM) — only when stats are available -----
        if self.stats is not None:
            stats_font = font_mono()
            painter.setFont(stats_font)
            painter.setPen(QPen(QColor(t.text_muted)))

            cpu_str = f"CPU {self.stats.cpu_percent:.0f}%"
            ram_str = f"RAM {self.stats.ram_percent:.0f}%"
            stats_text = f"{cpu_str}  ·  {ram_str}"

            stats_rect = QRectF(
                -self.W / 2 + 12.0,
                -self.H / 2 + 48.0,
                self.W - 24.0,
                14.0,
            )
            if stats_rect.width() > 0:
                painter.drawText(stats_rect, Qt.AlignLeft | Qt.AlignVCenter, stats_text)

    # ------------------------------------------------------------------
    # Hover events
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)


# ---------------------------------------------------------------------------
# LatticeEdgeItem
# ---------------------------------------------------------------------------

class LatticeEdgeItem(QGraphicsItem):
    """
    Straight line from hub center to node center with traveling pulse dots.

    · Single pulse if edge length ≤ 80 px, two pulses (offset 0.5) otherwise.
    · Fade uses smoothstep over the first / last 12 % of travel.
    · Pulse color chosen by port_accent_index for the connected node's port.
    """

    def __init__(
        self,
        hub_item: MachineHubItem,
        node_item: "ServerNodeItem",
    ) -> None:
        super().__init__()
        self.hub_item = hub_item
        self.node_item = node_item
        self.phase: float = 0.0
        self.setZValue(1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_phase(self, phase: float) -> None:
        """Advance the pulse position. phase ∈ [0, 1)."""
        self.prepareGeometryChange()
        self.phase = phase % 1.0
        self.update()

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        start = self.hub_item.pos()
        end = self.node_item.pos()
        rect = QRectF(start, end).normalized()
        margin = 32
        return rect.adjusted(-margin, -margin, margin, margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        t = theme_manager.tokens

        start = self.hub_item.pos()
        end = self.node_item.pos()

        # --- Edge line --------------------------------------------------
        if self.node_item.is_selected:
            line_c = QColor(t.accent_solid)
            line_c.setAlphaF(0.30)
        else:
            line_c = QColor(t.border_hairline)
            line_c.setAlphaF(0.55)

        painter.setPen(QPen(line_c, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(start, end)

        # --- Traveling pulse(s) ----------------------------------------
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        distance = math.hypot(dx, dy)

        if distance < 1.0:
            return

        accent_idx = port_accent_index(self.node_item.node.port)
        base_pulse = _pulse_color(accent_idx)

        # Two pulses only when edge is long enough
        offsets: list[float] = [0.0] if distance <= 80.0 else [0.0, 0.5]
        fade_zone = 0.12   # fraction of travel used for fade in/out
        dot_r = 2.5        # radius → 5 px diameter

        painter.setBrush(Qt.NoBrush)
        from PySide6.QtGui import QLinearGradient

        beam_len = 28.0
        
        for offset in offsets:
            progress = (self.phase + offset) % 1.0

            # Smoothstep fade envelope
            if progress < fade_zone:
                alpha_factor = _smoothstep(progress / fade_zone)
            elif progress > (1.0 - fade_zone):
                alpha_factor = _smoothstep((1.0 - progress) / fade_zone)
            else:
                alpha_factor = 1.0

            px = start.x() + dx * progress
            py = start.y() + dy * progress
            
            dir_x = dx / distance
            dir_y = dy / distance
            
            tail_x = px - dir_x * beam_len
            tail_y = py - dir_y * beam_len

            head_c = QColor(base_pulse)
            head_c.setAlphaF(head_c.alphaF() * alpha_factor)

            tail_c = QColor(base_pulse)
            tail_c.setAlphaF(0.0)

            # Draw the data stream beam
            grad = QLinearGradient(QPointF(px, py), QPointF(tail_x, tail_y))
            grad.setColorAt(0.0, head_c)
            grad.setColorAt(1.0, tail_c)

            pen = QPen(QBrush(grad), 2.5)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(px, py), QPointF(tail_x, tail_y))

            # Draw the bright twinkling core at the head
            core_c = QColor(base_pulse.red(), base_pulse.green(), base_pulse.blue(), int(255 * alpha_factor))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(core_c))
            painter.drawEllipse(QPointF(px, py), 1.5, 1.5)


# ---------------------------------------------------------------------------
# ServerNodeItem
# ---------------------------------------------------------------------------

class ServerNodeItem(QGraphicsObject):
    """
    Per-process / per-port card node.

    Geometry: 120 × 60 px, corner radius 6 px.
    Origin at the item's visual center.
    """

    W: int = 120
    H: int = 60
    RADIUS: int = 6

    def __init__(self, node: ServerNode, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)

        self.node: ServerNode = node
        self.is_selected: bool = False
        self.is_hovered: bool = False
        self.breath_phase: float = 0.0

        self.clean_name: str = node.clean_name
        self._target_pos: QPointF = QPointF(0.0, 0.0)
        self._accent_idx: int = port_accent_index(node.port)

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(5)
        self._rebuild_tooltip()

        # Premium soft shadow
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(QColor(15, 23, 42, 15))
        shadow.setBlurRadius(15)
        shadow.setYOffset(3)
        shadow.setXOffset(0)
        self.setGraphicsEffect(shadow)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_target_pos(self, pos: QPointF) -> None:
        """Set the destination position for lerp animation."""
        self._target_pos = pos

    def step_animation(self, factor: float = 0.16) -> bool:
        """
        Lerp current position toward _target_pos.
        Advances breath_phase by 0.035 per tick.
        Returns True while still moving.
        """
        self.breath_phase = (self.breath_phase + 0.035) % (2.0 * math.pi)

        curr = self.pos()
        diff = self._target_pos - curr
        moving = diff.manhattanLength() > 0.5
        if moving:
            self.setPos(curr + diff * factor)
        else:
            self.setPos(self._target_pos)
        self.update()
        return moving

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()

    def update_node(self, node: ServerNode) -> None:
        """Replace underlying node data and repaint."""
        self.node = node
        self.clean_name = node.clean_name
        self._accent_idx = port_accent_index(node.port)
        self._rebuild_tooltip()
        self.update()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rebuild_tooltip(self) -> None:
        lines = [
            f"Process: {self.clean_name}",
            f"Port: {self.node.port}",
            f"PID: {self.node.pid}  ·  IP: {self.node.ip}",
        ]
        if self.node.cmdline:
            lines.append(self.node.cmdline[:100])
        self.setToolTip("\n".join(lines))

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        # 10 px margin: covers glow rect (5 px) + pen width + dot radius
        margin = 10
        return QRectF(
            -self.W / 2 - margin,
            -self.H / 2 - margin,
            self.W + margin * 2,
            self.H + margin * 2,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        t = theme_manager.tokens

        rect = QRectF(-self.W / 2, -self.H / 2, self.W, self.H)

        # ----------------------------------------------------------------
        # Breathing ambient glow — only when idle (not selected, not hovered)
        # ----------------------------------------------------------------
        if not self.is_selected and not self.is_hovered:
            glow_alpha = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self.breath_phase))
            glow_alpha = max(0.0, min(1.0, glow_alpha))

            glow_rect = rect.adjusted(-4, -4, 4, 4)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, self.RADIUS + 4, self.RADIUS + 4)
            glow_c = QColor(t.node_halo)
            base_alpha = glow_c.alphaF()
            glow_c.setAlphaF(base_alpha * glow_alpha)
            painter.fillPath(glow_path, glow_c)

        # ----------------------------------------------------------------
        # Selected ambient glow
        # ----------------------------------------------------------------
        if self.is_selected:
            sel_glow_rect = rect.adjusted(-2, -2, 2, 2)
            sel_glow_path = QPainterPath()
            sel_glow_path.addRoundedRect(sel_glow_rect, self.RADIUS + 2, self.RADIUS + 2)
            sel_glow_c = QColor(t.node_halo)
            sel_glow_c.setAlphaF(0.40)
            painter.fillPath(sel_glow_path, sel_glow_c)

        # ----------------------------------------------------------------
        # Card body fill
        # ----------------------------------------------------------------
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        if self.is_selected or self.is_hovered:
            fill_c = QColor(t.bg_overlay)
        else:
            fill_c = QColor(t.bg_node)
        painter.fillPath(card_path, QBrush(fill_c))

        # ----------------------------------------------------------------
        # Card border
        # ----------------------------------------------------------------
        if self.is_selected:
            pen = QPen(QColor(t.accent_solid), 1.25)
        elif self.is_hovered:
            pen = QPen(QColor(t.border_focus), 1.25)
        else:
            # When using drop shadows on a premium surface, borderline can be softer
            pen = QPen(QColor(t.border_default), 1.0)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(card_path)

        # ----------------------------------------------------------------
        # Process name text & color-coded status dot
        # ----------------------------------------------------------------
        text_x = -self.W / 2 + 26.0        # moved left
        text_right_edge = self.W / 2 - 10.0
        text_w = text_right_edge - text_x

        if text_w > 0 and self.clean_name:
            name_font = font_body()
            painter.setFont(name_font)
            painter.setPen(QPen(QColor(t.text_primary)))

            # Upper half of card
            name_rect = QRectF(text_x, -self.H / 2 + 8.0, text_w, self.H / 2 - 8.0)
            fm = painter.fontMetrics()
            elided = fm.elidedText(self.clean_name, Qt.ElideRight, int(name_rect.width()))
            painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

            # Tiny color-coded status dot next to the text
            dot_cx = text_x - 10.0
            dot_cy = name_rect.center().y()
            
            accent_c = _pulse_color(self._accent_idx)
            solid_accent = QColor(accent_c.red(), accent_c.green(), accent_c.blue())
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(solid_accent))
            painter.drawEllipse(QPointF(dot_cx, dot_cy), 1.5, 1.5)

        # ----------------------------------------------------------------
        # Port number text
        # ----------------------------------------------------------------
        if text_w > 0:
            port_font = font_mono()
            painter.setFont(port_font)
            painter.setPen(QPen(QColor(t.text_secondary)))

            port_text = f":{self.node.port}"
            # Lower half of card
            port_rect = QRectF(text_x, 0.0, text_w, self.H / 2 - 8.0)
            painter.drawText(port_rect, Qt.AlignLeft | Qt.AlignVCenter, port_text)

    # ------------------------------------------------------------------
    # Hover events
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
