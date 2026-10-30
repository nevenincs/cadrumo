"""TUI presentation behavior for the installed activity-asset action door."""

from __future__ import annotations

import re
from datetime import date
from threading import Event

import pytest
from textual.widgets import Button, Input, Static

from .....application.calculations.actividad_asset_schedule import vehicle_affectation_verdict
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.operations import OperationEffect
from .....domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetValidationError,
    VehicleAffectationRecovery,
)
from .....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from .....domain.renta.actividad_asset.schedule import AssetScheduleHistory
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...operations.outcome import OperationOutcomeUnknownError, SessionExpiredOutcomeUnknownError
from ...tests.settling import SettleTimeoutError, settle, settle_until
from ..actividad_asset import ActivityAssetScreen
from ..controller import LedgerWorkspaceController
from ..models_actividad_asset import ActivityAssetCreationRequestV1, ActivityAssetForecastRequestV1
from ..workspace_injection import LedgerWorkspaceInjection
from .actividad_asset_fixtures import ActivityAssetActionStub, activity_asset_forecast, activity_asset_revision
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _screen(actions: ActivityAssetActionStub) -> ActivityAssetScreen:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), activity_asset_actions=actions),
    )
    return ActivityAssetScreen(controller)


async def _wait_for_screen_result(*, pilot, screen: ActivityAssetScreen, expected_prefix: str) -> str:
    """Wait for one public worker result from the screen."""
    rendered = ""

    def published() -> bool:
        nonlocal rendered
        rendered = str(screen.query_one("#asset-result", Static).render()).strip()
        return rendered.startswith(expected_prefix)

    try:
        await settle_until(pilot, published, f"the activity-asset result {expected_prefix!r}")
    except SettleTimeoutError as late:
        raise AssertionError(
            f"activity-asset TUI did not publish {expected_prefix!r}; last result: {rendered!r}"
        ) from late
    return rendered


async def _wait_for_current_revision_id(*, pilot, screen: ActivityAssetScreen) -> str:
    """Read the screen's public immutable revision identity."""
    match: re.Match[str] | None = None

    def exposed() -> bool:
        nonlocal match
        rendered = str(screen.query_one("#asset-current-revision-id", Static).render()).strip()
        match = re.fullmatch(r"current_revision_id\t([0-9a-f]{64})", rendered)
        return match is not None

    try:
        await settle_until(pilot, exposed, "the activity-asset revision identity")
    except SettleTimeoutError as late:
        raise AssertionError("activity-asset TUI did not expose the immutable revision identity") from late
    assert match is not None
    return str(match.group(1))


async def _activate(*, pilot, screen: ActivityAssetScreen, selector: str) -> None:
    name = screen.query_one("#asset-name", Input)
    if selector == "#asset-create" and not name.value:
        name.value = "Office laptop"
    button = screen.query_one(selector, Button)
    button.focus()
    await pilot.press("enter")
    await settle(pilot)


@pytest.mark.asyncio
async def test_activity_asset_screen_dispatches_typed_requests_and_renders_worker_projection() -> None:
    revision = activity_asset_revision("tui-runtime-screen")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="created\ttui-runtime-screen")
        assert await _wait_for_current_revision_id(pilot=pilot, screen=screen) == revision.revision_id

        screen.query_one("#asset-covered-from", Input).value = "2025-01-01"
        screen.query_one("#asset-covered-until", Input).value = "2026-01-01"
        await _activate(pilot=pilot, screen=screen, selector="#asset-forecast")
        rendered = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="forecast\t")
        assert rendered.startswith("forecast\t520.00\tTUI screen fixture only")

    assert [name for name, _request in actions.requests] == ["create", "forecast"]
    assert isinstance(actions.requests[0][1], ActivityAssetCreationRequestV1)
    assert isinstance(actions.requests[1][1], ActivityAssetForecastRequestV1)


@pytest.mark.asyncio
async def test_activity_asset_screen_clears_private_facts_when_the_session_is_lost() -> None:
    revision = activity_asset_revision("expired-screen")
    actions = ActivityAssetActionStub(revision, create_error=AccountSessionExpiredError())
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        for selector in (
            "#asset-id",
            "#asset-revision-json",
            "#asset-free-amount",
            "#asset-covered-from",
            "#asset-covered-until",
            "#asset-supersedes-claim-id",
            "#asset-name",
            "#asset-filing-tax-year",
            "#asset-filing-m130-period",
        ):
            screen.query_one(selector, Input).value = "private fixture"
        screen.query_one("#asset-current-revision-id", Static).update(f"current_revision_id\t{revision.revision_id}")
        screen._last_forecast = activity_asset_forecast(
            revision,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            history=AssetScheduleHistory(),
            requested_free_amount=None,
        )
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused") == "refused"
        assert screen._last_forecast is None
        assert screen._last_forecast_supersedes is None
        assert all(
            not screen.query_one(selector, Input).value
            for selector in (
                "#asset-id",
                "#asset-revision-json",
                "#asset-free-amount",
                "#asset-covered-from",
                "#asset-covered-until",
                "#asset-supersedes-claim-id",
                "#asset-name",
                "#asset-filing-tax-year",
                "#asset-filing-m130-period",
            )
        )
        assert str(screen.query_one("#asset-current-revision-id", Static).render()).strip() == ""


