"""Presentation handlers for worker-owned ledger inventory operations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.inventory.registered_evidence_operation import InventoryEvidenceAddRequest
from ...application.inventory.registered_requests import (
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryLedgerChangeRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n.render import tr
from ...domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from ...domain.contribuyente.inventory.records import (
    InventoryCorrectionReason,
    InventoryRetirementReason,
    MovementKind,
    ValuationMethod,
    load_inventory_acquisition_cost,
)
from ._date_parsing import _parse_iso_date
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from .common import active_bucket_id_or_refuse as _inventory_bucket_id
from .common import emit_envelope
from .ledger_business_payloads import InventoryClosingAuthorityRecordResult
from .operation_ledger_inventory import (
    add_inventory_evidence,
    add_inventory_movement,
    apply_inventory_ledger_change,
    create_inventory_ledger,
    inspect_inventory_ledger,
    preview_inventory_valuation,
    read_inventory_catalogue,
    record_inventory_closing_authority,
    record_inventory_closing_value,
)


def _parse_acquisition_cost(*, from_stdin: bool) -> InventoryAcquisitionCostRequest | None:
    """Read one typed purchase-cost request from the non-argv stdin channel."""
    if not from_stdin:
        return None
    value = typer.get_text_stream("stdin").read()
    try:
        acquisition = load_inventory_acquisition_cost(value)
        return InventoryAcquisitionCostRequest.from_domain(acquisition)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}" for error in exc.errors())
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.acquisition_cost_invalid", details=details),
            param_hint="--acquisition-cost-stdin",
        ) from exc


def inventory_list(ctx: typer.Context) -> None:
    """List the selected profile's activity ledgers from its worker."""
    completion, payload = read_inventory_catalogue(ctx)
    bucket_id = payload.bucket_id
    lines = [f"bucket\t{bucket_id}", f"count\t{payload.count}"]
    for row in completion.projection.rows:
        lines.append(
            f"{row.actividad_id}\t{row.year}\t{row.valuation_method.value}\t"
            f"opening={row.opening_stock.decimal}\tmovements={row.movement_count}"
            f"\tcorrections={row.correction_count}\tretired={row.retired}",
        )
    emit_envelope(ctx, command="ledger.inventory.list", result=payload, lines=lines)


