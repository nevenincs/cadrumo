"""FilingDraft ↔ Justificante reconciliation (#239).

Takes Kent's locally-approved :class:`aeat.filing.FilingDraft` and the
:class:`aeat.justificante.Justificante` parsed from AEAT's
authoritative PDF record, and emits a :class:`ReconciliationReport`
with a single Kent-observable verdict: MATCH / DIVERGENT /
NOT_YET_FOUND.

This module replaces the pre-discovery speculative reconciliation
against an invented ``RemoteFiling`` record. Every field compared
here is one AEAT actually prints on its justificante PDFs, verified
against live captures on 2026-04-24.

Public API:

    from aeat.filing.reconciliation import (
        FieldMismatch,
        FilingDivergenceKind,
        FilingDraftRef,
        JustificanteRefSummary,
        ReconciliationReport,
        ReconciliationStatus,
        reconcile,
    )
"""

from __future__ import annotations

from ._kind import FilingDivergenceKind
from ._reconcile import reconcile
from ._schema import (
    FieldMismatch,
    FilingDraftRef,
    JustificanteRefSummary,
    ReconciliationReport,
    ReconciliationStatus,
)

__all__ = [
    "FieldMismatch",
    "FilingDivergenceKind",
    "FilingDraftRef",
    "JustificanteRefSummary",
    "ReconciliationReport",
    "ReconciliationStatus",
    "reconcile",
]
