"""Stable operation identifiers and refusal vocabulary for the pension contribution certificate records."""

from __future__ import annotations

from typing import Final, Literal

PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID: Final = "ledger.prevision_social.list"
PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID: Final = "ledger.prevision_social.record"
PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID: Final = "ledger.prevision_social.remove"

PREVISION_SOCIAL_WRITE_REFUSAL_CODE: Final = "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_WRITE"
"""The registered code of every refusal except a stale revision."""

PREVISION_SOCIAL_REVISION_REFUSAL_CODE: Final = "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_REVISION_CONFLICT"
"""The registered code of a write or removal prepared against a revision that moved."""

type PrevisionSocialOperationId = Literal["list", "record", "remove"]

type PrevisionSocialRefusalReason = Literal[
    "ejercicio_unsupported",
    "identity_mismatch",
    "certificate_not_in_custody",
    "unplaced_clave",
    "indirect_match",
    "design_not_bundled",
    "same_plan_split_unstated",
    "beneficiary_out_of_scope",
    "stale_revision",
    "certificate_fingerprint_required",
    "certificate_file_unreadable",
    "certificate_fingerprint_mismatch",
    "clave_pair_undefined",
    "not_found",
    "validation",
]
"""Why an operation was refused before any change was stored.

The first eight are the write path's own refusals, the five placement refusals
among them; the rest are settled by the operation before the write path runs.
"""

PREVISION_SOCIAL_REFUSAL_CODES: Final[frozenset[str]] = frozenset(
    {PREVISION_SOCIAL_WRITE_REFUSAL_CODE, PREVISION_SOCIAL_REVISION_REFUSAL_CODE},
)
