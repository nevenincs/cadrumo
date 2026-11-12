"""Stable operation identifiers and refusal vocabulary for suffered-withholding certificates."""

from __future__ import annotations

from typing import Final, Literal

RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.list"
RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.record"
RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID: Final = "ledger.retencion_soportada.remove"

RETENCION_SOPORTADA_WRITE_REFUSAL_CODE: Final = "REFUSED_RETENCION_SOPORTADA_WRITE"
"""The registered code of every refusal except a stale revision."""

RETENCION_SOPORTADA_REVISION_REFUSAL_CODE: Final = "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"
"""The registered code of a write or removal prepared against a revision that moved."""

type RetencionSoportadaOperationId = Literal["list", "record", "remove"]

type RetencionSoportadaCertificadoRefusalReason = Literal[
    "own_tax_id",
    "ejercicio_unsupported",
    "family_not_declared",
    "identity_mismatch",
    "stale_revision",
    "repercutido_exceeds_ingreso_a_cuenta",
    "certificate_fingerprint_required",
    "certificate_not_in_custody",
    "certificate_file_unreadable",
    "certificate_fingerprint_mismatch",
    "taxpayer_tax_id_unknown",
    "not_found",
    "validation",
    "trabajo_certificate_figure_missing",
]
"""Why an operation was refused before any change was stored."""

RETENCION_SOPORTADA_REFUSAL_CODES: Final[frozenset[str]] = frozenset(
    {RETENCION_SOPORTADA_WRITE_REFUSAL_CODE, RETENCION_SOPORTADA_REVISION_REFUSAL_CODE},
)
