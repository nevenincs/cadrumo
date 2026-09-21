"""Installed command-tree evidence for activity-asset operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
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
from cadrumo.entrypoints.cli._actividad_asset_cli import _claim_payload
from cadrumo.entrypoints.cli.command_schema import command_schema_type

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


def test_activity_asset_claim_payload_includes_the_canonical_derived_claim_identity() -> None:
    """A machine receipt must retain the ID needed for correction/replay tracing."""
    revision = ActivityAssetRevision(
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
    )
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

    payload = _claim_payload(result)

    rendered_claim = payload.root["claim"]
    assert isinstance(rendered_claim, dict)
    assert rendered_claim["claim_id"] == claim.claim_id


def test_activity_asset_inspect_dispatches_to_profile_resolution() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "inspect", "missing-asset"])

    assert result.exit_code != 0
    assert "No hay un perfil activo" in result.output


def test_activity_asset_forecast_refuses_a_caller_authored_rate_envelope() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "actividad-asset",
            "forecast",
            "asset-1",
            "--authority-json",
            '{"annual_rate":"1"}',
            "--covered-from",
            "2025-01-01",
            "--covered-until",
            "2026-01-01",
        ],
    )

    assert result.exit_code != 0
    assert "--authority-json" in result.output
