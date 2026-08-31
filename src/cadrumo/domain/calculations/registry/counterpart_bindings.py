"""Counterpart-source registry binding helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.aggregation import COUNTERPART_SOURCE_KINDS, BindingSourceKind, CounterpartSourceKind
from ....core.country_code import CountryCodeAlpha2
from ....core.filing_year import FilingYear
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from ._m347_threshold import m347_declarable_party_ids
from .binding_selector_utils import (
    intracommunity_clave_validator,
    invariant_diagnostics,
    selector_against_model,
    unique_tuple,
    uppercase_alpha_code,
    validate_rectification_fields,
)
from .errors import RegistryValidationError
from .ids import BindingId
from .invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_family_row_values,
    resolve_invoice_family_scalar_values,
    validate_invoice_family_fact_and_aggregation,
)
from .invoice_bindings import (
    InvoiceSelector as _InvoiceSelector,
)
from .invoice_bindings import (
    RectificationScope as _RectificationScope,
)
from .invoice_bindings import (
    invoice_selector as _invoice_selector,
)
from .schema import DataBindingDefinition, ModeloRevision

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
_M347_DECLARANTE_SUMMARY_RECORD = "m347_declarante_summary"


class CounterpartAggregationObservation(BaseModel):
    """One factual line from the user's counterpart aggregation source.

    Mirrors :class:`InvoiceObservation` plus a ``source_kind`` field that is
    matched against the declared counterpart-source binding.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: CounterpartSourceKind = Field(
        default=BindingSourceKind.LEDGER_TRANSACTION,
    )
    source_id: str = Field(min_length=1, max_length=128)
    party_tax_id: TaxIdIdentityToken
    country_code: CountryCodeAlpha2
    transaction_date: date
    base_amount: Decimal
    invoice_total_amount: Decimal | None = None
    intracommunity_clave: str | None = Field(default=None, max_length=2)
    is_rectification: bool = False
    rectified_year: FilingYear | None = None
    rectified_period: str | None = Field(default=None, max_length=8)
    rectified_base_previous: Decimal | None = None
    party_legal_name: str | None = Field(default=None, max_length=200)

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))
    _clave_uppercase = field_validator("intracommunity_clave")(intracommunity_clave_validator())

    @field_validator("base_amount", "invoice_total_amount", "rectified_base_previous")
    @classmethod
    def _decimal_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
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
    """Project a counterpart observation onto the shared invoice-observation shape.

    ``source_kind`` is stated rather than left to a default, and the value is
    deliberately arbitrary: it is NOT read on this path. The supplier filters
    on the counterpart observation's OWN ``source_kind`` before calling here
    (see :func:`_counterpart_observation_supplier`), so by the time a record
    reaches this function its family has already been decided, and the field
    set below is never compared against a binding source again.

    It cannot carry the truthful value either. A counterpart observation's
    source kind is drawn from the counterpart taxonomy -- ``LEDGER_TRANSACTION``
    among them -- which :class:`InvoiceObservation` validates against the
    invoice binding family and would refuse.

    So this is a shape-fitting placeholder, and the reason it is written out
    explicitly is that the alternative reads as a claim. Left to the model
    default it silently asserted that every counterpart-derived observation was
    an ISSUED invoice, which is untrue for the received half and invisible.
    Anything downstream that starts reading this field for a counterpart-
    derived record must change this function rather than trust the value.
    """
    return InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id=observation.source_id,
        party_tax_id=observation.party_tax_id,
        country_code=observation.country_code,
        transaction_date=observation.transaction_date,
        base_amount=observation.base_amount,
        invoice_total_amount=observation.invoice_total_amount,
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
    m347_summary_values, invoice_family_revision = _resolve_m347_declarante_summary_values(revision, available)
    invoice_family_values = resolve_invoice_family_scalar_values(
        invoice_family_revision,
        source_kinds=COUNTERPART_BINDING_SOURCE_KINDS,
        validate_selector=_validated_counterpart_selector,
        observations_for_binding=_counterpart_observations_for_binding(available),
    )
    return {**invoice_family_values, **m347_summary_values}


def _resolve_m347_declarante_summary_values(
    revision: ModeloRevision,
    available: tuple[CounterpartAggregationObservation, ...],
) -> tuple[dict[BindingId, Decimal], ModeloRevision]:
    """Resolve M347 declarant summary bindings after applying the declaration floor.

    These scalar bindings summarize the Tipo 1 declarant totals for counterparties
    whose annual M347 amount exceeds the declaration threshold. They are not M349
    invoice-family clave rows, so thresholding happens before delegating the final
    count/sum operation to the shared scalar core.
    """
    summary_bindings: list[DataBindingDefinition] = []
    invoice_family_bindings: list[DataBindingDefinition] = []
    for binding in revision.bindings:
        if binding.source not in COUNTERPART_BINDING_SOURCE_KINDS:
            invoice_family_bindings.append(binding)
            continue
        selector = _validated_counterpart_selector(binding)
        if selector.record == _M347_DECLARANTE_SUMMARY_RECORD:
            summary_bindings.append(binding)
            continue
        invoice_family_bindings.append(binding)

    if not summary_bindings:
        return {}, revision

    declarable_party_ids = _m347_declarable_party_ids(available)
    thresholded = tuple(observation for observation in available if observation.party_tax_id in declarable_party_ids)
    summary_revision = revision.model_copy(update={"bindings": tuple(summary_bindings)})
    invoice_family_revision = revision.model_copy(update={"bindings": tuple(invoice_family_bindings)})
    return (
        resolve_invoice_family_scalar_values(
            summary_revision,
            source_kinds=COUNTERPART_BINDING_SOURCE_KINDS,
            validate_selector=_validated_counterpart_selector,
            observations_for_binding=_counterpart_observations_for_binding(thresholded),
        ),
        invoice_family_revision,
    )


def _m347_declarable_party_ids(
    observations: tuple[CounterpartAggregationObservation, ...],
) -> frozenset[str]:
    totals: dict[str, Decimal] = {}
    for observation in observations:
        totals[observation.party_tax_id] = totals.get(observation.party_tax_id, Decimal("0")) + _m347_summary_amount(
            observation,
        )
    return m347_declarable_party_ids(totals)


def _m347_summary_amount(observation: CounterpartAggregationObservation) -> Decimal:
    if observation.invoice_total_amount is None:
        raise RegistryValidationError(
            f"M347 counterpart summary requires invoice_total_amount on observation {observation.source_id!r}",
        )
    return observation.invoice_total_amount


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
