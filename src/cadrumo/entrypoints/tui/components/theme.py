"""The Cadrumo terminal design system: one palette, two appearances.

This module owns the presentation tokens and stylesheet shared by every
full-screen surface.  It does not read application settings or retain screen
state; callers resolve an appearance and pass it to the installation helper.
Reusable Textual widgets that consume these tokens live in
:mod:`cadrumo.entrypoints.tui.components.widgets`.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from textual.theme import Theme

if TYPE_CHECKING:
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

CADRUMO_CSS_TOKENS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # -- Shape ---------------------------------------------------------
        # ONE corner treatment for every bordered thing on screen. A panel
        # drawn `round`, a field drawn `tall` and a button drawn with no
        # border at all is three shapes claiming to be one system, and the
        # eye reads the inconsistency long before it can name it.
        "cadrumo-radius": "round",
        # -- Spacing scale, in terminal cells -------------------------------
        # Cells, not rem: the unit here is a character, so the useful scale is
        # tiny and every step has to earn itself. A web 4-point scale has no
        # meaning on a grid where one step is already the smallest visible
        # distance.
        "cadrumo-space-0": "0",
        "cadrumo-space-1": "1",
        "cadrumo-space-2": "2",
        "cadrumo-space-3": "3",
        # -- Semantic roles -------------------------------------------------
        # Call sites name the ROLE, never the number, so re-tuning density is
        # one edit here rather than a sweep of eighty literals.
        # gutter: breathing between a panel border and its content.
        # stack:  the vertical gap between sibling blocks.
        # indent: how far a dependent line sits under its parent.
        "cadrumo-gutter": "2",
        "cadrumo-stack": "1",
        "cadrumo-indent": "2",
        # -- Controls -------------------------------------------------------
        # Three rows is Textual's own button height: one row of label between
        # two rows of border. The previous single row with no border made a
        # button indistinguishable from a line of text.
        "cadrumo-control-height": "3",
        "cadrumo-control-pad-x": "3",
        "cadrumo-control-min-width": "14",
        # -- Chrome ---------------------------------------------------------
        "cadrumo-scrollbar": "1",
    },
)
"""The canonical presentation tokens every Cadrumo surface is built from.

Delivered through :func:`cadrumo_css_variables`, which every Cadrumo ``App``
returns from ``get_css_variables``. That hook is the only mechanism Textual
offers that reaches EVERY stylesheet -- app-level ``CSS`` and each widget's
``DEFAULT_CSS`` alike. Theme ``variables`` do not: they are resolved after
widget default styles are parsed, so a token spent there raises
``UnresolvedVariableError`` in exactly the places a design system most needs
to reach.

