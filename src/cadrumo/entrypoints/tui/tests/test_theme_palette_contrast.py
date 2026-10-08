"""Each shipped palette keeps its roles readable and apart.

Colour never carries meaning on its own in the TUI (every state has a glyph and
words), but it is what a filer's eye goes to first, so the attention scale only
works if its colours are unmistakable. Measured with the WCAG 2 relative
luminance and contrast ratio, per theme:

* every role colour a surface paints as text reads at 4.5:1 or better on the
  theme background, and some text colour does on every filled role;
* the error colour stands apart from the brand's primary and accent, either by
  at least 30 degrees of hue or, where the hues are close, by 1.8:1 of contrast,
  and warning is at least 20 degrees from error, so a heading drawn in the brand
  colour can never pass for a blocker. Hue is what separates two colours that
  must both read on one background: their luminance cannot differ much.

The checks are shown to bite: the terracotta palette the TUI shipped before,
whose primary sat within a few degrees of its error red, fails them.
"""

from __future__ import annotations

import colorsys
import math
from collections.abc import Mapping
from dataclasses import dataclass

import pytest
from textual.theme import Theme

from ..components.theme import CADRUMO_DARK, CADRUMO_LIGHT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TEXT_MINIMUM = 4.5
_ERROR_HUE_GAP = 30.0
_ERROR_CONTRAST_GAP = 1.8
_WARNING_HUE_GAP = 20.0
_TEXT_ROLES = ("foreground", "secondary", "primary", "accent", "success", "warning", "error")
_FILLED_ROLES = ("primary", "accent", "error", "warning", "success")


@dataclass(frozen=True, slots=True)
class Palette:
    """The role colours one appearance paints with."""

    name: str
    colours: Mapping[str, str]


def _palette(theme: Theme) -> Palette:
    colours = {role: str(getattr(theme, role)) for role in (*_TEXT_ROLES, "background")}
    return Palette(name=theme.name, colours=colours)


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    value = hex_colour.lstrip("#")
    return (int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255)


def _luminance(hex_colour: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

    r, g, b = (channel(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first: str, second: str) -> float:
    """The WCAG 2 contrast ratio between two colours."""
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _hue(hex_colour: str) -> float:
    return colorsys.rgb_to_hls(*_rgb(hex_colour))[0] * 360


def hue_gap(first: str, second: str) -> float:
    """The shorter way round the colour wheel between two hues, in degrees."""
    gap = abs(_hue(first) - _hue(second)) % 360
    return min(gap, 360 - gap)


def palette_problems(palette: Palette) -> list[str]:
    """Every way the palette falls short of readable, separable roles."""
    colours = palette.colours
    background = colours["background"]
    problems: list[str] = []
    for role in _TEXT_ROLES:
        ratio = contrast(colours[role], background)
        if ratio < _TEXT_MINIMUM:
            problems.append(f"{palette.name}: {role} text reads at {ratio:.2f}:1 on the background")
    for role in _FILLED_ROLES:
        best = max(contrast(colours[role], text) for text in (background, colours["foreground"], "#ffffff"))
        if best < _TEXT_MINIMUM:
            problems.append(f"{palette.name}: no text reads at {_TEXT_MINIMUM}:1 on a {role} fill")
    for brand in ("primary", "accent"):
        gap = hue_gap(colours["error"], colours[brand])
        ratio = contrast(colours["error"], colours[brand])
        if gap < _ERROR_HUE_GAP and ratio < _ERROR_CONTRAST_GAP:
            problems.append(
                f"{palette.name}: error is {gap:.1f} degrees and only {ratio:.2f}:1 from {brand}, so they read as one"
            )
    gap = hue_gap(colours["warning"], colours["error"])
    if gap < _WARNING_HUE_GAP:
        problems.append(f"{palette.name}: warning is {gap:.1f} degrees from error")
    return problems


@pytest.mark.parametrize("theme", [CADRUMO_LIGHT, CADRUMO_DARK], ids=lambda theme: theme.name)
def test_every_role_reads_and_the_attention_colours_stand_apart(theme: Theme) -> None:
    assert palette_problems(_palette(theme)) == []


@pytest.mark.parametrize("theme", [CADRUMO_LIGHT, CADRUMO_DARK], ids=lambda theme: theme.name)
def test_the_input_cursor_and_footer_keys_are_readable(theme: Theme) -> None:
    variables = theme.variables
    assert contrast(variables["input-cursor-background"], variables["input-cursor-foreground"]) >= _TEXT_MINIMUM
    assert contrast(variables["footer-key-foreground"], str(theme.background)) >= _TEXT_MINIMUM


_TERRACOTTA = {
    "light": Palette(
        name="terracotta-light",
        colours={
            "background": "#faf8f4",
            "foreground": "#1c1a17",
            "secondary": "#6b655c",
            "primary": "#c4553b",
            "accent": "#a8452f",
            "success": "#3f6f5b",
            "warning": "#845d1d",
            "error": "#a33322",
        },
    ),
    "dark": Palette(
        name="terracotta-dark",
        colours={
            "background": "#1a1815",
            "foreground": "#ece7dd",
            "secondary": "#a89e90",
            "primary": "#d9694e",
            "accent": "#e07d5f",
            "success": "#7fb096",
            "warning": "#d9a441",
            "error": "#f26c52",
        },
    ),
}


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_the_check_refuses_a_brand_colour_that_passes_for_an_error(appearance: str) -> None:
    problems = palette_problems(_TERRACOTTA[appearance])

    assert any("from primary, so they read as one" in problem for problem in problems), problems
    assert any("from accent, so they read as one" in problem for problem in problems), problems
