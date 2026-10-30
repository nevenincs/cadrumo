"""Thin machine-facing adapter for registered activity-asset operations."""

from __future__ import annotations

import typer
from pydantic import BaseModel, TypeAdapter

from ...application.actividad_asset.activity_asset_contracts import ActivityAssetSupersedingClaim
from ...core.errors.hierarchy import InternalInvariantError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.register_records import AcquisitionDocumentKind, ActivityAssetDescriptorFacts
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge, parse_requested_free_amount
from ._actividad_asset_payloads import (
    ActivityAssetFilingHandoffPayload,
    ActivityAssetForecastPayload,
    ActivityAssetHistoryPayload,
    ActivityAssetReadPayload,
)
from ._date_parsing import _parse_iso_date
from .actividad_asset_receipts import claim_receipt, inspection_receipt
from .common import emit_envelope
from .operation_ledger_actividad_asset import (
    acquisition_candidates_activity_asset,
    claim_activity_asset,
    correct_activity_asset,
    create_activity_asset,
    describe_activity_asset,
    filing_handoff_activity_asset,
    forecast_activity_asset,
    form_options_activity_asset,
    inspect_activity_asset,
    list_activity_assets,
    plan_activity_asset,
    timeline_activity_asset,
)

_SUPERSEDING_CLAIMS = TypeAdapter(tuple[ActivityAssetSupersedingClaim, ...])


def _descriptor(
    name: str,
    serial_number: str | None,
    description: str | None,
    document_kind: str | None,
    document_number: str | None,
    supplier_name: str | None,
    supplier_tax_id: str | None,
) -> ActivityAssetDescriptorFacts:
    return ActivityAssetDescriptorFacts(
        name=name,
        serial_number=serial_number,
        description=description,
        document_kind=None if document_kind is None else AcquisitionDocumentKind(document_kind),
        document_number=document_number,
        supplier_name=supplier_name,
        supplier_tax_id=supplier_tax_id,
    )


def actividad_asset_create(
    ctx: typer.Context,
    revision_json: str,
    name: str,
    serial_number: str | None = None,
    description: str | None = None,
    document_kind: str | None = None,
    document_number: str | None = None,
    supplier_name: str | None = None,
    supplier_tax_id: str | None = None,
) -> None:
    """Create an activity asset from a typed JSON revision and its descriptive facts."""
    result = create_activity_asset(
        ctx,
        revision=ActivityAssetRevision.model_validate_json(revision_json),
        descriptor=_descriptor(
            name,
            serial_number,
            description,
            document_kind,
            document_number,
            supplier_name,
            supplier_tax_id,
        ),
    )
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


def actividad_asset_correct(
    ctx: typer.Context,
    revision_json: str,
    superseding_claims_json: str | None = None,
) -> None:
    """Append a typed JSON correction revision, with the claims it replaces in the same write."""
    result = correct_activity_asset(
        ctx,
        revision=ActivityAssetRevision.model_validate_json(revision_json),
        superseding_claims=(
            () if superseding_claims_json is None else _SUPERSEDING_CLAIMS.validate_json(superseding_claims_json)
        ),
    )
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
    supersedes_claim_id: str | None = None,
) -> None:
    """Explicitly record one forecast as an idempotent claim."""
    completed = claim_activity_asset(
        ctx,
        forecast=ScheduledAmortizationCharge.model_validate_json(forecast_json),
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


def _emit_read(ctx: typer.Context, command: str, projection: BaseModel, *lines: str) -> None:
    document = projection.model_dump(mode="json", exclude={"profile_id", "authority", "outcome", "refusal"})
    emit_envelope(ctx, command=command, result=ActivityAssetReadPayload(root=document), lines=lines)


def actividad_asset_describe(
    ctx: typer.Context,
    asset_id: str,
    name: str,
    serial_number: str | None = None,
    description: str | None = None,
    document_kind: str | None = None,
    document_number: str | None = None,
    supplier_name: str | None = None,
    supplier_tax_id: str | None = None,
) -> None:
    """Append one element's descriptive facts, which change no calculation."""
    result = describe_activity_asset(
        ctx,
        asset_id=asset_id,
        descriptor=_descriptor(
            name,
            serial_number,
            description,
            document_kind,
            document_number,
            supplier_name,
            supplier_tax_id,
        ),
    )
    if result.history is None:
        raise InternalInvariantError("successful activity-asset description omitted its history")
    history = result.history.to_domain()
    emit_envelope(
        ctx,
        command="ledger.actividad_asset.describe",
        result=ActivityAssetHistoryPayload(root=history.model_dump(mode="json")),
        lines=(f"descriptors\t{len(history.descriptors)}",),
    )


def actividad_asset_list(ctx: typer.Context) -> None:
    """List the register's elements with their figures and findings."""
    result = list_activity_assets(ctx)
    _emit_read(
        ctx,
        "ledger.actividad_asset.list",
        result,
        *(f"{row.asset_id}\t{row.name or ''}\t{row.state.value}" for row in result.rows or ()),
    )


def actividad_asset_plan(ctx: typer.Context, asset_id: str) -> None:
    """Show one element's amortization plan, year by year."""
    result = plan_activity_asset(ctx, asset_id=asset_id)
    _emit_read(
        ctx,
        "ledger.actividad_asset.plan",
        result,
        *(
            f"{row.tax_year}\t{row.planned.decimal if row.planned else row.absence or ''}"
            f"\t{row.claimed.decimal}\t{row.claim_state.value}"
            for row in result.rows or ()
        ),
    )


def actividad_asset_timeline(ctx: typer.Context, asset_id: str) -> None:
    """Show one element's history in order."""
    result = timeline_activity_asset(ctx, asset_id=asset_id)
    _emit_read(
        ctx,
        "ledger.actividad_asset.timeline",
        result,
        *(f"{event.sequence}\t{event.kind.value}\t{event.record_id}" for event in result.events or ()),
    )


def actividad_asset_form_options(ctx: typer.Context, asset_kind: str, tax_year: int) -> None:
    """Show the methods and table groups the registry admits."""
    result = form_options_activity_asset(ctx, asset_kind=AssetKind(asset_kind), tax_year=tax_year)
    if result.options is None:
        raise InternalInvariantError("successful activity-asset form options omitted their content")
    _emit_read(
        ctx,
        "ledger.actividad_asset.form_options",
        result,
        f"methods\t{len(result.options.methods)}",
        f"table_groups\t{len(result.options.table_groups)}",
    )


def actividad_asset_acquisition_candidates(ctx: typer.Context) -> None:
    """List the ledger payments an element could name as its acquisition."""
    result = acquisition_candidates_activity_asset(ctx)
    _emit_read(
        ctx,
        "ledger.actividad_asset.acquisition_candidates",
        result,
        *(f"{item.transaction_id}\t{item.booked_date}\t{item.amount.decimal}" for item in result.candidates or ()),
    )


__all__ = [
    "actividad_asset_acquisition_candidates",
    "actividad_asset_correct",
    "actividad_asset_create",
    "actividad_asset_describe",
    "actividad_asset_filing_handoff",
    "actividad_asset_forecast",
    "actividad_asset_form_options",
    "actividad_asset_inspect",
    "actividad_asset_list",
    "actividad_asset_plan",
    "actividad_asset_record_claim",
    "actividad_asset_timeline",
]
