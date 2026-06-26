"""Central per-modelo aggregation service contracts.

Used by: :mod:`aeat.application.aggregation` package to route aggregation commands to appropriate providers.

This module owns the non-CLI aggregation boundary required by the CLI
workflow redesign. It routes strict Pydantic command payloads to the
implemented family aggregators without adding CLI-local conversion logic.

Providers: ``retenciones`` (111/115/123/180/190/193), ``counterpart`` (347/349), ``foreign_assets`` (720).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind, Modelo, Period
from ...core.external_constants import COUNTERPART_MODELOS, FOREIGN_ASSET_MODELOS, RETENCIONES_MODELOS
from ...core.logging import get_logger
from ._counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
)
from ._errors import AggregationConfigError, AggregationUnsupportedModeloError, t
from ._foreign_assets import ForeignAssetIngestObservation, ForeignAssetsAggregation, aggregate_foreign_assets_720
from ._retenciones import (
    RetencionesAggregation,
    RetencionObservation,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
)

LOGGER = get_logger(__name__)


class PerModeloAggregationProvider(StrEnum):
    """Implemented provider families owned by ``aeat.application.aggregation``."""

    RETENCIONES = "retenciones"
    COUNTERPART = "counterpart"
    FOREIGN_ASSETS = "foreign_assets"


ACCEPTED_SOURCE_KINDS: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.LEDGER_TRANSACTION,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.COLLECTIBLE_INVOICE,
)

AggregationErrorCodes: tuple[str, ...] = (
    "ERROR_FINANCIAL_AGGREGATION",
    "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO",
    "ERROR_FINANCIAL_AGGREGATION_VALIDATION",
)

_RETENCIONES_MODELOS = RETENCIONES_MODELOS
_COUNTERPART_MODELOS = COUNTERPART_MODELOS
_FOREIGN_ASSET_MODELOS = FOREIGN_ASSET_MODELOS


class PerModeloAggregationProviderContract(BaseModel):
    """Backend-owned contract for one aggregation provider family."""

    model_config = _STRICT_FROZEN

    provider: PerModeloAggregationProvider
    modelos: tuple[str, ...] = Field(min_length=1)
    service_owner: str = Field(pattern=r"^aeat\.application\.aggregation$")
    accepted_source_kinds: tuple[BindingSourceKind, ...] = Field(min_length=1)

    @field_validator("modelos")
    @classmethod
    def _modelos_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise AggregationConfigError(
                "provider modelos must be unique",
                translated_message="aggregation.service.errors.provider_modelos_not_unique",
            )
        return value


class PerModeloAggregationLogFields(BaseModel):
    """Stable, non-secret log fields emitted by the aggregation service."""

    model_config = _STRICT_FROZEN

    service_name: str = "per_modelo_aggregation"
    modelo: str = Field(min_length=1)
    period: Period
    provider: PerModeloAggregationProvider
    observation_count: int = Field(ge=0)
    source_kind_count: int = Field(ge=0)
    result_row_count: int = Field(ge=0)

    def as_extra(self) -> Mapping[str, object]:
        """Return a logging ``extra`` payload with stable field names."""
        return {
            "service_name": self.service_name,
            "modelo": self.modelo,
            "period": self.period.registry_token,
            "provider": self.provider.value,
            "observation_count": self.observation_count,
            "source_kind_count": self.source_kind_count,
            "result_row_count": self.result_row_count,
        }


class PerModeloAggregationContract(BaseModel):
    """Complete backend contract consumed by current and future adapters."""

    model_config = _STRICT_FROZEN

    schema_version: str = "1"
    service_owner: str = "aeat.application.aggregation"
    providers: tuple[PerModeloAggregationProviderContract, ...]
    accepted_source_kinds: tuple[BindingSourceKind, ...]
    error_codes: tuple[str, ...]

    @field_validator("providers")
    @classmethod
    def _providers_are_unique(
        cls,
        value: tuple[PerModeloAggregationProviderContract, ...],
    ) -> tuple[PerModeloAggregationProviderContract, ...]:
        providers = tuple(provider.provider for provider in value)
        if len(providers) != len(set(providers)):
            raise AggregationConfigError(
                "per-modelo aggregation providers must be unique",
                translated_message="aggregation.service.errors.per_modelo_providers_not_unique",
            )
        modelos = tuple(modelo for provider in value for modelo in provider.modelos)
        if len(modelos) != len(set(modelos)):
            raise AggregationConfigError(
                "per-modelo aggregation modelos must be owned by exactly one provider",
                translated_message="aggregation.service.errors.per_modelo_modelos_not_unique",
            )
        return value

    @field_validator("accepted_source_kinds")
    @classmethod
    def _source_kinds_are_exact(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if value != ACCEPTED_SOURCE_KINDS:
            raise AggregationConfigError(
                "source kinds must match the accepted four-kind taxonomy",
                translated_message="aggregation.service.errors.source_kinds_mismatch",
            )
        return value


class PerModeloAggregationCommand(BaseModel):
    """Command payload for a per-modelo aggregation run."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    retencion_observations: tuple[RetencionObservation, ...] = Field(default_factory=tuple)
    counterpart_observations: tuple[CounterpartObservation, ...] = Field(default_factory=tuple)
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _only_matching_observation_family_is_populated(self) -> PerModeloAggregationCommand:
        provider = provider_for_modelo(self.modelo)
        populated = {
            PerModeloAggregationProvider.RETENCIONES: bool(self.retencion_observations),
            PerModeloAggregationProvider.COUNTERPART: bool(self.counterpart_observations),
            PerModeloAggregationProvider.FOREIGN_ASSETS: bool(self.foreign_asset_observations),
        }
        invalid = tuple(
            candidate for candidate, has_rows in populated.items() if candidate is not provider and has_rows
        )
        if invalid:
            names = ", ".join(candidate.value for candidate in invalid)
            raise AggregationConfigError(
                f"observations for {names} cannot be supplied for modelo {self.modelo}",
                translated_message="aggregation.service.errors.observations_mismatch",
                context={"names": names, "modelo": self.modelo},
            )
        return self

    @computed_field
    @property
    def provider(self) -> PerModeloAggregationProvider:
        """Return the provider family selected by ``modelo``.

        Returns a :class:`PerModeloAggregationProvider`.
        """
        return provider_for_modelo(self.modelo)


