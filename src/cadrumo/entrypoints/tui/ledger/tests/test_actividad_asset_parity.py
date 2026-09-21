"""CLI/TUI parity over the shared activity-asset application operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from textual.widgets import Input, Static

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetAuthoritySelection,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
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
from cadrumo.domain.renta.actividad_asset.schedule import ScheduleAuthority, schedule_charge
from cadrumo.entrypoints.cli._actividad_asset_cli import ActivityAssetCli
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
    )


def _authority() -> ScheduleAuthority:
    return ScheduleAuthority(
        asset_kind=AssetKind.MATERIAL,
        annual_rate=Decimal("0.26"),
        authority_generation="irpf-2025-assets-test-v1",
        source_reference="AEAT simplified direct-estimation table 2025",
    )


def _selection() -> ActivityAssetAuthoritySelection:
    return ActivityAssetAuthoritySelection(
        regime=DirectEstimationRegime.SIMPLIFIED,
        asset_kind=AssetKind.MATERIAL,
        authority_class_key="equipment-test-class",
    )


def _forecast(
    revision,
    *,
    selection,
    covered_from,
    covered_until,
    accumulated_effective_claims,
    accumulated_effective_free_depreciation_claims,
):
    assert selection == _selection()
    return schedule_charge(
        revision,
        _authority(),
        covered_from=covered_from,
        covered_until=covered_until,
        accumulated_effective_claims=accumulated_effective_claims,
        accumulated_effective_free_depreciation_claims=accumulated_effective_free_depreciation_claims,
    )


def test_each_frontend_creates_and_the_other_frontend_continues() -> None:
    cli_created_repository = _MemoryRepository()
    cli_created_operations = ActivityAssetOperations(repository=cli_created_repository, forecast_operation=_forecast)
    cli = ActivityAssetCli(operations=cli_created_operations)
    tui_after_cli = ActivityAssetTuiActionsV1(operations=cli_created_operations)
    cli_revision = _revision("created-by-cli")

    cli.create(cli_revision.model_dump_json())
    assert tui_after_cli.inspect(cli_revision.asset_id).revisions == (cli_revision,)

    tui_created_repository = _MemoryRepository()
    tui_created_operations = ActivityAssetOperations(repository=tui_created_repository, forecast_operation=_forecast)
    tui = ActivityAssetTuiActionsV1(operations=tui_created_operations)
    cli_after_tui = ActivityAssetCli(operations=tui_created_operations)
    tui_revision = _revision("created-by-tui")

    tui.create(ActivityAssetCreationRequestV1(revision=tui_revision))
    assert cli_after_tui.inspect(tui_revision.asset_id).revisions == (tui_revision,)


def test_tui_route_composition_registers_the_shared_actions() -> None:
    operations = ActivityAssetOperations(repository=_MemoryRepository(), forecast_operation=_forecast)

    actions = actividad_asset_tui_actions(operations=operations)

    assert isinstance(actions, ActivityAssetTuiActionsV1)


def test_cli_and_tui_forecasts_are_the_same_non_consuming_operation() -> None:
    repository = _MemoryRepository()
    operations = ActivityAssetOperations(repository=repository, forecast_operation=_forecast)
    cli = ActivityAssetCli(operations=operations)
    tui = ActivityAssetTuiActionsV1(operations=operations)
    revision = _revision("forecast-parity")
    cli.create(revision.model_dump_json())
    selection = _selection()

    cli_forecast = cli.forecast(
        asset_id=revision.asset_id,
        selection_json=selection.model_dump_json(),
        covered_from="2025-01-01",
        covered_until="2026-01-01",
    )
    tui_forecast = tui.forecast(
        ActivityAssetForecastRequestV1(
            asset_id=revision.asset_id,
            regime=selection.regime.value,
            asset_kind=selection.asset_kind,
            authority_class_key=selection.authority_class_key,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
        ),
    )

    assert cli_forecast == tui_forecast
    assert cli_forecast.amount == Decimal("520.00")
    assert repository.history.claims == ()


@pytest.mark.asyncio
async def test_interactive_tui_creates_and_inspects_through_the_shared_door() -> None:
    repository = _MemoryRepository()
    actions = ActivityAssetTuiActionsV1(
        operations=ActivityAssetOperations(repository=repository, forecast_operation=_forecast),
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
        await pilot.click("#asset-create")
        await pilot.pause()
        assert "created\tinteractive-tui\trevisions=1" in str(screen.query_one("#asset-result", Static).render())
        await pilot.click("#asset-inspect")
        await pilot.pause()
        assert "asset\tinteractive-tui\trevisions=1" in str(screen.query_one("#asset-result", Static).render())
