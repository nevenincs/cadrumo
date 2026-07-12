"""Typed-id aliases for modelo records.

Each modelo record (work unit, calculation revision, filing record)
carries a content-addressed SHA-256 identity. The aliases here pin the
hex-64 shape at the pydantic boundary so a malformed identifier is
rejected on construction rather than leaking into persisted records.

The four identities share the same string-level shape but carry
distinct semantic roles (a work-unit id is not assignable to a
filing-record id field). Keeping them as separate aliases preserves
that distinction for downstream call sites; collapsing them to a
single hex-64 alias would lose the role separation.

The cross-cutting bucket identity lives in :mod:`aeat.core.identity`
because it is a per-profile storage-container identity owned by the
persistence boundary, not by any record domain. The ledger-transaction
identity lives in :mod:`aeat.domain.transactions._ids` under
owner-domain placement; the modelo records never reference the
transaction identity directly so no sibling-domain import is required.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

WorkUnitId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of a modelo work unit. Minted via ``new_work_unit_id()``."""

CalculationRevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of one calculation revision under a work unit."""

FilingRecordId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of one filing record bound to a calculation revision."""

VerificationReportId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of one verification report bound to a calculation revision."""

__all__ = (
    "CalculationRevisionId",
    "FilingRecordId",
    "VerificationReportId",
    "WorkUnitId",
)
