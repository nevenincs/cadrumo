"""Modelo 347/349 counterpart aggregation for informativa declarations.

Used by :mod:`~application.aggregation._service`, the per-modelo
aggregation service. This is not the live calculate source mesh: standalone
``CounterpartObservation`` rows are currently operator-supplied to the aggregate
surface, while calculation-facing source values use
:class:`~application.aggregation.CalculationSourceResolution`.
When a modelo revision declares only one counterpart source family, the
calculation resolver narrows the active
:class:`~domain.calculations.registry.ModeloRevision` view before projecting
the registry binding values.

Modelo 347 covers annual operations with third parties whose total exceeds the
declaration floor. Modelo 349 covers intra-EU operations by member-state
operation kind. Both aggregate per ``(source_kind, counterparty_nif,
operation_kind)`` using the counterpart subset of the canonical source-kind
taxonomy, then expose helpers such as :func:`declarable_counterparty_nifs_347`
for consumers that need the 347 threshold decision.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field, InstanceOf, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, Modelo, Period
from ...core.aggregation import (
    COUNTERPART_SOURCE_KINDS,
    BindingSourceKind,
    CounterpartSourceKind,
    OperationKind347,
    OperationKind349,
    counterpart_source_kind,
)
from ...core.external_constants import M347_THRESHOLD_EUR
from ...domain.calculations.registry import (
    CounterpartAggregationObservation,
    ModeloRevision,
    resolve_counterpart_binding_values,
)
from ._grouping import filter_observations_for_modelo, group_and_collect_names
from ._source_mesh import CalculationSourceContext, CalculationSourceProvenance, CalculationSourceResolution

_CANONICAL_SOURCE_KINDS = COUNTERPART_SOURCE_KINDS
_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.LEDGER_TRANSACTION,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
)
_OWNED_SOURCE_SET = frozenset(_OWNED_SOURCES)
_M349_CLAVE_BY_OPERATION_KIND: Mapping[str, str] = MappingProxyType(
    {
        OperationKind349.INTRA_DELIVERY.value: "E",
        OperationKind349.INTRA_ACQUISITION.value: "A",
        OperationKind349.INTRA_SERVICE_OUT.value: "S",
        OperationKind349.INTRA_SERVICE_IN.value: "I",
        OperationKind349.TRIANGULAR.value: "T",
    },
)
_M349_PAYABLE_SUMMARY_BINDING_MIRRORS: Mapping[str, str] = MappingProxyType(
    {
        "iva-349-declarante-numero-operadores-adquisicion": "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones-adquisicion": "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones-adquisicion": "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones-adquisicion": "iva-349-declarante-importe-rectificaciones",
    },
)


def _validate_source_kind(value: str) -> CounterpartSourceKind:
    return counterpart_source_kind(value)


def _validate_country(value: str, *, field_name: str) -> str:
    if len(value) != 2 or any(char < "A" or char > "Z" for char in value):
        raise ValueError(f"{field_name} must be uppercase ISO-3166 alpha-2, got {value!r}")
    return value


class CounterpartObservation(BaseModel):
    """One typed observation for a 347 or 349 aggregator pass."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: CounterpartSourceKind
    source_object_id: str = Field(min_length=1)
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: str = Field(default="ES", min_length=2, max_length=2)
    operation_kind: str = Field(min_length=1)
    operation_period: str = Field(min_length=1)  # ISO quarter / year identifier
    taxable_base: Decimal = Field(ge=Decimal("0"))
    invoice_total: Decimal = Field(ge=Decimal("0"))
    accrued_on: str = Field(min_length=10, max_length=10)
    groi_verified: bool = False
    nif_iva_verified: bool = False

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> CounterpartSourceKind:
        if not isinstance(value, str):
            raise ValueError("source_kind must be a string")
        return _validate_source_kind(value)

    @field_validator("counterparty_country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        return _validate_country(value, field_name="counterparty_country")


class CounterpartRollup(BaseModel):
    """One (source_kind, counterparty_nif, operation_kind) rollup row."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: CounterpartSourceKind
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: str = Field(min_length=2, max_length=2)
    operation_kind: str = Field(min_length=1)
    observations_count: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))
    requires_groi_check: bool = False
    requires_nif_iva_check: bool = False
    groi_ready: bool = True
    nif_iva_ready: bool = True
    declarable_readiness_satisfied: bool = True

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> CounterpartSourceKind:
        if not isinstance(value, str):
            raise ValueError("source_kind must be a string")
        return _validate_source_kind(value)

    @field_validator("counterparty_country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        return _validate_country(value, field_name="counterparty_country")


class CounterpartAggregation(BaseModel):
    """347 / 349 counterpart aggregation output."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[CounterpartRollup, ...] = Field(default_factory=tuple)
    total_counterparties: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> CounterpartAggregation:
        computed_base = sum((row.total_taxable_base for row in self.rollups), Decimal("0"))
        computed_total = sum((row.total_invoice_total for row in self.rollups), Decimal("0"))
        if computed_base != self.total_taxable_base:
            raise ValueError(
                f"total_taxable_base {self.total_taxable_base} != sum of rollups {computed_base}",
            )
        if computed_total != self.total_invoice_total:
            raise ValueError(
                f"total_invoice_total {self.total_invoice_total} != sum of rollups {computed_total}",
            )
        unique_counterparties = {row.counterparty_nif for row in self.rollups}
        if len(unique_counterparties) != self.total_counterparties:
            raise ValueError(
                f"total_counterparties {self.total_counterparties} != distinct NIFs {len(unique_counterparties)}",
            )
        return self


_MODELO_347_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind347)
_MODELO_349_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind349)
_MODELO_KIND_CATALOGUE: dict[str, frozenset[str]] = {
    Modelo.M347.value: _MODELO_347_KINDS,
    Modelo.M349.value: _MODELO_349_KINDS,
}
COUNTERPART_MODELO_KIND_CATALOGUE: Mapping[str, frozenset[str]] = MappingProxyType(_MODELO_KIND_CATALOGUE)


