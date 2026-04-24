"""Read-only comparator for ``FilingDraft`` versus ``RemoteFiling``.

``aeat.filing.reconciliation`` owns the typed comparator that walks a
local :class:`aeat.filing.FilingDraft` against AEAT's authoritative
:class:`aeat.remote.RemoteFiling` and emits the Kent-observable
terminal triad locked by the accepted ``aeat-verify`` ADR:
:attr:`ReconciliationStatus.MATCH`,
:attr:`ReconciliationStatus.DIVERGENT`, or
:attr:`ReconciliationStatus.NOT_YET_FOUND`.

Consumers MUST import only from this package; leading-underscore
modules are private and free to change. The comparator is pure,
async-free, and free of any I/O — fetching the remote side is the
caller's responsibility (the :class:`aeat.remote.RemoteFilingFetcher`
Protocol declared in :mod:`aeat.remote` covers the live path; tests
hand a Protocol-conforming Python class directly).

The subpackage is read-only by construction. Every record is strict,
frozen, ``extra="forbid"``; no symbol exported here carries a
write-verb name; no module under this tree references a state-changing
HTTP verb or Playwright primitive. The Layer 3 grep guard at
:mod:`aeat.filing.reconciliation.test_no_write_surface` walks the
full subpackage and rejects any drift.

The :func:`reconcile` function takes a frozen
:class:`aeat.filing.FilingDraft` and an optional
:class:`aeat.remote.RemoteFiling` and returns a frozen
:class:`ReconciliationReport`. The trilingual narrative builder
in :mod:`._narrative` mirrors the
:func:`aeat.verification._verify._compose_narrative` pattern;
:data:`RECONCILIATION_TOLERANCE` mirrors
:data:`aeat.verification._verify._DEFAULT_TOLERANCE` by value so
Kent sees one definition of "rounding" across the project.

Persistence into the existing Kent-facing divergence queue is
handled by :func:`_persist.reconciliation_records`. The closed
``aeat.sync._divergence.DivergencePayload`` discriminated union is
**not** widened (per ADR — adding filing-instance value kinds to that
union would silently widen the bounded auto-heal contract). Instead,
the persistence adapter emits a parallel
:class:`_persist.FilingReconciliationDivergenceRecord` whose shape
mirrors :class:`aeat.sync.DivergenceRecord` while keeping the
filing-value vocabulary isolated.
"""

from __future__ import annotations

from ._errors import ReconciliationError
from ._kind import FilingDivergenceKind
from ._reconcile import reconcile
from ._schema import (
    CasillaDelta,
    FilingDraftRef,
    ReconciliationReport,
    ReconciliationStatus,
)
from ._tolerance import RECONCILIATION_TOLERANCE

__all__ = [
    "RECONCILIATION_TOLERANCE",
    "CasillaDelta",
    "FilingDivergenceKind",
    "FilingDraftRef",
    "ReconciliationError",
    "ReconciliationReport",
    "ReconciliationStatus",
    "reconcile",
]
