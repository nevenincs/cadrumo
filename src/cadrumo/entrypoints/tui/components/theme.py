"""The Cadrumo terminal design system: one palette, two appearances.

This module owns the presentation tokens and stylesheet shared by every
full-screen surface.  It does not read application settings or retain screen
state; callers resolve an appearance and pass it to the installation helper.
Reusable Textual widgets that consume these tokens live in
:mod:`cadrumo.entrypoints.tui.components.widgets`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, override

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Size
from textual.theme import Theme
from textual.widgets import DataTable, Static

from ....core.config import TuiAppearance
from ....core.json_contract import Notice, NoticeSeverity, ResolvedNoticeAction

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textual.app import App


CADRUMO_LIGHT_THEME_NAME: Final[str] = "cadrumo-light"
CADRUMO_DARK_THEME_NAME: Final[str] = "cadrumo-dark"

CONTENT_WIDTH_PERCENT: Final[str] = "100%"
"""Share of the terminal the content column occupies."""


CADRUMO_LIGHT: Final[Theme] = Theme(
    name=CADRUMO_LIGHT_THEME_NAME,
    # Warm paper and near-black ink, verbatim from the frontend :root.
    background="#faf8f4",
    surface="#f1eee7",
    panel="#e9e3da",
    foreground="#1c1a17",
    primary="#c4553b",
    secondary="#6b655c",
    accent="#a8452f",
    # Sage and amber darkened from the brand's dark-terminal values.
    success="#3f6f5b",
    warning="#845d1d",
    error="#a33322",
    dark=False,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#c4553b",
        "input-selection-background": "#c4553b 25%",
    },
)

CADRUMO_DARK: Final[Theme] = Theme(
    name=CADRUMO_DARK_THEME_NAME,
    # A warm near-black rather than pure black, so the rust and sage keep hue.
    background="#1a1815",
    surface="#232019",
    panel="#2e2a22",
    foreground="#ece7dd",
    primary="#d9694e",
    secondary="#a89e90",
    accent="#e07d5f",
    success="#7fb096",
    warning="#d9a441",
    error="#f26c52",
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#e07d5f",
        "input-selection-background": "#d9694e 30%",
    },
)

CADRUMO_THEMES: Final[tuple[Theme, ...]] = (CADRUMO_LIGHT, CADRUMO_DARK)

SCROLLBAR_CELLS: Final[int] = 1
"""Width of the vertical scrollbar track, in cells."""

_BASE_CSS_TEMPLATE: Final[str] = """
    Screen {
        background: $background;
        color: $foreground;
        align: left top;
    }

    .cadrumo-column {
        width: 100%;
        height: auto;
    }

    .cadrumo-scroll {
        width: 100%;
        height: 1fr;
        align-horizontal: left;
        scrollbar-size-vertical: SCROLLBAR_CELLS;
        scrollbar-gutter: auto;
        padding: 0;
    }

    .cadrumo-scroll DataTable {
        height: auto;
        overflow-y: hidden;
        scrollbar-size-vertical: 0;
    }

    .cadrumo-banner {
        dock: top;
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    .cadrumo-panel {
        border: round $primary;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
        margin: 0;
        width: 100%;
        height: auto;
    }

    .cadrumo-subtle { color: $text-muted; }
    .cadrumo-note { color: $text-muted; text-style: italic; }

    Button {
        height: 1;
        border: none;
        padding: 0 1;
        background: $panel;
        color: $foreground;
    }
    Button:hover { background: $panel-lighten-1; }
    Button:focus {
        background: $primary;
        color: $text;
        text-style: bold reverse;
    }
    Button.-primary { background: $primary; color: $text; }
    Button.-primary:focus { text-style: bold reverse; }

    Input {
        width: 100%;
        border: tall $accent;
        background: $background;
    }
    Input:focus { border: tall $primary; }
"""

BASE_CSS: Final[str] = _BASE_CSS_TEMPLATE.replace("SCROLLBAR_CELLS", str(SCROLLBAR_CELLS))
"""Chrome and layout shared by every Cadrumo full-screen surface."""

NOTICE_BAND_CSS: Final[str] = """
    NoticeBand {
        height: auto;
    }
    .cadrumo-notice { margin: 0 0 1 0; }
    .cadrumo-notice-info { color: $text; }
    .cadrumo-notice-warning { color: $warning; text-style: bold; }
    .cadrumo-notice-action { color: $text-muted; margin: 0 0 1 2; }
"""
"""Styling for :class:`NoticeBand`; severity is also rendered as a glyph."""


class ContentScroll(VerticalScroll, can_focus=False):
    """The scroll host every Cadrumo surface puts its content column in."""


class ContentDataTable[CellType](DataTable[CellType]):
    """A table that expands to its rows inside the shared scroll host."""

    def watch_virtual_size(self, size: Size) -> None:
        """Keep the layout box equal to the current rows and header."""
        self.styles.height = max(1, size.height)


_NOTICE_GLYPH: Final[dict[NoticeSeverity, str]] = {
    NoticeSeverity.INFO: "ⓘ",
    NoticeSeverity.WARNING: "⚠",
}


def _notice_action_target(notice: Notice) -> str | None:
    """Return the typed executable target supplied by a notice producer."""
    action = notice.action
    if not isinstance(action, ResolvedNoticeAction) or action.action.cli_path is None or action.argument_bindings:
        return None
    return "aeat " + " ".join(action.action.cli_path)


class NoticeBand(Vertical, can_focus=False):
    """Render already-resolved notices without adding interaction state."""

    def __init__(self, notices: Sequence[Notice], *, id: str | None = None) -> None:
        """Store the immutable notice projection for rendering."""
        super().__init__(id=id)
        self._notices = tuple(notices)

    @override
    def compose(self) -> ComposeResult:
        for index, notice in enumerate(self._notices):
            glyph = _NOTICE_GLYPH.get(notice.severity, "•")
            yield Static(
                f"{glyph} {notice.message}",
                classes=f"cadrumo-notice cadrumo-notice-{notice.severity.value}",
                id=f"notice-{index}",
                markup=False,
            )
            action_target = _notice_action_target(notice)
            if action_target is not None:
                yield Static(
                    action_target,
                    classes="cadrumo-notice-action",
                    id=f"notice-{index}-action",
                    markup=False,
                )


def resolve_theme_name(appearance: TuiAppearance, *, host_prefers_dark: bool = True) -> str:
    """Return the registered theme name for an operator appearance choice."""
    if appearance is TuiAppearance.LIGHT:
        return CADRUMO_LIGHT_THEME_NAME
    if appearance is TuiAppearance.DARK:
        return CADRUMO_DARK_THEME_NAME
    return CADRUMO_DARK_THEME_NAME if host_prefers_dark else CADRUMO_LIGHT_THEME_NAME


def install_cadrumo_themes[ReturnT](
    app: App[ReturnT],
    *,
    appearance: TuiAppearance | None = None,
) -> None:
    """Register both themes on ``app`` and activate the resolved one.

    The component has no settings or application-state authority.  A caller
    that omits an appearance receives the neutral ``AUTO`` resolution.
    """
    selected = TuiAppearance.AUTO if appearance is None else appearance
    for theme in CADRUMO_THEMES:
        app.register_theme(theme)
    app.theme = resolve_theme_name(selected)


def toggle_appearance[ReturnT](app: App[ReturnT]) -> str:
    """Flip the active surface between the light and dark appearance."""
    app.theme = CADRUMO_LIGHT_THEME_NAME if app.theme == CADRUMO_DARK_THEME_NAME else CADRUMO_DARK_THEME_NAME
    return str(app.theme)


__all__ = [
    "BASE_CSS",
    "CADRUMO_DARK",
    "CADRUMO_DARK_THEME_NAME",
    "CADRUMO_LIGHT",
    "CADRUMO_LIGHT_THEME_NAME",
    "CADRUMO_THEMES",
    "CONTENT_WIDTH_PERCENT",
    "NOTICE_BAND_CSS",
    "ContentDataTable",
    "ContentScroll",
    "NoticeBand",
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
]
