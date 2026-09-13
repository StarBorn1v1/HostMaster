"""
theme.py — Hostmaster Design System

Color system, typography, and theme management for the Hostmaster application.
Aesthetic references: Linear, Vercel, Raycast.
Every token is intentional. Nothing decorative.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

try:
    from PySide6.QtCore import QSettings
except ImportError:
    QSettings = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme mode
# ---------------------------------------------------------------------------


class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"


# ---------------------------------------------------------------------------
# Color token dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColorTokens:
    """
    Flat, fully-typed color token set for a single theme mode.

    All QColor fields hold fully-resolved colors ready for painter / stylesheet
    use. Call .hex(color) to get the CSS hex string for any token.
    """

    # --- Backgrounds --------------------------------------------------------
    bg_void: QColor       # True canvas — behind everything
    bg_base: QColor       # Primary content surfaces
    bg_raised: QColor     # Sidebar, cards, panels
    bg_node: QColor       # Node cards
    bg_overlay: QColor    # Elevated cards, hover fill
    bg_control: QColor    # Inputs, interactive elements

    # --- Borders ------------------------------------------------------------
    border_hairline: QColor   # Pure structural dividers (barely visible)
    border_default: QColor    # Normal borders
    border_focus: QColor      # Hovered / active borders

    # --- Text ---------------------------------------------------------------
    text_max: QColor          # Headlines only
    text_primary: QColor      # Body, node labels
    text_secondary: QColor    # Metadata, ports, secondary info
    text_muted: QColor        # Placeholders, hints, disabled

    # --- Accent -------------------------------------------------------------
    accent_solid: QColor      # Interactive primary (buttons, selection rings)
    accent_dim: QColor        # Muted accent surfaces (badges, selected bg)
    accent_text: QColor       # Accent text on dark surfaces

    # --- Semantic -----------------------------------------------------------
    positive: QColor          # Active / healthy indicator
    positive_dim: QColor      # Muted positive surface
    destructive: QColor       # Kill action
    destructive_dim: QColor   # Hover fill for kill
    destructive_text: QColor  # Destructive text on dark surfaces

    # --- Special / animated -------------------------------------------------
    pulse_color: QColor       # Traveling lattice pulses
    node_halo: QColor         # Breathing halo around nodes

    # -----------------------------------------------------------------------

    @staticmethod
    def hex(q: QColor) -> str:
        """Return the CSS hex string (#RRGGBB) for any QColor token."""
        return q.name()


# ---------------------------------------------------------------------------
# Dark mode token singleton
# ---------------------------------------------------------------------------

DARK_TOKENS = ColorTokens(
    # Backgrounds
    bg_void=QColor("#0A0A0A"),
    bg_base=QColor("#111111"),
    bg_raised=QColor("#181818"),
    bg_node=QColor("#181818"),
    bg_overlay=QColor("#1F1F1F"),
    bg_control=QColor("#252525"),
    # Borders
    border_hairline=QColor("#1C1C1C"),
    border_default=QColor("#282828"),
    border_focus=QColor("#404040"),
    # Text
    text_max=QColor("#F5F5F5"),
    text_primary=QColor("#E0E0E0"),
    text_secondary=QColor("#888888"),
    text_muted=QColor("#484848"),
    # Accent
    accent_solid=QColor("#3B82F6"),
    accent_dim=QColor("#1D3461"),
    accent_text=QColor("#93C5FD"),
    # Semantic
    positive=QColor("#22C55E"),
    positive_dim=QColor("#14532D"),
    destructive=QColor("#EF4444"),
    destructive_dim=QColor("#450A0A"),
    destructive_text=QColor("#FCA5A5"),
    # Special / animated
    pulse_color=QColor(59, 130, 246, 80),
    node_halo=QColor(59, 130, 246, 20),
)

# ---------------------------------------------------------------------------
# Light mode token singleton
# ---------------------------------------------------------------------------

LIGHT_TOKENS = ColorTokens(
    # Backgrounds
    bg_void=QColor("#D4D4D4"),       # Dimmer neutral background (Pure gray)
    bg_base=QColor("#E5E5E5"),       # Base panel (Pure gray)
    bg_raised=QColor("#E5E5E5"),     # Sidebar panel (Pure gray)
    bg_node=QColor("#FAFAFA"),       # Node cards (Foreground punches through)
    bg_overlay=QColor("#FFFFFF"),    # Hovered node cards
    bg_control=QColor("#FAFAFA"),    # Buttons / Inputs
    # Borders
    border_hairline=QColor("#CDD5DF"),
    border_default=QColor("#CDD5DF"),
    border_focus=QColor("#94A3B8"),
    # Text
    text_max=QColor("#1E293B"),
    text_primary=QColor("#1E293B"),
    text_secondary=QColor("#64748B"),
    text_muted=QColor("#64748B"),
    # Accent
    accent_solid=QColor("#0F172A"),
    accent_dim=QColor("#E2E5E9"),
    accent_text=QColor("#0F172A"),
    # Semantic
    positive=QColor("#16A34A"),
    positive_dim=QColor("#DCFCE7"),
    destructive=QColor("#DC2626"),
    destructive_dim=QColor("#FEE2E2"),
    destructive_text=QColor("#B91C1C"),
    # Special / animated
    pulse_color=QColor(37, 99, 235, 110), # Higher opacity for gray background
    node_halo=QColor(37, 99, 235, 30),
)


# ---------------------------------------------------------------------------
# Theme manager
# ---------------------------------------------------------------------------

_SETTINGS_ORG = "Hostmaster"
_SETTINGS_APP = "Hostmaster"
_SETTINGS_KEY_MODE = "theme/mode"


class ThemeManager(QObject):
    """
    Singleton controller for application-wide theme state.

    Emits theme_changed when the mode flips and keeps the QPalette in sync.
    Persists the user's preference across sessions via QSettings.
    """

    theme_changed = Signal(ThemeMode)

    def __init__(self) -> None:
        super().__init__()
        self._mode: ThemeMode = ThemeMode.DARK
        self._load_preference()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def tokens(self) -> ColorTokens:
        return DARK_TOKENS if self._mode == ThemeMode.DARK else LIGHT_TOKENS

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def set_mode(self, mode: ThemeMode) -> None:
        """Switch to the given mode, apply palette, persist, and emit signal."""
        if self._mode == mode:
            return
        self._mode = mode
        self.apply_palette_to_app()
        self._save_preference()
        self.theme_changed.emit(mode)

    def toggle_mode(self) -> None:
        """Flip between dark and light."""
        target = ThemeMode.LIGHT if self._mode == ThemeMode.DARK else ThemeMode.DARK
        self.set_mode(target)

    # ------------------------------------------------------------------
    # Palette application
    # ------------------------------------------------------------------

    def apply_palette_to_app(self) -> None:
        """Push the current token set into the application QPalette."""
        app = QApplication.instance()
        if app is None:
            logger.debug("No QApplication instance — skipping palette apply")
            return

        t = self.tokens
        p = QPalette()

        # Window / surface
        p.setColor(QPalette.ColorRole.Window, t.bg_base)
        p.setColor(QPalette.ColorRole.WindowText, t.text_primary)
        p.setColor(QPalette.ColorRole.Base, t.bg_raised)
        p.setColor(QPalette.ColorRole.AlternateBase, t.bg_overlay)

        # Text
        p.setColor(QPalette.ColorRole.Text, t.text_primary)
        p.setColor(QPalette.ColorRole.PlaceholderText, t.text_muted)
        p.setColor(QPalette.ColorRole.BrightText, t.text_max)

        # Buttons
        p.setColor(QPalette.ColorRole.Button, t.bg_control)
        p.setColor(QPalette.ColorRole.ButtonText, t.text_primary)

        # Tooltips
        p.setColor(QPalette.ColorRole.ToolTipBase, t.bg_overlay)
        p.setColor(QPalette.ColorRole.ToolTipText, t.text_primary)

        # Selection / highlight
        p.setColor(QPalette.ColorRole.Highlight, t.accent_solid)
        p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

        # Borders / mid tones
        p.setColor(QPalette.ColorRole.Mid, t.border_default)
        p.setColor(QPalette.ColorRole.Midlight, t.border_focus)
        p.setColor(QPalette.ColorRole.Dark, t.bg_void)
        p.setColor(QPalette.ColorRole.Shadow, t.bg_void)

        # Disabled state — dim everything relative to primary
        for role, color in [
            (QPalette.ColorRole.WindowText, t.text_muted),
            (QPalette.ColorRole.Text, t.text_muted),
            (QPalette.ColorRole.ButtonText, t.text_muted),
            (QPalette.ColorRole.Highlight, t.accent_dim),
            (QPalette.ColorRole.HighlightedText, t.text_muted),
        ]:
            p.setColor(QPalette.ColorGroup.Disabled, role, color)

        app.setPalette(p)
        
        # Explicitly style QToolTip since QPalette is often ignored by the OS for tooltips
        app.setStyleSheet(f"""
            QToolTip {{
                background-color: {t.hex(t.bg_overlay)};
                color: {t.hex(t.text_primary)};
                border: 1px solid {t.hex(t.border_default)};
                padding: 4px;
                border-radius: 4px;
            }}
        """)

    # Alias kept for compatibility with code that called apply_theme_to_app
    apply_theme_to_app = apply_palette_to_app

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_preference(self) -> None:
        if QSettings is None:
            return
        try:
            settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
            settings.setValue(_SETTINGS_KEY_MODE, self._mode.value)
        except Exception as exc:
            logger.warning(f"Could not save theme preference: {exc}")

    def _load_preference(self) -> None:
        if QSettings is None:
            return
        try:
            settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
            raw = settings.value(_SETTINGS_KEY_MODE, ThemeMode.DARK.value)
            self._mode = ThemeMode(raw)
        except Exception as exc:
            logger.warning(f"Could not load theme preference, defaulting to DARK: {exc}")
            self._mode = ThemeMode.DARK


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

theme_manager = ThemeManager()


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

_UI_FONT_FAMILIES = ["Inter", "SF Pro Text", "-apple-system", "Segoe UI", "system-ui"]
_MONO_FONT_FAMILIES = ["JetBrains Mono", "Fira Code", "SF Mono", "Menlo", "Consolas", "monospace"]


def font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """
    Build a UI font at the given pixel size.

    Uses the Inter / system-ui font stack. Pixel sizes are used throughout
    for sub-pixel consistency across different DPI configurations.
    """
    f = QFont()
    f.setFamilies(_UI_FONT_FAMILIES)
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def _mono_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Build a monospace font at the given pixel size."""
    f = QFont()
    f.setFamilies(_MONO_FONT_FAMILIES)
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


# --- Named font shortcuts ---------------------------------------------------

def font_label() -> QFont:
    """14px Regular — sidebar labels, metadata."""
    return font(14, QFont.Weight.Normal)


def font_body() -> QFont:
    """13px Regular — node primary text, descriptions."""
    return font(13, QFont.Weight.Normal)


def font_ui() -> QFont:
    """14px Medium — button labels, form controls."""
    return font(14, QFont.Weight.Medium)


def font_heading() -> QFont:
    """13px SemiBold — card headers, section titles."""
    return font(13, QFont.Weight.DemiBold)


def font_mono() -> QFont:
    """12px Regular monospace — command lines, ports, PIDs."""
    return _mono_font(12, QFont.Weight.Normal)


def font_display() -> QFont:
    """15px Medium with letter spacing — metrics values, slot numbers."""
    f = font(15, QFont.Weight.Medium)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
    return f


def font_micro() -> QFont:
    """12px Bold uppercase — tiny section headers."""
    f = font(12, QFont.Weight.Bold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
    return f