PerModeloAggregationPayload = RetencionesAggregation | CounterpartAggregation | ForeignAssetsAggregation


class PerModeloAggregationResult(BaseModel):
    """Result envelope returned by the central per-modelo aggregation service."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    provider: PerModeloAggregationProvider
    aggregation: PerModeloAggregationPayload
    source_kinds: tuple[BindingSourceKind, ...]
    log_fields: PerModeloAggregationLogFields

    @field_validator("source_kinds")
    @classmethod
    def _source_kinds_are_unique(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if len(value) != len(set(value)):
            raise AggregationConfigError(
                "result source_kinds must be unique",
                translated_message="aggregation.service.errors.result_source_kinds_not_unique",
            )
        return value

    @model_validator(mode="after")
    def _envelope_matches_payload(self) -> PerModeloAggregationResult:
        if self.aggregation.modelo != self.modelo:
            raise AggregationConfigError(
                f"aggregation modelo {self.aggregation.modelo!r} does not match result modelo {self.modelo!r}",
                translated_message="aggregation.service.errors.envelope_modelo_mismatch",
                context={"aggregation_modelo": self.aggregation.modelo, "result_modelo": self.modelo},
            )
        if self.aggregation.period != self.period:
            raise AggregationConfigError(
                f"aggregation period {self.aggregation.period!r} does not match result period {self.period!r}",
                translated_message="aggregation.service.errors.envelope_period_mismatch",
                context={"aggregation_period": self.aggregation.period, "result_period": self.period},
            )
        expected_payload_types = {
            PerModeloAggregationProvider.RETENCIONES: RetencionesAggregation,
            PerModeloAggregationProvider.COUNTERPART: CounterpartAggregation,
            PerModeloAggregationProvider.FOREIGN_ASSETS: ForeignAssetsAggregation,
        }
        expected_type = expected_payload_types[self.provider]
        if not isinstance(self.aggregation, expected_type):
            raise AggregationConfigError(
                f"provider {self.provider.value!r} does not match aggregation payload "
                f"{type(self.aggregation).__name__!r}",
                translated_message="aggregation.service.errors.envelope_provider_payload_mismatch",
                context={
                    "provider": self.provider.value,
                    "payload_type": type(self.aggregation).__name__,
                },
            )
        return self


def build_per_modelo_aggregation_contract() -> PerModeloAggregationContract:
    """Build the immutable backend-owned aggregation contract.

    Returns a :class:`PerModeloAggregationContract` enumerating every
    registered provider, accepted source kinds, and known error codes.
    """
    providers = (
        PerModeloAggregationProviderContract(
            provider=PerModeloAggregationProvider.RETENCIONES,
            modelos=_RETENCIONES_MODELOS,
            service_owner="aeat.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        ),
        PerModeloAggregationProviderContract(
            provider=PerModeloAggregationProvider.COUNTERPART,
            modelos=_COUNTERPART_MODELOS,
            service_owner="aeat.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        ),
        PerModeloAggregationProviderContract(
            provider=PerModeloAggregationProvider.FOREIGN_ASSETS,
            modelos=_FOREIGN_ASSET_MODELOS,
            service_owner="aeat.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        ),
    )
    contract = PerModeloAggregationContract(
        providers=providers,
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        error_codes=AggregationErrorCodes,
    )
    LOGGER.debug(
        "built per-modelo aggregation contract",
        extra={
            "service_name": "per_modelo_aggregation",
            "provider_count": len(contract.providers),
            "source_kind_count": len(contract.accepted_source_kinds),
        },
    )
    return contract


@lru_cache(maxsize=1)
def get_per_modelo_aggregation_contract() -> PerModeloAggregationContract:
    """Return the cached backend-owned :class:`PerModeloAggregationContract`."""
    return build_per_modelo_aggregation_contract()


def provider_for_modelo(modelo: str) -> PerModeloAggregationProvider:
    """Return the provider family for a supported modelo.

    Returns a :class:`PerModeloAggregationProvider` member identifying
    the aggregation family that owns the given modelo number.
    """
    if modelo != modelo.strip():
        raise AggregationUnsupportedModeloError(
            t("aggregation.per_modelo.errors.unsupported_modelo"),
            context={"modelo": modelo},
            suggestion="use one of 111, 115, 123, 180, 190, 193, 347, 349, 720",
        )
    if modelo in _RETENCIONES_MODELOS:
        return PerModeloAggregationProvider.RETENCIONES
    if modelo in _COUNTERPART_MODELOS:
        return PerModeloAggregationProvider.COUNTERPART
    if modelo in _FOREIGN_ASSET_MODELOS:
        return PerModeloAggregationProvider.FOREIGN_ASSETS
    raise AggregationUnsupportedModeloError(
        t("aggregation.per_modelo.errors.unsupported_modelo"),
        context={"modelo": modelo},
        suggestion="use one of 111, 115, 123, 180, 190, 193, 347, 349, 720",
    )


def aggregate_per_modelo(command: PerModeloAggregationCommand) -> PerModeloAggregationResult:
    """Run the central application aggregation service for one modelo.

    Returns a :class:`PerModeloAggregationResult`.
    """
    provider = provider_for_modelo(command.modelo)
    if provider is PerModeloAggregationProvider.RETENCIONES:
        aggregation = _aggregate_retenciones(command.modelo, command.period, command.retencion_observations)
    elif provider is PerModeloAggregationProvider.COUNTERPART:
        aggregation = _aggregate_counterpart(command.modelo, command.period, command.counterpart_observations)
    else:
        aggregation = aggregate_foreign_assets_720(command.foreign_asset_observations, period=command.period)

    result = PerModeloAggregationResult(
        modelo=command.modelo,
        period=command.period,
        provider=provider,
        aggregation=aggregation,
        source_kinds=_source_kinds_for_payload(aggregation),
        log_fields=PerModeloAggregationLogFields(
            modelo=command.modelo,
            period=command.period,
            provider=provider,
            observation_count=_observation_count_for_command(command, provider),
            source_kind_count=len(_source_kinds_for_payload(aggregation)),
            result_row_count=len(aggregation.rollups),
        ),
    )
    LOGGER.debug("ran per-modelo aggregation", extra=result.log_fields.as_extra())
    return result


def _aggregate_retenciones(
    modelo: str,
    period: Period,
    observations: tuple[RetencionObservation, ...],
) -> RetencionesAggregation:
    dispatch = {
        Modelo.M111.value: aggregate_retenciones_111,
        Modelo.M115.value: aggregate_retenciones_115,
        Modelo.M123.value: aggregate_retenciones_123,
        Modelo.M180.value: aggregate_retenciones_180,
        Modelo.M190.value: aggregate_retenciones_190,
        Modelo.M193.value: aggregate_retenciones_193,
    }
    return dispatch[modelo](observations, period=period)


def _aggregate_counterpart(
    modelo: str,
    period: Period,
    observations: tuple[CounterpartObservation, ...],
) -> CounterpartAggregation:
    if modelo == Modelo.M347.value:
        return aggregate_counterpart_347(observations, period=period)
    return aggregate_counterpart_349(observations, period=period)


def _source_kinds_for_payload(payload: PerModeloAggregationPayload) -> tuple[BindingSourceKind, ...]:
    source_kind_values = sorted({row.source_kind for row in payload.rollups})
    return tuple(BindingSourceKind(value) for value in source_kind_values)


def _observation_count_for_command(
    command: PerModeloAggregationCommand,
    provider: PerModeloAggregationProvider,
) -> int:
    if provider is PerModeloAggregationProvider.RETENCIONES:
        return len(command.retencion_observations)
    if provider is PerModeloAggregationProvider.COUNTERPART:
        return len(command.counterpart_observations)
    return len(command.foreign_asset_observations)


__all__ = [
    "ACCEPTED_SOURCE_KINDS",
    "AggregationErrorCodes",
    "PerModeloAggregationCommand",
    "PerModeloAggregationContract",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationPayload",
    "PerModeloAggregationProvider",
    "PerModeloAggregationProviderContract",
    "PerModeloAggregationResult",
    "aggregate_per_modelo",
    "build_per_modelo_aggregation_contract",
    "get_per_modelo_aggregation_contract",
    "provider_for_modelo",
]
