"""The Cadrumo terminal design system: one palette, two appearances.

Every full-screen surface the operator meets — the profile manager, the
paged flow frontend, the read-only status page — renders through the two
``textual.theme.Theme`` objects declared here, and lays its content
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

from typing import TYPE_CHECKING, Final, override

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import Static

from ....core.config import TuiAppearance, load_settings
from ....core.json_contract import Notice, NoticeSeverity

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textual.app import App


CADRUMO_LIGHT_THEME_NAME: Final[str] = "cadrumo-light"
CADRUMO_DARK_THEME_NAME: Final[str] = "cadrumo-dark"

CONTENT_WIDTH_PERCENT: Final[str] = "86%"
"""Share of the terminal the content column occupies.

Expressed as a proportion, never a cell count. Cell constants were the
original defect: a body pinned at 96 cells wasted a wide terminal and
clipped a narrow one, and simply raising the number moves the problem
rather than removing it. A proportion scales with whatever the operator
actually gave the application, leaving a consistent gutter at every size.
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


SCROLLBAR_CELLS: Final[int] = 1
"""Width of the vertical scrollbar track, in cells.

The scroll host reserves this on the right (``scrollbar-gutter: stable``)
and pads by the same amount on the left, so the reservation is symmetric
and the centred content column lands on the terminal's true midline. The
two must always agree, which is why they are one constant substituted
into the stylesheet rather than two numbers typed twice.
"""

_BASE_CSS_TEMPLATE: Final[str] = """
    Screen {
        background: $background;
        color: $foreground;
        /* Both axes. Horizontal alone left every surface hugging the top of
           a tall terminal with the whole lower half empty, which is what
           "not centred" actually looked like. */
        align: center middle;
    }

    /* The shared fluid content column. A surface marks its body with this
       class instead of pinning a width: the column is a PROPORTION of the
       terminal, so it grows with a wide one and shrinks with a narrow one
       while keeping the same gutter on both sides. No cell constants. */
    .cadrumo-column {
        width: 86%;
        height: auto;
    }

    /* A scroll host must not eat the column's centring. `scrollbar-gutter:
       stable` reserves the track so the layout does not jump when the
       scrollbar appears — but it reserves on the RIGHT ONLY, which moves
       the content box off the terminal's midline and drags the centred
       column with it (measured: gutters 8 left / 10 right at 120 columns).
       Matching that reservation with an equal left padding restores the
       symmetry: the content box is now inset by the scrollbar width on
       both sides, so its midline is the terminal's midline. Both values
       track SCROLLBAR_CELLS — they are one measurement, not two. */
    .cadrumo-scroll {
        width: 100%;
        height: 1fr;
        align-horizontal: center;
        scrollbar-size-vertical: SCROLLBAR_CELLS;
        scrollbar-gutter: stable;
        padding: 0 0 0 SCROLLBAR_CELLS;
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

    /* One padding scale, so panels across surfaces breathe identically. */
    .cadrumo-panel {
        border: round $primary;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: 1 3;
        margin: 1 0;
        width: 100%;
        height: auto;
    }

    .cadrumo-subtle { color: $text-muted; }
    .cadrumo-note { color: $text-muted; text-style: italic; }

    /* Buttons must read as focused from across the room: reversed brand
       fill plus a marker, so focus never depends on colour alone. */
    Button {
        height: 3;
        border: none;
        padding: 0 3;
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

    /* Inputs take the same full-width treatment so a form reads as a column
       of equal-weight rows rather than ragged boxes. */
    Input {
        width: 100%;
        border: tall $accent;
        background: $background;
    }
    Input:focus { border: tall $primary; }
"""

BASE_CSS: Final[str] = _BASE_CSS_TEMPLATE.replace("SCROLLBAR_CELLS", str(SCROLLBAR_CELLS))
"""Chrome and layout shared by every Cadrumo full-screen surface.

An app composes this ahead of its own rules (``CSS = BASE_CSS + "..."``)
so the banner, the centred content column, and the button treatment are
defined once. Colours resolve through theme tokens exclusively, which is
what lets one app serve both appearances without a second stylesheet.
"""


class ContentScroll(VerticalScroll, can_focus=False):
    """The scroll host every Cadrumo surface puts its content column in.

    Identical to :class:`~textual.containers.VerticalScroll` except that it
    is removed from the tab order. A scrollable container is focusable by
    default so it can be scrolled from the keyboard, but on these surfaces
    it lands between the last control and the first as a stop that shows no
    focus and does nothing visible — the operator presses Tab, the
    highlight vanishes, and the form looks broken. The content is reachable
    by tabbing the real controls, and the scroll still responds to the
    mouse wheel and to Page Up / Page Down.
    """


NOTICE_BAND_CSS: Final[str] = """
    NoticeBand {
        height: auto;
    }
    .cadrumo-notice { margin: 0 0 1 0; }
    .cadrumo-notice-info { color: $text; }
    .cadrumo-notice-warning { color: $warning; text-style: bold; }
    .cadrumo-notice-action { color: $text-muted; margin: 0 0 1 2; }
"""
"""Styling for :class:`NoticeBand`. Severity drives both the glyph the band
prints and this colour, so meaning never rests on colour alone — the same
convention every other status glyph on these surfaces follows."""

_NOTICE_GLYPH: Final[dict[NoticeSeverity, str]] = {
    NoticeSeverity.INFO: "ⓘ",
    NoticeSeverity.WARNING: "⚠",
}


def _notice_action_target(notice: Notice) -> str | None:
    """Return the executable CLI path the read-only TUI may show.

    Notice producers resolve executable actions against the live operator
    surface before emission.  This adapter therefore projects only that typed
    target and never guesses from the dotted machine identity. Notices whose
    entrypoint has not supplied a canonical CLI path remain a single message
    line rather than exposing an internal command key to an operator.
    """
    action = notice.action
    if action is None or action.action.cli_path is None or action.argument_bindings:
        return None
    return "aeat " + " ".join(action.action.cli_path)


class NoticeBand(Vertical, can_focus=False):
    """Render :class:`~cadrumo.core.json_contract.Notice` values on a full-screen surface.

    The single reusable projection of the envelope's typed ``notices``
    channel onto a Cadrumo full-screen surface. A command's JSON envelope and
    its text-mode rendering already share one :class:`Notice` list per the
    ``aeat-cli-contract`` rule; this widget is that same list's third
    rendering, so a full-screen operator meets the identical advisory a
    scripted caller would see on stderr rather than a second, TUI-only
    vocabulary invented to route around the gap.

    Read-only and inert: it owns no interaction, no dismissal, and no state
    beyond the notices it was built with — a caller that wants a different
    set mounts a new band rather than mutating this one.
    """

    def __init__(self, notices: Sequence[Notice], *, id: str | None = None) -> None:
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
    "CONTENT_WIDTH_PERCENT",
    "NOTICE_BAND_CSS",
    "ContentScroll",
    "NoticeBand",
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
]
