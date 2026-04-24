"""Strict pydantic v2 records for the reconciliation comparator.

Every record in this module is ``strict=True``, ``frozen=True``,
``extra="forbid"`` and carries the Layer 1 write-guard marker
``mode: Literal["read"] = "read"``. Reports cross subpackage
boundaries (the CLI consumes them, the sync-run summary surfaces
them, the persistence adapter serialises them) so the strict-frozen
invariant is the same load-bearing one the rest of the project pins
against. No ``"write"`` literal is defined anywhere in this
subpackage; widening the marker requires a loud, explicit change
that surfaces in code review.

Two consumer-facing collaborators are referenced by type:

* :class:`aeat.remote.RemoteFilingRef` — the lightweight reference the
  comparator embeds when AEAT did surface a filing.
* :class:`aeat.filing.FilingDraftStatus` — re-exported as a typed
  field on :class:`FilingDraftRef` so the persisted report carries the
  draft's lifecycle status without forcing consumers to re-load the
  draft to interpret it.

The module also publishes :data:`KIND_TO_STATUS`, a static
:class:`types.MappingProxyType` that binds every
:class:`FilingDivergenceKind` variant to the
:class:`ReconciliationStatus` it implies. The comparator aggregates
per-casilla kinds into the report status by reducing through this
table; reviewers see the kind-to-status binding in one place rather
than scattered across conditional branches.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ...i18n import Translatable
from ...remote import RemoteFilingRef
from .._schema import FilingDraftStatus
from ._kind import FilingDivergenceKind

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_MODE_READ: Literal["read"] = "read"
"""Shared default for every ``mode`` field in this module."""


class ReconciliationStatus(StrEnum):
    """Kent-observable terminal triad for one reconciliation pass.

    Every reconciliation report resolves to exactly one member. The
    triad is mutually exclusive: :attr:`NOT_YET_FOUND` precludes any
    per-casilla comparison (AEAT has no record), and
    :attr:`DIVERGENT` strictly requires at least one non-rounding,
    non-not-yet-found divergence kind on the report.
    """

    MATCH = "match"
    """Zero divergences, or only :attr:`FilingDivergenceKind.ROUNDING_ONLY`."""
    DIVERGENT = "divergent"
    """One or more divergences outside the rounding tolerance."""
    NOT_YET_FOUND = "not_yet_found"
    """AEAT has no record of the expected ``(modelo, period)`` filing."""


class CasillaDelta(BaseModel):
    """One casilla-scoped divergence on a :class:`ReconciliationReport`.

    Attributes:
        casilla_id: Stable casilla identifier the delta refers to.
            Carries the sentinel ``"*"`` when the kind is
            :attr:`FilingDivergenceKind.FILING_NOT_YET_FOUND` or
            :attr:`FilingDivergenceKind.FILING_STATUS_DIVERGENCE`
            (the divergence is filing-scoped rather than casilla-scoped).
        kind: The :class:`FilingDivergenceKind` variant this delta
            instantiates.
        local_value: The local draft's printed value, or ``None`` when
            the local draft did not carry the casilla.
        remote_value: AEAT's printed value, or ``None`` when AEAT did
            not carry the casilla.
        delta: The signed monetary delta (``local - remote``) when both
            sides report a coercible decimal value; ``None`` otherwise.
        mode: Structural write-guard literal; always ``"read"``.
        narrative: Trilingual Kent-readable rationale for this delta.
    """

    model_config = _STRICT_FROZEN

    casilla_id: str = Field(min_length=1, max_length=16)
    kind: FilingDivergenceKind
    local_value: str | None = Field(default=None, max_length=256)
    remote_value: str | None = Field(default=None, max_length=256)
    delta: Decimal | None = None
    mode: Literal["read"] = _MODE_READ
    narrative: Translatable


class FilingDraftRef(BaseModel):
    """Lightweight reference to a :class:`aeat.filing.FilingDraft`.

    The comparator embeds a :class:`FilingDraftRef` rather than the
    full :class:`aeat.filing.FilingDraft` so persisted reports stay
    cheap to serialise and easy to deduplicate.

    Attributes:
        draft_id: Content-addressed identifier of the local draft.
        modelo: AEAT modelo code carried by the draft.
        period: Period identifier carried by the draft.
        profile_tax_id: Taxpayer identifier the draft was built for.
        status: Lifecycle status of the draft at the moment the
            report was emitted.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    profile_tax_id: str = Field(min_length=1, max_length=64)
    status: FilingDraftStatus
    mode: Literal["read"] = _MODE_READ


class ReconciliationReport(BaseModel):
    """Frozen report produced by :func:`reconcile`.

    Attributes:
        status: The Kent-observable terminal triad member the report
            resolves to.
        casilla_deltas: Ordered tuple of every divergence the
            comparator surfaced. Empty for :attr:`ReconciliationStatus.MATCH`
            with zero rounding entries; carries one sentinel entry
            for :attr:`ReconciliationStatus.NOT_YET_FOUND`.
        remote_ref: Reference to the AEAT-side filing that anchored
            the comparison, or ``None`` when ``status`` is
            :attr:`ReconciliationStatus.NOT_YET_FOUND`.
        draft_ref: Reference to the local draft side of the
            comparison.
        mode: Structural write-guard literal; always ``"read"``.
        reconciled_at: UTC timestamp at which the comparator emitted
            the report.
        narrative: Trilingual report-level summary that Kent reads at
            the top of the CLI output and inside the sync-run summary.
    """

    model_config = _STRICT_FROZEN

    status: ReconciliationStatus
    casilla_deltas: tuple[CasillaDelta, ...]
    remote_ref: RemoteFilingRef | None
    draft_ref: FilingDraftRef
    mode: Literal["read"] = _MODE_READ
    reconciled_at: AwareDatetime
    narrative: Translatable


KIND_TO_STATUS: Mapping[FilingDivergenceKind, ReconciliationStatus] = MappingProxyType(
    {
        FilingDivergenceKind.CASILLA_VALUE_MISMATCH: ReconciliationStatus.DIVERGENT,
        FilingDivergenceKind.CASILLA_MISSING_LOCAL: ReconciliationStatus.DIVERGENT,
        FilingDivergenceKind.CASILLA_EXTRA_LOCAL: ReconciliationStatus.DIVERGENT,
        FilingDivergenceKind.FILING_STATUS_DIVERGENCE: ReconciliationStatus.DIVERGENT,
        FilingDivergenceKind.ROUNDING_ONLY: ReconciliationStatus.MATCH,
        FilingDivergenceKind.FILING_NOT_YET_FOUND: ReconciliationStatus.NOT_YET_FOUND,
    }
)
"""Static binding from :class:`FilingDivergenceKind` to the report status.

The comparator aggregates per-delta kinds via this table:
:attr:`ReconciliationStatus.NOT_YET_FOUND` short-circuits the report
the moment any delta carries
:attr:`FilingDivergenceKind.FILING_NOT_YET_FOUND`;
:attr:`ReconciliationStatus.DIVERGENT` wins over
:attr:`ReconciliationStatus.MATCH` whenever any non-rounding-only
divergence is present; otherwise the report reports
:attr:`ReconciliationStatus.MATCH`.
"""


__all__ = [
    "KIND_TO_STATUS",
    "CasillaDelta",
    "FilingDraftRef",
    "ReconciliationReport",
    "ReconciliationStatus",
]
