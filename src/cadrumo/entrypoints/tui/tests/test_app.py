"""Focused contracts for the TUI workbench root."""

from __future__ import annotations

from typing import ClassVar, cast

import pytest
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from ....application.operations.composition import OperationComposedServices
from ....application.overview.home import HomeSessionPosture
from ....application.search.workbench import WorkbenchDestinationAdmissionState
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
