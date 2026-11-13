"""Stable operation identifiers and refusal vocabulary for the Modelo 232 related-party statements."""

from __future__ import annotations

from typing import Final, Literal

__all__ = [
    "M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_REFUSAL_CODE",
    "M232_RELATED_PARTY_REFUSAL_CODES",
    "M232_RELATED_PARTY_REVISION_REFUSAL_CODE",
    "M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID",
    "M232_RELATED_PARTY_WRITE_DEFINITION_IDS",
    "Modelo232RelatedPartyOperationId",
    "Modelo232RelatedPartyOperationRefusalReason",
]

M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.state_operation"
M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID: Final = (
    "ledger.operaciones_vinculadas.withdraw_operation"
)
M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.state_none"
M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.withdraw_none"
M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.state_turnover"
M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.withdraw_turnover"
M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID: Final = "ledger.operaciones_vinculadas.list"

M232_RELATED_PARTY_WRITE_DEFINITION_IDS: Final[frozenset[str]] = frozenset(
    {
        M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
    }
)
"""Every definition that commits a statement or its withdrawal."""

M232_RELATED_PARTY_REFUSAL_CODE: Final = "REFUSED_MODELO_232_RELATED_PARTY"
"""The registered code of every refusal except a stale revision."""

M232_RELATED_PARTY_REVISION_REFUSAL_CODE: Final = "REFUSED_MODELO_232_RELATED_PARTY_REVISION_CONFLICT"
"""The registered code of a write prepared against a guard or row revision that moved."""

type Modelo232RelatedPartyOperationId = Literal[
    "state_operation",
    "withdraw_operation",
    "state_none",
    "withdraw_none",
    "state_turnover",
    "withdraw_turnover",
    "list",
]

type Modelo232RelatedPartyOperationRefusalReason = Literal[
    "ejercicio_unsupported",
    "code_unknown",
    "already_stated",
    "not_stated",
    "none_stated",
    "operations_present",
    "specific_operation_required",
    "stale_revision",
    "validation",
]
"""Why a statement or its withdrawal was refused before any change was stored.

Every reason but ``validation`` is the guarded write path's own; ``validation``
names a statement whose fields do not form a Modelo 232 payload of its kind.
"""

M232_RELATED_PARTY_REFUSAL_CODES: Final[frozenset[str]] = frozenset(
    {M232_RELATED_PARTY_REFUSAL_CODE, M232_RELATED_PARTY_REVISION_REFUSAL_CODE},
)
