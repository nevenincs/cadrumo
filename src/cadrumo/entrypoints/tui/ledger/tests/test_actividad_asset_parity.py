"""CLI/TUI parity over the shared activity-asset application operations."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest
from textual.widgets import Button, Input, Static

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
            return match.group(1)
        await pilot.pause()
    raise AssertionError("activity-asset TUI did not expose the current immutable revision identity")


async def _activate_screen_button(*, pilot, screen: ActivityAssetScreen, selector: str) -> None:
    """Use the public keyboard activation path for a screen button."""
    button = screen.query_one(selector, Button)
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


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
    cli_readback = cli_after_tui.inspect(tui_revision.asset_id)
    assert cli_readback.asset_id == tui_revision.asset_id
    assert cli_readback.revisions == [tui_revision.model_dump(mode="json")]


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
            selection=selection,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
        ),
    )

    assert cli_forecast == tui_forecast
    assert cli_forecast.amount == Decimal("520.00")
    assert repository.history.claims == ()


@pytest.mark.asyncio
async def test_interactive_tui_exposes_correction_claim_replay_and_filing_through_the_shared_door() -> None:
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
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-create")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="created\tinteractive-tui\trevisions=1")
        first_revision_id = await _wait_for_current_revision_id(pilot=pilot, screen=screen)
        assert first_revision_id == revision.revision_id
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-inspect")
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="asset\tinteractive-tui\trevisions=1")
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
        assert await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="corrected\tinteractive-tui\trevisions=2")
        assert await _wait_for_current_revision_id(pilot=pilot, screen=screen) == correction.revision_id

        screen.query_one("#asset-selection-json", Input).value = _selection().model_dump_json()
        screen.query_one("#asset-covered-from", Input).value = "2025-01-01"
        screen.query_one("#asset-covered-until", Input).value = "2026-01-01"
        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-forecast")
        assert (await _wait_for_screen_result(pilot=pilot, screen=screen, expected_prefix="forecast\t")).startswith(
            "forecast\t468.00\t"
        )

        await _activate_screen_button(pilot=pilot, screen=screen, selector="#asset-claim")
        assert (
            await _wait_for_screen_result(
                pilot=pilot,
                screen=screen,
                expected_prefix="claim\t",
                expected_suffix="reused=false",
            )
        ).endswith("reused=false")
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
