"""Typer registration for ledger inventory commands.

The commands delegate inventory persistence and valuation to
:class:`InventoryService` and emit typed payloads
from :mod:`._ledger_payloads`.
"""

from __future__ import annotations

import json

import typer
from pydantic import ValidationError

from ...application.inventory import InventoryMovementCommand, InventoryService
from ...core.i18n import tr
from ...domain.contribuyente.inventory import (
    InventoryAcquisitionCost,
    InventoryClosingAuthorityRecord,
    InventoryLedger,
    MovementKind,
)
from ._common import (
    _emit_envelope,
    _parse_iso_date,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._common import (
    active_bucket_id_or_refuse as _inventory_bucket_id,
)
from ._config._secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)
from ._ledger_payloads import (
    InventoryClosingAuthorityRecordResult,
    InventoryCreateResult,
    InventoryListResult,
    InventoryMovementAddResult,
    InventoryValuationPreviewPayload,
)


class _InventoryClosingAuthorityInput(MachineSecretPayload):
    """Strict bounded structured input; values never appear in argv or output."""

    decision: dict[str, object]
    physical_observation: dict[str, object] | None
    prior_closing_link: dict[str, object]


def _inventory_service() -> InventoryService:
    return InventoryService()


def _safe_inventory_ledger_payload(ledger: InventoryLedger) -> dict[str, object]:
    """Project a ledger without evidence references or content digests."""
    payload: dict[str, object] = json.loads(ledger.model_dump_json())
    authority = payload.pop("closing_authority_record", None)
    if isinstance(authority, dict) and ledger.closing_authority_record is not None:
        record = ledger.closing_authority_record
        payload["closing_authority_fingerprints"] = {
            "record": record.fingerprint,
            "decision": record.decision.fingerprint,
            "physical_observation": (
                record.physical_observation.fingerprint if record.physical_observation is not None else None
            ),
            "prior_closing_link": record.prior_closing_link.fingerprint,
        }
    movements = payload["period_movements"]
    assert isinstance(movements, list)
    for movement in movements:
        assert isinstance(movement, dict)
        acquisition = movement.get("acquisition_cost")
        if not isinstance(acquisition, dict):
            continue
        evidence = acquisition.get("evidence")
        components = acquisition.get("attributable_cost_components")
        movement["acquisition_cost"] = {
            "consideration_excluding_iva": acquisition["consideration_excluding_iva"],
            "directly_attributable_cost_total": acquisition["directly_attributable_cost_total"],
            "nonrecoverable_iva_included": acquisition["nonrecoverable_iva_included"],
            "recoverable_iva_excluded": acquisition["recoverable_iva_excluded"],
            "total_acquisition_cost": acquisition["total_acquisition_cost"],
            "component_count": len(components) if isinstance(components, list) else 0,
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "complete": True,
        }
    return payload


def _parse_acquisition_cost(*, from_stdin: bool) -> InventoryAcquisitionCost | None:
    """Read one acquisition-cost object from the non-argv stdin channel."""
    if not from_stdin:
        return None
    value = typer.get_text_stream("stdin").read()
    try:
        return InventoryAcquisitionCost.model_validate_json(value)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}" for error in exc.errors())
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.acquisition_cost_invalid", details=details),
            param_hint="--acquisition-cost-stdin",
        ) from exc


def inventory_list(ctx: typer.Context) -> None:
    """List per-actividad ledgers via :meth:`InventoryService.list_all`."""
    bucket_id = _inventory_bucket_id()
    rows = _inventory_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(
            f"{row.actividad_id}\t{row.year}\t{row.valuation_method.value}\t"
            f"opening={row.opening_stock}\tmovements={row.movement_count}",
        )
    _emit_envelope(
        ctx,
        command="ledger.inventory.list",
        result=InventoryListResult.model_validate(payload),
        lines=lines,
    )


