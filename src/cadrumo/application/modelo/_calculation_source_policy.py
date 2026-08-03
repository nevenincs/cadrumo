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

from ...core import BindingSourceKind
from ..aggregation import DEFERRED_SOURCE_KINDS
from ..aggregation import BindingSourceDisposition as _BindingSourceDisposition
from ..aggregation import CallerOverrideDisposition as _CallerOverrideDisposition
from ..aggregation import build_binding_source_dispositions as _build_binding_source_dispositions
from ..aggregation import precedence_ladder_sources as _precedence_ladder_sources

# S26 boundary gate: source kinds handled by the live calculate path, either
# through an enrolled resolver or an explicitly-deferred advisory.
_ENROLLED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.RETENCIONES_AGGREGATION,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
        BindingSourceKind.WITHHOLDING,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.FOREIGN_ASSET,
        BindingSourceKind.ATRIBUCION_MEMBER,
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.PRORRATA_REGULARIZACION,
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION,
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

BINDING_SOURCE_DISPOSITIONS = _BINDING_SOURCE_DISPOSITIONS
ENROLLED_SOURCE_KINDS = _ENROLLED_SOURCE_KINDS

__all__ = [
    "ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS",
    "BUCKET_AGGREGATION_LOCK_SOURCES",
    "BUCKET_AGGREGATION_OWNED_SOURCES",
    "CALLER_OVERRIDABLE_CARRY_SOURCES",
]
