"""Source-kind policy for bucket aggregation calculation.

This module is the modelo-application projection of the source-mesh disposition
registry. It starts from the canonical :class:`aeat.core.BindingSourceKind`
taxonomy, classifies the live bucket-aggregation set with
:func:`aeat.application.aggregation.build_binding_source_dispositions`, and
exposes the enrolled / deferred union consumed by the calculate path's
novel-source gate.

``BUCKET_AGGREGATION_OWNED_SOURCES`` is the enrolled source set for live
calculation: sources routed by active resolvers, pre-mesh tiers, or
``manual_input``. ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` extends that set
with :data:`aeat.application.aggregation.DEFERRED_SOURCE_KINDS` so known
pull-only detail families produce standing
:class:`aeat.application.aggregation.CalculationSourceDiagnostic` advisories
instead of silently blanking.

``BUCKET_AGGREGATION_LOCK_SOURCES`` marks deterministic bucket-owned resolvers
whose values must not be caller-overridden on this path.
``CALLER_OVERRIDABLE_CARRY_SOURCES`` preserves the narrow fallback channel for
carry-style sources whose absence can be supplied by explicit caller values.

See Also:
    :class:`aeat.application.aggregation.BindingSourceDisposition`:
        The enrolled / deferred / reserved registry that keeps every source kind
        accounted for.
    :func:`aeat.application.modelo.assert_no_novel_source_kinds`:
        Rejects a registry source kind absent from both the enrolled and
        deferred policy sets before it can calculate as a silent blank.
"""

from __future__ import annotations

from ...core import BindingSourceKind
from ..aggregation._source_mesh import DEFERRED_SOURCE_KINDS
from ..aggregation._source_mesh import BindingSourceDisposition as _BindingSourceDisposition
from ..aggregation._source_mesh import build_binding_source_dispositions as _build_binding_source_dispositions

# S26 boundary gate: source kinds handled by the live calculate path, either
# through an enrolled resolver or an explicitly-deferred advisory.
_ENROLLED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.RETENCIONES_AGGREGATION,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
        BindingSourceKind.WITHHOLDING,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.PROFILE,
        BindingSourceKind.BORRADOR,
        BindingSourceKind.IVA_WALLET_DECISION,
        BindingSourceKind.MANUAL_INPUT,
    },
)

_BINDING_SOURCE_DISPOSITIONS = _build_binding_source_dispositions(_ENROLLED_SOURCE_KINDS)

BUCKET_AGGREGATION_OWNED_SOURCES: frozenset[BindingSourceKind] = frozenset(
    source
    for source, disposition in _BINDING_SOURCE_DISPOSITIONS.items()
    if disposition is _BindingSourceDisposition.ENROLLED
)

# Caller-override lock set: deterministic bucket-owned resolvers whose binding
# or bound-casilla values must not be supplied by the caller on the aggregation
# path. Optional-return carry/profile/OSS/invoice sources are intentionally not
# locked so legitimate fallback overrides can still reach the engine.
BUCKET_AGGREGATION_LOCK_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
    },
)

CALLER_OVERRIDABLE_CARRY_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
    },
)

ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS = BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS

__all__ = [
    "ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS",
    "BUCKET_AGGREGATION_LOCK_SOURCES",
    "BUCKET_AGGREGATION_OWNED_SOURCES",
    "CALLER_OVERRIDABLE_CARRY_SOURCES",
]