def _aggregate_for_modelo(
    observations: tuple[CounterpartObservation, ...],
    *,
    modelo: str,
    period: Period,
) -> CounterpartAggregation:
    filtered = filter_observations_for_modelo(
        observations,
        modelo=modelo,
        catalogue=_MODELO_KIND_CATALOGUE,
        attribute_fn=lambda obs: obs.operation_kind,
        aggregator_label="counterpart aggregator",
    )
    grouped, names = group_and_collect_names(
        filtered,
        group_key_fn=lambda obs: (obs.source_kind, obs.counterparty_nif, obs.operation_kind),
        identity_key_fn=lambda obs: (obs.source_kind, obs.counterparty_nif),
        name_fn=lambda obs: obs.counterparty_name,
    )
    rollups: list[CounterpartRollup] = []
    for (source_kind, nif, op_kind), group in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_invoice = sum((g.invoice_total for g in group), Decimal("0"))
        country = _single_counterparty_country(
            observations=tuple(group),
            source_kind=source_kind,
            counterparty_nif=nif,
            operation_kind=op_kind,
        )
        readiness = _counterpart_readiness_for_modelo(modelo=modelo, country=country, observations=tuple(group))
        rollups.append(
            CounterpartRollup(
                source_kind=source_kind,
                counterparty_nif=nif,
                counterparty_name=names.get((source_kind, nif), ""),
                counterparty_country=country,
                operation_kind=op_kind,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_invoice_total=total_invoice,
                **readiness,
            ),
        )
    counterparties = {row.counterparty_nif for row in rollups}
    return CounterpartAggregation(
        modelo=modelo,
        period=period,
        rollups=tuple(rollups),
        total_counterparties=len(counterparties),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_invoice_total=sum((row.total_invoice_total for row in rollups), Decimal("0")),
    )


def _single_counterparty_country(
    *,
    observations: tuple[CounterpartObservation, ...],
    source_kind: str,
    counterparty_nif: str,
    operation_kind: str,
) -> str:
    countries = frozenset(observation.counterparty_country for observation in observations)
    if len(countries) != 1:
        raise ValueError(
            "conflicting counterparty_country values for counterpart aggregation cohort "
            f"source_kind={source_kind!r}, counterparty_nif={counterparty_nif!r}, "
            f"operation_kind={operation_kind!r}: {sorted(countries)!r}",
        )
    return next(iter(countries))


