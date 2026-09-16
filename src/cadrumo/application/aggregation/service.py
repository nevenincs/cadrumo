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
from :mod:`application.aggregation.source_mesh`.

Providers: ``retenciones`` (111/115/123/180/190/193), ``counterpart``
(347/349), and ``foreign_assets`` (720).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.i18n.translatable import Translatable as t
from ...core.logging import LogExtra, get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.invoice_bindings import (
    CollectibleInvoiceProvider,
    M347ThirdPartyOperationProvider,
    PayableInvoiceProvider,
)
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.modelos.codes import ModeloCode
from ._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from .counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
)
from .errors import AggregationConfigError, AggregationUnsupportedModeloError
from .foreign_assets import ForeignAssetIngestObservation, ForeignAssetsAggregation, aggregate_foreign_assets_720
from .modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from .retenciones import RetencionesAggregation, RetencionObservation

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision

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


class PerModeloAggregationLogFields(BaseModel):
    """Stable, non-secret log fields emitted by the aggregation service."""

    model_config = _STRICT_FROZEN

    service_name: str = "per_modelo_aggregation"
    modelo: ModeloCode
    period: Period
    provider: PerModeloAggregationContributor
    observation_count: NonNegativeInt
    source_kind_count: NonNegativeInt
    result_row_count: NonNegativeInt

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
    @pydantic_validation_boundary
    def _source_kinds_are_unique(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        if len(value) != len(set(value)):
            raise AggregationConfigError(
                translated_message="aggregation.service.errors.result_source_kinds_not_unique",
            )
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
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


def _counterpart_binding(binding: BindingDefinition) -> bool:
    """Return whether a canonical invoice binding declares the M349 counterpart shape."""
    provider = binding.provider
    if isinstance(provider, M347ThirdPartyOperationProvider):
        return True
    if not isinstance(provider, PayableInvoiceProvider | CollectibleInvoiceProvider):
        return False
    return provider.grouping in {"operator_clave", "operator_clave_period"}


def _provider_for_modelo_revisions(
    modelo_id: str,
    revisions: tuple[ModeloRevision, ...],
) -> PerModeloAggregationContributor | None:
    """Classify one modelo from selected, explicitly enumerated revisions."""
    bindings = tuple(binding for revision in revisions for binding in revision.bindings)
    providers: set[PerModeloAggregationContributor] = set()
    # The retenciones resolver is itself the canonical aggregation registration:
    # some annual forms consume ``withholding`` or relation-prefill bindings
    # rather than a direct ``retenciones_aggregation`` binding, so source shape
    # alone would silently drop M123 and M190. Its registered typed dispatch is
    # therefore the authority for this application-owned provider family.
    if RetencionesAggregationSourceResolver.supports_modelo(modelo_id):
        providers.add(PerModeloAggregationContributor.RETENCIONES)
    if any(_counterpart_binding(binding) for binding in bindings):
        providers.add(PerModeloAggregationContributor.COUNTERPART)
    if any(binding.source is BindingSourceKind.FOREIGN_ASSET for binding in bindings):
        providers.add(PerModeloAggregationContributor.FOREIGN_ASSETS)
    if len(providers) > 1:
        raise AggregationConfigError(
            translated_message="aggregation.service.errors.per_modelo_modelos_not_unique",
            context={"modelo": modelo_id, "providers": ",".join(sorted(provider.value for provider in providers))},
        )
    return next(iter(providers), None)


def _registered_per_modelo_provider_modelos(
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[PerModeloAggregationContributor, tuple[str, ...]]:
    """Project aggregation ownership from explicit indexed registry components.

    This is intentionally not a second static modelo catalogue: the binding
    sources and selector shapes that calculation consumes are the canonical
    answer to which aggregation family can service a modelo. The contract is
    one of the few genuine bulk inventories, so it walks only the compact
    modelo directories and their addressed revision components.
    """
    grouped: dict[PerModeloAggregationContributor, list[str]] = {
        contributor: [] for contributor in PerModeloAggregationContributor
    }
    for modelo_id in operation.modelo_ids():
        directory = operation.modelo_directory(modelo_id)
        revisions = tuple(operation.revision(modelo_id, str(metadata.id)) for metadata in directory.revisions)
        if provider := _provider_for_modelo_revisions(modelo_id, tuple(revisions)):
            grouped[provider].append(modelo_id)
    return {contributor: tuple(sorted(modelos)) for contributor, modelos in grouped.items()}


def _supported_per_modelo_modelos(
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    """Return the exact accepted modelo ids in canonical registry order."""
    grouped = _registered_per_modelo_provider_modelos(operation=operation)
    return tuple(sorted(modelo for modelos in grouped.values() for modelo in modelos))


def provider_for_modelo(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation,
) -> PerModeloAggregationContributor:
    """Return the provider family for a supported modelo.

    Returns a :class:`PerModeloAggregationContributor` member identifying
    the aggregation family that owns the given modelo number.
    """
    supported = _supported_per_modelo_modelos(operation=operation)
    if modelo != modelo.strip():
        raise AggregationUnsupportedModeloError(
            t("aggregation.per_modelo.errors.unsupported_modelo"),
            context={"modelo": modelo},
            precondition_verdict=aggregation_no_recovery_verdict(
                AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
                facts={"modelo": modelo, "supported_modelos": "|".join(supported)},
            ),
        )
    for provider, modelos in _registered_per_modelo_provider_modelos(operation=operation).items():
        if modelo in modelos:
            return provider
    raise AggregationUnsupportedModeloError(
        t("aggregation.per_modelo.errors.unsupported_modelo"),
        context={"modelo": modelo},
        precondition_verdict=aggregation_no_recovery_verdict(
            AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED,
            facts={"modelo": modelo, "supported_modelos": "|".join(supported)},
        ),
    )


def aggregate_per_modelo(
    command: PerModeloAggregationCommand,
    *,
    operation: PinnedAuthorityOperation,
) -> PerModeloAggregationResult:
    """Run the central application aggregation service for one modelo.

    Returns a :class:`PerModeloAggregationResult`.
    """
    provider = provider_for_modelo(command.modelo, operation=operation)
    populated = {
        PerModeloAggregationContributor.RETENCIONES: bool(command.retencion_observations),
        PerModeloAggregationContributor.COUNTERPART: bool(command.counterpart_observations),
        PerModeloAggregationContributor.FOREIGN_ASSETS: bool(command.foreign_asset_observations),
    }
    invalid = tuple(candidate for candidate, has_rows in populated.items() if candidate is not provider and has_rows)
    if invalid:
        names = ", ".join(candidate.value for candidate in invalid)
        raise AggregationConfigError(
            translated_message="aggregation.service.errors.observations_mismatch",
            context={"names": names, "modelo": command.modelo},
        )
    # `command.modelo` is deliberately a loose `str` so an unsupported code earns
    # the late refusal above, which names the accepted set. `provider_for_modelo`
    # has now proven the code is one of those supported members, so this is the
    # boundary where the loose input becomes the typed identity the result and
    # log fields declare. `ModeloCode` re-validates the three-digit shape rather
    # than asserting it.
    modelo = ModeloCode(command.modelo)
    if provider is PerModeloAggregationContributor.RETENCIONES:
        aggregation = _aggregate_retenciones(command.modelo, command.period, command.retencion_observations)
    elif provider is PerModeloAggregationContributor.COUNTERPART:
        aggregation = _aggregate_counterpart(
            command.modelo,
            command.period,
            command.counterpart_observations,
            operation=operation,
        )
    else:
        aggregation = aggregate_foreign_assets_720(command.foreign_asset_observations, period=command.period)

    result = PerModeloAggregationResult(
        modelo=modelo,
        period=command.period,
        provider=provider,
        aggregation=aggregation,
        source_kinds=_source_kinds_for_payload(aggregation),
        log_fields=PerModeloAggregationLogFields(
            modelo=modelo,
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
    *,
    operation: PinnedAuthorityOperation,
) -> CounterpartAggregation:
    revision = operation.revision_for_context(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    if any(binding.source is BindingSourceKind.M347_THIRD_PARTY_OPERATION for binding in revision.bindings):
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
    "PerModeloAggregationCommand",
    "PerModeloAggregationContributor",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationPayload",
    "PerModeloAggregationResult",
    "aggregate_per_modelo",
    "provider_for_modelo",
]
