"""Reconcile a local :class:`ModeloDraft` against an AEAT :class:`Justificante`.

Takes a locally-approved :class:`aeat.domain.filing.ModeloDraft` and
the :class:`aeat.domain.justificante.Justificante` parsed from AEAT's
authoritative PDF record, then emits a
:class:`ReconciliationReport` with a single user-observable verdict:
``MATCH`` / ``DIVERGENT`` / ``NOT_YET_FOUND``.

Every field compared here is one AEAT actually prints on its
justificante PDFs, so the reconciliation surface stays tight to
ground truth rather than to a speculative remote-filing schema.

Examples:
    >>> from aeat.application.filing.reconciliation import reconcile
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