def aggregate_counterpart_347(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: Period,
) -> CounterpartAggregation:
    """Aggregate Modelo 347 (operaciones con terceros, annual).

    Filters to 347 operation kinds. Threshold gating (the €3,005.06
    declaration floor) belongs to the modelo binding consumer; this
    aggregator returns raw per-counterparty totals.

    Returns a :class:`CounterpartAggregation`.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M347.value, period=period)


def aggregate_counterpart_349(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: Period,
) -> CounterpartAggregation:
    """Aggregate Modelo 349 (operaciones intracomunitarias).

    Filters to 349 intracomunitarias operation kinds. Rollups carry
    the additional NIF-IVA / GROI readiness gates: Spanish
    counterparties require GROI readiness and non-Spanish
    counterparties require NIF-IVA readiness.

    Returns a :class:`CounterpartAggregation` with rollups sorted by
    ``(source_kind, counterparty_nif, operation_kind)``.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M349.value, period=period)


class CounterpartAggregationSourceResolver:
    """Resolve counterpart-source bindings from operator-supplied 347/349 observations.

    The resolver is deliberately repository-free: it wraps the existing
    ``CounterpartObservation`` aggregate surface and emits the source-mesh
    envelope used by calculation once a caller supplies those observations.
    """

    resolver_id = "counterpart_aggregation"
    owned_sources = _OWNED_SOURCES

    def __init__(self, *, observations: Iterable[CounterpartObservation] = ()) -> None:
        self._observations = tuple(observations)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        active_sources = _counterpart_sources_for_revision(context)
        if not active_sources:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        selected_observations = _selected_counterpart_observations(
            context=context,
            observations=self._observations,
            active_sources=active_sources,
        )
        aggregation = _aggregate_counterpart_for_context(context, selected_observations)
        registry_observations = _registry_observations_from_counterpart_aggregation(aggregation)
        active_revision = _revision_with_active_counterpart_bindings(context.revision, active_sources)
        binding_values = resolve_counterpart_binding_values(active_revision, registry_observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=_m349_declarante_summary_union(
                context=context,
                binding_values=binding_values,
                target_binding_ids=frozenset(binding.id for binding in active_revision.bindings),
            ),
            source_transaction_ids=tuple(
                sorted(
                    observation.source_object_id
                    for observation in selected_observations
                    if observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
                ),
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind=observation.source_kind.value,
                    source_ref=f"{observation.source_kind.value}:{observation.source_object_id}",
                )
                for observation in selected_observations
            ),
        )


def _counterpart_readiness_for_modelo(
    *,
    modelo: str,
    country: str,
    observations: tuple[CounterpartObservation, ...],
) -> dict[str, bool]:
    if modelo != Modelo.M349.value:
        return {
            "requires_groi_check": False,
            "requires_nif_iva_check": False,
            "groi_ready": True,
            "nif_iva_ready": True,
            "declarable_readiness_satisfied": True,
        }
    requires_groi = country == "ES"
    requires_nif_iva = country != "ES"
    groi_ready = (not requires_groi) or all(obs.groi_verified for obs in observations)
    nif_iva_ready = (not requires_nif_iva) or all(obs.nif_iva_verified for obs in observations)
    return {
        "requires_groi_check": requires_groi,
        "requires_nif_iva_check": requires_nif_iva,
        "groi_ready": groi_ready,
        "nif_iva_ready": nif_iva_ready,
        "declarable_readiness_satisfied": groi_ready and nif_iva_ready,
    }


def _counterpart_sources_for_revision(context: CalculationSourceContext) -> frozenset[BindingSourceKind]:
    sources: set[BindingSourceKind] = set()
    for binding in context.revision.bindings:
        try:
            source = BindingSourceKind(binding.source)
        except ValueError:
            continue
        if source in _OWNED_SOURCE_SET:
            sources.add(source)
    return frozenset(sources)


def _revision_with_active_counterpart_bindings(
    revision: ModeloRevision,
    active_sources: frozenset[BindingSourceKind],
) -> ModeloRevision:
    return revision.model_copy(
        update={
            "bindings": tuple(binding for binding in revision.bindings if binding.source in active_sources),
        },
    )


