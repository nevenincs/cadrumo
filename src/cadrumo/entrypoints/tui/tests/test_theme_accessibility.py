"""No meaning on the modelo workbench is carried by colour alone.

The property, stated so it is testable rather than aspirational: switching the
appearance may change how the workbench LOOKS and must change nothing a filer
has to READ or REACH. So the text it paints, the controls it mounts, and the
order those controls are reached in are compared between the two shipped
themes and must be identical. The state vocabulary exists for exactly this
reason: every origin and attention state has a glyph and words, so a colour
only ever repeats what is already written.

WHAT THIS PROVES, AND WHAT IT CANNOT: it proves appearance is not load-bearing
-- no glyph and no control appears, vanishes, changes wording or changes
position because of the theme. It cannot prove the palettes have enough
contrast; that is a property of the colours, not of the text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest

from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..components.theme import (
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
)
from ..modelo.workbench.installed import InstalledModeloWorkbench
from ..modelo.workbench.screen import ModeloWorkbenchScreen
from .modelo_workbench_session import real_workbench

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_THEMES = (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME)
_SURFACES = [
    pytest.param((), id="workbench"),
    pytest.param(("s",), id="sources"),
    pytest.param(("question_mark",), id="help"),
]
_TEXT_NODE = re.compile(r">([^<>]*)</text>")


@pytest.fixture(scope="module")
def workbench(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One seeded declaration, read-only for every assertion in this module."""
    root = tmp_path_factory.mktemp("themed")
    with real_workbench(root) as installed:
        yield installed


async def _observe(
    workbench: InstalledModeloWorkbench, keys: tuple[str, ...], theme: str
) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
    """Return the surface's readable glyphs and keyboard order under a theme.

    Read from the exported frame's text nodes: that is what the compositor put
    on the screen after layout and clipping, which is what a filer reads.
    Animation is off so a scroll never lands mid-way and differs by timing.
    """
    app = ScreenHostApp(ModeloWorkbenchScreen(workbench, actions=workbench))
    app.animation_level = "none"
    async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
        # The theme is set, then a fresh workbench is pushed, so its mount runs
        # under that theme rather than re-applying CSS to one mounted under the
        # default appearance -- which would make both observations identical.
        app.theme = theme
        await pilot.pause()
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        await app.push_screen(screen)
        for _ in range(200):
            await pilot.pause()
            if screen.form is not None:
                break
        assert screen.form is not None
        if keys:
            await pilot.press(*keys)
        await app.workers.wait_for_complete()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        await pilot.pause()
        glyphs = tuple(str(match.group(1)) for match in _TEXT_NODE.finditer(app.export_screenshot()))
        focus_ids: list[str | None] = []
        for widget in app.screen.focus_chain:
            widget_id = widget.id
            assert widget_id is None or isinstance(widget_id, str), f"a focusable widget reported {widget_id!r}"
            focus_ids.append(widget_id)
        app.exit(None)
    return glyphs, tuple(focus_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("keys", _SURFACES)
async def test_the_workbench_reads_and_navigates_identically_under_both_themes(
    keys: tuple[str, ...], workbench: InstalledModeloWorkbench
) -> None:
    """Appearance may change the palette; it may not change the content."""
    light_text, light_order = await _observe(workbench, keys, _THEMES[0])
    dark_text, dark_order = await _observe(workbench, keys, _THEMES[1])

    assert light_order == dark_order, f"a different keyboard order per theme: {light_order} vs {dark_order}"
    differing = [pair for pair in zip(light_text, dark_text, strict=False) if pair[0] != pair[1]]
    assert not differing, f"different text per theme, so colour is saying something words do not: {differing[:3]}"
    assert len(light_text) == len(dark_text), "a different number of painted text runs per theme"


def test_the_two_themes_are_actually_different_palettes() -> None:
    """The control for every assertion above: identical text across one theme twice proves nothing."""
    assert CADRUMO_LIGHT.name != CADRUMO_DARK.name, "the two appearances are one theme under two names"
    assert CADRUMO_LIGHT.dark != CADRUMO_DARK.dark, "both appearances declare the same lightness"
    assert CADRUMO_LIGHT.background != CADRUMO_DARK.background, (
        "the two appearances share a background, so switching between them changes nothing to compare"
    )
