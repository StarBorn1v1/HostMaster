"""
lattice_view.py — Hostmaster canvas

Two classes:
  · LatticeGraphicsScene  — QGraphicsScene with precision schematic background
  · LatticeGraphicsView   — Interactive canvas, layout engine, animation ticker
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from graphics_items import LatticeEdgeItem, MachineHubItem, ServerNodeItem
from models import ServerNode, SystemStats
from theme import ThemeMode, theme_manager


# ---------------------------------------------------------------------------
# LatticeGraphicsScene
# ---------------------------------------------------------------------------


class LatticeGraphicsScene(QGraphicsScene):
    """
    Custom scene with a precision schematic background.

    Three-layer background (drawn in order):
      1. Base fill       — bg_void, the true canvas colour
      2. Dot grid        — 32 px spacing, border_hairline @ 70% alpha, 1 px dots
      3. Reference rings — two concentric circles at 200 and 370 px, solid 1 px
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSceneRect(-1500, -1500, 3000, 3000)
        self._apply_background_brush()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        self._apply_background_brush()
        self.invalidate(self.sceneRect())

    def _apply_background_brush(self) -> None:
        t = theme_manager.tokens
        self.setBackgroundBrush(QBrush(t.bg_void))

    # ------------------------------------------------------------------
    # Background drawing
    # ------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()

        t = theme_manager.tokens

        # --- Layer 1: Base fill -----------------------------------------
        painter.fillRect(rect, QColor(t.bg_void))

        # --- Layer 2: Dot grid ------------------------------------------
        DOT_SPACING = 32

        # Clamp grid origin to visible rect (with 32 px padding to avoid
        # edge artifacts) so we never draw the full 3000x3000 scene.
        left = int(rect.left() - 32)
        left = left - (left % DOT_SPACING)
        top = int(rect.top() - 32)
        top = top - (top % DOT_SPACING)
        right = int(rect.right() + 32)
        bottom = int(rect.bottom() + 32)

        is_light = (theme_manager.mode == ThemeMode.LIGHT)
        
        dot_color = QColor(t.text_primary)
        dot_color.setAlphaF(0.25 if is_light else 0.12)
        painter.setPen(QPen(dot_color, 1.0))

        for x in range(left, right, DOT_SPACING):
            for y in range(top, bottom, DOT_SPACING):
                painter.drawPoint(x, y)

        # --- Layer 3: Concentric reference rings ------------------------
        ring_color = QColor(t.text_primary)
        ring_color.setAlphaF(0.20 if is_light else 0.08)
        ring_pen = QPen(ring_color, 1.0, Qt.SolidLine)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        
        # Draw concentric rings out to the scene bounds so large clusters fit
        for r in range(200, 1600, 170):
            painter.drawEllipse(QPointF(0.0, 0.0), float(r), float(r))

        painter.restore()


# ---------------------------------------------------------------------------
# LatticeGraphicsView
# ---------------------------------------------------------------------------


