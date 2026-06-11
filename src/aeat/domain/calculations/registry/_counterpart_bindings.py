"""Counterpart-source registry binding helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core.aggregation import COUNTERPART_SOURCE_KINDS, AggregationSourceKind, CounterpartSourceKind
from ._errors import RegistryValidationError
from ._invoice_bindings import (
    _INVOICE_FACTS,
    InvoiceObservation,
    _aggregate_invoice_binding,
    _build_invoice_rows,
    _filter_invoice_observations,
    _invoice_selector,
    _InvoiceGrouping,
    _InvoiceSelector,
    _RectificationScope,
    _validate_row_field_invoice_fact,
    _validate_scalar_invoice_fact_op,
)
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "COUNTERPART_BINDING_SOURCE_KINDS",
    "CounterpartAggregationObservation",
    "CounterpartObservationRequirement",
    "counterpart_binding_requirements",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
]

COUNTERPART_BINDING_SOURCE_KINDS: frozenset[CounterpartSourceKind] = COUNTERPART_SOURCE_KINDS


class CounterpartAggregationObservation(BaseModel):
    """One factual line from the user's counterpart aggregation source.

    Mirrors :class:`InvoiceObservation` plus a ``source_kind`` field that is
    matched against the declared counterpart-source binding.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_kind: CounterpartSourceKind = Field(
        default=AggregationSourceKind.LEDGER_TRANSACTION,
    )
    source_id: str = Field(min_length=1, max_length=128)
    party_tax_id: str = Field(min_length=1, max_length=64)
    country_code: str = Field(min_length=2, max_length=2)
    transaction_date: date
    base_amount: Decimal
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    is_rectification: bool = False
    rectified_year: int | None = Field(default=None, ge=2000, le=2099)
    rectified_period: str | None = Field(default=None, max_length=8)
    rectified_base_previous: Decimal | None = None
    party_legal_name: str | None = Field(default=None, max_length=200)

    @field_validator("country_code")
    @classmethod
    def _country_code_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise RegistryValidationError("country_code must be uppercase")
        if not value.isalpha():
            raise RegistryValidationError("country_code must be alphabetic")
        return value

    @field_validator("intracommunity_clave")
    @classmethod
    def _clave_uppercase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise RegistryValidationError("intracommunity_clave must be uppercase")
        if value not in {"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"}:
            raise RegistryValidationError(f"intracommunity_clave {value!r} is not an AEAT clave de operacion")
        return value

    @field_validator("base_amount", "rectified_base_previous")
    @classmethod
    def _decimal_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("counterpart amounts must be Decimal")
        return value

    @model_validator(mode="after")
    def _validate_rectification(self) -> CounterpartAggregationObservation:
        if self.is_rectification:
            if self.rectified_year is None or self.rectified_period is None:
                raise RegistryValidationError(
                    "rectification observation must declare rectified_year and rectified_period",
                )
            if self.rectified_base_previous is None:
                raise RegistryValidationError("rectification observation must declare rectified_base_previous")
        else:
            if self.rectified_year is not None or self.rectified_period is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_year/period")
            if self.rectified_base_previous is not None:
                raise RegistryValidationError("non-rectification observation must not declare rectified_base_previous")
        return self


class CounterpartObservationRequirement(BaseModel):
    """Counterpart slice declared by one or more counterpart-source bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    binding_ids: tuple[str, ...] = Field(min_length=1)
    source_kinds: tuple[str, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"

    @field_validator("binding_ids", "claves", "source_kinds")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("counterpart requirement tuple entries must be unique")
        return value


_COUNTERPART_FACTS = _INVOICE_FACTS


def _validated_counterpart_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    """Validate a counterpart-source binding selector with counterpart-flavoured errors."""
    selector = _invoice_selector(binding)
    if selector.fact not in _COUNTERPART_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported counterpart aggregation fact {selector.fact!r}",
        )
    op = str((binding.aggregation or {}).get("op", "sum"))
    _validate_scalar_invoice_fact_op(binding, selector, op)
    if selector.fact == "row_field":
        _validate_row_field_invoice_fact(binding, selector, op)
    return selector


def _counterpart_to_invoice(observation: CounterpartAggregationObservation) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=observation.source_id,
        party_tax_id=observation.party_tax_id,
        country_code=observation.country_code,
        transaction_date=observation.transaction_date,
        base_amount=observation.base_amount,
        iva_regime=None,
        intracommunity_clave=observation.intracommunity_clave,
        is_rectification=observation.is_rectification,
        rectified_year=observation.rectified_year,
        rectified_period=observation.rectified_period,
        rectified_base_previous=observation.rectified_base_previous,
        party_legal_name=observation.party_legal_name,
    )


def counterpart_binding_requirements(
    revision: ModeloRevision,
) -> tuple[CounterpartObservationRequirement, ...]:
    """Return :class:`CounterpartObservationRequirement` slices needed by ``revision``'s counterpart bindings.

    Args:
        revision: The :class:`ModeloRevision` whose counterpart bindings to inspect.
    """
    grouped: dict[tuple[tuple[str, ...], tuple[str, ...], _RectificationScope], set[str]] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        source_kinds = (binding.source,)
        key = (source_kinds, tuple(sorted(selector.claves)), selector.rectification_scope)
        grouped.setdefault(key, set()).add(binding.id)
    requirements: list[CounterpartObservationRequirement] = []
    for (source_kinds, claves, scope), binding_ids in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2]),
    ):
        requirements.append(
            CounterpartObservationRequirement(
                binding_ids=tuple(sorted(binding_ids)),
                source_kinds=source_kinds,
                claves=claves,
                rectification_scope=scope,
            ),
        )
    return tuple(requirements)


def resolve_counterpart_binding_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[str, Decimal]:
    """Resolve scalar counterpart-source bindings into Decimal aggregates.

    Args:
        revision: The :class:`ModeloRevision` whose counterpart bindings to resolve.
        observations: Typed counterpart aggregation observations the bindings
            filter by selector and aggregate into scalar Decimal values.
    """
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        if selector.fact == "row_field":
            continue
        matched = tuple(
            _counterpart_to_invoice(observation)
            for observation in available
            if observation.source_kind == binding.source
        )
        scope_filtered = tuple(_filter_invoice_observations(matched, selector))
        resolved[binding.id] = _aggregate_invoice_binding(binding, selector, scope_filtered)
    return resolved


def resolve_counterpart_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer counterpart-source bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose counterpart bindings are resolved.
        observations: Counterpart aggregation lines to group into rows.
    """
    available = tuple(observations)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    cohorts: dict[
        tuple[str, _InvoiceGrouping, _RectificationScope, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _InvoiceSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            continue
        selector = _validated_counterpart_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None
        cohort_key = (
            binding.source,
            selector.grouping,
            selector.rectification_scope,
            tuple(sorted(selector.claves)),
        )
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for cohort_key, members in cohorts.items():
        source_kind, grouping, _, _ = cohort_key
        _, sample_selector = members[0]
        matched = tuple(
            _counterpart_to_invoice(observation) for observation in available if observation.source_kind == source_kind
        )
        scope_filtered = tuple(_filter_invoice_observations(matched, sample_selector))
        rows = _build_invoice_rows(grouping, scope_filtered)
        for binding, selector in members:
            assert selector.row_field is not None
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}",
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


# ---------------------------------------------------------------------------
