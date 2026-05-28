"""Registry binding provider adapters for per-modelo aggregation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ...domain.calculations.registry import (
    CounterpartAggregationObservation as RegistryCounterpartObservation,
)
from ...domain.calculations.registry import (
    ModeloRevision,
    resolve_bound_casilla_inputs,
    resolve_counterpart_binding_row_values,
    resolve_counterpart_binding_values,
)
from ._counterpart import CounterpartAggregation, OperationKind349
from ._errors import AggregationUnsupportedModeloError, AggregationValidationError, t
from ._service import AggregationSourceKind, PerModeloAggregationCommand, PerModeloAggregationProvider, aggregate_per_modelo

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_COUNTERPART_BINDING_SOURCE_KINDS: frozenset[AggregationSourceKind] = frozenset(
    (
        AggregationSourceKind.LEDGER_TRANSACTION,
        AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
        AggregationSourceKind.PAYABLE_INVOICE,
        AggregationSourceKind.COLLECTIBLE_INVOICE,
    )
)

_OPERATION_KIND_349_TO_CLAVE = {
    OperationKind349.INTRA_DELIVERY.value: "E",
    OperationKind349.INTRA_ACQUISITION.value: "A",
    OperationKind349.INTRA_SERVICE_OUT.value: "S",
    OperationKind349.INTRA_SERVICE_IN.value: "I",
    OperationKind349.TRIANGULAR.value: "T",
}


class PerModeloRegistryBindingResolution(BaseModel):
    """Registry binding values produced by a per-modelo aggregation provider."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=16)
    provider: PerModeloAggregationProvider
    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    row_values: Mapping[tuple[str, int], Decimal | str] = Field(default_factory=dict)
    casilla_values: Mapping[str, Decimal] = Field(default_factory=dict)
    source_observation_count: int = Field(ge=0)

    @field_validator("binding_values", "casilla_values")
    @classmethod
    def _freeze_decimal_mapping(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("row_values")
    @classmethod
    def _freeze_row_values(
        cls,
        value: Mapping[tuple[str, int], Decimal | str],
    ) -> Mapping[tuple[str, int], Decimal | str]:
        return MappingProxyType(dict(sorted(value.items(), key=lambda item: (item[0][0], item[0][1]))))

    @field_serializer("binding_values", "casilla_values")
    def _serialize_decimal_mapping(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_serializer("row_values")
    def _serialize_row_values(self, value: Mapping[tuple[str, int], Decimal | str]) -> dict[str, Decimal | str]:
        return {f"{binding_id}:{row_index}": row_value for (binding_id, row_index), row_value in value.items()}


def resolve_per_modelo_registry_binding_values(
    command: PerModeloAggregationCommand,
    revision: ModeloRevision,
) -> PerModeloRegistryBindingResolution:
    """Resolve committed registry bindings from a per-modelo aggregation command.

    The current real registry-backed provider is Modelo 349 counterpart
    aggregation. Other modelos return an empty resolution unless their
    revision declares canonical counterpart binding sources, in which case
    refusing is safer than pretending a provider exists.
    """

    result = aggregate_per_modelo(command)
    counterpart_sources = _counterpart_binding_sources(revision)
    if not counterpart_sources:
        return PerModeloRegistryBindingResolution(
            modelo=result.modelo,
            period=result.period,
            provider=result.provider,
            source_observation_count=0,
        )
    if result.provider is not PerModeloAggregationProvider.COUNTERPART or result.modelo != "349":
        raise AggregationUnsupportedModeloError(
            t("aggregation.per_modelo.registry.errors.unsupported_provider"),
            context={"modelo": result.modelo, "provider": result.provider.value},
            suggestion="registry counterpart binding resolution is currently supported for Modelo 349",
        )

    aggregation = result.aggregation
    if not isinstance(aggregation, CounterpartAggregation):
        raise AggregationUnsupportedModeloError(
            t("aggregation.per_modelo.registry.errors.unsupported_provider"),
            context={"modelo": result.modelo, "provider": result.provider.value},
            suggestion="registry counterpart binding resolution requires a counterpart aggregation payload",
        )

    observations = _counterpart_registry_observations(
        command,
        source_kinds=counterpart_sources,
        ready_keys=_declarable_ready_counterpart_keys(aggregation),
    )
    binding_values = resolve_counterpart_binding_values(revision, observations)
    row_values = resolve_counterpart_binding_row_values(revision, observations)
    casilla_values = resolve_bound_casilla_inputs(revision, binding_values)
    return PerModeloRegistryBindingResolution(
        modelo=result.modelo,
        period=result.period,
        provider=result.provider,
        binding_values=binding_values,
        row_values=row_values,
        casilla_values=casilla_values,
        source_observation_count=len(observations),
    )


def _counterpart_binding_sources(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(
        binding.source for binding in revision.bindings if binding.source in _COUNTERPART_BINDING_SOURCE_KINDS
    )


def _counterpart_registry_observations(
    command: PerModeloAggregationCommand,
    *,
    source_kinds: frozenset[str],
    ready_keys: frozenset[tuple[str, str, str]],
) -> tuple[RegistryCounterpartObservation, ...]:
    observations: list[RegistryCounterpartObservation] = []
    for observation in command.counterpart_observations:
        if observation.source_kind not in source_kinds:
            continue
        key = (observation.source_kind, observation.counterparty_nif, observation.operation_kind)
        if key not in ready_keys:
            continue
        clave = _OPERATION_KIND_349_TO_CLAVE.get(observation.operation_kind)
        if clave is None:
            continue
        try:
            transaction_date = date.fromisoformat(observation.accrued_on)
        except ValueError as exc:
            raise AggregationValidationError(
                t("aggregation.per_modelo.registry.errors.invalid_accrued_on"),
                context={"source_object_id": observation.source_object_id, "accrued_on": observation.accrued_on},
            ) from exc
        observations.append(
            RegistryCounterpartObservation(
                source_kind=observation.source_kind,
                source_id=observation.source_object_id,
                party_tax_id=observation.counterparty_nif,
                country_code=observation.counterparty_country,
                transaction_date=transaction_date,
                base_amount=observation.taxable_base,
                intracommunity_clave=clave,
                party_legal_name=observation.counterparty_name or None,
            )
        )
    return tuple(observations)


def _declarable_ready_counterpart_keys(
    aggregation: CounterpartAggregation,
) -> frozenset[tuple[str, str, str]]:
    return frozenset(
        (rollup.source_kind, rollup.counterparty_nif, rollup.operation_kind)
        for rollup in aggregation.rollups
        if rollup.declarable_readiness_satisfied
    )


__all__ = [
    "PerModeloRegistryBindingResolution",
    "resolve_per_modelo_registry_binding_values",
]
