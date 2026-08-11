"""Typed JSON payloads for the capital-goods IVA regularización register CLI.

Each result model is a strict
:class:`OutputSchema` subclass registered under a
stable ``command`` key so the ``_emit_envelope`` spine and the JSON-schema
conformance gate bind the ``aeat app ledger bienes-inversion`` leaves to a schema.
"""

from __future__ import annotations

from ...core.json_contract import OutputSchema, register_schema


class BienInversionDisposalPayload(OutputSchema):
    """Optional LIVA art-110 disposal event on a register record."""

    year: int
    regime: str


class BienInversionRecordPayload(OutputSchema):
    """One capital-good register record.

    Mirrors :class:`BienInversionIvaRecord`'s
    ``model_dump(mode='json')`` plus the derived ``deduccion_efectuada`` the CLI
    appends at the emit site.
    """

    identifier: str
    description: str
    acquisition_year: int
    cuota_soportada: str
    prorrata_inicial_pct: str
    kind: str
    art108_elegible: bool
    asset_record_ref: str | None = None
    acquisition_ledger_id: str
    prorrata_sector_id: str | None = None
    disposal: BienInversionDisposalPayload | None = None
    deduccion_efectuada: str
    schema_version: str


@register_schema("ledger.bienes_inversion.declare")
class BienesInversionDeclareResult(OutputSchema):
    """JSON envelope for ``aeat app ledger bienes-inversion declare``."""

    bucket_id: str
    record: BienInversionRecordPayload
    count: int


@register_schema("ledger.bienes_inversion.list")
class BienesInversionListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger bienes-inversion list``."""

    bucket_id: str
    rows: list[BienInversionRecordPayload]
    count: int


__all__ = [
    "BienInversionDisposalPayload",
    "BienInversionRecordPayload",
    "BienesInversionDeclareResult",
    "BienesInversionListResult",
]