Spatial tokens are deliberately outside the two ``Theme`` objects. Light and
dark differ in colour, never in measure; duplicating the scale into both
themes would create two places for one fact to drift apart.
"""

SCROLLBAR_CELLS: Final[int] = int(CADRUMO_CSS_TOKENS["cadrumo-scrollbar"])
"""Width of the vertical scrollbar track, in cells."""


def cadrumo_css_variables(base: Mapping[str, str]) -> dict[str, str]:
    """Merge the canonical tokens over Textual's own CSS variables.

    Every Cadrumo ``App`` overrides ``get_css_variables`` to return this, so a
    token edit reaches every surface at once instead of being swept through
    each stylesheet by hand.
    """
    return {**base, **CADRUMO_CSS_TOKENS}


BASE_CSS: Final[str] = """
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
        scrollbar-size-vertical: $cadrumo-scrollbar;
        scrollbar-gutter: auto;
        padding: $cadrumo-space-0;
    }

    .cadrumo-scroll DataTable {
        height: auto;
        overflow-y: hidden;
        scrollbar-size-vertical: $cadrumo-space-0;
    }

    .cadrumo-banner {
        dock: top;
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: $cadrumo-space-0 $cadrumo-gutter;
    }

    .cadrumo-panel {
        border: $cadrumo-radius $primary;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: $cadrumo-space-0 $cadrumo-gutter;
        /* The gap that was missing. Two panels with no margin butt their
           borders together into one doubled line, so the eye reads a single
           smeared container instead of two ideas. One row is the smallest
           separation a terminal can show, and on a grid this dense it is
           enough. */
        margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-space-0;
        width: 100%;
        height: auto;
    }

    .cadrumo-subtle { color: $text-muted; }
    .cadrumo-note { color: $text-muted; text-style: italic; }

    Button {
        /* Three rows, not one. A borderless single-row button is a run of
           text that happens to be focusable; the border is what makes it
           read as a thing you press. */
        height: $cadrumo-control-height;
        min-width: $cadrumo-control-min-width;
        border: $cadrumo-radius $secondary;
        padding: $cadrumo-space-0 $cadrumo-control-pad-x;
        background: $panel;
        color: $foreground;
    }
    Button:hover { background: $panel-lighten-1; }
    Button:focus {
        background: $primary;
        color: $text;
        border: $cadrumo-radius $primary;
        text-style: bold;
    }
    Button.-primary {
        background: $primary;
        color: $text;
        border: $cadrumo-radius $primary;
    }
    Button.-primary:focus { text-style: bold; }

    Input {
        width: 100%;
        height: $cadrumo-control-height;
        /* Was `tall`, while panels were `round` and buttons had none: three
           shapes claiming to be one system. */
        border: $cadrumo-radius $accent;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        background: $background;
    }
    Input:focus { border: $cadrumo-radius $primary; }
"""
"""Chrome and layout shared by every Cadrumo full-screen surface.

Every measure and every corner resolves from :data:`CADRUMO_CSS_TOKENS`, so
re-tuning the system's density or shape is an edit to the token table rather
than a sweep through this stylesheet and the eighteen others beside it.
"""

NOTICE_BAND_CSS: Final[str] = """
    NoticeBand {
        height: auto;
    }
    .cadrumo-notice { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-space-0; }
    .cadrumo-notice-info { color: $text; }
    .cadrumo-notice-warning { color: $warning; text-style: bold; }
    .cadrumo-notice-action {
        color: $text-muted;
        margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-indent;
    }
"""


def resolve_theme_name(appearance: str, *, host_prefers_dark: bool = True) -> str:
    """Return the registered theme name for an operator appearance choice."""
    if appearance == "light":
        return CADRUMO_LIGHT_THEME_NAME
    if appearance == "dark":
        return CADRUMO_DARK_THEME_NAME
    return CADRUMO_DARK_THEME_NAME if host_prefers_dark else CADRUMO_LIGHT_THEME_NAME


def install_cadrumo_themes[ReturnT](
    app: App[ReturnT],
    *,
    appearance: str | None = None,
) -> None:
    """Register both themes on ``app`` and activate the resolved one.

    The component has no settings or application-state authority.  A caller
    that omits an appearance receives the neutral ``AUTO`` resolution.
    """
    selected = "auto" if appearance is None else appearance
    for theme in CADRUMO_THEMES:
        app.register_theme(theme)
    app.theme = resolve_theme_name(selected)


def toggle_appearance[ReturnT](app: App[ReturnT]) -> str:
    """Flip the active surface between the light and dark appearance."""
    app.theme = CADRUMO_LIGHT_THEME_NAME if app.theme == CADRUMO_DARK_THEME_NAME else CADRUMO_DARK_THEME_NAME
    return str(app.theme)


__all__ = [
    "BASE_CSS",
    "CADRUMO_CSS_TOKENS",
    "CADRUMO_DARK",
    "CADRUMO_DARK_THEME_NAME",
    "CADRUMO_LIGHT",
    "CADRUMO_LIGHT_THEME_NAME",
    "CADRUMO_THEMES",
    "CONTENT_WIDTH_PERCENT",
    "NOTICE_BAND_CSS",
    "SCROLLBAR_CELLS",
    "cadrumo_css_variables",
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
]
