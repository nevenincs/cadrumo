"""Closed enumeration of filing-instance reconciliation divergence kinds.

This enum is intentionally **disjoint** from
:class:`aeat.sync._divergence.DivergenceKind`. The sync divergence
vocabulary is the backbone of the bounded auto-heal contract — its
``ADDITIVE`` classification implies *safe-to-heal* on schema-level
drift (corpus additions, ruleset removals, portal URL changes). Adding
filing-instance value divergences to that enum would silently widen
the auto-heal surface to per-filing comparisons that must never be
auto-healed: AEAT's authoritative record cannot be reconciled by the
system mutating either side.

The accepted ``aeat-verify`` ADR therefore forks the vocabulary along
the orthogonal axis. Reviewers reading
:class:`aeat.sync._divergence.DivergenceKind` continue to see only the
schema-safety axis; reviewers reading :class:`FilingDivergenceKind`
see only the filing-value axis. The two enums are persisted via the
same Kent-facing queue (see :mod:`aeat.filing.reconciliation._persist`)
but the discriminator on the persisted payload distinguishes them at
consumer sites.

Variants:

* :attr:`FilingDivergenceKind.CASILLA_VALUE_MISMATCH` — both sides
  carry a value for the casilla and the absolute delta exceeds
  :data:`aeat.filing.reconciliation.RECONCILIATION_TOLERANCE`.
* :attr:`FilingDivergenceKind.CASILLA_MISSING_LOCAL` — AEAT reports a
  casilla the local draft does not carry.
* :attr:`FilingDivergenceKind.CASILLA_EXTRA_LOCAL` — the local draft
  carries a value AEAT does not.
* :attr:`FilingDivergenceKind.FILING_STATUS_DIVERGENCE` — the local
  draft's lifecycle status disagrees with the remote filing status,
  or the remote status itself is non-terminal-clean (``RECHAZADA`` /
  ``ANULADA`` / ``UNKNOWN``).
* :attr:`FilingDivergenceKind.ROUNDING_ONLY` — the absolute delta lies
  within :data:`aeat.filing.reconciliation.RECONCILIATION_TOLERANCE`.
  Rounding-only entries do not flip the report status away from
  :attr:`ReconciliationStatus.MATCH`.
* :attr:`FilingDivergenceKind.FILING_NOT_YET_FOUND` — AEAT has no
  record of the ``(modelo, period)`` the local draft expects. The
  delta tuple in this case carries a single sentinel entry; per-casilla
  comparison is undefined when the remote is absent.
"""

from __future__ import annotations

from enum import StrEnum


class FilingDivergenceKind(StrEnum):
    """Per-casilla / per-filing divergence kind for reconciliation reports.

    See the module docstring for the rationale separating this enum
    from :class:`aeat.sync._divergence.DivergenceKind`.
    """

    CASILLA_VALUE_MISMATCH = "casilla_value_mismatch"
    """Local and remote both report a value; the delta exceeds tolerance."""
    CASILLA_MISSING_LOCAL = "casilla_missing_local"
    """AEAT reports a casilla the local draft never set."""
    CASILLA_EXTRA_LOCAL = "casilla_extra_local"
    """Local draft has a value AEAT does not."""
    FILING_STATUS_DIVERGENCE = "filing_status_divergence"
    """Local draft status and remote filing status disagree."""
    ROUNDING_ONLY = "rounding_only"
    """Delta within the rounding tolerance; reported but non-blocking."""
    FILING_NOT_YET_FOUND = "filing_not_yet_found"
    """AEAT has no record of the expected ``(modelo, period)`` filing."""


__all__ = ["FilingDivergenceKind"]
