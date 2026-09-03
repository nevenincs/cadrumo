"""Focused contracts for the TUI workbench root."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar, cast

import pytest
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Static

from ....application.operations.composition import OperationComposedServices
from ....application.overview.home import HomeSessionPosture
from ....application.search.workbench import WorkbenchDestinationAdmissionState, WorkbenchSearchService
from ....application.user_profile.login_session import ProfileLoginOutcome
from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ....core.operations import OperationTerminalCondition
from ..account import (
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
)
from ..app import CadrumoTuiApp
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..home import HomeScreen
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
from ..operations.modal import OperationModalSettledOutcomeV1

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
async def test_expired_child_return_tears_down_profile_bound_doors_and_recomposes() -> None:
    """Expiry discards the complete old root before asking bootstrap to resume."""
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

        assert app.query_one("#root-account", Static).render() == "Expired profile"
        assert app._active_target is None
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        with pytest.raises(RuntimeError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(RuntimeError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_expired_custody_refresh_recomposes_without_rendering_a_stale_root() -> None:
    """A precise custody expiry becomes the same non-secret expiry handoff."""
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: (_ for _ in ()).throw(AccountSessionExpiredError()),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(HandoverScreen()),
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        assert app._account_factories is None
        with pytest.raises(RuntimeError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(RuntimeError, match="no composed workbench search"):
            _ = app.workbench_search_service


class HandoverScreen(Screen[ProfileLoginOutcome | None]):
    """A test door returning the same safe outcome as the existing Login owner."""


def _account_factories(
    change_user: Screen[ProfileLoginOutcome | None],
    *,
    password: Screen[ProfilePassphraseRotationOutcome | None] | None = None,
) -> AccountFactoriesV1:
    """Supply observable account doors without reproducing an account surface."""
    return cast(
        AccountFactoriesV1,
        SimpleNamespace(
            profile=lambda context: MarkerScreen(context),
            change_user=lambda: change_user,
            password=lambda: password or Screen(),
            appearance=lambda _app: "appearance.changed",
            language=lambda _screen: None,
            sign_out=lambda: None,
        ),
    )


@pytest.mark.asyncio
async def test_change_user_returns_typed_identity_and_revokes_old_profile_root() -> None:
    """A successful handover cannot leave the prior catalogue or search callable."""
    contexts: list[TuiScreenContextV1] = []
    new_profile_id = "11111111-1111-4111-8111-111111111111"
    authenticated_at = datetime(2026, 9, 3, tzinfo=UTC)
    outcome = ProfileLoginOutcome(
        bucket_id=new_profile_id,
        label="Profile two",
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(minutes=15),
        absolute_deadline=authenticated_at + timedelta(hours=8),
        session_persisted=False,
        already_authenticated=False,
        closed_previous_bucket_id="22222222-2222-4222-8222-222222222222",
    )
    handover = HandoverScreen()
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(handover),
    )

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one("#root-change-user", Button).press()
        await pilot.pause()
        assert app.screen is handover
        handover.dismiss(outcome)
        await pilot.pause()

        assert app.return_value == AccountRecomposeRequiredV1(
            reason=AccountRecomposeReasonV1.CHANGE_USER,
            profile_id=str(new_profile_id),
            profile_label="Profile two",
        )
        assert app._account_factories is None
        with pytest.raises(RuntimeError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(RuntimeError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_password_rotation_recomposes_before_the_old_session_root_can_be_reused() -> None:
    """A new custody generation cannot leave prior profile-bound doors live."""
    password = Screen[ProfilePassphraseRotationOutcome | None]()
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(HandoverScreen(), password=password),
    )
    outcome = ProfilePassphraseRotationOutcome(
        profile_id="11111111-1111-4111-8111-111111111111",
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=True,
    )

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one("#root-password", Button).press()
        await pilot.pause()
        assert app.screen is password
        password.dismiss(outcome)
        await pilot.pause()

        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)
        assert app._account_factories is None
        with pytest.raises(RuntimeError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(RuntimeError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_successful_sign_out_tears_down_root_but_refusal_does_not_claim_logout() -> None:
    """Only a canonical successful settlement authorizes signed-out recomposition."""
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(HandoverScreen()),
    )
    refused = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.REFUSED))
    )
    succeeded = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.SUCCEEDED))
    )

    async with app.run_test() as pilot:
        app._on_sign_out_dismissed(refused)
        assert app.return_value is None
        assert str(app.query_one("#root-account-refusal", Static).render())

        app._on_sign_out_dismissed(succeeded)
        await pilot.pause()
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.SIGNED_OUT)
        assert app._account_factories is None
        with pytest.raises(RuntimeError, match="no composed destination"):
            _ = app.destination_catalogue


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120])
async def test_account_header_is_keyboard_reachable_without_horizontal_overflow(width: int) -> None:
    """Every account utility remains a real focus target at supported widths."""
    app = CadrumoTuiApp(
        services=cast(OperationComposedServices, object()),
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(HandoverScreen()),
    )
    expected = {
        "root-change-user",
        "root-password",
        "root-profile",
        "root-appearance",
        "root-language",
        "root-sign-out",
    }

    async with app.run_test(size=(width, 24)) as pilot:
        await pilot.pause()
        buttons = list(app.query("#root-account-actions Button"))
        assert {button.id for button in buttons} == expected
        assert all(button.can_focus and not button.disabled for button in buttons)
        assert all(button.region.x >= 0 and button.region.right <= width for button in buttons)
        assert app.query_one("#root-account-bar").scrollable_content_region.width <= width


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
async def test_failed_search_refresh_retains_last_good_and_sanitizes_refusal() -> None:
    """A bad refreshed projection retains the last complete search generation."""
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

    assert app.workbench_search_refusal_code == "workbench.search.refresh_unavailable"
    assert app.workbench_search_service is initial_search
    assert "12345678Z" not in app.workbench_search_refusal_code
    assert "protected" not in app.workbench_search_refusal_code
