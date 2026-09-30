"""The review renders in colour whatever terminal preference the render was started under.

Textual draws every frame in monochrome when ``NO_COLOR`` is set, and many
automated shells export it. A render inheriting it would review surfaces whose
colour roles never appear, so the harness driver drops it. The test proves both
halves over the real harness: the variable really does strip the colour, and a
capture through the driver keeps it anyway.
"""

from __future__ import annotations

import colorsys
import os
import re
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command

from .. import _harness, _viewports
from .._artifacts import ThemeName

_SURFACE = "aeat-sync-overview--blocked"
_FILL = re.compile(r'fill[:=]\s*"?(#[0-9a-fA-F]{6})')
_WINDOW_CHROME = frozenset({"#ff5f57", "#febc2e", "#28c840"})
"""The exporter's own window buttons, which it paints whatever the app draws."""


def _painted_colours(svg: Path) -> set[str]:
    """The saturated colours the app itself painted into an exported frame."""
    found: set[str] = set()
    for colour in _FILL.findall(svg.read_text(encoding=UTF_8)):
        red, green, blue = (int(colour[index : index + 2], 16) / 255 for index in (1, 3, 5))
        _, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
        if saturation > 0.25 and 0.1 < lightness < 0.9 and colour.lower() not in _WINDOW_CHROME:
            found.add(colour.lower())
    return found


@pytest.mark.integration
@pytest.mark.hex_core
def test_a_render_started_under_no_color_still_paints_the_colour_roles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monochrome = tmp_path / "inherited.svg"
    opening = ("open", _SURFACE, "--size", "120x40", "--shot", str(monochrome))
    inherited = run_command(
        [sys.executable, "-m", _harness.HARNESS_MODULE, *opening],
        cwd=REPO_ROOT,
        environment={**os.environ, "PYTHONIOENCODING": UTF_8},
    )

    captured = _harness.capture(
        _SURFACE,
        _viewports.resolve("medium"),
        theme=ThemeName.DARK,
        svg_path=tmp_path / "driven.svg",
        workspace="colour-check",
    )

    assert inherited.returncode == 0, inherited.stderr
    assert not _painted_colours(monochrome), "NO_COLOR no longer strips colour, so this check proves nothing"
    assert _painted_colours(captured.svg_path)
