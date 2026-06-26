"""Strict boundary models for financial transaction aggregation.

Carries the per-casilla :class:`CasillaProvenance` trace and the aggregated
:class:`CasillaAggregation` ledger shape. The aggregation package re-exports
the canonical :class:`aeat.core.Period`; period construction and date-span
authority live in core, not in an application-layer wrapper.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    field_serializer,
    field_validator,
)

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain.calculations.registry import CasillaId
from ...domain.categories import SpendingCategory


def _coerce_spending_category(value: object) -> object:
    """Accept the canonical SpendingCategory value string AND the enum member.

    Strict pydantic refuses str→Enum coercion by default. Wrapping the
    field with a ``BeforeValidator`` keeps registry/JSON payloads (which
    carry the enum's ``.value`` string) loadable without weakening
    strict-mode for every other field on the model.
    """
    if value is None or isinstance(value, SpendingCategory):
        return value
    if isinstance(value, str):
        return SpendingCategory(value)
    return value


_SpendingCategoryField = Annotated[SpendingCategory, BeforeValidator(_coerce_spending_category)]


class CasillaProvenance(BaseModel):
    """Transaction trace backing one (casilla, category) subtotal.

    Attributes:
        casilla_id: Target canonical casilla id (e.g. ``"02"``).
        transaction_ids: Sorted, frozen tuple of contributing
            transaction IDs.
        subtotal: Sum of contributions for this casilla/category pair.
        category_id: Optional category identifier when the contribution
            came from an expense bucket.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    transaction_ids: Sequence[str] = Field(default_factory=tuple)
    subtotal: Decimal
    # Typed SpendingCategory enum (was bare ``str`` before R025/R026
    # follow-up). The BeforeValidator coerces canonical string inputs
    # to the enum member so existing TOML/JSON payloads round-trip
    # without registry-data changes. Downstream comparisons no longer
    # need a manual ``normalize_spending_category`` step.
    category_id: _SpendingCategoryField | None = None

    @field_validator("transaction_ids")
    @classmethod
    def _freeze_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)


class CasillaAggregation(BaseModel):
    """Aggregated casilla ledger for one modelo and period.

    Attributes:
        modelo: Modelo identifier (``ModeloCode.value``) the totals
            belong to.
        period: The :class:`Period` covered.
        casilla_values: Mapping of canonical casilla id to summed
            :class:`~decimal.Decimal` value, sorted and frozen.
        provenance: Tuple of :class:`CasillaProvenance` rows tracing
            each contribution back to its source transactions.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    casilla_values: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    provenance: Sequence[CasillaProvenance] = Field(default_factory=tuple)

    @field_validator("casilla_values")
    @classmethod
    def _freeze_casilla_values(cls, value: Mapping[CasillaId, Decimal]) -> Mapping[CasillaId, Decimal]:
        """Return ``value`` as a sorted, immutable :class:`MappingProxyType`."""
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("casilla_values")
    def _serialize_casilla_values(self, value: Mapping[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
        """Serialise the immutable view back to a plain ``dict`` for JSON output."""
        return dict(value)

    @field_validator("provenance")
    @classmethod
    def _freeze_provenance(cls, value: Sequence[CasillaProvenance]) -> tuple[CasillaProvenance, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)


__all__ = [
    "CasillaAggregation",
    "CasillaProvenance",
    "Period",
]
