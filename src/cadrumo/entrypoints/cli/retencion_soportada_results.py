"""Typed JSON payloads for the suffered-withholding certificate CLI.

No payload carries a payer tax identifier: a record is named by its keyed
``payer_ref`` and the payer's legal name;
:class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class RetencionSoportadaRowPayload(OutputSchema):
    """One stored payer record without the payer's tax identifier."""

    ejercicio: int
    income_class: str
    payer_ref: str
    payer_name: str | None = None
    importe_integro_dinerario: str
    valoracion_especie: str
    retencion: str
    ingreso_a_cuenta: str
    ingreso_a_cuenta_repercutido: str
    reducciones_aplicables: str | None = None
    gastos_deducibles: str | None = None
    pago_a_cuenta: str
    origin: str
    evidence_sha256: str | None = None
    revision_id: str


class RetencionSoportadaRecordResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada record``."""

    bucket_id: BucketId
    row: RetencionSoportadaRowPayload
    count: int


class RetencionSoportadaListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada list``."""

    bucket_id: BucketId
    ejercicio: int
    rows: list[RetencionSoportadaRowPayload]
    count: int


class RetencionSoportadaRemoveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada remove``."""

    bucket_id: BucketId
    ejercicio: int
    income_class: str
    payer_ref: str
    count: int


__all__ = [
    "RetencionSoportadaListResult",
    "RetencionSoportadaRecordResult",
    "RetencionSoportadaRemoveResult",
    "RetencionSoportadaRowPayload",
]
