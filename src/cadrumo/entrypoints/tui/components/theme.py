"""The Cadrumo terminal design system: one palette, two appearances.

This module owns the presentation tokens and stylesheet shared by every
full-screen surface.  It does not read application settings or retain screen
state; callers resolve an appearance and pass it to the installation helper.
Reusable Textual widgets that consume these tokens live in
:mod:`cadrumo.entrypoints.tui.components.widgets`.
"""

from __future__ import annotations

import re
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
        # A terminal has no shadow, so border WEIGHT is the only elevation
        # channel there is. Overlays therefore keep a deliberately heavier
        # edge: it is the one signal that a dialog floats above the page
        # rather than sitting in it. Five different border styles were in use
        # before this -- round, thick, tall, solid and none -- and only this
        # one distinction among them was carrying meaning.
        "cadrumo-radius-overlay": "thick",
        # A single edge is a RULE, not a box. `round` draws corners, so
        # spending it on one edge asks for a corner that has nowhere to
        # go. Separators and the bar that marks an aside share this.
        "cadrumo-rule": "solid",
        # -- Fixed measures --------------------------------------------------
        "cadrumo-band-height": "1",
        "cadrumo-modal-width": "80%",
        "cadrumo-modal-height": "80%",
        "cadrumo-log-max-height": "12",
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
        # Spacing has to express GROUPING, not a single uniform gap. One
        # value repeated everywhere gives every relationship equal weight,
        # which is the same as having no grouping at all. So the scale is a
        # rhythm, tight inside a group and generous between them:
        #
        #   tight   0  parts of one thought (a label and its own hint)
        #   stack   1  sibling blocks inside one group
        #   section 2  between logical groups, and between panels
        #
        # gutter/gutter-y: breathing between a panel border and its content.
        #   gutter-y is the axis that did not exist before: panel content sat
        #   directly on the border row, top and bottom.
        # indent: how far a dependent line sits under its parent.
        "cadrumo-tight": "0",
        "cadrumo-stack": "1",
        "cadrumo-section": "2",
        "cadrumo-gutter": "2",
        "cadrumo-gutter-y": "1",
        "cadrumo-indent": "2",
        # -- Controls -------------------------------------------------------
        # A button is a filled slab, not a line box: `block` edges are drawn
        # as half-blocks in the border colour and merge with the fill, which
        # is how Textual builds one. Height is deliberately absent -- the
        # widget sizes itself, and pinning a number is what pushed content
        # out of its own box.
        "cadrumo-control-edge": "block",
        # Horizontal breathing inside a control. Spent on `line-pad`, the
        # property Textual gives buttons for exactly this; `padding` insets
        # the content box instead and leaves a ring inside the border.
        "cadrumo-control-pad-x": "2",
        # Textual's own default is 16. The previous 14 made buttons SMALLER
        # than the library intends, while the complaint was that they were
        # small.
        "cadrumo-control-min-width": "16",
        # The gap between sibling action buttons. Nine stylesheets each
        # repeated this as a literal; two bordered boxes one cell apart
        # read as one smeared control, so the role gets a name and a
        # value that actually separates them.
        "cadrumo-control-gap": "2",
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


class UnknownDesignTokenError(KeyError):
    """A stylesheet referenced a ``$cadrumo-`` token that is not declared."""


_TOKEN_REFERENCE: Final = re.compile(r"\$(cadrumo-[a-z0-9-]+)")


def tokenised(css: str) -> str:
    """Resolve every ``$cadrumo-`` token in ``css`` to its declared value.

    Substitution happens HERE, at import time, rather than through Textual's
    ``get_css_variables`` hook. The hook works, but it makes a widget's own
    ``DEFAULT_CSS`` depend on the application that happens to host it: mount a
    Cadrumo component inside any app that does not implement the hook -- a
    test host, an embedder, a future surface someone forgets to wire -- and
    the widget fails to mount on an undefined variable. A component's styling
    should not be a contract with its host.

    Resolving into the string keeps one canonical table and one place to edit,
    and leaves the shipped stylesheets self-contained. Textual's own ``$``
    variables (``$primary``, ``$text-muted``, the theme colours) are untouched
    and still resolve at mount, which is right: those DO change at runtime
    when the operator flips appearance, and these measures never do.

    Raises:
        UnknownDesignTokenError: When the stylesheet names a token that is not
            declared. A silent pass-through would reach Textual as an
            undefined variable and fail far from the typo.
    """

    def _resolve(match: re.Match[str]) -> str:
        name = match.group(1)
        value = CADRUMO_CSS_TOKENS.get(name)
        if value is None:
            declared = ", ".join(sorted(CADRUMO_CSS_TOKENS))
            message = f"unknown design token ${name}; declared: {declared}"
            raise UnknownDesignTokenError(message)
        return value

    return _TOKEN_REFERENCE.sub(_resolve, css)


BASE_CSS: Final[str] = tokenised("""
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
        height: $cadrumo-band-height;
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

    /* Textual's own button model, rather than a box drawn over the top of
       it. The widget sizes itself (`height: auto`), pads its label with
       `line-pad`, and edges itself with a `block` border -- half-block
       glyphs in the border colour, which merge with the fill into one solid
       slab. Setting `padding` and a contrasting line border instead is what
       produced an outline sitting inside a filled button: an inner border,
       which is not a thing a button has. */
    Button {
        height: auto;
        min-width: $cadrumo-control-min-width;
        line-pad: $cadrumo-control-pad-x;
        border: $cadrumo-control-edge $panel;
        background: $panel;
        color: $foreground;
    }
    Button:hover {
        border: $cadrumo-control-edge $panel-lighten-1;
        background: $panel-lighten-1;
    }
    /* The edge always matches its own fill, so the slab stays seamless and
       state is carried by the fill colour, never by a second outline. */
    Button:focus {
        border: $cadrumo-control-edge $primary;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    Button.-primary {
        border: $cadrumo-control-edge $primary;
        background: $primary;
        color: $text;
    }
    Button.-primary:focus {
        border: $cadrumo-control-edge $accent;
        background: $accent;
        text-style: bold;
    }

    Input {
        width: 100%;
        height: auto;
        /* A field is a line box, unlike a button: `round` is right here, and
           matches the panels it sits inside. */
        border: $cadrumo-radius $accent;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        background: $background;
    }
    Input:focus { border: $cadrumo-radius $primary; }
""")
"""Chrome and layout shared by every Cadrumo full-screen surface.

Every measure and every corner resolves from :data:`CADRUMO_CSS_TOKENS`, so
re-tuning the system's density or shape is an edit to the token table rather
than a sweep through this stylesheet and the eighteen others beside it.
"""

NOTICE_BAND_CSS: Final[str] = tokenised("""
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
""")


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
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
    "tokenised",
]
