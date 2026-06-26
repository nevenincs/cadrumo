"""Counterpart-source registry binding helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import COUNTERPART_SOURCE_KINDS, AggregationSourceKind, CounterpartSourceKind
from ._binding_selector_utils import (
    intracommunity_clave_validator,
    invariant_diagnostics,
    selector_against_model,
    unique_tuple,
    uppercase_alpha_code,
    validate_rectification_fields,
)
from ._errors import RegistryValidationError
from ._ids import BindingId
from ._invoice_bindings import (
    InvoiceObservation,
    _invoice_selector,
    _InvoiceSelector,
    _RectificationScope,
    resolve_invoice_family_row_values,
    resolve_invoice_family_scalar_values,
    validate_invoice_family_fact_and_aggregation,
)
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "COUNTERPART_BINDING_SOURCE_KINDS",
    "CounterpartAggregationObservation",
    "CounterpartObservationRequirement",
    "counterpart_binding_requirements",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
    "validate_counterpart_binding",
]

COUNTERPART_BINDING_SOURCE_KINDS: frozenset[CounterpartSourceKind] = COUNTERPART_SOURCE_KINDS


class CounterpartAggregationObservation(BaseModel):
    """One factual line from the user's counterpart aggregation source.

    Mirrors :class:`InvoiceObservation` plus a ``source_kind`` field that is
    matched against the declared counterpart-source binding.
    """

    model_config = STRICT_FROZEN_CONFIG

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

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))
    _clave_uppercase = field_validator("intracommunity_clave")(intracommunity_clave_validator())

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
        validate_rectification_fields(self)
        return self


class CounterpartObservationRequirement(BaseModel):
    """Counterpart slice declared by one or more counterpart-source bindings."""

    model_config = STRICT_FROZEN_CONFIG

    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    source_kinds: tuple[str, ...] = Field(min_length=1)
    claves: tuple[str, ...] = ()
    rectification_scope: _RectificationScope = "any"

    _values_unique = field_validator("binding_ids", "claves", "source_kinds")(
        unique_tuple("counterpart requirement tuple")
    )


def _validated_counterpart_selector(binding: DataBindingDefinition) -> _InvoiceSelector:
    """Validate a counterpart-source binding selector with counterpart-flavoured errors.

    Delegates to the shared invoice/counterpart fact + aggregation-op invariant
    parameterised with the ``counterpart aggregation`` family label. The
    counterpart family historically omitted the invoice-only scalar-shape guards
    (``non-row fact must not declare row_field/grouping`` and ``op 'rows'
    requires fact 'row_field'``), so ``strict_scalar_shape`` is ``False`` to
    preserve that behaviour exactly.
    """
    selector = _invoice_selector(binding)
    validate_invoice_family_fact_and_aggregation(
        binding,
        selector,
        family_label="counterpart aggregation",
        strict_scalar_shape=False,
    )
    return selector


def validate_counterpart_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a counterpart-source binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_InvoiceSelector` and lifts the counterpart fact/op invariants to
    build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _InvoiceSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "counterpart", lambda b: _validated_counterpart_selector(b))


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
    grouped: dict[tuple[tuple[str, ...], tuple[str, ...], _RectificationScope], set[BindingId]] = {}
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


def _counterpart_observations_for_binding(
    available: tuple[CounterpartAggregationObservation, ...],
) -> Callable[[DataBindingDefinition], tuple[InvoiceObservation, ...]]:
    """Build a per-binding observation supplier matching ``source_kind`` to the binding source.

    Counterpart aggregation observations carry a ``source_kind`` that must match
    the declared counterpart-source binding; the supplier filters by that match
    and converts each matched observation to the shared
    :class:`InvoiceObservation` shape the invoice-family resolver cores consume.
    """

    def _supplier(binding: DataBindingDefinition) -> tuple[InvoiceObservation, ...]:
        return tuple(
            _counterpart_to_invoice(observation)
            for observation in available
            if observation.source_kind == binding.source
        )

    return _supplier


def resolve_counterpart_binding_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[BindingId, Decimal]:
    """Resolve scalar counterpart-source bindings into Decimal aggregates.

    Delegates to the shared invoice-family scalar resolver core
    (:func:`resolve_invoice_family_scalar_values`) parameterised by the
    counterpart membership set, the counterpart selector validator, and a
    ``source_kind``-matched observation supplier.

    Args:
        revision: The :class:`ModeloRevision` whose counterpart bindings to resolve.
        observations: Typed counterpart aggregation observations the bindings
            filter by selector and aggregate into scalar Decimal values.
    """
    available = tuple(observations)
    return resolve_invoice_family_scalar_values(
        revision,
        source_kinds=COUNTERPART_BINDING_SOURCE_KINDS,
        validate_selector=_validated_counterpart_selector,
        observations_for_binding=_counterpart_observations_for_binding(available),
    )


def resolve_counterpart_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[CounterpartAggregationObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer counterpart-source bindings into per-row indexed values.

    Delegates to the shared invoice-family row resolver core
    (:func:`resolve_invoice_family_row_values`) with ``cohort_by_source = True``
    so a different counterpart source kind does not share row indexes.

    Args:
        revision: The :class:`ModeloRevision` whose counterpart bindings are resolved.
        observations: Counterpart aggregation lines to group into rows.
    """
    available = tuple(observations)
    return resolve_invoice_family_row_values(
        revision,
        source_kinds=COUNTERPART_BINDING_SOURCE_KINDS,
        validate_selector=_validated_counterpart_selector,
        observations_for_binding=_counterpart_observations_for_binding(available),
        cohort_by_source=True,
    )


# ---------------------------------------------------------------------------
