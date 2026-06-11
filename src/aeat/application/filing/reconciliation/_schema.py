"""Strict pydantic v2 records for ModeloDraft to Justificante reconciliation.

Defines the closed set of record types consumed by :func:`reconcile`
and surfaced in :class:`ReconciliationReport`. Every record is derived
from what AEAT's live post-auth sede actually emits — a justificante
PDF with metadata and totals.

The schema deliberately covers only fields the justificante PDF exposes
directly; per-casilla reconciliation is a modelo-specific follow-up
handled elsewhere.

See :class:`ModeloDivergenceKind` for the closed taxonomy of divergence
reasons referenced by :class:`FieldMismatch`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ....core import Period
from ._kind import ModeloDivergenceKind

_STRICT_FROZEN: Final[ConfigDict] = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
)


class ReconciliationStatus(StrEnum):
    """Operator-observable verdict of a ModeloDraft vs Justificante compare.

    Attributes:
        COINCIDE: Every compared field agreed within tolerance.
        DIVERGENTE: At least one :class:`FieldMismatch` was detected.
        NOT_YET_FOUND: AEAT's sede has no record of a matching
            submission for this ``(modelo, period)``.
    """

    COINCIDE = "coincide"
    DIVERGENTE = "divergente"
    NOT_YET_FOUND = "not_yet_found"


class ModeloDraftRef(BaseModel):
    """Lightweight reference to the local ModeloDraft side of a compare.

    Attributes:
        draft_id: Stable identifier of the source
            :class:`aeat.domain.filing.ModeloDraft`.
        modelo: Modelo code copied verbatim from the draft.
        period: Period label copied verbatim from the draft.
        profile_tax_id: NIF / NIE recorded on the draft's profile.
        mode: Structural read-only marker enforcing the no-write
            invariant of :mod:`aeat.application.filing.reconciliation`.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    profile_tax_id: str = Field(min_length=4, max_length=32)
    mode: Literal["read"] = "read"


class JustificanteRefSummary(BaseModel):
    """Trimmed :class:`aeat.domain.justificante.Justificante` snapshot for a report.

    Carries only the fields the reconciliation compare depends on, so
    the full parsed justificante (with ``source_pdf_path`` and friends)
    does not bleed into persistence layers that have no need for it.

    Attributes:
        csv: Código Seguro de Verificación assigned by AEAT.
        modelo: Modelo code printed on the justificante PDF.
        period: Filing period resolved from the justificante PDF.
        ejercicio: Four-digit fiscal year, when present.
        tax_id: NIF / NIE printed on the justificante PDF.
        presented_at: Timestamp at which AEAT recorded the presentation.
        presentation_id: Número de justificante, when present.
        total_a_ingresar: AEAT-recorded amount payable, in EUR.
        total_a_devolver: AEAT-recorded amount refundable, in EUR.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    csv: str = Field(min_length=8, max_length=32)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
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

    kind: ModeloDivergenceKind
    field_name: str = Field(min_length=1, max_length=64)
    draft_value: str = Field(max_length=256)
    remote_value: str = Field(max_length=256)
    mode: Literal["read"] = "read"


class ReconciliationReport(BaseModel):
    """Operator-observable outcome of reconciling one ModeloDraft.

    Returned by :func:`reconcile` for every compare. The ``status``
    field is the primary verdict; ``mismatches`` carries the detailed
    per-field breakdown when ``status`` is
    :attr:`ReconciliationStatus.DIVERGENTE`.

    Attributes:
        status: One of :class:`ReconciliationStatus` — MATCH, DIVERGENT,
            or NOT_YET_FOUND.
        draft_ref: Summary of the local draft that was compared.
        justificante: Snapshot of the AEAT-side justificante; ``None``
            when ``status == NOT_YET_FOUND``.
        mismatches: Tuple of concrete field-level divergences. Empty
            for MATCH; always non-empty for DIVERGENT.
        reconciled_at: UTC timestamp at compare completion.
        narrative: Multilingual (es / en / hu) human-readable summary.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    status: ReconciliationStatus
    draft_ref: ModeloDraftRef
    justificante: JustificanteRefSummary | None
    mismatches: tuple[FieldMismatch, ...] = ()
    reconciled_at: datetime
    narrative: str
    mode: Literal["read"] = "read"


__all__ = [
    "FieldMismatch",
    "JustificanteRefSummary",
    "ModeloDraftRef",
    "ReconciliationReport",
    "ReconciliationStatus",
]