@pytest.mark.asyncio
async def test_an_activity_asset_write_whose_outcome_is_unknown_is_not_reported_as_refused() -> None:
    revision = activity_asset_revision("unknown-outcome")
    unknown = OperationOutcomeUnknownError(operation_id="f" * 64, effect=OperationEffect.UNKNOWN)
    actions = ActivityAssetActionStub(revision, create_error=unknown)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 35)) as pilot:
            screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
            await _activate(pilot=pilot, screen=screen, selector="#asset-create")
            rendered = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="unknown\t")
            assert rendered == f"unknown\t{resolve_error_message(unknown)}"
            assert "refused" not in rendered


@pytest.mark.asyncio
async def test_activity_asset_refusal_retains_the_registered_recovery_presentation() -> None:
    revision = activity_asset_revision("undeclared-van")
    recovery = VehicleAffectationRecovery(
        asset_id=revision.asset_id,
        revision_id=revision.revision_id,
        class_key="transporte",
    )
    refusal = ActividadAssetIncompleteError(
        f"activity asset {revision.asset_id!r} requires a vehicle affectation declaration",
        precondition_verdict=vehicle_affectation_verdict(recovery),
        vehicle_affectation_recovery=recovery,
    )
    actions = ActivityAssetActionStub(revision, forecast_error=refusal)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-covered-from", Input).value = "2025-01-01"
        screen.query_one("#asset-covered-until", Input).value = "2026-01-01"
        await _activate(pilot=pilot, screen=screen, selector="#asset-forecast")
        rejected = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused\t")
        assert "undeclared-van" in rejected
        assert str(screen.query_one("#asset-recovery", Static).render()).strip() == (
            "recovery\toperator.ledger.actividad_asset.correct_revision"
            f"\tasset\tundeclared-van\trevision\t{revision.revision_id}"
        )
        assert screen.focused is screen.query_one("#asset-correct", Button)


@pytest.mark.asyncio
async def test_activity_asset_screen_clears_old_result_while_action_runs() -> None:
    revision = activity_asset_revision("pending-public-result")
    worker_entered = Event()
    release_worker = Event()
    actions = ActivityAssetActionStub(revision, create_started=worker_entered, create_release=release_worker)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        screen.query_one("#asset-name", Input).value = "Office laptop"
        screen.query_one("#asset-result", Static).update("claim\tfixture\treused=false")
        button = screen.query_one("#asset-create", Button)
        button.press()
        try:
            await settle_until(pilot, worker_entered.is_set, "the creation to reach its action", workers=False)
            # The action runs in a worker, so the screen keeps answering while it is out.
            await settle(pilot, workers=False)
            assert str(screen.query_one("#asset-result", Static).render()).strip() == "pending\tasset-create"
            assert screen.in_flight
            # A second press while one action is out does not queue another behind it.
            button.press()
            await settle(pilot, workers=False)
            assert [name for name, _request in actions.requests] == ["create"]
        finally:
            release_worker.set()
        await settle(pilot)
        assert not screen.in_flight
        assert str(screen.query_one("#asset-result", Static).render()).strip() == (
            "created\tpending-public-result\trevisions=1"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("covered_from", "free_amount"),
    (
        ("20250101", ""),
        ("2025-W01-3", ""),
        ("2025-01-01", "NaN"),
        ("2025-01-01", "1e3"),
        ("2025-01-01", "+5"),
        ("2025-01-01", "1_000"),
    ),
)
async def test_activity_asset_forecast_refuses_the_shapes_the_command_line_refuses(
    covered_from: str, free_amount: str
) -> None:
    revision = activity_asset_revision("tui-runtime-shape")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-covered-from", Input).value = covered_from
        screen.query_one("#asset-covered-until", Input).value = "2026-01-01"
        screen.query_one("#asset-free-amount", Input).value = free_amount
        await _activate(pilot=pilot, screen=screen, selector="#asset-forecast")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused\t")

    assert actions.requests == []


_WRITE_BUTTONS = ("#asset-create", "#asset-correct", "#asset-claim", "#asset-describe")


