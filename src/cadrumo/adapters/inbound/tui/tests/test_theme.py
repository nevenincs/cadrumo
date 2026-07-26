"""Behaviour and accessibility proofs for the Cadrumo terminal design system.

Two kinds of claim are checked here, both against something external to
the module under test.

The contrast claims are checked against the WCAG 2.1 relative-luminance
formula, recomputed here from the published coefficients rather than
imported from the code being tested. That keeps the check non-tautological:
if someone retunes a palette hex to something unreadable, the arithmetic
fails regardless of what the module's docstring asserts.

The rendering claims are checked by mounting the real apps through
Textual's headless Pilot. Textual parses an app's CSS at mount, so an
undefined token or a malformed rule surfaces as a mount failure — which
makes "the app mounts under both appearances" a genuine stylesheet proof
rather than a smoke test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.containers import Vertical
from textual.theme import Theme

from .....core.config import TuiAppearance
from .. import (
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
    RegistrationApp,
    StatusApp,
    StatusPageData,
    resolve_theme_name,
)
from .._theme import BASE_CSS, SCROLLBAR_CELLS

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import App


# ── WCAG 2.1 contrast, recomputed from the published formula ────────────────

_WCAG_AA_BODY_TEXT = 4.5
"""The WCAG 2.1 AA minimum contrast ratio for normal-size body text (SC 1.4.3)."""

_WCAG_AA_NON_TEXT = 3.0
"""The WCAG 2.1 AA minimum for UI components and graphical objects (SC 1.4.11).

Borders and band fills are governed by this bar, not the body-text one.
"""


def _linearise(channel: float) -> float:
    """Undo the sRGB transfer function for one 0..1 channel (WCAG 2.1)."""
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_colour: str) -> float:
    """Return the WCAG relative luminance of a ``#rrggbb`` string."""
    raw = hex_colour.lstrip("#")
    r, g, b = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _linearise(r) + 0.7152 * _linearise(g) + 0.0722 * _linearise(b)


