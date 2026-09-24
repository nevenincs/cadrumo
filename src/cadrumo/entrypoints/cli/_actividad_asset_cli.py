"""Thin machine-facing adapter for shared activity-asset operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import typer

from ...application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ...application.actividad_asset.modality import direct_estimation_modality
from ...application.actividad_asset.operations import ActivityAssetFilingHandoff, ActivityAssetOperations
from ...application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ...core.period import Period
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.user_profile.plantilla_media import PlantillaMediaYear, plantilla_media_years
from ._actividad_asset_payloads import (
    ActivityAssetFilingHandoffPayload,
    ActivityAssetForecastPayload,
    ActivityAssetHistoryPayload,
    ActivityAssetInspectionPayload,
)
from .actividad_asset_receipts import claim_receipt, inspection_receipt
from .common import active_bucket_id_or_refuse, emit_envelope
from .state_projection_support import authority_operation, calculation_action_ports_factory, profile_read_ports_factory


class ActivityAssetCli:
    """CLI boundary that parses wire values and delegates every operation."""

    def __init__(self, *, operations: ActivityAssetOperations) -> None:
        self._operations = operations

    def create(self, revision_json: str) -> ActivityAssetHistory:
        return self._operations.create(ActivityAssetRevision.model_validate_json(revision_json))

    def inspect(self, asset_id: str) -> ActivityAssetInspectionPayload:
        return inspection_receipt(asset_id, self._operations.inspect(asset_id))

    def correct(self, revision_json: str) -> ActivityAssetHistory:
        return self._operations.correct(ActivityAssetRevision.model_validate_json(revision_json))

    def forecast(
        self,
        *,
        asset_id: str,
        covered_from: str,
        covered_until: str,
        free_depreciation_amount: str | None = None,
        supersedes_claim_id: str | None = None,
    ) -> ScheduledAmortizationCharge:
        return self._operations.forecast(
            asset_id=asset_id,
            covered_from=date.fromisoformat(covered_from),
            covered_until=date.fromisoformat(covered_until),
            requested_free_amount=_parse_free_amount(free_depreciation_amount),
            supersedes_claim_id=supersedes_claim_id,
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


def _parse_free_amount(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ActividadAssetValidationError("free-depreciation amount must be a decimal euro amount") from exc


def _runtime_cli(ctx: typer.Context) -> ActivityAssetCli:
    bucket_id = active_bucket_id_or_refuse()
    authority = authority_operation(ctx)
    ports = calculation_action_ports_factory(ctx)(bucket_id=bucket_id, operation=authority)
    profile_values = profile_read_ports_factory(ctx)(bucket_id).path_values

    def _taxpayer_workforce() -> tuple[PlantillaMediaYear, ...]:
        values = profile_values.load_path_values(bucket_id=bucket_id)
        return () if values is None else plantilla_media_years(values)

    def _forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=authority.revision("100", str(covered_from.year)),
            authority_generation=authority.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=_taxpayer_workforce,
            requested_free_amount=requested_free_amount,
        )

    def _taxpayer_modality() -> DirectEstimationRegime:
        values = profile_values.load_path_values(bucket_id=bucket_id)
        token = None if values is None else values.get("irpf.estimation_regime")
        return direct_estimation_modality(token, authority=authority)

    return ActivityAssetCli(
        operations=ActivityAssetOperations(
            repository=ports.activity_asset_history_repository,
            forecast_operation=_forecast,
            taxpayer_modality=_taxpayer_modality,
        ),
    )


def actividad_asset_create(ctx: typer.Context, revision_json: str) -> None:
    """Create an activity asset from a typed JSON revision."""
    result = _runtime_cli(ctx).create(revision_json)
    payload = ActivityAssetHistoryPayload(root=result.model_dump(mode="json"))
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.create",
        result=payload,
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
    payload = ActivityAssetHistoryPayload(root=result.model_dump(mode="json"))
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.correct",
        result=payload,
        lines=(f"revisions\t{len(result.revisions)}",),
    )


def actividad_asset_forecast(
    ctx: typer.Context,
    asset_id: str,
    covered_from: str,
    covered_until: str,
    free_depreciation_amount: str | None = None,
    supersedes_claim_id: str | None = None,
) -> None:
    """Preview an asset charge under its revision's election without recording a claim."""
    result = _runtime_cli(ctx).forecast(
        asset_id=asset_id,
        covered_from=covered_from,
        covered_until=covered_until,
        free_depreciation_amount=free_depreciation_amount,
        supersedes_claim_id=supersedes_claim_id,
    )
    payload = ActivityAssetForecastPayload(root=result.model_dump(mode="json"))
    emit_envelope(ctx, command="ledger.actividad_asset.forecast", result=payload, lines=(f"amount\t{result.amount}",))


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
        result=claim_receipt(result),
        lines=(f"claim_id\t{result.claim.claim_id}", f"reused\t{str(result.reused_existing_claim).lower()}"),
    )


def actividad_asset_filing_handoff(ctx: typer.Context, tax_year: int, m130_period: str) -> None:
    """Inspect non-consuming M100 and M130 claim projections."""
    result = _runtime_cli(ctx).filing_handoff(tax_year=tax_year, m130_period=m130_period)
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.filing_handoff",
        result=ActivityAssetFilingHandoffPayload(root=result.model_dump(mode="json")),
        lines=(
            f"m100_material\t{result.material_m100.amount}",
            f"m100_intangible\t{result.intangible_m100.amount}",
            f"m130_material\t{result.material_m130.amount}",
            f"m130_intangible\t{result.intangible_m130.amount}",
        ),
    )


__all__ = [
    "ActivityAssetCli",
    "actividad_asset_correct",
    "actividad_asset_create",
    "actividad_asset_filing_handoff",
    "actividad_asset_forecast",
    "actividad_asset_inspect",
    "actividad_asset_record_claim",
]
