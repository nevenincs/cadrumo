"""The operator's journey from choosing an entry to classifying it.

Every other Ledger test builds the controller it wants and asserts on one
screen.  That proves the pieces and not the journey: the workspace's whole
reason to exist is that a selection made on the entries body is still the
selection after the body has been replaced by another one.  Nothing exercised
that, which is how the selection channel came to be written, deleted, and left
with a reader and no writer without a single test turning red.

These tests drive the real path -- select a row, then choose an area from the
navigation table -- under a host that swaps bodies exactly the way the
production root does, including the deferral onto the host's own message pump.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.widgets import DataTable, Static

from .....application.ledger.workspace import LedgerWorkspaceArea
from ....tui.components.host import ScreenHostApp
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController, ledger_copy
from ..entries import LedgerEntriesScreen
from ..routes import LedgerUnavailableScreen, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_flows import _ClassificationDoor, _classify_action
from .test_ledger_workspace import _context, _projection, _review_action

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.screen import Screen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NAVIGATION_ROWS = tuple(LedgerWorkspaceArea)


class _WorkspaceHostApp(ScreenHostApp[None]):
    """A host that replaces a workspace body the way the production root does.

    The deferral is the point.  Textual dispatches a screen's result callback
    through whichever message pump was active when that screen was pushed, so
    pushing a replacement from inside the outgoing screen's own handler
    registers the return journey against a pump that is about to stop.  The
    root defers the swap onto its own pump for exactly that reason, and a host
    that pushed directly would pass this test while production stranded the
    operator.  Mirroring the deferral keeps the proof honest.
    """

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Defer the swap onto this host's pump, as the root shell does."""
        self.call_next(self._replace_workspace_body, screen)

    def _replace_workspace_body(self, screen: Screen[None]) -> None:
        """Discard the outgoing body before mounting exactly one replacement."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen, self.exit)


def _entries_screen(*, door: _ClassificationDoor) -> LedgerEntriesScreen:
    """The entries body a newly-opened workspace shows, with no row chosen yet."""
    return LedgerEntriesScreen(
        LedgerWorkspaceController(
            _context(),
            _projection(),
            LedgerWorkspaceInjection(
                review_action=_review_action(),
                classify_action=_classify_action(),
                classification_submitter=door,
            ),
        )
    )


async def _choose_area(pilot: Pilot[None], screen: LedgerEntriesScreen, area: LedgerWorkspaceArea) -> None:
    """Select ``area`` from the navigation table as the operator would."""
    navigation = screen.query_one("#ledger-navigation", DataTable)
    navigation.focus()
    navigation.move_cursor(row=_NAVIGATION_ROWS.index(area))
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_a_chosen_entry_survives_the_body_swap_into_classification() -> None:
    """Choosing a row then choosing classification reaches the real screen."""
    door = _ClassificationDoor()
    screen = _entries_screen(door=door)
    app = _WorkspaceHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        entries = screen.query_one("#ledger-entries", DataTable)
        entries.focus()
        entries.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause()
        chosen = screen.controller.classification_target
        assert chosen == _projection().entries[0].transaction_id

        await _choose_area(pilot, screen, LedgerWorkspaceArea.CLASSIFICATION)
        await pilot.pause()
        body = app.screen
        assert isinstance(body, LedgerClassificationScreen), (
            f"the chosen entry did not survive the body swap; the operator reached {type(body).__name__}"
        )
        assert body.controller.classification_target == chosen


@pytest.mark.asyncio
async def test_without_a_chosen_entry_classification_refuses_and_says_why() -> None:
    """The control: the same journey without the selection is refused."""
    screen = _entries_screen(door=_ClassificationDoor())
    app = _WorkspaceHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert screen.controller.classification_target is None

        await _choose_area(pilot, screen, LedgerWorkspaceArea.CLASSIFICATION)
        await pilot.pause()
        assert app.screen is screen, "an unreachable area must not replace the body"
        notice = str(screen.query_one("#ledger-refusal", Static).render())
        assert notice == ledger_copy("tui.ledger.refusal.selection_required")
        assert notice != ledger_copy("tui.ledger.refusal.submission_unavailable")


def test_the_refused_classification_body_names_the_missing_selection() -> None:
    """Resolving the area unchosen yields the refusal screen, not the task."""
    screen = _entries_screen(door=_ClassificationDoor())
    controller = screen.controller
    refused = resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.CLASSIFICATION))
    assert isinstance(refused, LedgerUnavailableScreen)
    assert refused.refusal is not None
    assert refused.refusal.reason_key == "tui.ledger.refusal.selection_required"

    focused = controller.with_transaction_focus(_projection().entries[0].transaction_id)
    assert isinstance(
        resolve_ledger_screen(focused, focused.route_target(LedgerWorkspaceArea.CLASSIFICATION)),
        LedgerClassificationScreen,
    )