class LatticeGraphicsView(QGraphicsView):
    """
    Interactive canvas: pan, zoom, radial layout, animation ticker, selection.

    Signals
    -------
    node_selected     emits ServerNode when a server node is clicked
    hub_selected      emits SystemStats | None when the hub is clicked
    selection_cleared emits when the user clicks empty space
    """

    node_selected = Signal(object)   # ServerNode
    hub_selected = Signal(object)    # SystemStats | None
    selection_cleared = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Scene
        self.lattice_scene = LatticeGraphicsScene(self)
        self.setScene(self.lattice_scene)

        # Render quality
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Update mode — only repaint dirty regions
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)

        # Scrollbars always hidden
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Pan by dragging
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.NoFrame)

        # Zoom toward the cursor
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        # Central hub
        self.hub_item = MachineHubItem()
        self.hub_item.setPos(0, 0)
        self.hub_item.setZValue(10)
        self.lattice_scene.addItem(self.hub_item)

        # Node / edge registries
        self.node_items: dict[tuple[int, int], ServerNodeItem] = {}
        self.edge_items: dict[tuple[int, int], LatticeEdgeItem] = {}

        # Selection state
        self.selected_key: tuple[int, int] | None = None
        self.is_hub_selected: bool = False

        # Zoom tracking (for clamping)
        self._zoom_level: float = 1.0

        # Animation timer — ~30 fps
        self.pulse_phase: float = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(50)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start()

        # Theme updates
        theme_manager.theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        for item in self.node_items.values():
            item.update()
        for edge in self.edge_items.values():
            edge.update()
        self.hub_item.update()
        self.viewport().update()

    # ------------------------------------------------------------------
    # Public data update API
    # ------------------------------------------------------------------

    def update_system_stats(self, stats: SystemStats) -> None:
        """Push fresh system stats to the hub and optionally refresh sidebar."""
        self.hub_item.set_stats(stats)
        if self.is_hub_selected:
            self.hub_selected.emit(stats)

    def update_nodes_diff(
        self,
        all_nodes: list[ServerNode],
        added_nodes: list[ServerNode],
        removed_keys: list[tuple[int, int]],
    ) -> None:
        """Apply a diff of added/removed nodes, then re-run radial layout."""
        # Remove stale nodes
        for key in removed_keys:
            node_item = self.node_items.pop(key, None)
            if node_item is not None:
                try:
                    self.lattice_scene.removeItem(node_item)
                except RuntimeError:
                    pass  # item may already be gone

            edge_item = self.edge_items.pop(key, None)
            if edge_item is not None:
                try:
                    self.lattice_scene.removeItem(edge_item)
                except RuntimeError:
                    pass

            if self.selected_key == key:
                self.selected_key = None
                self.selection_cleared.emit()

        # Add new nodes
        for node in added_nodes:
            key = node.key
            if key in self.node_items:
                continue  # already exists, skip

            node_item = ServerNodeItem(node)
            node_item.setPos(0, 0)
            node_item.set_target_pos(QPointF(0, 0))
            self.lattice_scene.addItem(node_item)
            self.node_items[key] = node_item

            edge_item = LatticeEdgeItem(self.hub_item, node_item)
            self.lattice_scene.addItem(edge_item)
            self.edge_items[key] = edge_item

        self._rearrange_radial_layout(all_nodes)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _rearrange_radial_layout(self, all_nodes: list[ServerNode]) -> None:
        """
        Distribute nodes evenly around a dynamic-radius circle centred on (0,0).

        Radius formula: enough circumference to keep nodes ~140 px apart,
        clamped between 200 and 600 px.
        """
        n = len(all_nodes)
        if n == 0:
            return

        # Node width is 120 px -> min arc spacing 140 px
        # circumference = 2*pi*r  ->  r = (n*140) / (2*pi)
        # Uncapped max radius allows many servers to push outwards infinitely
        radius = max(200.0, (n * 140.0) / (2.0 * math.pi))
        angle_step = (2.0 * math.pi) / n

        # Sort by port for deterministic, stable ordering
        sorted_nodes = sorted(all_nodes, key=lambda nd: nd.port)

        for idx, node in enumerate(sorted_nodes):
            key = node.key
            item = self.node_items.get(key)
            if item is None:
                continue
            theta = idx * angle_step - (math.pi / 2)  # start from top
            target_x = radius * math.cos(theta)
            target_y = radius * math.sin(theta)
            item.set_target_pos(QPointF(target_x, target_y))

    # ------------------------------------------------------------------
    # Animation tick
    # ------------------------------------------------------------------

    def _on_anim_tick(self) -> None:
        base_speed = 0.003
        
        for edge in self.edge_items.values():
            # Get CPU percent from the edge's specific ServerNode
            cpu_usage = edge.node_item.node.cpu_percent if hasattr(edge.node_item.node, 'cpu_percent') else 0.0
            
            # Calculate an independent speed for this edge
            speed = base_speed + (cpu_usage / 100.0) * 0.05
            
            # Step the edge's phase independently
            edge.set_phase(edge.phase + speed)

        any_moving = any(
            node_item.step_animation() for node_item in self.node_items.values()
        )
        
        # --- Smooth Opacity Fade for unselected nodes ---
        has_selection = (self.selected_key is not None) or self.is_hub_selected
        dim_opacity = 0.25
        
        for key, node_item in self.node_items.items():
            target_opacity = 1.0
            if has_selection:
                if self.selected_key is not None and key == self.selected_key:
                    target_opacity = 1.0
                else:
                    target_opacity = dim_opacity
                    
            current_op = node_item.opacity()
            if abs(current_op - target_opacity) > 0.005:
                new_op = current_op + (target_opacity - current_op) * 0.15
                node_item.setOpacity(new_op)
                edge = self.edge_items.get(key)
                if edge:
                    edge.setOpacity(new_op)
                any_moving = True

        if any_moving:
            for edge in self.edge_items.values():
                edge.prepareGeometryChange()
                edge.update()

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        # Allow scene to process the event first (drag, item events, etc.)
        super().mousePressEvent(event)

        scene_pos = self.mapToScene(event.pos())
        item = self.lattice_scene.itemAt(scene_pos, self.transform())

        # Walk the parent chain to identify what was actually clicked
        target: QGraphicsItem | None = item
        found_node: ServerNodeItem | None = None
        found_hub: MachineHubItem | None = None

        while target is not None:
            if isinstance(target, MachineHubItem):
                found_hub = target
                break
            elif isinstance(target, ServerNodeItem):
                found_node = target
                break
            target = target.parentItem()

        if found_hub is not None:
            self._select_hub()
        elif found_node is not None:
            self._select_node(found_node)
        elif item is None:
            # Clicked empty space — clear selection
            self._clear_selection()

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select_hub(self) -> None:
        """Deselect previous item, select hub, emit signal."""
        # Deselect previous node if any
        if self.selected_key is not None:
            prev = self.node_items.get(self.selected_key)
            if prev is not None:
                prev.set_selected(False)
            self.selected_key = None

        self.is_hub_selected = True
        self.hub_item.set_selected(True)
        self.hub_selected.emit(self.hub_item.stats)

    def _select_node(self, node_item: ServerNodeItem) -> None:
        """Deselect previous item, select node, emit signal."""
        # Deselect hub if selected
        if self.is_hub_selected:
            self.is_hub_selected = False
            self.hub_item.set_selected(False)

        # Deselect previous node if different
        if self.selected_key is not None:
            prev = self.node_items.get(self.selected_key)
            if prev is not None:
                prev.set_selected(False)

        self.selected_key = node_item.node.key
        node_item.set_selected(True)
        self.node_selected.emit(node_item.node)

    def _clear_selection(self) -> None:
        """Deselect everything and emit cleared signal."""
        if self.is_hub_selected:
            self.is_hub_selected = False
            self.hub_item.set_selected(False)

        if self.selected_key is not None:
            prev = self.node_items.get(self.selected_key)
            if prev is not None:
                prev.set_selected(False)
            self.selected_key = None

        self.selection_cleared.emit()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        factor = 1.12 if delta > 0 else (1.0 / 1.12)
        new_zoom = self._zoom_level * factor

        # Clamp zoom between 0.3x and 3.0x
        if 0.3 <= new_zoom <= 3.0:
            self._zoom_level = new_zoom
            self.scale(factor, factor)

        event.accept()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_view(self) -> None:
        """Reset pan and zoom, centre on origin."""
        self.resetTransform()
        self._zoom_level = 1.0
        self.centerOn(QPointF(0, 0))
