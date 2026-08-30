"""Central per-modelo aggregation service contracts.

This module owns the non-CLI service boundary for the aggregate command
surface. It routes a strict :class:`PerModeloAggregationCommand` to the
provider family that owns the requested modelo and returns a typed
:class:`PerModeloAggregationResult` without requiring CLI-local conversion
logic.

The service is distinct from the live calculate source mesh. Retenciones,
counterpart, and foreign-assets providers return per-modelo aggregation
payloads for operator-facing aggregation/reporting flows; source-derived
values that feed calculation use :class:`~application.aggregation.CalculationSourceResolution`
from :mod:`application.aggregation._source_mesh`.

Providers: ``retenciones`` (111/115/123/180/190/193), ``counterpart``
(347/349), and ``foreign_assets`` (720).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from ...core.aggregation import COUNTERPART_SOURCE_KIND_ORDER, BindingSourceKind
from ...core.external_constants import COUNTERPART_MODELOS, FOREIGN_ASSET_MODELOS, RETENCIONES_MODELOS
from ...core.logging import LogExtra, get_logger
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.modelos.codes import ModeloCode
from ._counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
)
from ._foreign_assets import ForeignAssetIngestObservation, ForeignAssetsAggregation, aggregate_foreign_assets_720
from ._modelo_bindings import RetencionesAggregationSourceResolver
from ._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from ._retenciones import RetencionesAggregation, RetencionObservation
from .errors import AggregationConfigError, AggregationUnsupportedModeloError, t

LOGGER = get_logger(__name__)


class PerModeloAggregationContributor(StrEnum):
    """Implemented aggregation-contributor families owned by ``cadrumo.application.aggregation``.

    Names the contributor-role axis (which backend family aggregates a
    modelo's ledger evidence), distinct from the settled
    :class:`ModeloSourceResolver` calculate-mesh port. The member string
    values (``retenciones`` / ``counterpart`` / ``foreign_assets``) are
    unchanged.
    """

    RETENCIONES = "retenciones"
    COUNTERPART = "counterpart"
    FOREIGN_ASSETS = "foreign_assets"


ACCEPTED_SOURCE_KINDS: tuple[BindingSourceKind, ...] = COUNTERPART_SOURCE_KIND_ORDER

AggregationErrorCodes: tuple[str, ...] = (
    "ERROR_FINANCIAL_AGGREGATION",
    "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO",
    "ERROR_FINANCIAL_AGGREGATION_VALIDATION",
)

_RETENCIONES_MODELOS = RETENCIONES_MODELOS
_COUNTERPART_MODELOS = COUNTERPART_MODELOS
_FOREIGN_ASSET_MODELOS = FOREIGN_ASSET_MODELOS
_SUPPORTED_PER_MODELO_MODELOS = tuple(sorted((*_RETENCIONES_MODELOS, *_COUNTERPART_MODELOS, *_FOREIGN_ASSET_MODELOS)))


class PerModeloAggregationContributorContract(BaseModel):
    """Backend-owned contract for one aggregation provider family."""

    model_config = _STRICT_FROZEN

    provider: PerModeloAggregationContributor
    modelos: tuple[str, ...] = Field(min_length=1)
    service_owner: str = Field(pattern=r"^cadrumo\.application\.aggregation$")
    accepted_source_kinds: tuple[BindingSourceKind, ...] = Field(min_length=1)

    @field_validator("modelos")
    @classmethod
    def _modelos_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.provider_modelos_not_unique",
            )
        return value


class PerModeloAggregationLogFields(BaseModel):
    """Stable, non-secret log fields emitted by the aggregation service."""

    model_config = _STRICT_FROZEN

    service_name: str = "per_modelo_aggregation"
    modelo: ModeloCode
    period: Period
    provider: PerModeloAggregationContributor
    observation_count: int = Field(ge=0)
    source_kind_count: int = Field(ge=0)
    result_row_count: int = Field(ge=0)

    def as_extra(self) -> LogExtra:
        """Return a typed logging ``extra`` payload with stable field names."""
        return LogExtra(
            {
                "service_name": self.service_name,
                "modelo": self.modelo,
                "period": self.period.registry_token,
                "provider": self.provider.value,
                "observation_count": self.observation_count,
                "source_kind_count": self.source_kind_count,
                "result_row_count": self.result_row_count,
            }
        )


class PerModeloAggregationContract(BaseModel):
    """Complete backend contract consumed by current and future adapters."""

    model_config = _STRICT_FROZEN

    schema_version: str = "1"
    service_owner: str = "cadrumo.application.aggregation"
    providers: tuple[PerModeloAggregationContributorContract, ...]
    accepted_source_kinds: tuple[BindingSourceKind, ...]
    error_codes: tuple[str, ...]

    @field_validator("providers")
    @classmethod
    def _providers_are_unique(
        cls,
        value: tuple[PerModeloAggregationContributorContract, ...],
    ) -> tuple[PerModeloAggregationContributorContract, ...]:
        providers = tuple(provider.provider for provider in value)
        if len(providers) != len(set(providers)):
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.per_modelo_providers_not_unique",
            )
        modelos = tuple(modelo for provider in value for modelo in provider.modelos)
        if len(modelos) != len(set(modelos)):
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.per_modelo_modelos_not_unique",
            )
        return value

    @field_validator("accepted_source_kinds")
    @classmethod
    def _source_kinds_are_exact(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if value != ACCEPTED_SOURCE_KINDS:
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.source_kinds_mismatch",
            )
        return value


class PerModeloAggregationCommand(BaseModel):
    """Command payload for a per-modelo aggregation run.

    ``modelo`` is deliberately NOT :class:`ModeloCode` here, though the result
    and contract models beside it are. Which modelos this service supports is
    registry-driven, and the CLI contract allows a late refusal for exactly that
    reason provided it names the accepted set. Typing the field would refuse a
    malformed code at construction with a generic shape error instead, losing
    the listing the operator needs.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    retencion_observations: tuple[RetencionObservation, ...] = Field(default_factory=tuple)
    counterpart_observations: tuple[CounterpartObservation, ...] = Field(default_factory=tuple)
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...] = Field(default_factory=tuple)
    withholding_observations: tuple[WithholdingObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _only_matching_observation_family_is_populated(self) -> PerModeloAggregationCommand:
        provider = provider_for_modelo(self.modelo)
        populated = {
            PerModeloAggregationContributor.RETENCIONES: bool(self.retencion_observations),
            PerModeloAggregationContributor.COUNTERPART: bool(self.counterpart_observations),
            PerModeloAggregationContributor.FOREIGN_ASSETS: bool(self.foreign_asset_observations),
        }
        invalid = tuple(
            candidate for candidate, has_rows in populated.items() if candidate is not provider and has_rows
        )
        if invalid:
            names = ", ".join(candidate.value for candidate in invalid)
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.observations_mismatch",
                context={"names": names, "modelo": self.modelo},
            )
        return self

    @computed_field
    @property
    def provider(self) -> PerModeloAggregationContributor:
        """Return the provider family selected by ``modelo``.

        Returns a :class:`PerModeloAggregationContributor`.
        """
        return provider_for_modelo(self.modelo)


