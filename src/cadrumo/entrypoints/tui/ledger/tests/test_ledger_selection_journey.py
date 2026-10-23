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
from .....core.i18n.render import tr
from ...tests.settling import settle
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController
from ..entries import LedgerEntriesScreen
from ..routes import LedgerUnavailableScreen, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import (
    ClassificationDoor,
    WorkspaceHostApp,
    ledger_classify_action,
    ledger_context,
    ledger_projection,
    ledger_review_action,
)

if TYPE_CHECKING:
    from textual.pilot import Pilot

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NAVIGATION_ROWS = tuple(LedgerWorkspaceArea)


def _entries_screen(*, door: ClassificationDoor) -> LedgerEntriesScreen:
    """The entries body a newly-opened workspace shows, with no row chosen yet."""
    return LedgerEntriesScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(
                review_action=ledger_review_action(),
                classify_action=ledger_classify_action(),
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
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_chosen_entry_survives_the_body_swap_into_classification() -> None:
    """Choosing a row then choosing classification reaches the real screen."""
    door = ClassificationDoor()
    screen = _entries_screen(door=door)
    app = WorkspaceHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        entries = screen.query_one("#ledger-entries", DataTable)
        entries.focus()
        entries.move_cursor(row=0)
        await pilot.press("enter")
        await settle(pilot)
        chosen = screen.controller.classification_target
        assert chosen == ledger_projection().entries[0].transaction_id

        await _choose_area(pilot, screen, LedgerWorkspaceArea.CLASSIFICATION)
        await settle(pilot)
        body = app.screen
        assert isinstance(body, LedgerClassificationScreen), (
            f"the chosen entry did not survive the body swap; the operator reached {type(body).__name__}"
        )
        assert body.controller.classification_target == chosen


@pytest.mark.asyncio
async def test_without_a_chosen_entry_classification_refuses_and_says_why() -> None:
    """The control: the same journey without the selection is refused."""
    screen = _entries_screen(door=ClassificationDoor())
    app = WorkspaceHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        assert screen.controller.classification_target is None

        await _choose_area(pilot, screen, LedgerWorkspaceArea.CLASSIFICATION)
        await settle(pilot)
        assert app.screen is screen, "an unreachable area must not replace the body"
        notice = str(screen.query_one("#ledger-refusal", Static).render())
        assert notice == tr("tui.ledger.refusal.selection_required")
        assert notice != tr("tui.ledger.refusal.submission_unavailable")


def test_the_refused_classification_body_names_the_missing_selection() -> None:
    """Resolving the area unchosen yields the refusal screen, not the task."""
    screen = _entries_screen(door=ClassificationDoor())
    controller = screen.controller
    refused = resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.CLASSIFICATION))
    assert isinstance(refused, LedgerUnavailableScreen)
    assert refused.refusal is not None
    assert refused.refusal.reason_key == "tui.ledger.refusal.selection_required"

    focused = controller.with_transaction_focus(ledger_projection().entries[0].transaction_id)
    assert isinstance(
        resolve_ledger_screen(focused, focused.route_target(LedgerWorkspaceArea.CLASSIFICATION)),
        LedgerClassificationScreen,
    )
