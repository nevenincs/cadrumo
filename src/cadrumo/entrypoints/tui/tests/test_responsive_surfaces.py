"""Every routed workspace destination, proven to fit the terminals we support.

WHY THIS IS A SEPARATE MODULE FROM ``test_visual_verification``, since a second
geometry suite is exactly the thing the shared size declaration exists to
prevent. It is not a second authority on WHICH sizes matter: it imports
``SUPPORTED_TERMINAL_SIZES`` and declares no size of its own, so there is one
answer to that question and this module is not it. What differs is fixture
economy. The visual suite's surfaces are per-test context managers, and a real
workspace session costs an isolated encrypted profile, a seeded taxpayer, a
created work unit and a full static-inspection resolution against the bundled
registry. Enrolling six destinations there would pay that cost once per
destination per size per test. Here the session is built ONCE for the module
and every destination mounts against it.

WHAT THIS COVERS THAT NOTHING DID. The visual suite enrols nine surfaces, and
of the six routed workspace destinations exactly zero are among them --
``modelo-review`` is the bounded review screen the picker used to reach, not a
workspace destination. So every destination an operator actually lands on after
selecting a work unit had no geometry proof at any size.

The destinations are read from ``MODELO_WORKSPACE_DESTINATIONS`` rather than
listed here. A hand-written list would be correct about itself and silent about
a seventh destination, which is the failure mode this campaign has already
recorded more than once; taking the route table means a new destination is
covered the moment it is routed, and a destination removed from the table stops
being asserted about rather than failing as a stale name.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.widget import Widget

from ....tests.modelo_workspace_session import real_workspace_inspection_result
from ....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ..components.host import ScreenHostApp
from ..modelo.routes import MODELO_WORKSPACE_DESTINATIONS
from ..modelo.view.controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..modelo.view.models import ModeloWorkspaceDestinationIdV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZES = [
    pytest.param(size, id=size_id)
    for size, size_id in zip(SUPPORTED_TERMINAL_SIZES, SUPPORTED_TERMINAL_SIZE_IDS, strict=True)
]
_DESTINATIONS = [
    pytest.param(destination_id, id=destination_id.rsplit(".", 1)[-1])
    for destination_id in MODELO_WORKSPACE_DESTINATIONS
]


_ADDRESSES = [
    pytest.param({"modelo": "130", "filing_year": 2026, "period_code": "1T"}, id="compact"),
    pytest.param({"modelo": "100", "filing_year": 2024, "period_code": "0A"}, id="dense"),
]
"""Two real addresses, chosen for the SHAPE of the content they produce.