def inventory_create(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    valuation_method: str,
    opening_stock: str = "0",
) -> None:
    """Create one ledger through the selected profile's authenticated worker."""
    bucket_id = _inventory_bucket_id()
    request = InventoryCreateRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        valuation_method=valuation_method,
        opening_stock=PublicDecimal(decimal=str(parse_decimal_amount(opening_stock, label="opening-stock"))),
    )
    completion, payload = create_inventory_ledger(ctx, request=request)
    ledger = completion.projection.ledger
    if ledger is None:
        raise InternalInvariantError("inventory create bridge returned no canonical ledger")
    emit_envelope(
        ctx,
        command="ledger.inventory.create",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"valuation_method\t{ledger.valuation_method.value}",
            f"opening_stock\t{ledger.opening_stock.decimal}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_movement_add(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    movement_id: str,
    movement_date: str,
    kind: MovementKind,
    quantity: str,
    unit_cost: str | None = None,
    taxable_base: str | None = None,
    acquisition_cost_stdin: bool = False,
) -> None:
    """Append one typed movement through the selected profile's worker."""
    bucket_id = _inventory_bucket_id()
    unit_cost_amount = parse_optional_decimal_amount(unit_cost, label="unit-cost")
    taxable_base_amount = parse_optional_decimal_amount(taxable_base, label="taxable-base")
    request = InventoryMovementAddRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        movement_id=movement_id,
        movement_date=_parse_iso_date(movement_date, label="--date"),
        kind=kind,
        quantity=PublicDecimal(decimal=str(parse_decimal_amount(quantity, label="quantity"))),
        unit_cost=PublicDecimal(decimal=str(unit_cost_amount)) if unit_cost_amount is not None else None,
        taxable_base=PublicDecimal(decimal=str(taxable_base_amount)) if taxable_base_amount is not None else None,
        acquisition_cost=_parse_acquisition_cost(from_stdin=acquisition_cost_stdin),
    )
    _completion, payload = add_inventory_movement(ctx, request=request)
    emit_envelope(
        ctx,
        command="ledger.inventory.movement.add",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{payload.actividad_id}",
            f"year\t{payload.year}",
            f"movements\t{len(payload.period_movements)}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def _emit_ledger_change(ctx: typer.Context, *, command: str, request: InventoryLedgerChangeRequest) -> None:
    """Submit one change and report the worker's own outcome and resulting state."""
    _completion, payload = apply_inventory_ledger_change(ctx, request=request)
    emit_envelope(
        ctx,
        command=command,
        result=payload,
        lines=(
            f"outcome\t{payload.outcome}",
            f"actividad_id\t{payload.actividad_id}",
            f"year\t{payload.year}",
            f"movements\t{len(payload.period_movements)}",
            f"corrections\t{len(payload.history)}",
            f"retired\t{payload.retired}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_inspect(ctx: typer.Context, actividad_id: str, year: int) -> None:
    """Show one ledger with its effective movements and retained history."""
    request = InventoryInspectRequest(profile_id=UUID(_inventory_bucket_id()), actividad_id=actividad_id, year=year)
    _completion, payload = inspect_inventory_ledger(ctx, request=request)
    lines = [
        f"actividad_id\t{payload.actividad_id}",
        f"year\t{payload.year}",
        f"valuation_method\t{payload.valuation_method}",
        f"opening_stock\t{payload.opening_stock}",
        f"retired\t{payload.retired}",
    ]
    lines.extend(
        f"movement\t{item.movement_id}\t{item.movement_date}\t{item.kind}\t{item.quantity}"
        for item in payload.period_movements
    )
    lines.extend(f"history\t{item.correction_id}\t{item.kind}\t{item.recorded_at}" for item in payload.history)
    emit_envelope(ctx, command="ledger.inventory.inspect", result=payload, lines=lines)


def inventory_describe(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    correction_id: str,
    label: str,
    description: str | None = None,
) -> None:
    """Replace the inventory's descriptive facts."""
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.describe",
        request=InventoryDescribeRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
            label=label,
            description=description,
        ),
    )


def inventory_correct(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    correction_id: str,
    reason: InventoryCorrectionReason,
    opening_stock: str | None = None,
    valuation_method: ValuationMethod | None = None,
) -> None:
    """Rectify the opening value or valuation method, retaining what they displace."""
    amount = parse_optional_decimal_amount(opening_stock, label="opening-stock")
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.correct",
        request=InventoryCorrectRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
            reason=reason,
            opening_stock=PublicDecimal(decimal=str(amount)) if amount is not None else None,
            valuation_method=valuation_method,
        ),
    )


def inventory_movement_correct(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    correction_id: str,
    target_movement_id: str,
    reason: InventoryCorrectionReason,
    movement_id: str,
    movement_date: str,
    kind: MovementKind,
    quantity: str,
    unit_cost: str | None = None,
    taxable_base: str | None = None,
    acquisition_cost_stdin: bool = False,
) -> None:
    """Supersede one movement with a replacement, retaining the movement it displaces."""
    unit_cost_amount = parse_optional_decimal_amount(unit_cost, label="unit-cost")
    taxable_base_amount = parse_optional_decimal_amount(taxable_base, label="taxable-base")
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.movement.correct",
        request=InventoryMovementCorrectRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
            target_movement_id=target_movement_id,
            reason=reason,
            movement_id=movement_id,
            movement_date=_parse_iso_date(movement_date, label="--date"),
            kind=kind,
            quantity=PublicDecimal(decimal=str(parse_decimal_amount(quantity, label="quantity"))),
            unit_cost=PublicDecimal(decimal=str(unit_cost_amount)) if unit_cost_amount is not None else None,
            taxable_base=PublicDecimal(decimal=str(taxable_base_amount)) if taxable_base_amount is not None else None,
            acquisition_cost=_parse_acquisition_cost(from_stdin=acquisition_cost_stdin),
        ),
    )


def inventory_movement_reverse(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    correction_id: str,
    target_movement_id: str,
    reason: InventoryCorrectionReason,
) -> None:
    """Take one movement out of the effective set, retaining it as evidence."""
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.movement.reverse",
        request=InventoryMovementReverseRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
            target_movement_id=target_movement_id,
            reason=reason,
        ),
    )


