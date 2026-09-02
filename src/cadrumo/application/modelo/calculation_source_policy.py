"""Source-kind policy for bucket aggregation calculation.

This module is the modelo-application projection of the source-mesh disposition
registry. It starts from the canonical :class:`core.BindingSourceKind`
taxonomy, classifies the live bucket-aggregation set with
:func:`application.aggregation.build_binding_source_dispositions`, and
exposes the enrolled / deferred union consumed by the calculate path's
novel-source gate.

``BUCKET_AGGREGATION_OWNED_SOURCES`` is the enrolled source set for live
calculation: sources routed by active resolvers, pre-mesh tiers, or
``manual_input``. ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` extends that set
with :data:`application.aggregation.DEFERRED_SOURCE_KINDS` so known
pull-only detail families produce standing
:class:`application.aggregation.CalculationSourceDiagnostic` advisories
instead of silently blanking.

``BUCKET_AGGREGATION_LOCK_SOURCES`` marks deterministic bucket-owned resolvers
whose values must not be caller-overridden on this path.
``CALLER_OVERRIDABLE_CARRY_SOURCES`` preserves the narrow fallback channel for
carry-style sources whose absence can be supplied by explicit caller values.

See Also:
    :class:`application.aggregation.BindingSourceDisposition`:
        The enrolled / deferred / reserved registry that keeps every source kind
        accounted for.
    :func:`application.modelo.assert_no_novel_source_kinds`:
        Rejects a registry source kind absent from both the enrolled and
        deferred policy sets before it can calculate as a silent blank.
"""

from __future__ import annotations

from ...core.aggregation import BindingSourceKind
from ..aggregation import DEFERRED_SOURCE_KINDS
from ..aggregation import CallerOverrideDisposition as _CallerOverrideDisposition
from ..aggregation import precedence_ladder_sources as _precedence_ladder_sources
from .calculation_route import (
    CALCULATION_ROUTE_ENROLLED_SOURCES,
)

# Boundary gate: source kinds handled by the live calculate path, either
# through an enrolled resolver or an explicitly-deferred advisory.
BUCKET_AGGREGATION_OWNED_SOURCES = CALCULATION_ROUTE_ENROLLED_SOURCES

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

ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS = BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS


__all__ = [
    "ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS",
    "BUCKET_AGGREGATION_LOCK_SOURCES",
    "BUCKET_AGGREGATION_OWNED_SOURCES",
    "CALLER_OVERRIDABLE_CARRY_SOURCES",
]
