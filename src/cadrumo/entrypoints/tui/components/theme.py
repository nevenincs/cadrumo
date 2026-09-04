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
        # Declared, not inherited. Anything left undeclared is derived by
        # Textual from its own defaults, which is how a near-black element
        # appeared on the light page.
        "input-cursor-background": "#c4553b",
        "input-cursor-foreground": "#faf8f4",
        "scrollbar": "#d8cec0",
        "scrollbar-hover": "#c9bcaa",
        "scrollbar-active": "#c4553b",
        "scrollbar-background": "#f1eee7",
        "scrollbar-corner-color": "#f1eee7",
        "border": "#c4553b",
        "border-blurred": "#d8cec0",
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
        # Same declaration set as the light appearance; the two differ in
        # colour only, never in which variables exist.
        "input-cursor-background": "#d9694e",
        "input-cursor-foreground": "#1a1815",
        "scrollbar": "#3d382e",
        "scrollbar-hover": "#4d4739",
        "scrollbar-active": "#d9694e",
        "scrollbar-background": "#232019",
        "scrollbar-corner-color": "#232019",
        "border": "#d9694e",
        "border-blurred": "#3d382e",
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
        #
        # Held at 1, which is Textual's own default, because `line-pad` is NOT
        # counted in a button's auto-width: at 2 the widest label loses four
        # cells, wraps to a second line, and that button alone grows a row --
        # leaving a ragged action row. Short labels still get their breathing
        # from `control-min-width`.
        "cadrumo-control-pad-x": "1",
        # Textual's own default is 16. The previous 14 made buttons SMALLER
        # than the library intends, while the complaint was that they were
        # small.
        "cadrumo-control-min-width": "16",
        # Wide enough that no declared action label wraps. Derived, not
        # chosen: the longest is 43 cells ("Obtener todas las declaraciones
        # presentadas" in es, and the Catalan of the same length), and a button
        # spends two on its border and two on `line-pad`, so 47 is the floor
        # and this is the next even value.
        #
        # The old 28 wrapped almost every action label in every locale --
        # measured, only one of the four AEAT actions fits it in any language.
        # A wrapped label costs a row and makes that button alone taller,
        # producing the ragged action row the `control-pad-x` note above
        # already warns against; two buttons in one column then measured 3 and
        # 5 rows tall. It also had a consequence beyond looks: the taller
        # neighbour reached far enough to consume a simulated press aimed at
        # the button above it.
        "cadrumo-control-max-width": "48",
        # The gap between sibling action buttons. Nine stylesheets each
        # repeated this as a literal; two bordered boxes one cell apart
        # read as one smeared control, so the role gets a name and a
        # value that actually separates them.
        "cadrumo-control-gap": "2",
        # Table density. One number for every table in the product, because a
        # row's leading is what the eye uses to find the column edge: Home's
        # lists sat flush at column 0 while every other table was inset by one
        # cell, so two surfaces of the same product disagreed about where a row
        # begins. Tables also inset their FIRST column by this much, so the
        # heading above them takes the same indent and the group shares one
        # left edge.
        "cadrumo-cell-padding": "1",
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

    /* A section heading and the content it owns. The two gaps are
       deliberately asymmetric: the SECTION gap above separates this group from
       the previous one, the smaller STACK gap below binds the heading to its
       own rows. A heading equidistant from both reads as floating between
       them; a heading with no gap below reads as fused to its content, which
       is how a screen becomes one continuous run of data. */
    .cadrumo-heading {
        height: auto;
        text-style: bold;
        /* The same inset a table gives its first column, so a heading and the
           rows it owns share one left edge. Without it the heading starts a
           cell to the left of its own data and the group reads as ragged. */
        padding-left: $cadrumo-cell-padding;
        margin-top: $cadrumo-section;
        margin-bottom: $cadrumo-stack;
    }
    /* The heading that OPENS a scroll region takes the SMALLER gap. It has no
       previous group to separate from, so the section gap buys nothing there
       -- and on Home it actively costs: the leading heading is only painted
       at this value. At `0` it lands on the row the session line occupies and
       is overdrawn; at the section gap it disappears from the frame entirely.
       Both are measurable at 100x40 and neither is a rhythm problem: the
       enclosing `height: auto` container mis-places its first child. Until
       that is fixed, this value is a workaround, not a design choice. */
    .cadrumo-heading.cadrumo-heading-lead {
        margin-top: $cadrumo-stack;
        /* Restated, not inherited: a rule that sets one margin edge here
           replaces the whole box, so omitting this silently zeroes the gap
           the heading needs BELOW it and refuses the rhythm entirely. */
        margin-bottom: $cadrumo-stack;
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
        /* Both axes. Content used to sit directly on the border row, so a
           panel read as a box crushed around its text. */
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        /* Panels are separate logical groups, so they get the SECTION gap,
           not the sibling one: two panels a single row apart still read as
           one smeared container. */
        margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-section $cadrumo-space-0;
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