def inventory_retire(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    correction_id: str,
    reason: InventoryRetirementReason,
) -> None:
    """Take the inventory out of the active register with every fact retained."""
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.retire",
        request=InventoryRetireRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
            reason=reason,
        ),
    )


def inventory_restore(ctx: typer.Context, actividad_id: str, year: int, correction_id: str) -> None:
    """Bring a retired inventory back to the active register."""
    _emit_ledger_change(
        ctx,
        command="ledger.inventory.restore",
        request=InventoryRestoreRequest(
            profile_id=UUID(_inventory_bucket_id()),
            actividad_id=actividad_id,
            year=year,
            correction_id=correction_id,
        ),
    )


def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
) -> None:
    """Preview the canonical valuation through the selected profile worker."""
    bucket_id = _inventory_bucket_id()
    request = InventoryValuationPreviewRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
    )
    _completion, payload = preview_inventory_valuation(ctx, request=request)
    emit_envelope(
        ctx,
        command="ledger.inventory.valuation.preview",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{payload.actividad_id}",
            f"year\t{payload.year}",
            f"valuation_method\t{payload.valuation_method}",
            f"derived_closing_value\t{payload.derived_closing_value}",
            f"cogs\t{payload.cogs}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_closing_authority_record(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    file: Path,
) -> None:
    """Read one typed authority DTO, then persist it in the profile worker."""
    bucket_id = _inventory_bucket_id()
    try:
        authority = InventoryClosingAuthorityRecord.model_validate_json(file.read_text(encoding=UTF_8_ENCODING))
        authority_record = InventoryClosingAuthorityRecordInput.from_domain(authority)
    except (OSError, ValidationError) as exc:
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.authority_invalid"),
            param_hint="--file",
        ) from exc
    request = InventoryClosingAuthorityRecordRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        authority_record=authority_record,
    )
    _completion, payload = record_inventory_closing_authority(ctx, request=request)
    result: InventoryClosingAuthorityRecordResult = payload
    emit_envelope(
        ctx,
        command="ledger.inventory.closing-authority.record",
        result=result,
        lines=(
            f"actividad_id\t{result.actividad_id}",
            f"year\t{result.year}",
            f"authority_record_fingerprint\t{result.authority_record_fingerprint}",
        ),
    )


def inventory_evidence_add(ctx: typer.Context, source_path: str) -> None:
    """Store one purchase document in the profile's custody and print the identity a purchase names it by."""
    result = add_inventory_evidence(
        ctx,
        request=InventoryEvidenceAddRequest(
            profile_id=UUID(_inventory_bucket_id()),
            source_path=source_path,
            source_directory=str(Path.cwd()),
        ),
    )
    emit_envelope(
        ctx,
        command="ledger.inventory.evidence.add",
        result=result,
        lines=(f"reference\t{result.reference}", f"content_digest\t{result.content_digest}"),
    )


def inventory_closing_value_record(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    file: Path,
) -> None:
    """Read the plain facts of one closing value, then record it in the profile worker."""
    bucket_id = _inventory_bucket_id()
    try:
        facts = InventoryClosingValueFactsInput.model_validate_json(file.read_text(encoding=UTF_8_ENCODING))
    except (OSError, ValidationError) as exc:
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.closing_value_file_invalid"),
            param_hint="--file",
        ) from exc
    request = InventoryClosingValueRecordRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        facts=facts,
    )
    _completion, result = record_inventory_closing_value(ctx, request=request)
    emit_envelope(
        ctx,
        command="ledger.inventory.closing-value.record",
        result=result,
        lines=(
            f"actividad_id\t{result.actividad_id}",
            f"year\t{result.year}",
            f"authority_record_fingerprint\t{result.authority_record_fingerprint}",
        ),
    )


__all__ = [
    "inventory_closing_authority_record",
    "inventory_closing_value_record",
    "inventory_correct",
    "inventory_create",
    "inventory_describe",
    "inventory_evidence_add",
    "inventory_inspect",
    "inventory_list",
    "inventory_movement_add",
    "inventory_movement_correct",
    "inventory_movement_reverse",
    "inventory_restore",
    "inventory_retire",
    "inventory_valuation_preview",
]