def _aggregate_counterpart_for_context(
    context: CalculationSourceContext,
    observations: tuple[CounterpartObservation, ...],
) -> CounterpartAggregation:
    if str(context.modelo) == Modelo.M347.value:
        return aggregate_counterpart_347(observations, period=context.period)
    if str(context.modelo) == Modelo.M349.value:
        return aggregate_counterpart_349(observations, period=context.period)
    return CounterpartAggregation(
        modelo=str(context.modelo),
        period=context.period,
        rollups=(),
        total_counterparties=0,
        total_taxable_base=Decimal("0"),
        total_invoice_total=Decimal("0"),
    )


def _selected_counterpart_observations(
    *,
    context: CalculationSourceContext,
    observations: tuple[CounterpartObservation, ...],
    active_sources: frozenset[BindingSourceKind],
) -> tuple[CounterpartObservation, ...]:
    modelo_kinds = _MODELO_KIND_CATALOGUE.get(str(context.modelo), frozenset())
    return tuple(
        observation
        for observation in observations
        if observation.source_kind in active_sources and observation.operation_kind in modelo_kinds
    )


def _registry_observations_from_counterpart_aggregation(
    aggregation: CounterpartAggregation,
) -> tuple[CounterpartAggregationObservation, ...]:
    return tuple(_registry_observation_from_counterpart_rollup(aggregation, rollup) for rollup in aggregation.rollups)


def _registry_observation_from_counterpart_rollup(
    aggregation: CounterpartAggregation,
    rollup: CounterpartRollup,
) -> CounterpartAggregationObservation:
    return CounterpartAggregationObservation(
        source_kind=rollup.source_kind,
        source_id=f"{rollup.source_kind.value}:{rollup.counterparty_nif}:{rollup.operation_kind}",
        party_tax_id=rollup.counterparty_nif,
        country_code=rollup.counterparty_country,
        transaction_date=_period_representative_date(aggregation.period),
        base_amount=rollup.total_taxable_base,
        invoice_total_amount=rollup.total_invoice_total,
        intracommunity_clave=_m349_clave_for_operation_kind(rollup.operation_kind),
        party_legal_name=rollup.counterparty_name or None,
    )


def _period_representative_date(period: Period) -> date:
    if period.has_date_span():
        return period.start_date
    return date(period.year, 1, 1)


def _m349_clave_for_operation_kind(operation_kind: str) -> str | None:
    return _M349_CLAVE_BY_OPERATION_KIND.get(operation_kind)


def _m349_declarante_summary_union(
    *,
    context: CalculationSourceContext,
    binding_values: dict[str, Decimal],
    target_binding_ids: frozenset[str],
) -> dict[str, Decimal]:
    if str(context.modelo) != Modelo.M349.value:
        return binding_values
    merged = dict(binding_values)
    for payable_binding, public_binding in _M349_PAYABLE_SUMMARY_BINDING_MIRRORS.items():
        if payable_binding not in binding_values:
            continue
        if public_binding not in target_binding_ids:
            continue
        merged[public_binding] = merged.get(public_binding, Decimal("0")) + binding_values[payable_binding]
    return merged


def declarable_counterparty_nifs_347(aggregation: CounterpartAggregation) -> frozenset[str]:
    """Return counterparties whose full Modelo 347 total exceeds the declaration floor."""
    totals: dict[str, Decimal] = {}
    for rollup in aggregation.rollups:
        totals[rollup.counterparty_nif] = totals.get(rollup.counterparty_nif, Decimal("0")) + rollup.total_invoice_total
    return frozenset(nif for nif, total in totals.items() if total > M347_THRESHOLD_EUR)


def declarable_for_347(aggregation: CounterpartAggregation, *, counterparty_nif: str) -> bool:
    """Return True iff a counterparty exceeds the 347 declaration floor across all cohorts."""
    return counterparty_nif in declarable_counterparty_nifs_347(aggregation)


__all__ = [
    "COUNTERPART_MODELO_KIND_CATALOGUE",
    "CounterpartAggregation",
    "CounterpartAggregationSourceResolver",
    "CounterpartObservation",
    "CounterpartRollup",
    "OperationKind347",
    "OperationKind349",
    "aggregate_counterpart_347",
    "aggregate_counterpart_349",
    "declarable_counterparty_nifs_347",
    "declarable_for_347",
]
