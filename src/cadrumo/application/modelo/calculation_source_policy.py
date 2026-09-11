"""Source-kind policy for bucket aggregation calculation.

This module projects executable calculation-route ownership into the calculate
path's source guard.

``BUCKET_AGGREGATION_LOCK_SOURCES`` marks deterministic bucket-owned resolvers
whose values must not be caller-overridden on this path.
``CALLER_OVERRIDABLE_CARRY_SOURCES`` preserves the narrow fallback channel for
carry-style sources whose absence can be supplied by explicit caller values.

See Also:
    :func:`application.modelo.assert_no_novel_source_kinds`:
        Rejects a registry source kind absent from both the enrolled and
        deferred policy sets before it can calculate as a silent blank.
"""

from __future__ import annotations

from ...core.aggregation import BindingSourceKind
from ..aggregation.source_mesh import CallerOverrideDisposition as _CallerOverrideDisposition
from ..aggregation.source_mesh import precedence_ladder_sources as _precedence_ladder_sources

# Caller-override lock / carry sets, DERIVED from the ordered precedence-ladder
# declaration (``CALLER_OVERRIDE_PRECEDENCE_LADDER`` in the aggregation package)
# rather than hand-listed here. LOCK: deterministic bucket-owned resolvers whose
# binding or bound-casilla values must not be supplied by the caller on the
# aggregation path. CARRY: optional-return carry sources intentionally NOT locked
# so legitimate fallback overrides can still reach the engine. The conformance
# gate ``test_precedence_ladder_conformance`` binds these to the declaration so
# the guard and the ladder cannot silently diverge.
BUCKET_AGGREGATION_LOCK_SOURCES: frozenset[BindingSourceKind] = _precedence_ladder_sources(
    _CallerOverrideDisposition.LOCK,
)

CALLER_OVERRIDABLE_CARRY_SOURCES: frozenset[BindingSourceKind] = _precedence_ladder_sources(
    _CallerOverrideDisposition.CARRY,
)

__all__ = [
    "BUCKET_AGGREGATION_LOCK_SOURCES",
    "CALLER_OVERRIDABLE_CARRY_SOURCES",
]
