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
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from textual.containers import Vertical
from textual.screen import Screen
from textual.theme import Theme

from ....application.user_profile.status_projection import StatusPageData
from ....core.config import TuiAppearance
from ....core.directory_scan import scan_directory
from ....entrypoints.tui.profile.status import StatusApp
from ....entrypoints.tui.secret.credentials import CredentialHostApp, CredentialScreen
from ....entrypoints.tui.secret.registration import RegistrationScreen
from ..components.theme import (
    BASE_CSS,
    CADRUMO_CSS_TOKENS,
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
    NOTICE_BAND_CSS,
    SCROLLBAR_CELLS,
    UnknownDesignTokenError,
    resolve_theme_name,
    tokenised,
)

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


def _registration_screen() -> RegistrationScreen:
    """The registration surface wired to its real doors.

    Geometry never calls them, but the screen takes them because it does
    not reach up into the application layer for itself.
    """
    from ....core.credentials import assess_profile_password
    from ..devtools.fixture import registration_attempt

    return RegistrationScreen(assess=assess_profile_password, register=registration_attempt)


def _gutters(active: Screen[Any]) -> tuple[int, int]:
    """Return the cells outside the full-width content column.

    Read off the mounted screen rather than its host, so one measurement
    serves a surface opened standalone and the same surface navigated to
    inside a shell.
    """
    screen = active.region
    column = active.query_one(".cadrumo-column", Vertical).region
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
    surface = build()
    app = CredentialHostApp(surface) if isinstance(surface, CredentialScreen) else surface
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        left, right = _gutters(pilot.app.screen)
        assert left == 0, f"left gutter at {width}x{height}: {left}"
        assert 0 <= right <= SCROLLBAR_CELLS, f"unused width at {width}x{height}: left={left} right={right}"
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_the_outer_scrollbar_does_not_reserve_permanent_side_gutters() -> None:
    """Only overflow may consume the single scrollbar cell.

    Read off a MOUNTED scroll container rather than the stylesheet text. The
    measures now resolve from design tokens, so asserting a literal spelling
    would prove which token was named and not the width the operator gets --
    and it would break on every token rename while a genuinely reserved
    gutter slipped through.
    """
    app = CredentialHostApp(_registration_screen())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scroll = pilot.app.screen.query_one(".cadrumo-scroll")
        assert scroll.styles.scrollbar_size_vertical == SCROLLBAR_CELLS
        assert scroll.styles.scrollbar_gutter != "stable", "a stable gutter reserves the cell even with no overflow"
        pilot.app.exit(None)


def test_no_stylesheet_carries_an_unsubstituted_token() -> None:
    """A misspelled token is invalid CSS, not a silently ignored declaration."""
    for stylesheet in (BASE_CSS, NOTICE_BAND_CSS):
        for name in re.findall(r"\$([a-z0-9-]+)", stylesheet):
            if name.startswith("cadrumo-"):
                assert name in CADRUMO_CSS_TOKENS, f"{name} is not a declared token"


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


# ── the design system is the only source of measure ─────────────────────────

_CSS_DECLARATION = re.compile(
    r"\b(padding|margin|border|border-top|border-bottom|border-left|border-right"
    r"|height|min-height|max-height|width|min-width|max-width): ([^;\n]+);",
)
_TUI_ROOT = Path(__file__).resolve().parents[1]

_STRUCTURAL_VALUES = frozenset({"auto", "100%", "1fr", "none", "hidden", "0"})
"""Values that describe topology rather than measure.

``auto``/``1fr``/``100%`` say "fill what is there", which is a layout
relationship and not a number the design system should own. ``none`` and
``hidden`` remove a treatment rather than choosing one.
"""


def _css_target(node: object) -> str | None:
    """Name of the stylesheet a node assigns, whether annotated or not."""
    import ast

    if isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    elif isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    else:
        return None
    if value is None or not isinstance(target, ast.Name):
        return None
    if target.id in {"CSS", "DEFAULT_CSS"} or target.id.endswith("_CSS"):
        return target.id
    return None