def _contrast(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two ``#rrggbb`` strings."""
    lighter, darker = sorted((_relative_luminance(foreground), _relative_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_helper_agrees_with_the_published_reference_ratio() -> None:
    """Anchor the helper itself: black on white is the canonical 21:1."""
    assert _contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert _contrast("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)


@pytest.mark.parametrize("theme", CADRUMO_THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("surface_token", ["background", "surface", "panel"])
def test_foreground_meets_aa_on_every_surface(theme: Theme, surface_token: str) -> None:
    """Body ink clears AA against each of the three stacked surfaces.

    A theme whose foreground passes on ``background`` but fails on the
    raised ``panel`` renders unreadable text inside a bordered box, which
    is exactly where this design system puts most of its prose.
    """
    foreground = str(theme.foreground)
    surface = str(getattr(theme, surface_token))
    assert _contrast(foreground, surface) >= _WCAG_AA_BODY_TEXT


@pytest.mark.parametrize("theme", CADRUMO_THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("status_token", ["success", "warning", "error"])
def test_status_colours_meet_aa_on_every_surface_they_render_on(theme: Theme, status_token: str) -> None:
    """Status ink clears AA on the page AND on the raised panel.

    These render as ``color:`` on real prose — the answer echo, the live
    validation line, the stale-page badge — so they are body text, not
    decoration, and are held to the body-text ratio.

    All three surfaces are checked because the raised ``panel`` is the
    tightest and the one most of this prose actually sits on; a palette
    tuned only against the page passes a weaker test than it needs to.
    """
    colour = str(getattr(theme, status_token))
    for surface_token in ("background", "surface", "panel"):
        surface = str(getattr(theme, surface_token))
        assert _contrast(colour, surface) >= _WCAG_AA_BODY_TEXT, f"{status_token} on {surface_token}"


@pytest.mark.parametrize("theme", CADRUMO_THEMES, ids=lambda t: t.name)
def test_primary_meets_the_non_text_threshold_on_every_surface(theme: Theme) -> None:
    """The brand rust clears the 3:1 bar that actually governs it.

    ``$primary`` is never a body-text colour on these surfaces: it is a
    box border and the fill of the docked title band (whose ink is the
    separately-checked auto-contrast ``$text``). WCAG SC 1.4.11
    "Non-text Contrast" governs that role at 3:1, not the 4.5:1 body-text
    bar — so holding it to 4.5 would force a darker rust for no
    accessibility gain and cost the brand its identity colour.
    """
    primary = str(theme.primary)
    for surface_token in ("background", "surface", "panel"):
        surface = str(getattr(theme, surface_token))
        assert _contrast(primary, surface) >= _WCAG_AA_NON_TEXT, f"primary on {surface_token}"


@pytest.mark.parametrize("theme", CADRUMO_THEMES, ids=lambda t: t.name)
def test_banner_text_is_legible_on_the_primary_band(theme: Theme) -> None:
    """The docked title band resolves ``$text`` to a legible auto-contrast ink.

    ``$text`` is Textual's ``auto`` token: it picks whichever of black or
    white contrasts better with the band it lands on. The palette is only
    safe if that better choice actually clears AA, so assert the max.
    """
    band = str(theme.primary)
    best = max(_contrast("#ffffff", band), _contrast("#000000", band))
    assert best >= _WCAG_AA_BODY_TEXT


# ── appearance resolution ───────────────────────────────────────────────────


def test_explicit_appearance_is_honoured_over_the_host_preference() -> None:
    """An operator who picked light gets light even on a dark host."""
    assert resolve_theme_name(TuiAppearance.LIGHT, host_prefers_dark=True) == CADRUMO_LIGHT_THEME_NAME
    assert resolve_theme_name(TuiAppearance.DARK, host_prefers_dark=False) == CADRUMO_DARK_THEME_NAME


def test_auto_appearance_follows_the_host() -> None:
    assert resolve_theme_name(TuiAppearance.AUTO, host_prefers_dark=True) == CADRUMO_DARK_THEME_NAME
    assert resolve_theme_name(TuiAppearance.AUTO, host_prefers_dark=False) == CADRUMO_LIGHT_THEME_NAME


def test_the_two_appearances_declare_opposite_polarity() -> None:
    """``dark`` drives Textual's derived-token generation, so it must be set."""
    assert CADRUMO_LIGHT.dark is False
    assert CADRUMO_DARK.dark is True


def test_light_is_actually_lighter_than_dark() -> None:
    """Guards a copy-paste that leaves both appearances the same polarity."""
    assert _relative_luminance(str(CADRUMO_LIGHT.background)) > _relative_luminance(str(CADRUMO_DARK.background))


def test_the_content_column_is_a_proportion_not_a_cell_count() -> None:
    """The column must scale with the terminal, never pin a width.

    Cell constants were the original defect: a body pinned at 96 cells
    wasted a wide terminal and clipped a narrow one. Raising the number
    moves the problem; expressing it as a share removes it.
    """
    assert CONTENT_WIDTH_PERCENT.endswith("%")
    assert 50 < int(CONTENT_WIDTH_PERCENT.rstrip("%")) < 100


# ── rendered geometry ───────────────────────────────────────────────────────

_GEOMETRY_SIZES = [(80, 30), (120, 40), (200, 50)]
"""A narrow, an ordinary, and a wide terminal.

Three sizes rather than one because the defect this guards was invisible
at some widths and obvious at others: a fixed bias reads as tolerable
rounding on a wide terminal and as a visibly shoved page on a narrow one.
"""


def _registration_screen() -> RegistrationApp:
    """The registration surface wired to its real doors.

    Geometry never calls them, but the screen takes them because it does
    not reach up into the application layer for itself.
    """
    from .....application.user_profile import assess_passphrase
    from .....entrypoints.cli._config._manager_frontend import attempt_registration

    return RegistrationApp(assess=assess_passphrase, register=attempt_registration)


def _gutters(app: App[object]) -> tuple[int, int]:
    """Return the empty cells left and right of the centred content column."""
    screen = app.screen.region
    column = app.query_one(".cadrumo-column", Vertical).region
    return (column.x - screen.x, (screen.x + screen.width) - (column.x + column.width))


@pytest.mark.asyncio
@pytest.mark.parametrize(("width", "height"), _GEOMETRY_SIZES)
@pytest.mark.parametrize(
    "build",
    [_registration_screen, lambda: StatusApp(StatusPageData())],
    ids=["registration", "status"],
)
async def test_the_content_column_lands_on_the_terminal_midline(
    build: Callable[[], App[object]],
    width: int,
    height: int,
) -> None:
    """Left and right gutters must match to within one cell.

    Measured from the real rendered ``region`` of the mounted widgets, not
    from a screenshot: scraped output made the page look 9 cells off when
    the true bias was 2, because unfilled prose lines read as gutter.

    One cell of slack is the honest tolerance, not a fudge. When the space
    left over after the column is odd it cannot be split evenly across a
    cell grid, so a perfect-equality assertion would be unsatisfiable at
    half the terminal widths in existence.
    """
    app = build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        left, right = _gutters(app)
        assert abs(left - right) <= 1, f"off-centre at {width}x{height}: left={left} right={right}"
        assert left > 0, "the column must not touch the terminal edge"
        app.exit(None)


@pytest.mark.asyncio
async def test_dropping_the_left_reservation_really_does_shove_the_page() -> None:
    """Anti-tautology: the guard above fails on the layout it was written for.

    Reproduces the original defect by removing the compensating left
    padding, leaving ``scrollbar-gutter: stable`` reserving on the right
    alone. If this app centres, the assertion in the test above is
    measuring nothing.
    """

    class UncompensatedApp(RegistrationApp):
        CSS = RegistrationApp.CSS.replace("padding: 0 0 0 1;", "")

    reference = _registration_screen()
    app = UncompensatedApp(assess=reference._assess_passphrase, register=reference._create_profile)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        left, right = _gutters(app)
        assert abs(left - right) > 1, f"the defect did not reproduce: left={left} right={right}"
        app.exit(None)


def test_the_scrollbar_reservation_is_declared_once_for_both_sides() -> None:
    """The right-hand track and the left-hand pad come from one constant.

    Typing the number twice is how they drift apart, and a drifted pair is
    exactly the off-centre page above — so the stylesheet substitutes
    :data:`SCROLLBAR_CELLS` into both and this pins that it happened.
    """
    assert f"scrollbar-size-vertical: {SCROLLBAR_CELLS};" in BASE_CSS
    assert f"padding: 0 0 0 {SCROLLBAR_CELLS};" in BASE_CSS
    assert "SCROLLBAR_CELLS" not in BASE_CSS, "an unsubstituted token would be invalid CSS"


def test_no_surface_pins_a_cell_width_in_its_stylesheet() -> None:
    """No screen may reintroduce a hardcoded width or max-width in cells.

    Scans the shipped stylesheets for a bare integer width. Percentages and
    ``fr`` units pass; ``width: 96`` or ``max-width: 110`` do not. This is
    the regression guard for the whole fluid-layout property, which is
    otherwise easy to undo one screen at a time.
    """
    import re
    from pathlib import Path

    tui_dir = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for module in sorted(tui_dir.glob("*.py")):
        for match in re.finditer(r"(max-)?width:\s*(\d+)\s*;", module.read_text(encoding="utf-8")):
            offenders.append(f"{module.name}: {match.group(0)}")
    assert not offenders, f"hardcoded cell widths: {offenders}"