def inventory_create(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    valuation_method: str,
    opening_stock: str = "0",
) -> None:
    """Create a ledger via :meth:`InventoryService.create`."""
    bucket_id = _inventory_bucket_id()
    result = _inventory_service().create(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        valuation_method=valuation_method,
        opening_stock=parse_decimal_amount(opening_stock, label="opening-stock"),
    )
    ledger = result.ledger
    payload = _safe_inventory_ledger_payload(ledger)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit_envelope(
        ctx,
        command="ledger.inventory.create",
        result=InventoryCreateResult.model_validate_json(json.dumps(payload)),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"valuation_method\t{ledger.valuation_method.value}",
            f"opening_stock\t{ledger.opening_stock}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
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
    """Append an :class:`InventoryMovementCommand` to an actividad ledger."""
    bucket_id = _inventory_bucket_id()
    command = InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=_parse_iso_date(movement_date, label="--date"),
        kind=kind,
        quantity=parse_decimal_amount(quantity, label="quantity"),
        unit_cost=parse_optional_decimal_amount(unit_cost, label="unit-cost"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        acquisition_cost=_parse_acquisition_cost(from_stdin=acquisition_cost_stdin),
    )
    result = _inventory_service().movement_add(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        movement=command,
    )
    ledger = result.ledger
    payload = _safe_inventory_ledger_payload(ledger)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit_envelope(
        ctx,
        command="ledger.inventory.movement.add",
        result=InventoryMovementAddResult.model_validate_json(json.dumps(payload)),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"movements\t{len(ledger.period_movements)}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
) -> None:
    """Preview valuation via :meth:`InventoryService.valuation_preview`."""
    bucket_id = _inventory_bucket_id()
    result = _inventory_service().valuation_preview(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
    preview = result.preview
    _emit_envelope(
        ctx,
        command="ledger.inventory.valuation.preview",
        result=InventoryValuationPreviewPayload.from_result(result),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{preview.actividad_id}",
            f"year\t{preview.year}",
            f"valuation_method\t{preview.valuation_method.value}",
            f"derived_closing_value\t{preview.derived_closing_value}",
            f"cogs\t{preview.cogs}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


def inventory_closing_authority_record(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    authority_stdin: bool = False,
    authority_fd: int | None = None,
) -> None:
    """Record one complete authority bundle through a bounded non-argv channel."""
    selection = select_machine_secret_channel(secrets_stdin=authority_stdin, secrets_fd=authority_fd)
    if selection is None:
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.authority_channel_required"),
            param_hint="--authority-stdin/--authority-fd",
        )
    incoming = read_machine_secret_payload(_InventoryClosingAuthorityInput, selection=selection)
    try:
        record = InventoryClosingAuthorityRecord.model_validate_json(
            incoming.model_dump_json(),
        )
        result = _inventory_service().closing_authority_record(
            bucket_id=_inventory_bucket_id(),
            actividad_id=actividad_id,
            year=year,
            authority_record=record,
        )
    except ValidationError as exc:
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.authority_invalid"),
            param_hint="--authority-stdin/--authority-fd",
        ) from exc
    persisted = result.ledger.closing_authority_record
    assert persisted is not None
    payload = InventoryClosingAuthorityRecordResult(
        actividad_id=actividad_id,
        year=year,
        authority_record_fingerprint=persisted.fingerprint,
        decision_fingerprint=persisted.decision.fingerprint,
        physical_observation_fingerprint=(
            persisted.physical_observation.fingerprint if persisted.physical_observation is not None else None
        ),
        prior_closing_link_fingerprint=persisted.prior_closing_link.fingerprint,
    )
    _emit_envelope(
        ctx,
        command="ledger.inventory.closing-authority.record",
        result=payload,
        lines=(
            f"actividad_id\t{actividad_id}",
            f"year\t{year}",
            f"authority_record_fingerprint\t{persisted.fingerprint}",
        ),
    )