PerModeloAggregationPayload = RetencionesAggregation | CounterpartAggregation | ForeignAssetsAggregation


class PerModeloAggregationResult(BaseModel):
    """Result envelope returned by the central per-modelo aggregation service."""

    model_config = _STRICT_FROZEN

    modelo: ModeloCode
    period: Period
    provider: PerModeloAggregationContributor
    aggregation: PerModeloAggregationPayload
    source_kinds: tuple[BindingSourceKind, ...]
    log_fields: PerModeloAggregationLogFields

    @field_validator("source_kinds")
    @classmethod
    def _source_kinds_are_unique(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if len(value) != len(set(value)):
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.result_source_kinds_not_unique",
            )
        return value

    @model_validator(mode="after")
    def _envelope_matches_payload(self) -> PerModeloAggregationResult:
        if self.aggregation.modelo != self.modelo:
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.envelope_modelo_mismatch",
                context={"aggregation_modelo": self.aggregation.modelo, "result_modelo": self.modelo},
            )
        if self.aggregation.period != self.period:
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.envelope_period_mismatch",
                context={"aggregation_period": self.aggregation.period, "result_period": self.period},
            )
        provider_matches_payload = (
            (
                self.provider is PerModeloAggregationContributor.RETENCIONES
                and isinstance(self.aggregation, RetencionesAggregation)
            )
            or (
                self.provider is PerModeloAggregationContributor.COUNTERPART
                and isinstance(self.aggregation, CounterpartAggregation)
            )
            or (
                self.provider is PerModeloAggregationContributor.FOREIGN_ASSETS
                and isinstance(self.aggregation, ForeignAssetsAggregation)
            )
        )
        if not provider_matches_payload:
            raise AggregationConfigError(
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
        PerModeloAggregationContributorContract(
            provider=PerModeloAggregationContributor.RETENCIONES,
            modelos=_RETENCIONES_MODELOS,
            service_owner="cadrumo.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        ),
        PerModeloAggregationContributorContract(
            provider=PerModeloAggregationContributor.COUNTERPART,
            modelos=_COUNTERPART_MODELOS,
            service_owner="cadrumo.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        ),
        PerModeloAggregationContributorContract(
            provider=PerModeloAggregationContributor.FOREIGN_ASSETS,
            modelos=_FOREIGN_ASSET_MODELOS,
            service_owner="cadrumo.application.aggregation",
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


def provider_for_modelo(modelo: str) -> PerModeloAggregationContributor:
    """Return the provider family for a supported modelo.

    Returns a :class:`PerModeloAggregationContributor` member identifying
    the aggregation family that owns the given modelo number.
    """
    if modelo != modelo.strip():
        raise AggregationUnsupportedModeloError(
            t("aggregation.per_modelo.errors.unsupported_modelo"),
            context={"modelo": modelo},
            precondition_verdict=aggregation_no_recovery_verdict(
                AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
                facts={"modelo": modelo, "supported_modelos": "|".join(_SUPPORTED_PER_MODELO_MODELOS)},
            ),
        )
    if modelo in _RETENCIONES_MODELOS:
        return PerModeloAggregationContributor.RETENCIONES
    if modelo in _COUNTERPART_MODELOS:
        return PerModeloAggregationContributor.COUNTERPART
    if modelo in _FOREIGN_ASSET_MODELOS:
        return PerModeloAggregationContributor.FOREIGN_ASSETS
    raise AggregationUnsupportedModeloError(
        t("aggregation.per_modelo.errors.unsupported_modelo"),
        context={"modelo": modelo},
        precondition_verdict=aggregation_no_recovery_verdict(
            AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
            facts={"modelo": modelo, "supported_modelos": "|".join(_SUPPORTED_PER_MODELO_MODELOS)},
        ),
    )


def aggregate_per_modelo(command: PerModeloAggregationCommand) -> PerModeloAggregationResult:
    """Run the central application aggregation service for one modelo.

    Returns a :class:`PerModeloAggregationResult`.
    """
    provider = provider_for_modelo(command.modelo)
    if provider is PerModeloAggregationContributor.RETENCIONES:
        aggregation = _aggregate_retenciones(command.modelo, command.period, command.retencion_observations)
    elif provider is PerModeloAggregationContributor.COUNTERPART:
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
    LOGGER.debug("ran per-modelo aggregation", extra=result.log_fields.as_extra().for_logging())
    return result


def _aggregate_retenciones(
    modelo: str,
    period: Period,
    observations: tuple[RetencionObservation, ...],
) -> RetencionesAggregation:
    # Delegate to the ONE canonical mesh resolver aggregation entry point so the
    # per-modelo service (CLI aggregate / pull) and the live calculate mesh share
    # a single retenciones dispatch and cannot drift
    # (aeat-calculation-aggregation). ``provider_for_modelo`` has
    # already confirmed ``modelo`` is one of the retenciones modelos.
    return RetencionesAggregationSourceResolver.aggregate(modelo, observations, period=period)


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
    provider: PerModeloAggregationContributor,
) -> int:
    if provider is PerModeloAggregationContributor.RETENCIONES:
        return len(command.retencion_observations)
    if provider is PerModeloAggregationContributor.COUNTERPART:
        return len(command.counterpart_observations)
    return len(command.foreign_asset_observations)


__all__ = [
    "ACCEPTED_SOURCE_KINDS",
    "AggregationErrorCodes",
    "PerModeloAggregationCommand",
    "PerModeloAggregationContract",
    "PerModeloAggregationContributor",
    "PerModeloAggregationContributorContract",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationPayload",
    "PerModeloAggregationResult",
    "aggregate_per_modelo",
    "build_per_modelo_aggregation_contract",
    "get_per_modelo_aggregation_contract",
    "provider_for_modelo",
]
