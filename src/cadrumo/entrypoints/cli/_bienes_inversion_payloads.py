"""Typed JSON payloads for the capital-goods IVA regularización register CLI.

Each result model is a strict
:class:`OutputSchema` subclass referenced as a deferred public target under a
stable ``command`` key so the ``emit_envelope`` spine and the JSON-schema
conformance gate bind the ``aeat app ledger bienes-inversion`` leaves to a schema.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...core.json_contract import OutputSchema


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


class BienesInversionDeclareResult(OutputSchema):
    """JSON envelope for ``aeat app ledger bienes-inversion declare``."""

    bucket_id: BucketId
    record: BienInversionRecordPayload
    count: int


class BienesInversionListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger bienes-inversion list``."""

    bucket_id: BucketId
    rows: list[BienInversionRecordPayload]
    count: int


__all__ = [
    "BienInversionDisposalPayload",
    "BienInversionRecordPayload",
    "BienesInversionDeclareResult",
    "BienesInversionListResult",
]
