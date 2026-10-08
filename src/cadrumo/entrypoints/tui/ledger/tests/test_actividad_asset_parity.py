"""TUI presentation behavior for the installed activity-asset action door."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from decimal import Decimal
from threading import Event

import pytest
from textual.widgets import Button, Input, Static

from cadrumo.application.actividad_asset.history import ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetFilingHandoff
from cadrumo.application.calculations.actividad_asset_schedule import vehicle_affectation_verdict
from cadrumo.domain.renta.actividad_asset.claims import ClaimProjection
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    VehicleAffectationRecovery,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.actividad_asset import ActivityAssetScreen
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
    ActivityAssetFilingRequestV1,
    ActivityAssetForecastRequestV1,
    ActivityAssetInspectionV1,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection

from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _revision(asset_id: str) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="1" * 64,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="2" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000"),
            prior_allocation_provenance="ledger allocation source",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-informacion-software",
        ),
    )


def _forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="tui-screen-fixture-v1",
            source_reference="TUI screen fixture only",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


class _ActionStub:
    """Supply typed screen responses without reopening profile services."""

    def __init__(
        self,
        revision: ActivityAssetRevision,
        *,
        forecast_error: Exception | None = None,
        create_started: Event | None = None,
        create_release: Event | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self.revision = revision
        self.forecast_error = forecast_error
        self.create_started = create_started
        self.create_release = create_release
        self.create_error = create_error
        self.requests: list[tuple[str, object]] = []

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        self.requests.append(("create", request))
        if self.create_started is not None:
            self.create_started.set()
        if self.create_release is not None and not self.create_release.wait(timeout=2.0):
            raise RuntimeError("test action was not released")
        if self.create_error is not None:
            raise self.create_error
        return ActivityAssetInspectionV1(asset_id=request.revision.asset_id, revisions=(request.revision,))

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        self.requests.append(("inspect", asset_id))
        return ActivityAssetInspectionV1(asset_id=asset_id, revisions=(self.revision,))

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        self.requests.append(("correct", request))
        return ActivityAssetInspectionV1(asset_id=request.revision.asset_id, revisions=(request.revision,))

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        self.requests.append(("forecast", request))
        if self.forecast_error is not None:
            raise self.forecast_error
        history = AssetScheduleHistory()
        return _forecast(
            self.revision,
            covered_from=request.covered_from,
            covered_until=request.covered_until,
            history=history,
            requested_free_amount=request.requested_free_amount,
        )

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        self.requests.append(("record_claim", request))
        raise AssertionError("this screen test does not exercise claim execution")

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        self.requests.append(("filing_handoff", request))
        return ActivityAssetFilingHandoff(
            material_m100=ClaimProjection(
                target_casilla_id="0113", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
            intangible_m100=ClaimProjection(
                target_casilla_id="0114", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
            material_m130=ClaimProjection(
                target_casilla_id="0120", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
            intangible_m130=ClaimProjection(
                target_casilla_id="0121", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
        )


def _screen(actions: _ActionStub) -> ActivityAssetScreen:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), activity_asset_actions=actions),
    )
    return ActivityAssetScreen(controller)


async def _wait_for_screen_result(*, pilot, screen: ActivityAssetScreen, expected_prefix: str) -> str:
    """Wait for one public worker result from the screen."""
    rendered = ""
    for _ in range(180):
        rendered = str(screen.query_one("#asset-result", Static).render()).strip()
        if rendered.startswith(expected_prefix):
            return rendered
        await pilot.pause()
    raise AssertionError(f"activity-asset TUI did not publish {expected_prefix!r}; last result: {rendered!r}")


async def _wait_for_current_revision_id(*, pilot, screen: ActivityAssetScreen) -> str:
    """Read the screen's public immutable revision identity."""
    for _ in range(180):
        rendered = str(screen.query_one("#asset-current-revision-id", Static).render()).strip()
        match = re.fullmatch(r"current_revision_id\t([0-9a-f]{64})", rendered)
        if match is not None:
            return str(match.group(1))
        await pilot.pause()
    raise AssertionError("activity-asset TUI did not expose the immutable revision identity")


async def _activate(*, pilot, screen: ActivityAssetScreen, selector: str) -> None:
    button = screen.query_one(selector, Button)
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_activity_asset_screen_dispatches_typed_requests_and_renders_worker_projection() -> None:
    revision = _revision("tui-runtime-screen")
    actions = _ActionStub(revision)
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
    revision = _revision("expired-screen")
    actions = _ActionStub(revision, create_error=AccountSessionExpiredError())
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
            "#asset-creating-operation",
            "#asset-filing-tax-year",
            "#asset-filing-m130-period",
        ):
            screen.query_one(selector, Input).value = "private fixture"
        screen.query_one("#asset-current-revision-id", Static).update(f"current_revision_id\t{revision.revision_id}")
        screen._last_forecast = _forecast(
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
                "#asset-creating-operation",
                "#asset-filing-tax-year",
                "#asset-filing-m130-period",
            )
        )
        assert str(screen.query_one("#asset-current-revision-id", Static).render()).strip() == ""


@pytest.mark.asyncio
async def test_activity_asset_refusal_retains_the_registered_recovery_presentation() -> None:
    revision = _revision("undeclared-van")
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
    actions = _ActionStub(revision, forecast_error=refusal)
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
    revision = _revision("pending-public-result")
    worker_entered = Event()
    release_worker = Event()
    actions = _ActionStub(revision, create_started=worker_entered, create_release=release_worker)
    screen = _screen(actions)
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        screen.query_one("#asset-result", Static).update("claim\tfixture\treused=false")
        button = screen.query_one("#asset-create", Button)
        handler = asyncio.create_task(screen.on_button_pressed(Button.Pressed(button)))
        try:
            assert await asyncio.to_thread(worker_entered.wait, 1.0)
            await pilot.pause()
            assert str(screen.query_one("#asset-result", Static).render()).strip() == "pending\tasset-create"
        finally:
            release_worker.set()
        await handler
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
    revision = _revision("tui-runtime-shape")
    actions = _ActionStub(revision)
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
