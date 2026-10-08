"""The modelo workbench and its views, proven to fit the terminals we support.

WHY THIS IS A SEPARATE MODULE FROM ``test_visual_verification``, since a second
geometry suite is exactly the thing the shared size declaration exists to
prevent. It is not a second authority on WHICH sizes matter: it imports
``SUPPORTED_TERMINAL_SIZES`` and declares no size of its own. What differs is
fixture economy: a real workbench costs an isolated encrypted profile, a
seeded taxpayer, a created work unit and a full form read against the bundled
registry, so the declaration is built ONCE per address for the module and each
surface is mounted over it.

The surfaces are the workbench itself, its sources view and its expanded help,
each reached the way the filer reaches it. Two real addresses supply the
shapes: a compact quarterly return and a dense annual one whose labels are
long because the law names them at that length and whose pages run far past a
screen because the modelo declares that many boxes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widget import Widget

from ....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ..components.host import ScreenHostApp
from ..modelo.workbench.installed import InstalledModeloWorkbench
from ..modelo.workbench.screen import ModeloWorkbenchScreen
from ..modelo.workbench.sources import WorkbenchSourcesScreen
from .modelo_workbench_session import real_workbench

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZES = [
    pytest.param(size, id=size_id)
    for size, size_id in zip(SUPPORTED_TERMINAL_SIZES, SUPPORTED_TERMINAL_SIZE_IDS, strict=True)
]
_SURFACES = [
    pytest.param((), id="workbench"),
    pytest.param(("s",), id="sources"),
    pytest.param(("question_mark",), id="help"),
]
_ADDRESSES = [
    pytest.param({"modelo": "130", "filing_year": 2026, "period_code": "1T"}, id="compact"),
    pytest.param({"modelo": "100", "filing_year": 2024, "period_code": "0A"}, id="dense"),
]


@pytest.fixture(scope="module", params=_ADDRESSES)
def workbench(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """One real declaration per address, read-only for every assertion in this module."""
    root: Path = tmp_path_factory.mktemp("responsive")
    with real_workbench(root, **request.param) as installed:
        yield installed


async def _open(pilot: Pilot[None], screen: ModeloWorkbenchScreen, keys: tuple[str, ...]) -> None:
    """Wait for the form to be read, then reach the surface the way the filer does."""
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            break
    assert screen.form is not None, "the workbench never finished reading its declaration"
    if keys:
        await pilot.press(*keys)
    await pilot.pause()
    await pilot.pause()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("keys", _SURFACES)
async def test_a_surface_never_forces_the_terminal_to_scroll_sideways(
    keys: tuple[str, ...], size: tuple[int, int], workbench: InstalledModeloWorkbench
) -> None:
    """Content may run past the bottom; it must never run past the right edge.

    Horizontal overflow removes information rather than relocating it: the
    columns past the edge are unreachable. Asserted on mounted widths against
    the viewport, because a screenshot is clipped at the edge and looks the
    same whether the content fitted or was cut off.
    """
    width, _height = size
    screen = ModeloWorkbenchScreen(workbench, actions=workbench)
    app = ScreenHostApp(screen)
    async with app.run_test(size=size) as pilot:
        await _open(pilot, screen, keys)
        overflowing = [widget for widget in app.screen.query(Widget) if widget.display and widget.region.right > width]
        assert not overflowing, (
            f"{keys or 'workbench'} at {width} columns pushes "
            + ", ".join(f"{type(w).__name__}(id={w.id!r}) to x={w.region.right}" for w in overflowing[:5])
            + " past the right edge, where the filer cannot reach it"
        )
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("keys", _SURFACES)
async def test_a_surface_paints_its_content_at_every_supported_size(
    keys: tuple[str, ...], size: tuple[int, int], workbench: InstalledModeloWorkbench
) -> None:
    """A surface that mounts empty at the floor has failed, not adapted.

    The casilla list is the subject: a layout that resolves it to zero height
    raises nothing and renders a frame indistinguishable from one the filer
    has not scrolled.
    """
    screen = ModeloWorkbenchScreen(workbench, actions=workbench)
    app = ScreenHostApp(screen)
    async with app.run_test(size=size) as pilot:
        await _open(pilot, screen, keys)
        lists = [widget for widget in app.screen.query("CasillaList") if widget.display]
        assert lists, f"{keys or 'workbench'} shows no casilla list at {size}"
        assert all(widget.region.height > 0 and widget.region.width > 0 for widget in lists), (
            f"{keys or 'workbench'} collapses its casilla list to nothing at {size}"
        )
        assert "<text" in app.export_screenshot(), f"{keys or 'workbench'} rendered no text at {size}"
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("keys", _SURFACES)
async def test_every_control_stays_reachable_by_keyboard_at_the_floor(
    keys: tuple[str, ...], workbench: InstalledModeloWorkbench
) -> None:
    """At the smallest terminal, every displayed focusable control is in the focus chain."""
    screen = ModeloWorkbenchScreen(workbench, actions=workbench)
    app = ScreenHostApp(screen)
    async with app.run_test(size=SUPPORTED_TERMINAL_SIZES[0]) as pilot:
        await _open(pilot, screen, keys)
        focusable = [
            widget
            for widget in app.screen.query(Widget)
            if widget.focusable and all(node.display for node in widget.ancestors_with_self if node is not app)
        ]
        chain = list(app.screen.focus_chain)
        assert len(chain) == len(focusable), (
            f"{keys or 'workbench'} mounts {len(focusable)} focusable controls at the floor "
            f"but only {len(chain)} are in the focus chain, so the rest cannot be reached"
        )
        app.exit(None)


@pytest.mark.parametrize("surface", [ModeloWorkbenchScreen, WorkbenchSourcesScreen])
def test_every_declared_binding_names_an_action_that_exists(surface: type[Widget]) -> None:
    """A key bound to a missing action is offered to the filer and does nothing.

    Textual resolves ``action_<name>`` at press time, so the mismatch would be
    found by an operator rather than a suite unless the declaration is checked
    against the class. Parametrised actions are reduced to their method name.
    """
    unresolved = []
    for binding in getattr(surface, "BINDINGS", ()):
        action = getattr(binding, "action", None)
        if not isinstance(action, str) or "." in action:
            continue
        method = f"action_{action.split('(', 1)[0].strip()}"
        if not hasattr(surface, method):
            unresolved.append(f"{binding.key!r} -> {method}()")
    assert not unresolved, f"{surface.__name__} declares bindings whose actions do not exist: {', '.join(unresolved)}"
