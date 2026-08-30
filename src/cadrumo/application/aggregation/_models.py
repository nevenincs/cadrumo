"""Strict boundary models for financial transaction aggregation.

Carries the per-casilla :class:`CasillaProvenance` trace, the aggregated
:class:`CasillaAggregation` ledger shape, and :class:`LedgerAggregationResultBase`,
the shared envelope every ledger-projection aggregation result (renta income,
renta gasto, IRNR income, impatriado income, and the Modelo 100 first-slice
expense aggregation) subclasses. The aggregation package re-exports the
canonical :class:`core.Period`; period construction and date-span authority
live in core, not in an application-layer wrapper.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import Annotated, Generic, Self, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...domain.categories.spending_category import SpendingCategory
from .errors import AggregationValidationError, t


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


ObservationT = TypeVar("ObservationT", bound=BaseModel)
IssueT = TypeVar("IssueT", bound=BaseModel)


class LedgerAggregationResultBase(BaseModel, Generic[ObservationT, IssueT]):  # noqa: UP046 -- see docstring: PEP 695 type params are unresolvable across modules here
    """Shared envelope for one ledger-projection aggregation result.

    Declared with classic :class:`~typing.TypeVar` / :class:`~typing.Generic`
    rather than PEP 695 ``class Foo[T]`` syntax: a PEP 695 type parameter is
    scoped to the class statement only and is not a resolvable module-level
    name, so a concrete subclass parametrising this base FROM ANOTHER MODULE
    (every one of the five known subclasses does) fails to build
    (``PydanticUndefinedAnnotation: name 'ObservationT' is not defined``) the
    moment this module also carries ``from __future__ import annotations``.
    ``TypeVar`` names are real module attributes pydantic's forward-ref
    resolver can always find, so this form has no such gap.

    Every ledger-projection family (renta income, renta gasto, IRNR income,
    impatriado income, and the Modelo 100 first-slice expense aggregation)
    resolves to the same shape: a modelo/period pair, the typed observations
    and issues the projection produced, and the :class:`CasillaAggregation`
    those observations fold into. ``_validate_casilla_period`` cross-checks the
    envelope's own ``modelo``/``period`` against the fold it carries, so the
    two can never silently drift apart.

    ``out_of_window_summary`` is deliberately NOT declared here even though
    four of the five known subclasses carry it: the Modelo 100 first-slice
    expense aggregation has no repository-backed date partition and never had
    this field. Lifting it into this base would silently WIDEN that
    subclass's ``extra="forbid"`` accepted-input surface (a previously-refused
    keyword would validate) and add a key to its ``model_dump()`` output that
    was never there. Each subclass that needs it declares it itself, exactly
    as it did before this extraction.

    A subclass's own extra fields (e.g. a selected official code, a profile
    year) always follow every field declared here, per ordinary pydantic
    field-declaration inheritance -- this can reorder a field that, before
    this extraction, was declared between ``period`` and ``observations``.
    Verified inert for the five current subclasses: none is persisted,
    hashed, or compared via ``model_dump_json()`` string equality anywhere in
    this codebase, so the reordering changes no observable behaviour.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    observations: Sequence[ObservationT] = Field(default_factory=tuple)
    issues: Sequence[IssueT] = Field(default_factory=tuple)
    casilla_aggregation: CasillaAggregation

    @field_validator("observations")
    @classmethod
    def _freeze_observations(cls, value: Sequence[ObservationT]) -> tuple[ObservationT, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[IssueT]) -> tuple[IssueT, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)

    @model_validator(mode="after")
    def _validate_casilla_period(self) -> Self:
        """Refuse a ``casilla_aggregation`` whose modelo/period drifts from the envelope's own."""
        if self.casilla_aggregation.modelo != self.modelo:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.modelo_mismatch"))
        if self.casilla_aggregation.period != self.period:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.period_mismatch"))
        return self

    @field_serializer("observations")
    def _serialize_observations(self, value: Sequence[ObservationT]) -> tuple[ObservationT, ...]:
        """Serialise the frozen observation tuple back to a plain tuple for JSON output."""
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(self, value: Sequence[IssueT]) -> tuple[IssueT, ...]:
        """Serialise the frozen issue tuple back to a plain tuple for JSON output."""
        return tuple(value)


__all__ = [
    "CasillaAggregation",
    "CasillaProvenance",
    "LedgerAggregationResultBase",
    "Period",
]
