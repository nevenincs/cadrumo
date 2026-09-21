"""Thin machine-facing adapter for shared activity-asset operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import typer
from pydantic import BaseModel

from ...application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ...application.actividad_asset.operations import ActivityAssetFilingHandoff, ActivityAssetOperations
from ...application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.actividad_asset_bindings import ActivityAssetAuthoritySelection
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from .common import active_bucket_id_or_refuse, emit_envelope
from .state_projection_support import authority_operation, calculation_action_ports_factory


class ActivityAssetInspectionPayload(BaseModel):
    """Stable JSON-capable inspection result."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str
    revisions: tuple[ActivityAssetRevision, ...]


class ActivityAssetCli:
    """CLI boundary that parses wire values and delegates every operation."""

    def __init__(self, *, operations: ActivityAssetOperations) -> None:
        self._operations = operations

    def create(self, revision_json: str) -> ActivityAssetHistory:
        return self._operations.create(ActivityAssetRevision.model_validate_json(revision_json))

    def inspect(self, asset_id: str) -> ActivityAssetInspectionPayload:
        return ActivityAssetInspectionPayload(asset_id=asset_id, revisions=self._operations.inspect(asset_id))

    def correct(self, revision_json: str) -> ActivityAssetHistory:
        return self._operations.correct(ActivityAssetRevision.model_validate_json(revision_json))

    def forecast(
        self,
        *,
        asset_id: str,
        selection_json: str,
        covered_from: str,
        covered_until: str,
    ) -> ScheduledAmortizationCharge:
        return self._operations.forecast(
            asset_id=asset_id,
            selection=ActivityAssetAuthoritySelection.model_validate_json(selection_json),
            covered_from=date.fromisoformat(covered_from),
            covered_until=date.fromisoformat(covered_until),
        )

    def record_claim(
        self,
        forecast_json: str,
        *,
        creating_operation: str,
        supersedes_claim_id: str | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        return self._operations.record_claim(
            ScheduledAmortizationCharge.model_validate_json(forecast_json),
            creating_operation=creating_operation,
            supersedes_claim_id=supersedes_claim_id,
        )

    def filing_handoff(self, *, tax_year: int, m130_period: str) -> ActivityAssetFilingHandoff:
        return self._operations.filing_handoff(
            tax_year=tax_year,
            m130_period=Period.from_year_and_code(tax_year, m130_period),
        )


def _runtime_cli(ctx: typer.Context) -> ActivityAssetCli:
    bucket_id = active_bucket_id_or_refuse()
    authority = authority_operation(ctx)
    ports = calculation_action_ports_factory(ctx)(bucket_id=bucket_id, operation=authority)

    def _forecast(
        revision: ActivityAssetRevision,
        *,
        selection: ActivityAssetAuthoritySelection,
        covered_from: date,
        covered_until: date,
        accumulated_effective_claims: Decimal,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=authority.revision("100", "2025"),
            selection=selection,
            authority_generation=authority.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            accumulated_effective_claims=accumulated_effective_claims,
        )

    return ActivityAssetCli(
        operations=ActivityAssetOperations(
            repository=ports.activity_asset_history_repository,
            forecast_operation=_forecast,
        ),
    )


def actividad_asset_create(ctx: typer.Context, revision_json: str) -> None:
    """Create an activity asset from a typed JSON revision."""
    result = _runtime_cli(ctx).create(revision_json)
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.create",
        result=result,
        lines=(f"revisions\t{len(result.revisions)}",),
    )


def actividad_asset_inspect(ctx: typer.Context, asset_id: str) -> None:
    """Inspect one activity asset revision chain."""
    result = _runtime_cli(ctx).inspect(asset_id)
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.inspect",
        result=result,
        lines=(f"asset_id\t{result.asset_id}", f"revisions\t{len(result.revisions)}"),
    )


def actividad_asset_correct(ctx: typer.Context, revision_json: str) -> None:
    """Append a typed JSON correction revision."""
    result = _runtime_cli(ctx).correct(revision_json)
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.correct",
        result=result,
        lines=(f"revisions\t{len(result.revisions)}",),
    )


def actividad_asset_forecast(
    ctx: typer.Context,
    asset_id: str,
    selection_json: str,
    covered_from: str,
    covered_until: str,
) -> None:
    """Preview an asset charge without recording a claim."""
    result = _runtime_cli(ctx).forecast(
        asset_id=asset_id,
        selection_json=selection_json,
        covered_from=covered_from,
        covered_until=covered_until,
    )
    emit_envelope(ctx, command="ledger.actividad_asset.forecast", result=result, lines=(f"amount\t{result.amount}",))


def actividad_asset_record_claim(
    ctx: typer.Context,
    forecast_json: str,
    creating_operation: str,
    supersedes_claim_id: str | None = None,
) -> None:
    """Explicitly record one forecast as an idempotent claim."""
    result = _runtime_cli(ctx).record_claim(
        forecast_json,
        creating_operation=creating_operation,
        supersedes_claim_id=supersedes_claim_id,
    )
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.claim",
        result=result,
        lines=(f"claim_id\t{result.claim.claim_id}", f"reused\t{str(result.reused_existing_claim).lower()}"),
    )


def actividad_asset_filing_handoff(ctx: typer.Context, tax_year: int, m130_period: str) -> None:
    """Inspect non-consuming M100 and M130 claim projections."""
    result = _runtime_cli(ctx).filing_handoff(tax_year=tax_year, m130_period=m130_period)
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.filing_handoff",
        result=result,
        lines=(
            f"m100_material\t{result.material_m100.amount}",
            f"m100_intangible\t{result.intangible_m100.amount}",
            f"m130_material\t{result.material_m130.amount}",
            f"m130_intangible\t{result.intangible_m130.amount}",
        ),
    )


__all__ = [
    "ActivityAssetCli",
    "ActivityAssetInspectionPayload",
    "actividad_asset_correct",
    "actividad_asset_create",
    "actividad_asset_filing_handoff",
    "actividad_asset_forecast",
    "actividad_asset_inspect",
    "actividad_asset_record_claim",
]
