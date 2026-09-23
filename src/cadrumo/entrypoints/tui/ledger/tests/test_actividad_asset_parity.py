"""TUI parity with the shared activity-asset application operations.

The CLI adapter delegates every command to the same operations object; the
installed acceptance journeys prove the real CLI and TUI processes against
one encrypted store in both continuation directions.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from decimal import Decimal
from threading import Event

import pytest
from textual.widgets import Button, Input, Static

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
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
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.actividad_asset import ActivityAssetScreen, ActivityAssetTuiActionsV1
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.models_actividad_asset import (
    ActivityAssetCreationRequestV1,
    ActivityAssetForecastRequestV1,
)
from cadrumo.entrypoints.tui.ledger.routes import actividad_asset_tui_actions
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection

from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _simplified() -> DirectEstimationRegime:
    return DirectEstimationRegime.SIMPLIFIED


class _MemoryRepository:
    def __init__(self) -> None:
        self.history = ActivityAssetHistory()

    def load(self) -> ActivityAssetHistory:
        return self.history

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        self.history = self.history.append_revision(revision)
        return self.history

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        result = self.history.record_claim(claim)
        self.history = result.history
        return result


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
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="irpf-2025-assets-test-v1",
            source_reference="AEAT simplified direct-estimation table 2025",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


async def _wait_for_screen_result(
    *,
    pilot,
    screen: ActivityAssetScreen,
    expected_prefix: str,
    expected_suffix: str | None = None,
) -> str:
    """Wait for the public result text produced by one background screen action."""
    rendered = ""
    for _ in range(180):
        rendered = str(screen.query_one("#asset-result", Static).render())
        if rendered.startswith(expected_prefix) and (expected_suffix is None or rendered.endswith(expected_suffix)):
            return rendered
        await pilot.pause()
    raise AssertionError(f"activity-asset TUI did not publish {expected_prefix!r}; last public result: {rendered!r}")


async def _wait_for_current_revision_id(*, pilot, screen: ActivityAssetScreen) -> str:
    """Read the current revision through the screen's public immutable-ID projection."""
    for _ in range(180):
        rendered = str(screen.query_one("#asset-current-revision-id", Static).render())
        match = re.fullmatch(r"current_revision_id\t([0-9a-f]{64})", rendered)
        if match is not None:
            return str(match.group(1))
        await pilot.pause()
    raise AssertionError("activity-asset TUI did not expose the current immutable revision identity")


async def _activate_screen_button(*, pilot, screen: ActivityAssetScreen, selector: str) -> None:
    """Use the public keyboard activation path for a screen button."""
    button = screen.query_one(selector, Button)
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


def test_shared_operations_and_tui_continue_each_others_assets() -> None:
    operations_repository = _MemoryRepository()
    shared_operations = ActivityAssetOperations(
        repository=operations_repository, forecast_operation=_forecast, taxpayer_modality=_simplified
    )
    tui_after_operations = ActivityAssetTuiActionsV1(operations=shared_operations)
    operations_revision = _revision("created-by-shared-operation")

    shared_operations.create(operations_revision)
    assert tui_after_operations.inspect(operations_revision.asset_id).revisions == (operations_revision,)

    tui_repository = _MemoryRepository()
    tui_operations = ActivityAssetOperations(
        repository=tui_repository, forecast_operation=_forecast, taxpayer_modality=_simplified
    )
    tui = ActivityAssetTuiActionsV1(operations=tui_operations)
    tui_revision = _revision("created-by-tui")

    tui.create(ActivityAssetCreationRequestV1(revision=tui_revision))
    assert tui_operations.inspect(tui_revision.asset_id) == (tui_revision,)
    assert tui_repository.history.revisions == (tui_revision,)


def test_tui_route_composition_registers_the_shared_actions() -> None:
    operations = ActivityAssetOperations(
        repository=_MemoryRepository(), forecast_operation=_forecast, taxpayer_modality=_simplified
    )

    actions = actividad_asset_tui_actions(operations=operations)

    assert isinstance(actions, ActivityAssetTuiActionsV1)


