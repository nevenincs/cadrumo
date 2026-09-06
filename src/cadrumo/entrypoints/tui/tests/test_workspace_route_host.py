"""The installed root and a real workspace, joined by a real keypress.

Every other test in this tree sits on one side of this join. The root's own
tests run the real application against stub screens and move between them by
calling ``navigate_to`` in Python; the workspace tests build real screens and
mount them under the single-screen host, then assert an attribute the screen
set on itself just before posting its message. Both pass whether or not any
host consumes that message, because neither one ever has a real workspace
screen and a real root in the same process.

That gap is not hypothetical. It is exactly how the workspaces came to post
``*RouteRequested`` into a void: navigation looked proven from both sides
while an operator pressing Enter on a navigation row got silence and no
feedback. So this test deliberately uses no stub on either side -- the real
``CadrumoTuiApp``, the real ledger factory, and ``pilot.press`` rather than a
method call -- because a substitute at either end restores the blind spot it
exists to remove.
"""

from __future__ import annotations

from typing import cast

import pytest
from textual.widgets import DataTable, Static

from ....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from ....application.operations.composition import OperationComposedServices
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....core.identity import TransactionId
from ..app import CadrumoTuiApp
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..home import HomeScreen
from ..ledger.entries import LedgerEntriesScreen
from ..ledger.overview import LedgerOverviewScreen
from ..ledger.review import LedgerReviewScreen
from ..ledger.routes import ledger_screen_factory
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEDGER_TARGET = TuiNavigationTargetV1(
    destination="workbench.ledger",
    focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
)


_ENTRY = LedgerWorkspaceEntryRefV1(
    transaction_id=cast("TransactionId", "a" * 64),
    review_status="pending",
    date="2026-03-14",
    amount="1250.00",
    currency="EUR",
    direction="outgoing",
    counterparty="Suministros Delta SL",
    description="Material de oficina",
    business_classification="business",
)


def _projection() -> LedgerWorkspaceProjectionV1:
    """Every area available, so a refusal cannot stand in for a working route."""
    return LedgerWorkspaceProjectionV1(
        bucket_id="synthetic-bucket",
        areas=tuple(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                availability=LedgerWorkspaceAvailability.AVAILABLE,
                reason_code=None,
                status=LedgerWorkspaceStatus.NEEDS_ATTENTION,
                item_count=1,
            )
            for area in LedgerWorkspaceArea
        ),
        entries=(_ENTRY,),
        review_transaction_ids=(_ENTRY.transaction_id,),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def _catalogue() -> TuiDestinationCatalogueV1:
    """Admit the whole catalogue, but give Ledger its real production factory."""
    review_action = ActionReference(action_id=lookup_action("operator.ledger.review").action_id)
    ledger_factory = ledger_screen_factory(_projection(), review_action=review_action)

    def absent(context: TuiScreenContextV1) -> None:
        raise AssertionError(f"no other destination should be built by this test: {context.destination}")

    admissions = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: cast("TuiScreenFactoryV1", absent) for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories["workbench.ledger"] = ledger_factory
    return build_destination_catalogue(admissions=admissions, factories=factories)


def _app() -> CadrumoTuiApp:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    return CadrumoTuiApp(
        services=cast("OperationComposedServices", object()),
        destination_catalogue=_catalogue(),
        refresh_home=lambda: projection,
    )


@pytest.mark.asyncio
async def test_enter_on_a_navigation_row_reaches_the_named_area() -> None:
    """The keypress an operator actually makes must change the mounted body."""
    app = _app()
    async with app.run_test() as pilot:
        app.navigate_to(_LEDGER_TARGET)
        await pilot.pause()
        assert isinstance(app.screen, LedgerOverviewScreen)

        table = cast("DataTable[str]", app.screen.query_one("#ledger-navigation", DataTable))
        table.focus()
        # The catalogue is emitted in canonical area order, so one row below
        # Overview is Entries. Moving the cursor rather than indexing keeps the
        # test honest about what the operator does.
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, LedgerEntriesScreen), (
            "Enter on the Entries row left the operator on "
            f"{type(app.screen).__name__}; the route message reached no host."
        )
        assert len(app.screen_stack) == 2, "replacing a workspace body must not deepen the stack"


@pytest.mark.asyncio
async def test_selecting_a_review_row_reports_the_pending_state() -> None:
    """A selection with no consumer must say so; silence reads as a dead key."""
    app = _app()
    async with app.run_test() as pilot:
        app.navigate_to(_LEDGER_TARGET)
        await pilot.pause()
        table = cast("DataTable[str]", app.screen.query_one("#ledger-navigation", DataTable))
        table.focus()
        # Overview, Entries, then Review in canonical area order.
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        review = app.screen
        assert isinstance(review, LedgerReviewScreen)

        rows = cast("DataTable[str]", review.query_one("#ledger-review", DataTable))
        rows.focus()
        await pilot.press("enter")
        await pilot.pause()

        notice = str(review.query_one("#ledger-refusal", Static).render())
        assert notice, "selecting a review row produced no visible outcome at all"


@pytest.mark.asyncio
async def test_escape_from_an_internal_area_returns_to_home() -> None:
    """A replaced body keeps the destination's return journey, it does not nest."""
    app = _app()
    async with app.run_test() as pilot:
        app.navigate_to(_LEDGER_TARGET)
        await pilot.pause()
        table = cast("DataTable[str]", app.screen.query_one("#ledger-navigation", DataTable))
        table.focus()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LedgerEntriesScreen)

        await pilot.press("escape")
        # The return crosses several pumps: the binding posts, the screen
        # dismisses, and the root's deferred callback rebuilds and pushes Home.
        # Settling once only reaches the dismissal, so this waits for the end
        # state rather than the first observable step.
        for _ in range(4):
            await pilot.pause()

        assert isinstance(app.screen, HomeScreen), (
            f"Escape from an internal Ledger area left the operator on {type(app.screen).__name__}"
        )
        assert len(app.screen_stack) == 2
