"""Typed JSON payloads for the suffered-withholding absence attestation CLI.

This module uses :class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class RetencionSoportadaAbsencePayload(OutputSchema):
    """One stored absence attestation, an operator assertion and never a payer's statement."""

    ejercicio: int
    income_class: str
    note: str
    state: str
    attested_at: str
    withdrawn_at: str | None = None
    revision_id: str


class RetencionSoportadaAbsenceRowPayload(RetencionSoportadaAbsencePayload):
    """One listed absence attestation with the label of its income class."""

    income_class_label: str


class RetencionSoportadaListAbsencesResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada list-absences``."""

    bucket_id: BucketId
    ejercicio: int
    attestations: list[RetencionSoportadaAbsenceRowPayload]
    count: int


class RetencionSoportadaAttestAbsenceResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada attest-absence``."""

    bucket_id: BucketId
    attestation: RetencionSoportadaAbsencePayload


class RetencionSoportadaWithdrawAbsenceResult(OutputSchema):
    """JSON envelope for ``aeat app ledger retencion-soportada withdraw-absence``."""

    bucket_id: BucketId
    attestation: RetencionSoportadaAbsencePayload


__all__ = [
    "RetencionSoportadaAbsencePayload",
    "RetencionSoportadaAbsenceRowPayload",
    "RetencionSoportadaAttestAbsenceResult",
    "RetencionSoportadaListAbsencesResult",
    "RetencionSoportadaWithdrawAbsenceResult",
]
