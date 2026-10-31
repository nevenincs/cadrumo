"""TUI presentation behavior for the installed activity-asset action door."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from threading import Event

import pytest
from textual.widgets import Button, Input, Static

from .....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from .....application.calculations.actividad_asset_schedule import vehicle_affectation_verdict
from .....application.operations.public_scalar import PublicDecimal
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....core.operations import OperationEffect
from .....domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason
from .....domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetValidationError,
    VehicleAffectationRecovery,
)
from .....domain.renta.actividad_asset.lifecycle import AssetKind
from .....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from .....domain.renta.actividad_asset.schedule import AssetScheduleHistory
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...operations.outcome import OperationOutcomeUnknownError, SessionExpiredOutcomeUnknownError
from ...tests.settling import SettleTimeoutError, settle, settle_until
from ..actividad_asset import ActivityAssetScreen
from ..actividad_asset_inputs import stated_revision
from ..controller import LedgerWorkspaceController
from ..models_actividad_asset import ActivityAssetCreationRequestV1, ActivityAssetForecastRequestV1
from ..workspace_injection import LedgerWorkspaceInjection
from .actividad_asset_fixtures import (
    ActivityAssetActionStub,
    activity_asset_forecast,
    activity_asset_form_options,
    activity_asset_list_rows,
    activity_asset_revision,
    activity_asset_timeline_events,
)
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

_EURO = "\N{NO-BREAK SPACE}\N{EURO SIGN}"

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


_WRITE_BUTTONS = ("#asset-create", "#asset-correct", "#asset-claim", "#asset-describe", "#asset-dispose")


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
        assert _writes_disabled(screen) == [True, True, True, True, True]
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        assert [name for name, _request in actions.requests] == ["create"]

        await _activate(pilot=pilot, screen=screen, selector="#asset-inspect")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset\tunknown-then-reread")
        assert _writes_disabled(screen) == [False, False, False, False, False]

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
        assert _writes_disabled(screen) == [True, True, True, True, True]

        # Reading another asset says nothing about whether the held creation landed.
        screen.query_one("#asset-id", Input).value = "another-asset"
        # Pressed directly: a key press on a button still showing its last press is ignored.
        screen.query_one("#asset-inspect", Button).press()
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset	another-asset")
        assert _writes_disabled(screen) == [True, True, True, True, True]

        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-inspect", Button).press()
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset	held-asset")
        assert _writes_disabled(screen) == [False, False, False, False, False]

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

        assert _writes_disabled(screen) == [True, True, True, True, True]


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
            assert _writes_disabled(screen) == [True, True, True, True, True]


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
        plan = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Information equipment")
        assert "31/12/2034" in plan
        assert "equipo-informacion-software" not in plan

    assert actions.requests[0] == (
        "describe",
        (revision.asset_id, ActivityAssetDescriptorFacts(name="Renamed laptop", serial_number="SN-2")),
    )
    assert actions.requests[1] == ("plan", revision.asset_id)


@pytest.mark.asyncio
async def test_activity_asset_plan_labels_the_minimum_amortization_and_flags_an_incomplete_one() -> None:
    revision = activity_asset_revision("tui-plan-minimum")
    screen = _screen(ActivityAssetActionStub(revision))
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            screen.query_one("#asset-id", Input).value = revision.asset_id
            await _activate(pilot=pilot, screen=screen, selector="#asset-plan")
            plan = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Information equipment")
        label = tr("tui.ledger.activity_asset.plan_minimum")
        incomplete = tr("tui.ledger.activity_asset.plan_minimum_incomplete")

    lines = plan.splitlines()
    # Only the year that omitted a year's minimum says so.
    assert any(line.startswith("2025") and f"{label}: 130.00" in line and incomplete not in line for line in lines)
    assert any(line.startswith("2036") and f"{label}: 130.00{_EURO} ({incomplete})" in line for line in lines)


@pytest.mark.asyncio
async def test_activity_asset_plan_says_each_year_in_words_with_its_glyph_and_remedy() -> None:
    revision = activity_asset_revision("tui-plan-words")
    screen = _screen(ActivityAssetActionStub(revision))
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            screen.query_one("#asset-id", Input).value = revision.asset_id
            await _activate(pilot=pilot, screen=screen, selector="#asset-plan")
            plan = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Information equipment")
        remedy = tr(
            "desktop.ledger.assets.opening_unknown",
            field=tr("ledger.actividad_asset.field.opening_history.accumulated_amount"),
        )
        not_applicable = tr("desktop.ledger.assets.mark.not_applicable")
        missing = tr("ledger.actividad_asset.claim_state.missing")
        history_missing = tr("ledger.actividad_asset.errors.opening_history_missing")

    lines = {line.split("\t")[0]: line for line in plan.splitlines()[1:]}
    assert f"! {missing}" in lines["2025"]
    assert "Maximum period elapsed" in lines["2036"]
    # The incomplete year says why in the register's sentence, and names the entry that settles it.
    assert history_missing in lines["2037"]
    assert remedy in lines["2037"]
    # A year with nothing to work out says it does not apply instead of reading as a missing figure.
    assert not_applicable in lines["2038"]
    assert "basis_exhausted" not in plan
    assert "period_elapsed" not in plan
    assert "not_due" not in plan


@pytest.mark.asyncio
async def test_activity_asset_list_does_not_read_a_pending_that_does_not_apply_as_money_owed() -> None:
    revision = activity_asset_revision("tui-list")
    actions = ActivityAssetActionStub(revision, list_rows=activity_asset_list_rows(), register_default_year=2027)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            await _activate(pilot=pilot, screen=screen, selector="#asset-list")
            listing = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Office laptop")
        not_applicable = tr("desktop.ledger.assets.mark.not_applicable")
        in_service = tr("ledger.actividad_asset.register_state.in_service")
        remedy = tr(
            "desktop.ledger.assets.opening_unknown",
            field=tr("ledger.actividad_asset.field.opening_history.accumulated_amount"),
        )

    rows = {line.split("\t")[-1]: line for line in listing.splitlines()}
    assert "1,480.00" in rows["laptop"]
    assert "[!] 2" in rows["laptop"]
    assert remedy in rows["desk"]
    assert in_service in rows["desk"]
    assert not_applicable in rows["printer"]
    assert "900" not in rows["printer"]
    assert "30/06/2026" in rows["printer"]
    assert "in_service" not in listing
    assert "out_of_service" not in listing


@pytest.mark.asyncio
async def test_activity_asset_timeline_says_what_each_record_did_and_changed() -> None:
    revision = activity_asset_revision("tui-timeline")
    actions = ActivityAssetActionStub(revision, timeline_events=activity_asset_timeline_events())
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            screen.query_one("#asset-id", Input).value = revision.asset_id
            await _activate(pilot=pilot, screen=screen, selector="#asset-timeline")
            timeline = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="1\t")
        created = tr("ledger.actividad_asset.event_kind.created")
        corrected = tr("ledger.actividad_asset.event_kind.corrected")
        method = tr("ledger.actividad_asset.field.amortization.method")
        linear = tr("ledger.actividad_asset.method.linear")
        not_recorded = tr("desktop.ledger.assets.timeline.time_not_recorded")
        no_changes = tr("desktop.ledger.assets.timeline.no_changes")
        not_in_calculation = tr("desktop.ledger.assets.timeline.not_in_calculation")

    first, second = timeline.splitlines()
    assert created in first
    assert no_changes in first
    assert corrected in second
    assert not_recorded in second
    assert not_in_calculation in second
    assert f"{method}: {linear}" in second
    assert "15/03/2025" in second
    assert "record-one" not in timeline
    assert "record-two" not in timeline
    assert "constant_percentage" not in timeline


@pytest.mark.asyncio
async def test_activity_asset_screen_opens_with_no_dates_year_or_quarter_of_its_own() -> None:
    revision = activity_asset_revision("tui-no-defaults")
    screen = _screen(ActivityAssetActionStub(revision))
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 60)):
        for selector in (
            "#asset-covered-from",
            "#asset-covered-until",
            "#asset-filing-tax-year",
            "#asset-filing-m130-period",
        ):
            assert screen.query_one(selector, Input).value == ""


@pytest.mark.asyncio
async def test_activity_asset_reads_fill_the_year_and_the_claim_dates_but_leave_the_quarter_to_the_operator() -> None:
    revision = activity_asset_revision("laptop")
    options = activity_asset_form_options(m130_periods=("1T", "2T", "3T"))
    actions = ActivityAssetActionStub(
        revision, list_rows=activity_asset_list_rows(), register_default_year=2031, form_options_view=options
    )
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            await _activate(pilot=pilot, screen=screen, selector="#asset-list")
            await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Office laptop")
            assert screen.query_one("#asset-filing-tax-year", Input).value == "2031"

            screen.query_one("#asset-id", Input).value = "laptop"
            await _activate(pilot=pilot, screen=screen, selector="#asset-plan")
            await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Information equipment")
            assert screen.query_one("#asset-covered-from", Input).value == "2025-01-01"
            assert screen.query_one("#asset-covered-until", Input).value == "2026-01-01"

            await _activate(pilot=pilot, screen=screen, selector="#asset-form-options")
            shown = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Method")
            # The served quarters are listed, and none is chosen for the operator.
            assert "1T, 2T, 3T" in shown
            assert screen.query_one("#asset-filing-m130-period", Input).value == ""
            assert "methods=" not in shown
            assert "edition=" not in shown
            assert "fixture-edition" not in shown

    assert ("form_options", (AssetKind.MATERIAL, 2031)) in actions.requests


@pytest.mark.asyncio
async def test_activity_asset_reads_leave_what_the_operator_typed() -> None:
    revision = activity_asset_revision("laptop")
    actions = ActivityAssetActionStub(revision, list_rows=activity_asset_list_rows(), register_default_year=2031)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 60)) as pilot:
        screen.query_one("#asset-filing-tax-year", Input).value = "2029"
        await _activate(pilot=pilot, screen=screen, selector="#asset-list")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="Office laptop")
        assert screen.query_one("#asset-filing-tax-year", Input).value == "2029"


@pytest.mark.asyncio
async def test_activity_asset_filing_without_a_year_asks_for_one_instead_of_reading_an_empty_number() -> None:
    revision = activity_asset_revision("tui-no-year")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            await _activate(pilot=pilot, screen=screen, selector="#asset-filing-handoff")
            refused = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused")
        asked = tr("desktop.ledger.assets.filing.choose_year")

    assert asked in refused
    assert not [name for name, _ in actions.requests if name == "filing_handoff"]


@pytest.mark.asyncio
async def test_activity_asset_screen_records_a_baja_and_reads_its_figures() -> None:
    revision = activity_asset_revision("tui-baja")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 70)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-disposal-date", Input).value = "2026-06-30"
        screen.query_one("#asset-disposal-reason", Input).value = "sale"
        screen.query_one("#asset-disposal-proceeds", Input).value = "2000.00"
        screen.query_one("#asset-disposal-costs", Input).value = "100.00"
        await _activate(pilot=pilot, screen=screen, selector="#asset-disposal-calculate")
        figures = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="disposal\t")
        assert figures == "disposal\tnet_value=1222.14\texcess=0.00\tresult=677.86"

        await _activate(pilot=pilot, screen=screen, selector="#asset-dispose")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="disposed\ttui-baja")

    stated = ActivityAssetDisposalSnapshot(
        disposal_date=date(2026, 6, 30),
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=PublicDecimal(decimal="2000.00"),
        transmission_costs=PublicDecimal(decimal="100.00"),
    )
    assert actions.requests == [
        ("disposal_calculate", (revision.asset_id, stated)),
        ("dispose", (revision.asset_id, stated)),
    ]


@pytest.mark.asyncio
async def test_activity_asset_creation_takes_the_typed_facts_over_the_revision_it_carries() -> None:
    revision = activity_asset_revision("tui-typed-facts")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 70)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        screen.query_one("#asset-price", Input).value = "1.500,00"
        screen.query_one("#asset-non-deductible-iva", Input).value = "315.00"
        screen.query_one("#asset-in-service-date", Input).value = "2025-03-01"
        screen.query_one("#asset-method", Input).value = "linear"
        screen.query_one("#asset-serial", Input).value = "SN-1"
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="created\ttui-typed-facts")

    created = actions.requests[0][1]
    assert isinstance(created, ActivityAssetCreationRequestV1)
    assert created.revision.basis.basis_amount == Decimal("1500.00")
    assert created.revision.basis.non_deductible_iva == Decimal("315.00")
    assert created.revision.in_service_date == date(2025, 3, 1)
    assert created.revision.amortization.method.value == "linear"
    assert created.descriptor == ActivityAssetDescriptorFacts(name="Office laptop", serial_number="SN-1")


@pytest.mark.asyncio
async def test_activity_asset_creation_leaves_a_fact_left_empty_as_the_revision_states_it() -> None:
    revision = activity_asset_revision("tui-untyped-facts")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 70)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="created\ttui-untyped-facts")

    created = actions.requests[0][1]
    assert isinstance(created, ActivityAssetCreationRequestV1)
    assert created.revision == revision


@pytest.mark.asyncio
async def test_activity_asset_creation_refuses_an_ambiguous_price_without_calling_the_door() -> None:
    revision = activity_asset_revision("tui-ambiguous-price")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 70)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        screen.query_one("#asset-price", Input).value = "1.5.0"
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused\t")

    assert actions.requests == []


@pytest.mark.asyncio
async def test_activity_asset_creation_shows_the_refusal_of_a_method_the_revision_cannot_carry() -> None:
    revision = activity_asset_revision("tui-method-refused")
    actions = ActivityAssetActionStub(revision)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 70)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        screen.query_one("#asset-method", Input).value = "sum_of_digits"
        await _activate(pilot=pilot, screen=screen, selector="#asset-create")
        shown = await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="refused	")

    assert shown == f"refused\t{tr('ledger.actividad_asset.errors.election_requires_fact')}"
    assert actions.requests == []


def test_stated_method_keeps_the_registered_missing_fact_for_presentation() -> None:
    revision = activity_asset_revision("tui-method-fact")

    with pytest.raises(ActividadAssetValidationError) as refused:
        stated_revision(lambda name: "sum_of_digits" if name == "asset-method" else "", revision.model_dump_json())

    assert refused.value.translated_message == "ledger.actividad_asset.errors.election_requires_fact"
    assert refused.value.context == {"method": "sum_of_digits", "field": "sum_of_digits_period_years"}
