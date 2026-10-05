"""Thin machine-facing adapter for registered activity-asset operations."""

from __future__ import annotations

import typer

from ...core.errors.hierarchy import InternalInvariantError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge, parse_requested_free_amount
from ._actividad_asset_payloads import (
    ActivityAssetFilingHandoffPayload,
    ActivityAssetForecastPayload,
    ActivityAssetHistoryPayload,
)
from ._date_parsing import _parse_iso_date
from .actividad_asset_receipts import claim_receipt, inspection_receipt
from .common import emit_envelope
from .runtime_ledger_actividad_asset import (
    claim_activity_asset,
    correct_activity_asset,
    create_activity_asset,
    filing_handoff_activity_asset,
    forecast_activity_asset,
    inspect_activity_asset,
)


def actividad_asset_create(ctx: typer.Context, revision_json: str) -> None:
    """Create an activity asset from a typed JSON revision."""
    result = create_activity_asset(ctx, revision=ActivityAssetRevision.model_validate_json(revision_json))
    if result.history is None:
        raise InternalInvariantError("successful activity-asset creation omitted its history")
    history = result.history.to_domain()
    payload = ActivityAssetHistoryPayload(root=history.model_dump(mode="json"))
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.create",
        result=payload,
        lines=(f"revisions\t{len(history.revisions)}",),
    )


def actividad_asset_inspect(ctx: typer.Context, asset_id: str) -> None:
    """Inspect one activity asset revision chain."""
    result = inspect_activity_asset(ctx, asset_id=asset_id)
    if result.asset_id is None or result.revisions is None:
        raise InternalInvariantError("successful activity-asset inspection omitted its revision chain")
    receipt = inspection_receipt(asset_id, tuple(item.revision.to_domain() for item in result.revisions))
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.inspect",
        result=receipt,
        lines=(f"asset_id\t{receipt.asset_id}", f"revisions\t{len(receipt.revisions)}"),
    )


def actividad_asset_correct(ctx: typer.Context, revision_json: str) -> None:
    """Append a typed JSON correction revision."""
    result = correct_activity_asset(ctx, revision=ActivityAssetRevision.model_validate_json(revision_json))
    if result.history is None:
        raise InternalInvariantError("successful activity-asset correction omitted its history")
    history = result.history.to_domain()
    payload = ActivityAssetHistoryPayload(root=history.model_dump(mode="json"))
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.correct",
        result=payload,
        lines=(f"revisions\t{len(history.revisions)}",),
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
    result = forecast_activity_asset(
        ctx,
        asset_id=asset_id,
        covered_from=_parse_iso_date(covered_from, label="covered-from"),
        covered_until=_parse_iso_date(covered_until, label="covered-until"),
        requested_free_amount=parse_requested_free_amount(free_depreciation_amount),
        supersedes_claim_id=supersedes_claim_id,
    )
    if result.forecast is None:
        raise InternalInvariantError("successful activity-asset forecast omitted its schedule")
    forecast = result.forecast.to_domain()
    payload = ActivityAssetForecastPayload(root=forecast.model_dump(mode="json"))
    emit_envelope(ctx, command="ledger.actividad_asset.forecast", result=payload, lines=(f"amount\t{forecast.amount}",))


def actividad_asset_record_claim(
    ctx: typer.Context,
    forecast_json: str,
    creating_operation: str,
    supersedes_claim_id: str | None = None,
) -> None:
    """Explicitly record one forecast as an idempotent claim."""
    completed = claim_activity_asset(
        ctx,
        forecast=ScheduledAmortizationCharge.model_validate_json(forecast_json),
        creating_operation=creating_operation,
        supersedes_claim_id=supersedes_claim_id,
    )
    if completed.claim_result is None:
        raise InternalInvariantError("successful activity-asset claim omitted its persisted result")
    result = completed.claim_result.to_domain()
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.claim",
        result=claim_receipt(result),
        lines=(f"claim_id\t{result.claim.claim_id}", f"reused\t{str(result.reused_existing_claim).lower()}"),
    )


def actividad_asset_filing_handoff(ctx: typer.Context, tax_year: int, m130_period: str) -> None:
    """Inspect non-consuming M100 and M130 claim projections."""
    result = filing_handoff_activity_asset(ctx, tax_year=tax_year, m130_period=m130_period)
    if result.filing_handoff is None:
        raise InternalInvariantError("successful activity-asset handoff omitted its filing projections")
    handoff = result.filing_handoff.to_domain()
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.filing_handoff",
        result=ActivityAssetFilingHandoffPayload(root=handoff.model_dump(mode="json")),
        lines=(
            f"m100_material\t{handoff.material_m100.amount}",
            f"m100_intangible\t{handoff.intangible_m100.amount}",
            f"m130_material\t{handoff.material_m130.amount}",
            f"m130_intangible\t{handoff.intangible_m130.amount}",
        ),
    )


__all__ = [
    "actividad_asset_correct",
    "actividad_asset_create",
    "actividad_asset_filing_handoff",
    "actividad_asset_forecast",
    "actividad_asset_inspect",
    "actividad_asset_record_claim",
]