def test_tui_forecast_is_the_shared_non_consuming_operation() -> None:
    repository = _MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository, forecast_operation=_forecast, taxpayer_modality=_simplified
    )
    tui = ActivityAssetTuiActionsV1(operations=operations)
    revision = _revision("forecast-parity")
    operations.create(revision)

    shared_forecast = operations.forecast(
        asset_id=revision.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    tui_forecast = tui.forecast(
        ActivityAssetForecastRequestV1(
            asset_id=revision.asset_id,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
        ),
    )

    assert tui_forecast == shared_forecast
    assert tui_forecast.amount == Decimal("520.00")
    assert repository.history.claims == ()


@pytest.mark.asyncio
async def test_interactive_tui_exposes_correction_claim_replay_and_filing_through_the_shared_door() -> None:
    repository = _MemoryRepository()
    actions = ActivityAssetTuiActionsV1(
        operations=ActivityAssetOperations(
            repository=repository, forecast_operation=_forecast, taxpayer_modality=_simplified
        ),
    )
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), activity_asset_actions=actions),
    )
    screen = ActivityAssetScreen(controller)
    revision = _revision("interactive-tui")
    app = ScreenHostApp[None](screen)

    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-id", Input).value = revision.asset_id
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-create")
        assert await _wait_for_screen_result(
            pilot=pilot, screen=screen, expected_prefix="created\tinteractive-tui\trevisions=1"
        )
        first_revision_id = await _wait_for_current_revision_id(pilot=pilot, screen=screen)
        assert first_revision_id == revision.revision_id
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-inspect")
        assert await _wait_for_screen_result(
            pilot=pilot, screen=screen, expected_prefix="asset\tinteractive-tui\trevisions=1"
        )
        assert await _wait_for_current_revision_id(pilot=pilot, screen=screen) == first_revision_id

        correction = revision.model_copy(
            update={
                "revision_number": 2,
                "supersedes_revision_id": first_revision_id,
                "basis": ActivityAssetBasis(
                    stage=AssetBasisStage.BUSINESS_ALLOCATED,
                    basis_amount=Decimal("1800.00"),
                    prior_allocation_provenance="corrected ledger allocation source",
                ),
            }
        )
        screen.query_one("#asset-revision-json", Input).value = correction.model_dump_json()
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-correct")
        assert await _wait_for_screen_result(
            pilot=pilot, screen=screen, expected_prefix="corrected\tinteractive-tui\trevisions=2"
        )
        assert await _wait_for_current_revision_id(pilot=pilot, screen=screen) == correction.revision_id

        screen.query_one("#asset-covered-from", Input).value = "2025-01-01"
        screen.query_one("#asset-covered-until", Input).value = "2026-01-01"
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-forecast")
        assert (await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="forecast\t")).startswith(
            "forecast\t468.00\t"
        )

        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-claim")
        first_claim = await _wait_for_screen_result(
            pilot=pilot,
            screen=screen,
            expected_prefix="claim\t",
            expected_suffix="reused=false",
        )
        first_claim_id = first_claim.split("\t")[1]
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-claim")
        assert (
            await _wait_for_screen_result(
                pilot=pilot,
                screen=screen,
                expected_prefix="claim\t",
                expected_suffix="reused=true",
            )
        ).endswith("reused=true")

        screen.query_one("#asset-filing-tax-year", Input).value = "2025"
        screen.query_one("#asset-filing-m130-period", Input).value = "4T"
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-filing-handoff")
        assert (
            await _wait_for_screen_result(
                pilot=pilot,
                screen=screen,
                expected_prefix="filing_handoff\t",
            )
        ) == "filing_handoff\tm100_material=468.00\tm100_intangible=0.00\tm130_material=468.00\tm130_intangible=0.00"

        second_correction = correction.model_copy(
            update={
                "revision_number": 3,
                "supersedes_revision_id": correction.revision_id,
                "basis": ActivityAssetBasis(
                    stage=AssetBasisStage.BUSINESS_ALLOCATED,
                    basis_amount=Decimal("1500.00"),
                    prior_allocation_provenance="second corrected ledger allocation source",
                ),
            }
        )
        screen.query_one("#asset-revision-json", Input).value = second_correction.model_dump_json()
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-correct")
        assert await _wait_for_screen_result(
            pilot=pilot, screen=screen, expected_prefix="corrected\tinteractive-tui\trevisions=3"
        )
        screen.query_one("#asset-supersedes-claim-id", Input).value = first_claim_id
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-forecast")
        # The replaced 468.00 is left out, so the corrected 1,500 basis yields 1,500 x 26% = 390.00.
        assert (await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="forecast\t")).startswith(
            "forecast\t390.00\t"
        )
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-claim")
        superseding_claim = await _wait_for_screen_result(
            pilot=pilot,
            screen=screen,
            expected_prefix="claim\t",
            expected_suffix="reused=false",
        )
        assert superseding_claim.split("\t")[1] != first_claim_id
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-filing-handoff")
        assert (
            await _wait_for_screen_result(
                pilot=pilot,
                screen=screen,
                expected_prefix="filing_handoff\t",
            )
        ) == "filing_handoff\tm100_material=390.00\tm100_intangible=0.00\tm130_material=390.00\tm130_intangible=0.00"


@pytest.mark.asyncio
async def test_activity_asset_screen_clears_a_stale_public_result_before_worker_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repeated public action cannot be observed as the prior claim result."""
    repository = _MemoryRepository()
    actions = ActivityAssetTuiActionsV1(
        operations=ActivityAssetOperations(
            repository=repository, forecast_operation=_forecast, taxpayer_modality=_simplified
        ),
    )
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), activity_asset_actions=actions),
    )
    screen = ActivityAssetScreen(controller)
    revision = _revision("pending-public-result")
    original_create = actions.create
    worker_entered = Event()
    release_worker = Event()

    def delayed_create(request: ActivityAssetCreationRequestV1):
        worker_entered.set()
        if not release_worker.wait(timeout=2.0):
            raise RuntimeError("test worker was not released")
        return original_create(request)

    monkeypatch.setattr(actions, "create", delayed_create)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 35)) as pilot:
        screen.query_one("#asset-revision-json", Input).value = revision.model_dump_json()
        # This represents the prior first-claim result that used to remain
        # visible while the next worker action began.
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
