"""Stable operation identifiers and refusal vocabulary for suffered-withholding absence attestations."""

from __future__ import annotations

from typing import Final, Literal

__all__ = [
    "RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID",
    "RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID",
    "RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE",
    "RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES",
    "RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE",
    "RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID",
    "RetencionSoportadaAbsenceOperationId",
    "RetencionSoportadaAbsenceOperationRefusalReason",
]

RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.attest_absence"
RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.withdraw_absence"
RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.list_absences"

RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE: Final = "REFUSED_RETENCION_SOPORTADA_ABSENCE"
"""The registered code of every refusal except a stale revision."""

RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE: Final = "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"
"""The registered code of a write prepared against a revision that moved; shared with the payer records."""

type RetencionSoportadaAbsenceOperationId = Literal["attest", "withdraw", "list"]

type RetencionSoportadaAbsenceOperationRefusalReason = Literal[
    "ejercicio_unsupported",
    "family_not_declared",
    "records_present",
    "already_attested",
    "not_attested",
    "stale_revision",
]
"""Why an attestation or its withdrawal was refused before any change was stored."""

RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES: Final[frozenset[str]] = frozenset(
    {RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE, RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE},
)
