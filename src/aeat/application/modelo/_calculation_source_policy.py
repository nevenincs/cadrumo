"""Source-kind policy for bucket aggregation calculation."""

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
