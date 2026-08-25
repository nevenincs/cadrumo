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

import math
from typing import TYPE_CHECKING, Any

import pytest
from textual.containers import Vertical
from textual.theme import Theme

from cadrumo.entrypoints.tui.components.theme import (
    BASE_CSS,
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
    SCROLLBAR_CELLS,
    resolve_theme_name,
)

from ....application.user_profile.status_projection import StatusPageData
from ....core import scan_directory
from ....core.config import TuiAppearance
from ....entrypoints.tui.profile.status import StatusApp
from ....entrypoints.tui.secret.registration import RegistrationApp

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_entrypoint,
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
    return channel / 12.92 if channel <= 0.03928 else math.pow((channel + 0.055) / 1.055, 2.4)


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


def test_the_content_column_uses_all_available_width() -> None:
    """The shared column must not impose an artificial width ceiling."""
    assert CONTENT_WIDTH_PERCENT == "100%"


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
    from ....core import assess_profile_password
    from ....entrypoints.cli import attempt_registration

    return RegistrationApp(assess=assess_profile_password, register=attempt_registration)


def _gutters(app: App[Any]) -> tuple[int, int]:
    """Return the cells outside the full-width content column.

    ``App`` is invariant in its return type, so this reads any app rather
    than ``App[object]`` alone: the measurement touches screen geometry only
    and never the value the app eventually returns.
    """
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
async def test_the_content_column_consumes_the_available_terminal(
    build: Callable[[], App[object]],
    width: int,
    height: int,
) -> None:
    """Real mounted surfaces use every cell except an active scrollbar."""
    app = build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        left, right = _gutters(app)
        assert left == 0, f"left gutter at {width}x{height}: {left}"
        assert 0 <= right <= SCROLLBAR_CELLS, f"unused width at {width}x{height}: left={left} right={right}"
        app.exit(None)


def test_the_outer_scrollbar_does_not_reserve_permanent_side_gutters() -> None:
    """Only overflow may consume the single scrollbar cell."""
    assert f"scrollbar-size-vertical: {SCROLLBAR_CELLS};" in BASE_CSS
    assert "scrollbar-gutter: auto;" in BASE_CSS
    assert "scrollbar-gutter: stable;" not in BASE_CSS
    assert "padding: 0 0 0 1;" not in BASE_CSS
    assert "SCROLLBAR_CELLS" not in BASE_CSS, "an unsubstituted token would be invalid CSS"


def test_no_surface_pins_or_caps_its_content_width() -> None:
    """No screen may reintroduce a cell width or sub-full percentage cap.

    Scans the shipped stylesheets rather than sampling one app. ``width: 96``
    and ``width: 60%`` both waste or clip available terminal space; only a
    full ``100%`` declaration is admitted for percentage widths.
    """
    import re
    from pathlib import Path

    tui_dir = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for module in scan_directory(tui_dir, pattern="*.py"):
        for match in re.finditer(r"(max-)?width:\s*(\d+)\s*;", module.read_text(encoding="utf-8")):
            offenders.append(f"{module.name}: {match.group(0)}")
        for match in re.finditer(r"(max-)?width:\s*(\d+)%\s*;", module.read_text(encoding="utf-8")):
            if match.group(2) != "100":
                offenders.append(f"{module.name}: {match.group(0)}")
    assert not offenders, f"width limits: {offenders}"
