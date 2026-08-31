"""Per-perceptor retenciones source resolver for modelo calculation bindings."""

from __future__ import annotations

from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.retenciones_bindings import resolve_retenciones_aggregation_binding_values
from ._modelo_bindings_support import (
    _STORAGE_DEGRADATION_ERRORS,
    _empty_source_resolution,
    _revision_has_binding_source,
)
from ._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from ._retencion_observations_repository import RetencionObservationRepository
from ._retencion_rate_advisory import (
    administrador_retencion_rate_advisory_observations,
)
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
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .errors import AggregationValidationError, t
from .source_resolution_operations import (
    source_provenance_for as _provenance_for,
)
from .source_resolution_operations import storage_degradation_resolution

_RETENCIONES_AGGREGATORS = {
    Modelo.M111.value: aggregate_retenciones_111,
    Modelo.M115.value: aggregate_retenciones_115,
    Modelo.M123.value: aggregate_retenciones_123,
    Modelo.M180.value: aggregate_retenciones_180,
    Modelo.M190.value: aggregate_retenciones_190,
    Modelo.M193.value: aggregate_retenciones_193,
}


class RetencionesAggregationSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor retención store.

    Reads the bucket-scoped per-perceptor retención observations
    (:class:`~._retencion_observations_repository.RetencionObservationRepository`)
    for the modelo's period and materialises the declared retenciones aggregation
    bindings through the matching validated aggregator. Modelo 115 consumes the
    quarterly URBAN_RENTAL count/base; annual summary modelos consume the same
    family store for their distinct-NIF count. Modelo 190's percepciones count is
    handled by :class:`~._withholding_source.WithholdingSourceResolver`.
    """

    resolver_id: ClassVar[str] = "retenciones_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.RETENCIONES_AGGREGATION,)

    def __init__(self, *, retencion_repository: RetencionObservationRepository | None = None) -> None:
        self._retencion_repository = retencion_repository

    @staticmethod
    def aggregate(
        modelo: str,
        observations: tuple[RetencionObservation, ...],
        *,
        period: Period,
    ) -> RetencionesAggregation:
        """Aggregate per-perceptor retención observations for ``modelo``.

        The ONE canonical retenciones aggregation entry point. Both this
        resolver's live calculate path (:meth:`resolve`) and the per-modelo
        aggregation service (:func:`~._service.aggregate_per_modelo`, the CLI
        ``aggregate`` / pull surface) route through this single method over the
        shared :data:`_RETENCIONES_AGGREGATORS` dispatch, so the calculate and
        pull surfaces produce byte-identical aggregation and cannot drift
        (``aeat-calculation-aggregation``). Raises ``KeyError``
        for a non-retenciones modelo, matching the prior service dispatch.
        """
        return _RETENCIONES_AGGREGATORS[modelo](tuple(observations), period=period)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "retenciones_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        if str(context.modelo) not in _RETENCIONES_AGGREGATORS:
            # Defensive: a revision declares the source for a modelo with no
            # retenciones aggregator. Resolve empty rather than guess values.
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        repository = self._retencion_repository or RetencionObservationRepository()
        try:
            observations = repository.load_observations(str(context.modelo), context.period)
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if not observations:
            # Modelo 111 is the one retenciones modelo with a prescribed remedy:
            # a quarter with no retenciones is ATTESTED, never filed blank. Name
            # that path, following the Modelo 180 precedent of carrying the flag
            # in the message. The typed action channel cannot express it -- the
            # wizard setup command projects no inputs to bind against.
            is_m111 = str(context.modelo) == Modelo.M111.value
            message = t(
                "aggregation.retenciones.errors.m111_no_retenciones_attestation_missing"
                if is_m111
                else "aggregation.retenciones.errors.perceptor_observations_missing",
            )
            # ``Translatable`` carries only the key; the renderer interpolates
            # from this context, so the attestation period travels there.
            refusal_context: dict[str, object] = {
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "retenciones_aggregation",
            }
            if is_m111:
                refusal_context["attestation_period"] = f"{context.filing_year}:{context.period.registry_token}"
            raise AggregationValidationError(
                message,
                context=refusal_context,
                precondition_verdict=aggregation_no_recovery_verdict(
                    AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT,
                    facts={
                        "modelo": str(context.modelo),
                        "filing_year": str(context.filing_year),
                        "period": context.period.registry_token,
                        "source_kind": "retenciones_aggregation",
                    },
                ),
            )
        aggregation = self.aggregate(str(context.modelo), tuple(observations), period=context.period)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
            diagnostics=administrador_retencion_rate_advisory_observations(observations),
            provenance=_provenance_for(
                aggregation.rollups,
                lambda rollup: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.RETENCIONES_AGGREGATION,
                    contributor_source_kind="retenciones_aggregation",
                    contributor_binding_source=BindingSourceKind.RETENCIONES_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"perceptor:{rollup.perceptor_nif}",
                    parent_source_ref=None,
                ),
            ),
        )