def _writes_disabled(screen: ActivityAssetScreen) -> list[bool]:
    return [screen.query_one(selector, Button).disabled for selector in _WRITE_BUTTONS]


@pytest.mark.asyncio
async def test_an_activity_asset_write_whose_outcome_is_unknown_is_offered_again_only_over_a_reread_asset() -> None:
    revision = activity_asset_revision("unknown-then-reread")
    unknown = OperationOutcomeUnknownError(operation_id="f" * 64, effect=OperationEffect.UPDATED)
    actions = ActivityAssetActionStub(revision, create_error=unknown)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="unknown\t")

        # The asset may already be created: no write is offered over the asset as last read.
        assert _writes_disabled(screen) == [True, True, True, True]
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        assert [name for name, _request in actions.requests] == ["create"]

        await _activate(pilot=pilot, screen=screen, selector="#asset-inspect")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset\tunknown-then-reread")
        assert _writes_disabled(screen) == [False, False, False, False]

        actions.create_error = None
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="created\t")

    assert [name for name, _request in actions.requests] == ["create", "inspect", "create"]


@pytest.mark.asyncio
async def test_an_activity_asset_write_whose_outcome_is_unknown_is_released_only_by_reading_that_asset() -> None:
    revision = activity_asset_revision("held-asset")
    unknown = OperationOutcomeUnknownError(operation_id="f" * 64, effect=OperationEffect.UNKNOWN)
    actions = ActivityAssetActionStub(revision, create_error=unknown)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="unknown	")
        assert _writes_disabled(screen) == [True, True, True, True]

        # Reading another asset says nothing about whether the held creation landed.
        screen.query_one("#asset-id", Input).value = "another-asset"
        # Pressed directly: a key press on a button still showing its last press is ignored.
        screen.query_one("#asset-inspect", Button).press()
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset	another-asset")
        assert _writes_disabled(screen) == [True, True, True, True]

        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-inspect", Button).press()
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset	held-asset")
        assert _writes_disabled(screen) == [False, False, False, False]

    assert actions.requests[1:] == [("inspect", "another-asset"), ("inspect", "held-asset")]


@pytest.mark.asyncio
async def test_an_activity_asset_write_whose_outcome_is_unknown_stays_withheld_when_the_reread_is_refused() -> None:
    revision = activity_asset_revision("unknown-reread-refused")
    unknown = OperationOutcomeUnknownError(operation_id="f" * 64, effect=OperationEffect.UNKNOWN)
    actions = ActivityAssetActionStub(
        revision,
        create_error=unknown,
        inspect_error=ActividadAssetValidationError("activity asset could not be read"),
    )
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="unknown\t")
        await _activate(pilot=pilot, screen=screen, selector="#asset-inspect")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused\t")

        assert _writes_disabled(screen) == [True, True, True, True]


@pytest.mark.asyncio
async def test_an_activity_asset_write_whose_session_is_lost_with_its_outcome_unknown_is_not_reported_as_refused() -> (
    None
):
    revision = activity_asset_revision("lost-unknown")
    lost = SessionExpiredOutcomeUnknownError(
        OperationOutcomeUnknownError(operation_id="e" * 64, effect=OperationEffect.UPDATED)
    )
    actions = ActivityAssetActionStub(revision, create_error=lost)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 35)) as pilot:
            screen.query_one("#asset-id", Input).value = revision.asset_id
            screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
            await _activate(pilot=pilot, screen=screen, selector="#asset-create")
            rendered = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="unknown\t")

            assert rendered == f"unknown\t{resolve_error_message(lost)}"
            assert "e" * 64 in rendered
            # The private facts still go with the lost session.
            assert not screen.query_one("#asset-id", Input).value
            assert not screen.query_one("#asset-revision-json", Input).value
            assert _writes_disabled(screen) == [True, True, True, True]


@pytest.mark.asyncio
async def test_activity_asset_screen_reaches_describe_and_every_register_read() -> None:
    revision = activity_asset_revision("tui-register-reads")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 60)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-name", Input).value = "Renamed laptop"
        screen.query_one("#asset-serial", Input).value = "SN-2"
        await _activate(pilot=pilot, screen=screen, selector="#asset-describe")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="described\ttui-register-reads")

        await _activate(pilot=pilot, screen=screen, selector="#asset-plan")
        plan = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="equipo-informacion-software")
        assert "2035-01-01" in plan
        assert "2025\t520.00\t0.00\tnot_due" in plan
        assert "2036\tperiod_elapsed\t0.00\tnot_due" in plan

    assert actions.requests[0] == (
        "describe",
        (revision.asset_id, ActivityAssetDescriptorFacts(name="Renamed laptop", serial_number="SN-2")),
    )
    assert actions.requests[1] == ("plan", revision.asset_id)
