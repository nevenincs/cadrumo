"""Focused contracts for the TUI workbench root."""

from __future__ import annotations

from typing import ClassVar, cast

import pytest
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from ....application.operations.composition import OperationComposedServices
from ....application.overview.home import HomeSessionPosture
from ....application.search.workbench import WorkbenchDestinationAdmissionState, WorkbenchSearchService
from ..app import CadrumoTuiApp
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..home import HomeScreen
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    DestinationUnavailableError,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class MarkerScreen(Screen[None]):
    """A destination body whose injected semantic context is observable."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context

    def action_close(self) -> None:
        """Dismiss through Textual's real child-screen return protocol."""
        self.dismiss(None)


def _catalogue(contexts: list[TuiScreenContextV1]) -> TuiDestinationCatalogueV1:
    """Build the complete admitted catalogue around one observable factory seam."""

    def factory(context: TuiScreenContextV1) -> Screen[None]:
        contexts.append(context)
        return MarkerScreen(context)

    admissions: dict[str, TuiDestinationAdmissionV1] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: factory for descriptor in TUI_DESTINATION_CATALOGUE
    }
    return build_destination_catalogue(admissions=admissions, factories=factories)


@pytest.mark.asyncio
async def test_child_dismissal_refreshes_home_and_restores_its_semantic_focus() -> None:
    """A real child return restores the selected Home identity rather than a row index."""
    contexts: list[TuiScreenContextV1] = []
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: projection,
    )
    target = TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger",
            semantic_key="ledger.entry",
            restore_token="a" * 64,
        ),
    )

    async with app.run_test() as pilot:
        initial_home = app.screen
        assert isinstance(initial_home, HomeScreen)
        assert len(app.screen_stack) == 2
        selected = initial_home.highlighted_target
        assert selected is not None

        await pilot.press("enter")
        await pilot.pause()
        assert initial_home.selected_target == selected

        app.navigate_to(target)
        await pilot.pause()

        assert isinstance(app.screen, MarkerScreen)
        assert app.screen.context == TuiScreenContextV1(destination="workbench.ledger", focus=target.focus)
        assert contexts == [app.screen.context]
        assert len(app.screen_stack) == 2

        await pilot.press("escape")
        await pilot.pause()

        returned_home = app.screen
        assert isinstance(returned_home, HomeScreen)
        assert returned_home.highlighted_target == selected
        assert len(app.screen_stack) == 2


@pytest.mark.asyncio
async def test_expired_child_return_locks_non_home_admission_and_refuses_navigation() -> None:
    """Expiry returns to Home and makes every non-Home route truthfully unavailable."""
    contexts: list[TuiScreenContextV1] = []
    ready = build_home_projection_fixture(HomeFixtureScenario.READY)
    expired = ready.model_copy(
        update={
            "account": ready.account.model_copy(
                update={"posture": HomeSessionPosture.EXPIRED, "profile_label": "Expired profile"}
            )
        }
    )
    projections = [ready, expired]
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: projections.pop(0),
    )

    async with app.run_test() as pilot:
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.declarations",
                focus=TuiFocusIdentityV1(destination="workbench.declarations", semantic_key="declaration.case"),
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, MarkerScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)
        assert app.screen.projection.account.posture is HomeSessionPosture.EXPIRED
        assert app.query_one("#root-account", Static).render() == "Expired profile"
        assert len(app.screen_stack) == 2
        assert app._active_target is None
        assert (
            app.destination_catalogue.resolve("workbench.home").admission.state
            is WorkbenchDestinationAdmissionState.AVAILABLE
        )
        assert all(
            route.admission.state is WorkbenchDestinationAdmissionState.LOCKED
            and route.admission.reason_code == "session.expired"
            and route.factory is None
            for route in app.destination_catalogue.routes
            if route.descriptor.destination != "workbench.home"
        )
        with pytest.raises(DestinationUnavailableError):
            app.navigate_to(
                TuiNavigationTargetV1(
                    destination="workbench.ledger",
                    focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
                )
            )
        assert app._active_target is None


@pytest.mark.asyncio
async def test_authoritative_child_return_rebuilds_the_injected_search_snapshot_once() -> None:
    """Search changes only at the explicit child-return lifecycle boundary."""
    contexts: list[TuiScreenContextV1] = []
    initial_search = WorkbenchSearchService(())
    refreshed_search = WorkbenchSearchService(())
    refreshes: list[WorkbenchSearchService] = []
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=initial_search,
        refresh_workbench_search=lambda: (refreshes.append(refreshed_search), refreshed_search)[1],
    )

    async with app.run_test() as pilot:
        assert app.workbench_search_service is initial_search
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.ledger",
                focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
            )
        )
        await pilot.pause()
        assert app.workbench_search_service is initial_search

        await pilot.press("escape")
        await pilot.pause()

    assert refreshes == [refreshed_search]
    assert app.workbench_search_service is refreshed_search


@pytest.mark.asyncio
async def test_failed_search_refresh_retains_last_good_service_and_sanitizes_refusal() -> None:
    """A bad refreshed projection cannot erase current search or leak its error."""
    contexts: list[TuiScreenContextV1] = []
    initial_search = WorkbenchSearchService(())

    def fail_refresh() -> WorkbenchSearchService:
        raise RuntimeError("12345678Z C:\\protected\\search.json")

    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=initial_search,
        refresh_workbench_search=fail_refresh,
    )

    async with app.run_test() as pilot:
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.ledger",
                focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
            )
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert app.workbench_search_service is initial_search
    assert app.workbench_search_refusal_code == "workbench.search.refresh_unavailable"
    assert "12345678Z" not in app.workbench_search_refusal_code
    assert "protected" not in app.workbench_search_refusal_code