def _stylesheets() -> list[tuple[Path, str]]:
    """Every CSS string literal the shipped TUI declares.

    Collected through the AST so only real stylesheet constants are read: a
    regex over raw source would also sweep up prose in docstrings that happens
    to mention a CSS declaration.
    """
    import ast

    found: list[tuple[Path, str]] = []
    for path in sorted(_TUI_ROOT.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # AnnAssign as well as Assign: `BASE_CSS: Final[str] = ...` is how
            # the design system itself declares every stylesheet, so a
            # collector that only matched bare assignment skipped the one file
            # that matters most and passed vacuously.
            target = _css_target(node)
            if target is None or not isinstance(node, ast.AnnAssign | ast.Assign) or node.value is None:
                continue
            for literal in ast.walk(node.value):
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str) and "{" in literal.value:
                    found.append((path, literal.value))
    return found


def test_every_shipped_stylesheet_is_found_by_the_scan() -> None:
    """Anti-tautology: a scan that finds nothing would pass every rule below."""
    sheets = _stylesheets()
    assert len(sheets) >= 10, f"the stylesheet scan collected only {len(sheets)}"
    collected = {path.name for path, _body in sheets}
    assert "theme.py" in collected, "the design system's own stylesheets were not collected"
    assert any(".cadrumo-panel {" in body for _p, body in sheets), "BASE_CSS was not collected"


def _offending_declarations(body: str) -> list[str]:
    """Declarations in ``body`` whose value is a raw measure, not a token."""
    offenders = []
    for match in _CSS_DECLARATION.finditer(body):
        words = match.group(2).strip().split()
        if not all(word in _STRUCTURAL_VALUES or word.startswith("$") for word in words):
            offenders.append(f"{match.group(1)}: {match.group(2).strip()}")
    return offenders


def test_no_stylesheet_hardcodes_a_measure_the_token_table_should_own() -> None:
    """Spacing, borders and fixed sizes come from the design system, or not at all.

    This is what makes the token table canonical rather than merely present:
    without it, the next hurried edit puts ``margin: 0`` back and the system
    quietly stops describing the product.
    """
    offenders = [f"{path.name}: {found}" for path, body in _stylesheets() for found in _offending_declarations(body)]
    assert offenders == [], "hardcoded measures; declare them in CADRUMO_CSS_TOKENS:\n" + "\n".join(offenders)


def test_the_hardcoded_measure_scan_actually_fires() -> None:
    """Anti-tautology for the rule above, proved on a synthetic stylesheet."""
    assert _offending_declarations("Foo { padding: 0 1; }") == ["padding: 0 1"]
    assert _offending_declarations("Foo { border: round $primary; }") == ["border: round $primary"]
    assert _offending_declarations("Foo { padding: $cadrumo-gutter; height: auto; width: 100%; }") == []


def test_every_token_bearing_stylesheet_is_wrapped_in_the_resolver() -> None:
    """A stylesheet that names a token must resolve it before Textual sees it.

    Asserting that the RESOLVED string carries no ``$cadrumo-`` would be
    tautological, since that is what the resolver does by construction. The
    defect worth catching is the one a hurried edit actually causes: a new
    token added to a stylesheet whose assignment was never wrapped, which
    reaches Textual as an undefined variable and fails at mount.
    """
    import ast

    unwrapped: list[str] = []
    for path in sorted(_TUI_ROOT.rglob("*.py")):
        if "tests" in path.parts or path.name == "theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            target = _css_target(node)
            if target is None or not isinstance(node, ast.AnnAssign | ast.Assign) or node.value is None:
                continue
            segment = ast.get_source_segment(source, node.value) or ""
            if "$cadrumo-" in segment and "tokenised(" not in segment:
                unwrapped.append(f"{path.name}: {target}")

    assert unwrapped == [], "token-bearing stylesheets not passed through tokenised():\n" + "\n".join(unwrapped)


def test_the_resolver_refuses_a_token_it_does_not_declare() -> None:
    """A typo fails loudly at import, not as a mount error far from its cause."""
    assert tokenised("Foo { padding: $cadrumo-gutter; }") == "Foo { padding: 2; }"
    with pytest.raises(UnknownDesignTokenError):
        tokenised("Foo { padding: $cadrumo-guttter; }")
