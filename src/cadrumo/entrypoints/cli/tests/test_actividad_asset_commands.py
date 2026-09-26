"""Installed command-tree evidence for activity-asset operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.calculations.actividad_asset_schedule import vehicle_affectation_verdict
from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetIncompleteError, VehicleAffectationRecovery
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
from cadrumo.entrypoints.cli.actividad_asset_receipts import claim_receipt, inspection_receipt
from cadrumo.entrypoints.cli.command_schema import command_schema_type
from cadrumo.entrypoints.cli.common import resolve_cli_precondition_action

from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_activity_asset_group_exposes_the_shared_operation_set() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "--help"])

    assert result.exit_code == 0
    for token in ("create", "inspect", "correct", "forecast", "claim", "filing-handoff"):
        assert token in result.output


def test_activity_asset_commands_resolve_strict_registered_output_schemas() -> None:
    """The real JSON emission gate must not receive application models directly."""
    expected = {
        "create": "ActivityAssetHistoryPayload",
        "inspect": "ActivityAssetInspectionPayload",
        "correct": "ActivityAssetHistoryPayload",
        "forecast": "ActivityAssetForecastPayload",
        "claim": "ActivityAssetClaimPayload",
        "filing_handoff": "ActivityAssetFilingHandoffPayload",
    }

    for command, schema_name in expected.items():
        assert command_schema_type(f"ledger.actividad_asset.{command}").__name__ == schema_name


def _revision() -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="asset-1",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("300.00"),
            prior_allocation_provenance="test allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


def test_activity_asset_inspection_payload_names_each_revision_a_correction_can_supersede() -> None:
    first = _revision()
    correction = first.model_copy(update={"revision_number": 2, "supersedes_revision_id": first.revision_id})

    payload = inspection_receipt(first.asset_id, (first, correction))

    assert [revision["revision_id"] for revision in payload.revisions] == [first.revision_id, correction.revision_id]
    assert payload.revisions[1]["supersedes_revision_id"] == first.revision_id


def test_activity_asset_claim_payload_includes_the_canonical_derived_claim_identity() -> None:
    """A machine receipt must retain the ID needed for correction/replay tracing."""
    revision = _revision()
    claim = AmortizationClaim(
        asset_id=revision.asset_id,
        asset_revision_id=revision.revision_id,
        asset_kind=revision.asset_kind,
        tax_year=2025,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        amount=Decimal("300.00"),
        schedule_fingerprint="c" * 64,
        authority_generation="test-authority",
        source_reference="test source",
        creating_operation="test.claim",
    )
    result = ActivityAssetHistoryClaimResult(
        history=ActivityAssetHistory(revisions=(revision,), claims=(claim,)),
        claim=claim,
        reused_existing_claim=False,
    )

    payload = claim_receipt(result)

    rendered_claim = payload.root["claim"]
    assert isinstance(rendered_claim, dict)
    assert rendered_claim["claim_id"] == claim.claim_id


def test_an_undeclared_vehicle_refusal_names_the_live_correct_command() -> None:
    recovery = VehicleAffectationRecovery(asset_id="car-1", revision_id="a" * 64, class_key="transporte-externo")
    error = ActividadAssetIncompleteError(
        "activity asset 'car-1' requires a vehicle affectation declaration",
        precondition_verdict=vehicle_affectation_verdict(recovery),
        vehicle_affectation_recovery=recovery,
    )

    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    resolved = resolve_cli_precondition_action(verdict)

    action = resolved.action
    assert action is not None
    assert action.action_id == "operator.ledger.actividad_asset.correct_revision"
    assert action.target_command_key == "ledger.actividad_asset.correct"
    assert action.cli_path is not None
    assert action.cli_path[-2:] == ("actividad-asset", "correct")
    assert resolved.missing_argument_names == ("revision_json",)
    assert resolved.evidence[0].values["asset_id"] == "car-1"


def test_activity_asset_inspect_dispatches_to_profile_resolution() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "inspect", "missing-asset"])

    assert result.exit_code != 0
    assert "No hay un perfil activo" in result.output


@pytest.mark.parametrize("retired_option", ["--authority-json", "--selection-json"])
def test_activity_asset_forecast_refuses_a_caller_authored_authority_envelope(retired_option: str) -> None:
    """The election lives on the revision; a forecast accepts no rate or selector envelope."""
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "actividad-asset",
            "forecast",
            "asset-1",
            retired_option,
            '{"annual_rate":"1"}',
            "--covered-from",
            "2025-01-01",
            "--covered-until",
            "2026-01-01",
        ],
    )

    assert result.exit_code != 0
    assert retired_option in result.output


def test_activity_asset_forecast_exposes_only_the_optional_free_depreciation_amount() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "forecast", "--help"])

    assert result.exit_code == 0
    assert "--free-depreciation-amount" in result.output
    assert "--selection-json" not in result.output
