"""Error hierarchy for the reconciliation comparator.

Every error inherits from :class:`aeat.errors.AeatError` per the
project-wide convention. The reconciler is a pure comparator and does
not raise on per-casilla mismatches — those are surfaced via the
typed :class:`ReconciliationReport`. The only errors that escape the
comparator are programming-time invariants (e.g. an unhandled
:class:`FilingDivergenceKind` variant in a switch site) and
persistence-side adapter failures.
"""

from __future__ import annotations

from ...errors import AeatError


class ReconciliationError(AeatError):
    """Base error for the :mod:`aeat.filing.reconciliation` subpackage."""


__all__ = ["ReconciliationError"]
