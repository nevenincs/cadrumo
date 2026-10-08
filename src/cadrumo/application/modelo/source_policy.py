"""Where each binding source's values come from, and what a filer may do about them.

Every value a registry binding supplies has one source kind. This module gives
each kind the three facts an editor needs to explain it to a person: the
family it belongs to (the filer's own records, a register they keep, their
profile, an earlier filing, the AEAT draft, a value they type, or a constant the
official design fixes), whether a filer may replace its value, and which
product surface owns the data.

The override policy is not decided here. Whether a caller may override a source
is the calculation's own precedence ladder
(:data:`~cadrumo.application.aggregation.source_mesh.CALLER_OVERRIDE_PRECEDENCE_LADDER`),
and this table reads it rather than restating it: a locked source is fixed at
its source, a carried one may be overridden with a reason. The few kinds the
ladder does not govern carry an explicit policy only where the product already
owns the answer -- a typed value is entered, a design constant is fixed, a
profile fact is corrected in the profile. Every other kind is
:attr:`SourceOverridePolicy.UNDECIDED`: whether a filer may replace it is a tax
question nobody has grounded yet, and an editor shows that plainly instead of
guessing a lock or an override.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import InternalInvariantError
from ...core.models import STRICT_FROZEN_CONFIG
from ..aggregation.source_mesh import CallerOverrideDisposition, precedence_ladder_sources


class SourceFamily(StrEnum):
    """The kind of place a value comes from, as a filer thinks of it."""

    RECORDS = "records"
    REGISTERS = "registers"
    PROFILE = "profile"
    EARLIER_FILINGS = "earlier_filings"
    AEAT_DRAFT = "aeat_draft"
    YOUR_ENTRIES = "your_entries"
    FIXED_BY_DESIGN = "fixed_by_design"


class SourceOverridePolicy(StrEnum):
    """What a filer may do about a value this source supplies."""

    FIX_AT_SOURCE = "fix_at_source"
    OVERRIDE_WITH_REASON = "override_with_reason"
    EDIT_AT_HOME = "edit_at_home"
    ENTER = "enter"
    FIXED = "fixed"
    UNDECIDED = "undecided"


class SourceSurface(StrEnum):
    """The product surface that owns a source's data, when one exists."""

    LEDGER = "ledger"
    WITHHOLDING = "withholding"
    PROFILE = "profile"
    DECLARATIONS = "declarations"
    NONE = "none"


class SourcePolicyV1(BaseModel):
    """The family, policy and owning surface of one binding source kind."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    family: SourceFamily
    override_policy: SourceOverridePolicy
    surface: SourceSurface

    @property
    def label_key(self) -> str:
        """The catalogue key naming this source in a few words."""
        return f"flows.modelo_review.filter.option.binding_source.{self.source_kind.value}"

    @property
    def origin_sentence_key(self) -> str:
        """The catalogue key saying in a sentence where a value from this source comes from."""
        return f"docs.casilla.binding_source.{self.source_kind.value}"


_FAMILY_AND_SURFACE: Final[Mapping[BindingSourceKind, tuple[SourceFamily, SourceSurface]]] = MappingProxyType(
    {
        BindingSourceKind.LEDGER_OSS_AGGREGATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.LEDGER_IVA_AGGREGATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (
            SourceFamily.RECORDS,
            SourceSurface.LEDGER,
        ),
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION: (
            SourceFamily.RECORDS,
            SourceSurface.LEDGER,
        ),
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.LEDGER_TRANSACTION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.COLLECTIBLE_INVOICE: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.PAYABLE_INVOICE: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.M347_THIRD_PARTY_OPERATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION: (SourceFamily.RECORDS, SourceSurface.LEDGER),
        BindingSourceKind.RETENCIONES_AGGREGATION: (SourceFamily.REGISTERS, SourceSurface.WITHHOLDING),
        BindingSourceKind.WITHHOLDING: (SourceFamily.REGISTERS, SourceSurface.WITHHOLDING),
        BindingSourceKind.WITHHOLDING296: (SourceFamily.REGISTERS, SourceSurface.WITHHOLDING),
        BindingSourceKind.INVENTORY: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.PRORRATA_REGULARIZACION: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.FOREIGN_ASSET: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.ATRIBUCION_MEMBER: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.GASTO193_CONTRIBUTOR: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.AFILIADO_COTIZACION: (SourceFamily.REGISTERS, SourceSurface.NONE),
        BindingSourceKind.PROFILE: (SourceFamily.PROFILE, SourceSurface.PROFILE),
        BindingSourceKind.PREVIOUS_FILING: (SourceFamily.EARLIER_FILINGS, SourceSurface.DECLARATIONS),
        BindingSourceKind.RELATION_PREFILL: (SourceFamily.EARLIER_FILINGS, SourceSurface.DECLARATIONS),
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION: (
            SourceFamily.EARLIER_FILINGS,
            SourceSurface.DECLARATIONS,
        ),
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY: (
            SourceFamily.EARLIER_FILINGS,
            SourceSurface.DECLARATIONS,
        ),
        BindingSourceKind.IVA_WALLET_DECISION: (SourceFamily.EARLIER_FILINGS, SourceSurface.DECLARATIONS),
        BindingSourceKind.BORRADOR: (SourceFamily.AEAT_DRAFT, SourceSurface.NONE),
        BindingSourceKind.MANUAL_INPUT: (SourceFamily.YOUR_ENTRIES, SourceSurface.NONE),
        BindingSourceKind.DESIGN_CONSTANT: (SourceFamily.FIXED_BY_DESIGN, SourceSurface.NONE),
    },
)
"""The family and owning surface of every source kind; total over :class:`BindingSourceKind`."""

_POLICY_OUTSIDE_THE_LADDER: Final[Mapping[BindingSourceKind, SourceOverridePolicy]] = MappingProxyType(
    {
        BindingSourceKind.MANUAL_INPUT: SourceOverridePolicy.ENTER,
        BindingSourceKind.DESIGN_CONSTANT: SourceOverridePolicy.FIXED,
        BindingSourceKind.PROFILE: SourceOverridePolicy.EDIT_AT_HOME,
    },
)
"""The policies the product owns for kinds the calculation ladder does not govern."""


class UnclassifiedSourceKindError(InternalInvariantError):
    """A binding source kind has no declared family, so no explanation is invented for it."""


def _override_policy(kind: BindingSourceKind) -> SourceOverridePolicy:
    if kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK):
        return SourceOverridePolicy.FIX_AT_SOURCE
    if kind in precedence_ladder_sources(CallerOverrideDisposition.CARRY):
        return SourceOverridePolicy.OVERRIDE_WITH_REASON
    return _POLICY_OUTSIDE_THE_LADDER.get(kind, SourceOverridePolicy.UNDECIDED)


def source_policy(kind: BindingSourceKind) -> SourcePolicyV1:
    """Return the family, override policy and owning surface of one source kind."""
    try:
        family, surface = _FAMILY_AND_SURFACE[kind]
    except KeyError:
        raise UnclassifiedSourceKindError(f"binding source kind {kind.value!r} has no declared family") from None
    return SourcePolicyV1(source_kind=kind, family=family, override_policy=_override_policy(kind), surface=surface)


__all__ = [
    "SourceFamily",
    "SourceOverridePolicy",
    "SourcePolicyV1",
    "SourceSurface",
    "UnclassifiedSourceKindError",
    "source_policy",
]
