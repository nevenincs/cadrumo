"""The Cadrumo terminal design system: one palette, two appearances.

Every full-screen surface the operator meets — the profile manager, the
paged flow frontend, the read-only status page — renders through the two
:class:`~textual.theme.Theme` objects declared here, and lays its content
out with :data:`BASE_CSS`. This module is the single source of truth for
the terminal look, so a screen never hardcodes a colour or a column
width, and the light and dark appearances cannot drift apart.

The palette is not new. It is the shipped Cadrumo brand, lifted from the
marketing frontend's custom properties (``frontend/src/styles.css``) and
the README CLI demo renderer (``dev/readme/render_cli_demo.py``): warm
paper, near-black ink, a rust primary, a muted sage success, an amber
warning. Reusing it keeps the terminal surface recognisably the same
product as the website and the documentation screenshots, and replaces
the previous ad-hoc use of Textual's stock developer palette.

Contrast is a constraint, not a preference. Every foreground token below
was checked against the background it renders on at the WCAG AA 4.5:1
body-text ratio. The light appearance therefore *darkens* the brand's
sage and amber: those hues are tuned for a dark terminal capture and land
at roughly 3.2:1 on warm paper, which fails. The dark appearance lifts
the rust for the same reason. Colour is never the sole carrier of meaning
on these surfaces — every status colour is paired with a label or glyph.

See Also:
    :class:`~cadrumo.core.config.TuiAppearance`
        The closed light/dark/auto axis the operator selects through
        ``CADRUMO_TUI_APPEARANCE``.
    :func:`install_cadrumo_themes`
        Registers both themes on an app and activates the resolved one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from textual.theme import Theme

from ....core.config import TuiAppearance

if TYPE_CHECKING:
    from textual.app import App


CADRUMO_LIGHT_THEME_NAME: Final[str] = "cadrumo-light"
CADRUMO_DARK_THEME_NAME: Final[str] = "cadrumo-dark"

CONTENT_MAX_WIDTH: Final[int] = 110
"""Maximum column width in cells for a body of prose, form, or table.

The previous surfaces pinned ``width: 96`` outright, so a wide terminal
wasted its space and a narrow one clipped. The column now fills the
available width and caps here: wide enough to hold a review table
comfortably, narrow enough that a full-width 200-column terminal does not
render a line of prose too long to track back to the next line's start.
"""


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
    # Sage and amber darkened from the brand's dark-terminal values
    # (#568a73 / #b6812c), which fall to ~3.2:1 on warm paper. The amber is
    # darker than a first pass suggested: it must clear AA against the
    # RAISED panel (#e9e3da), not merely against the page.
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
    # A warm near-black rather than pure black, so the rust and sage keep
    # their hue instead of reading as pure saturation against #000.
    background="#1a1815",
    surface="#232019",
    panel="#2e2a22",
    foreground="#ece7dd",
    primary="#d9694e",
    secondary="#a89e90",
    accent="#e07d5f",
    success="#7fb096",
    warning="#d9a441",
    # Lifted so it clears AA against the raised panel (#2e2a22), where the
    # brand's #e0644c lands at 4.15:1.
    error="#f26c52",
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#e07d5f",
        "input-selection-background": "#d9694e 30%",
    },
)

CADRUMO_THEMES: Final[tuple[Theme, ...]] = (CADRUMO_LIGHT, CADRUMO_DARK)


BASE_CSS: Final[str] = """
    Screen {
        background: $background;
        color: $foreground;
        align-horizontal: center;
    }

    /* The shared responsive content column. A surface marks its body with
       this class instead of pinning a width, so every screen breathes with
       the terminal and stays centred. */
    .cadrumo-column {
        width: 100%;
        max-width: 110;
        height: auto;
    }

    /* The docked title band every full-screen surface carries. */
    .cadrumo-banner {
        dock: top;
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 2;
    }

    .cadrumo-subtle { color: $text-muted; }
    .cadrumo-note { color: $text-muted; text-style: italic; }

    Button {
        height: 1;
        border: none;
        padding: 0 2;
        min-width: 12;
        background: $panel;
        color: $foreground;
    }
    Button:hover { background: $panel-lighten-1; }
    Button:focus { background: $primary; color: $text; text-style: bold; }
    Button.-primary { background: $primary; color: $text; }
    Button.-primary:focus { text-style: bold reverse; }
"""
"""Chrome and layout shared by every Cadrumo full-screen surface.

An app composes this ahead of its own rules (``CSS = BASE_CSS + "..."``)
so the banner, the centred content column, and the button treatment are
defined once. Colours resolve through theme tokens exclusively, which is
what lets one app serve both appearances without a second stylesheet.
"""


def resolve_theme_name(appearance: TuiAppearance, *, host_prefers_dark: bool = True) -> str:
    """Return the registered theme name for the operator's appearance choice.

    ``AUTO`` defers to ``host_prefers_dark``, which callers source from the
    host terminal rather than guessing here; the default reflects the
    overwhelming convention that a terminal is dark. ``LIGHT`` and ``DARK``
    are explicit operator choices and are honoured verbatim.
    """
    if appearance is TuiAppearance.LIGHT:
        return CADRUMO_LIGHT_THEME_NAME
    if appearance is TuiAppearance.DARK:
        return CADRUMO_DARK_THEME_NAME
    return CADRUMO_DARK_THEME_NAME if host_prefers_dark else CADRUMO_LIGHT_THEME_NAME


def install_cadrumo_themes[ReturnT](app: App[ReturnT], *, appearance: TuiAppearance | None = None) -> None:
    """Register both Cadrumo themes on ``app`` and activate the resolved one.

    Generic over the app's run-return type: ``App`` is invariant in it, so
    naming a concrete ``App[None]`` here would lock the design system to
    surfaces that return nothing.

    Call from ``on_mount``. When ``appearance`` is omitted the operator's
    ``CADRUMO_TUI_APPEARANCE`` setting is read, so a surface picks up the
    configured look without every app re-reading settings itself.
    """
    if appearance is None:
        from ....core.config import load_settings

        appearance = load_settings().cadrumo_tui_appearance
    for theme in CADRUMO_THEMES:
        app.register_theme(theme)
    app.theme = resolve_theme_name(appearance)


def toggle_appearance[ReturnT](app: App[ReturnT]) -> str:
    """Flip the active surface between the light and dark appearance.

    Returns the newly-activated theme name. A surface that is showing some
    third theme (an operator pick through the command palette) resolves to
    the dark appearance, so the toggle always lands somewhere defined.
    """
    app.theme = CADRUMO_LIGHT_THEME_NAME if app.theme == CADRUMO_DARK_THEME_NAME else CADRUMO_DARK_THEME_NAME
    return str(app.theme)


__all__ = [
    "BASE_CSS",
    "CADRUMO_DARK",
    "CADRUMO_DARK_THEME_NAME",
    "CADRUMO_LIGHT",
    "CADRUMO_LIGHT_THEME_NAME",
    "CADRUMO_THEMES",
    "CONTENT_MAX_WIDTH",
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
]
