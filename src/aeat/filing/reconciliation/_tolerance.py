"""Rounding tolerance shared with the local PDF-vs-engine verifier.

The accepted ``aeat-verify`` ADR locks one Kent-visible definition of
"close enough" across the project: the local PDF-vs-engine verifier in
:mod:`aeat.verification` and the local-vs-AEAT reconciler in
:mod:`aeat.filing.reconciliation` both use a single-cent tolerance.
Sourcing the value from a per-deployment setting fragments Kent's
mental model — the verifier could accept 0.01 € while the reconciler
accepts something else, and the same casilla could pass one CLI verb
and fail another. Reusing :data:`RECONCILIATION_TOLERANCE` (which
mirrors :data:`aeat.verification._verify._DEFAULT_TOLERANCE` by value)
keeps a single rounding definition in play.

The duplication is **deliberate**. Importing the constant from
:mod:`aeat.verification` at runtime would create an avoidable inbound
edge in the module dependency graph (the verifier is the older
subpackage and predates this one). The tie is documentational: any
contributor nudging one constant must also nudge the other; the
:func:`tests.test_tolerance` suite asserts the value invariant
locally so the duplication does not silently drift.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

RECONCILIATION_TOLERANCE: Final[Decimal] = Decimal("0.01")
"""Maximum absolute monetary delta still treated as a rounding-only divergence.

Any per-casilla absolute delta strictly less than or equal to this
value is classified as :attr:`FilingDivergenceKind.ROUNDING_ONLY` and
does not flip the report status away from
:attr:`ReconciliationStatus.MATCH`. Anything strictly greater is
classified as :attr:`FilingDivergenceKind.CASILLA_VALUE_MISMATCH` and
flips the report to :attr:`ReconciliationStatus.DIVERGENT`.

Mirrors :data:`aeat.verification._verify._DEFAULT_TOLERANCE` by value
to keep the local PDF-vs-engine verifier and the local-vs-AEAT
reconciler in lockstep on Kent's "rounding" definition. See the
``aeat-verify`` ADR rationale paragraph titled *Rounding tolerance
shared with aeat.verification* for the full reasoning.
"""


__all__ = ["RECONCILIATION_TOLERANCE"]