The compact quarterly return is the ordinary case. The dense annual return is
this suite's long-labels, deep-sections and paged-rows stimulus, and it is a
REAL address rather than a padded fixture: its labels are long because the law
names them at that length, and its rows run past a page because the modelo
declares that many. A fixture padded with invented rows would prove the layout
against content the product never renders, which is a proof about the fixture.
"""


@pytest.fixture(scope="module", params=_ADDRESSES)
def workspace_session(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """One admitted workspace session per address, shared across destinations.

    Module-scoped deliberately. The session is read-only for every assertion
    here -- nothing mounted mutates it -- so rebuilding it per test would buy
    isolation nothing uses and cost an encrypted profile build each time.
    """
    root: Path = tmp_path_factory.mktemp("responsive")
    with real_workspace_inspection_result(root, **request.param) as seeded:
        session, refusal = admit_workspace_session(seeded.result)
        assert refusal is None, f"expected an admitted projection, got: {refusal}"
        assert session is not None
        yield session


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("destination_id", _DESTINATIONS)
async def test_a_destination_never_forces_the_terminal_to_scroll_sideways(
    destination_id: ModeloWorkspaceDestinationIdV1,
    size: tuple[int, int],
    workspace_session: ModeloWorkspaceReadSession,
) -> None:
    """Content may run past the bottom; it must never run past the right edge.

    Vertical overflow is ordinary and scrollable. HORIZONTAL overflow is not:
    the columns past the edge are unreachable, so a table that overruns its
    width silently removes information rather than relocating it. Asserted on
    the mounted widths against the viewport rather than on a rendered
    screenshot, because a screenshot is clipped at the edge and therefore looks
    identical whether the content fitted or was cut off.
    """
    width, _height = size
    screen = MODELO_WORKSPACE_DESTINATIONS[destination_id](workspace_session)
    app = ScreenHostApp(screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        overflowing = [widget for widget in app.screen.query(Widget) if widget.display and widget.region.right > width]
        assert not overflowing, (
            f"{destination_id} at {width} columns pushes "
            + ", ".join(f"{type(w).__name__}(id={w.id!r}) to x={w.region.right}" for w in overflowing[:5])
            + " past the right edge, where the operator cannot reach it"
        )
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("destination_id", _DESTINATIONS)
async def test_a_destination_paints_something_at_every_supported_size(
    destination_id: ModeloWorkspaceDestinationIdV1,
    size: tuple[int, int],
    workspace_session: ModeloWorkspaceReadSession,
) -> None:
    """A destination that mounts empty at the floor has failed, not adapted.

    The failure this catches is a layout that resolves every region to zero
    height at a small terminal: it raises nothing, renders a blank frame, and
    is indistinguishable from a screen the operator simply has not scrolled.
    """
    screen = MODELO_WORKSPACE_DESTINATIONS[destination_id](workspace_session)
    app = ScreenHostApp(screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        painted = [
            widget
            for widget in app.screen.query(Widget)
            if widget.display and widget.region.height > 0 and widget.region.width > 0
        ]
        assert painted, f"{destination_id} painted no widget with area at {size}"
        rendered = app.export_screenshot()
        assert "<text" in rendered, f"{destination_id} rendered no text at {size}"
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("destination_id", _DESTINATIONS)
async def test_every_control_stays_reachable_by_keyboard_at_the_floor(
    destination_id: ModeloWorkspaceDestinationIdV1,
    workspace_session: ModeloWorkspaceReadSession,
) -> None:
    """At the smallest terminal, a focusable control must still be focusable.

    The floor is where a control gets pushed out of the layout rather than
    merely crowded, and a control that is mounted but unreachable reads to
    every other gate as present. Tabbing is the operator's only route to it, so
    the focus chain is the thing that has to hold, not the mount.
    """
    screen = MODELO_WORKSPACE_DESTINATIONS[destination_id](workspace_session)
    app = ScreenHostApp(screen)
    async with app.run_test(size=SUPPORTED_TERMINAL_SIZES[0]) as pilot:
        await pilot.pause()
        focusable = [widget for widget in app.screen.query(Widget) if widget.focusable]
        chain = list(app.screen.focus_chain)
        assert len(chain) == len(focusable), (
            f"{destination_id} mounts {len(focusable)} focusable controls at the floor "
            f"but only {len(chain)} are in the focus chain, so the rest cannot be reached"
        )
        app.exit(None)


@pytest.mark.parametrize("destination_id", _DESTINATIONS)
def test_every_declared_binding_names_an_action_that_exists(
    destination_id: ModeloWorkspaceDestinationIdV1,
    workspace_session: ModeloWorkspaceReadSession,
) -> None:
    """A key bound to a missing action is offered to the operator and does nothing.

    This is the affordance equivalent of a dangling import, and no other gate
    in the tree can see it: the binding is well-formed, the footer advertises
    it, the screen mounts, every geometry and render check passes, and the key
    silently does nothing when pressed. Textual resolves ``action_<name>`` at
    PRESS time, so the mismatch is discovered by an operator rather than by a
    suite -- unless something checks the declaration against the class.

    Namespaced actions (``app.quit``) and parametrised ones (``toggle('x')``)
    are reduced to their bare method name before the lookup, because that is
    the name the resolver will actually seek.
    """
    screen = MODELO_WORKSPACE_DESTINATIONS[destination_id](workspace_session)
    unresolved = []
    for binding in getattr(type(screen), "BINDINGS", ()):
        action = getattr(binding, "action", None)
        if not isinstance(action, str) or "." in action:
            continue
        method = f"action_{action.split('(', 1)[0].strip()}"
        if not hasattr(screen, method):
            unresolved.append(f"{binding.key!r} -> {method}()")
    assert not unresolved, f"{destination_id} declares bindings whose actions do not exist: {', '.join(unresolved)}"
