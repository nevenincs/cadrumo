"""Strict pydantic records for FilingDraft → Justificante reconciliation.

These replace the speculative ``RemoteFiling``-based schema from the
pre-discovery version of this feature. Every record is derived from
what AEAT's live post-auth sede actually emits: a justificante PDF
with metadata + totals. Per-casilla reconciliation is a modelo-specific
follow-up handled elsewhere.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...i18n import Translatable
from ._kind import FilingDivergenceKind

_STRICT_FROZEN: Final[ConfigDict] = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
)


class ReconciliationStatus(StrEnum):
    """Kent-observable verdict of a FilingDraft ↔ Justificante compare."""

    MATCH = "match"
    DIVERGENT = "divergent"
    NOT_YET_FOUND = "not_yet_found"


class FilingDraftRef(BaseModel):
    """Lightweight reference to the local FilingDraft side of a compare."""

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    profile_tax_id: str = Field(min_length=4, max_length=32)
    mode: Literal["read"] = "read"


class JustificanteRefSummary(BaseModel):
    """The trimmed Justificante snapshot shown in a ReconciliationReport.

    Carries only the fields the reconciliation compare depends on, so
    the full parsed Justificante (with source_pdf_path and friends)
    doesn't bleed into persistence layers that don't need it.
    """

    model_config = _STRICT_FROZEN

    csv: str = Field(min_length=8, max_length=32)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    ejercicio: str | None = Field(default=None, min_length=4, max_length=4)
    tax_id: str = Field(min_length=4, max_length=32)
    presented_at: datetime
    presentation_id: str | None = Field(default=None, min_length=1, max_length=64)
    total_a_ingresar: Decimal | None = None
    total_a_devolver: Decimal | None = None
    mode: Literal["read"] = "read"


class FieldMismatch(BaseModel):
    """One concrete field-level divergence between draft and justificante.

    Attributes:
        kind: Classified divergence variant.
        field_name: Dotted path of the mismatching field (e.g.
            ``"tax_id"``, ``"total_a_ingresar"``).
        draft_value: Stringified draft-side value at the time of compare.
        remote_value: Stringified AEAT-side value at the time of compare.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    kind: FilingDivergenceKind
    field_name: str = Field(min_length=1, max_length=64)
    draft_value: str = Field(max_length=256)
    remote_value: str = Field(max_length=256)
    mode: Literal["read"] = "read"


class ReconciliationReport(BaseModel):
    """The Kent-observable outcome of reconciling one FilingDraft.

    Attributes:
        status: Kent-observable triad verdict.
        draft_ref: Summary of the local draft that was compared.
        justificante: Snapshot of the AEAT-side justificante — ``None``
            when ``status == NOT_YET_FOUND``.
        mismatches: Tuple of concrete field-level divergences
            (empty for ``MATCH``; always non-empty for ``DIVERGENT``).
        reconciled_at: UTC timestamp at compare completion.
        narrative: Trilingual (es/en/hu) human-readable summary.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    status: ReconciliationStatus
    draft_ref: FilingDraftRef
    justificante: JustificanteRefSummary | None
    mismatches: tuple[FieldMismatch, ...] = ()
    reconciled_at: datetime
    narrative: Translatable
    mode: Literal["read"] = "read"


__all__ = [
    "FieldMismatch",
    "FilingDraftRef",
    "JustificanteRefSummary",
    "ReconciliationReport",
    "ReconciliationStatus",
]
