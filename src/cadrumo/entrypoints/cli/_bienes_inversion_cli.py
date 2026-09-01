"""Behavior handlers for the capital-goods IVA regularización register.

The commands delegate register persistence to
:class:`BienesInversionRegisterService` and emit
typed payloads from :mod:`._bienes_inversion_payloads`. The
register feeds the LIVA arts. 107-110 regularización (Modelo 303 casilla 43 /
Modelo 390); the annual compute itself is the pure domain function
:func:`compute_regularizacion_anual`.
"""

from __future__ import annotations

import typer

from ...application.bienes_inversion.service import BienesInversionRegisterService
from ...core.i18n.render import tr
from ...domain.bienes_inversion.register import (
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from ._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionRecordPayload,
)
from ._common import _bad, emit_envelope
from ._common import active_bucket_id_or_refuse as _register_bucket_id
from ._decimal_parsing import parse_decimal_amount


def _parse_kind(raw: BienInversionKind) -> BienInversionKind:
    return raw


def _parse_disposal_regime(raw: str) -> BienInversionDisposalRegime:
    try:
        return BienInversionDisposalRegime(raw)
    except ValueError as exc:
        accepted = ", ".join(member.value for member in BienInversionDisposalRegime)
        raise _bad(
            tr(
                "cli.app.ledger.bienes_inversion.unknown_disposal_regime",
                default="Unknown disposal regime {regime!r}; accepted: {accepted}",
                regime=raw,
                accepted=accepted,
            ),
        ) from exc


def _record_payload(record: BienInversionIvaRecord) -> BienInversionRecordPayload:
    data = record.model_dump(mode="json")
    data["deduccion_efectuada"] = str(record.deduccion_efectuada)
    return BienInversionRecordPayload.model_validate(data)


def bienes_inversion_declare(
    ctx: typer.Context,
    identifier: str,
    description: str,
    acquisition_year: int,
    acquisition_ledger_id: str,
    cuota_soportada: str,
    prorrata_inicial_pct: str,
    kind: BienInversionKind,
    art108_elegible: bool = True,
    asset_record_ref: str | None = None,
    prorrata_sector_id: str | None = None,
    disposal_year: int | None = None,
    disposal_regime: str | None = None,
) -> None:
    """Persist one :class:`BienInversionIvaRecord`."""
    bucket_id = _register_bucket_id()
    disposal: BienInversionDisposal | None = None
    if disposal_year is not None or disposal_regime is not None:
        if disposal_year is None or disposal_regime is None:
            raise _bad(
                tr(
                    "cli.app.ledger.bienes_inversion.disposal_requires_both",
                    default="--disposal-year and --disposal-regime must be supplied together.",
                ),
            )
        disposal = BienInversionDisposal(year=disposal_year, regime=_parse_disposal_regime(disposal_regime))
    record = BienInversionIvaRecord(
        identifier=identifier,
        description=description,
        acquisition_year=acquisition_year,
        cuota_soportada=parse_decimal_amount(cuota_soportada, label="cuota-soportada"),
        prorrata_inicial_pct=parse_decimal_amount(prorrata_inicial_pct, label="prorrata-inicial"),
        kind=_parse_kind(kind),
        art108_elegible=art108_elegible,
        asset_record_ref=asset_record_ref,
        acquisition_ledger_id=acquisition_ledger_id,
        prorrata_sector_id=prorrata_sector_id,
        disposal=disposal,
    )
    register = BienesInversionRegisterService().declare(record)
    payload = BienesInversionDeclareResult(
        bucket_id=bucket_id,
        record=_record_payload(record),
        count=len(register.records),
    )
    emit_envelope(
        ctx,
        command="ledger.bienes_inversion.declare",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"identifier\t{record.identifier}",
            f"acquisition_year\t{record.acquisition_year}",
            f"kind\t{record.kind.value}",
            f"cuota_soportada\t{record.cuota_soportada}",
            f"prorrata_inicial_pct\t{record.prorrata_inicial_pct}",
            f"deduccion_efectuada\t{record.deduccion_efectuada}",
            f"count\t{len(register.records)}",
        ),
    )


def bienes_inversion_list(ctx: typer.Context) -> None:
    """List register records via :class:`BienesInversionRegisterService`."""
    bucket_id = _register_bucket_id()
    register = BienesInversionRegisterService().list_all()
    rows = [_record_payload(record) for record in register.records]
    payload = BienesInversionListResult(bucket_id=bucket_id, rows=rows, count=len(rows))
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for record in register.records:
        lines.append(
            f"{record.identifier}\t{record.acquisition_year}\t{record.kind.value}\t"
            f"cuota={record.cuota_soportada}\tprorrata={record.prorrata_inicial_pct}",
        )
    emit_envelope(
        ctx,
        command="ledger.bienes_inversion.list",
        result=payload,
        lines=lines,
    )
