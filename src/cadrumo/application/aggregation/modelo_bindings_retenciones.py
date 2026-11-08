"""Per-perceptor retenciones source resolver for modelo calculation bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.i18n.translatable import Translatable as tr
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.retenciones_bindings import (
    resolve_retenciones_aggregation_binding_row_values,
    resolve_retenciones_aggregation_binding_values,
)
from ..calculations.m115_no_relevant_payments import is_m115_no_relevant_payment_period
from .errors import RetencionesWindowEmptyError
from .modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from .retencion_observations_repository import (
    RetencionObservationPersistenceError,
    RetencionObservationPorts,
)
from .retencion_rate_advisory import (
    administrador_retencion_rate_advisory_observations,
)
from .retenciones import (
    RetencionesAggregation,
    RetencionObservation,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    source_context_operation,
    source_provenance_for,
    storage_degradation_resolution,
)
from .withholding_modelo_routing import annual_source_observations_modelo

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision

_RETENCIONES_AGGREGATORS = {
    Modelo("111").value: aggregate_retenciones_111,
    Modelo("115").value: aggregate_retenciones_115,
    Modelo("123").value: aggregate_retenciones_123,
    Modelo("180").value: aggregate_retenciones_180,
    Modelo("190").value: aggregate_retenciones_190,
    Modelo("193").value: aggregate_retenciones_193,
}


class RetencionesAggregationSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor retención store.

    Reads the bucket-scoped per-perceptor retención observations
    (:class:`~.retencion_observations_repository.RetencionObservationRepository`)
    for the modelo's period and materialises the declared retenciones aggregation
    bindings through the matching validated aggregator. Modelo 115 consumes the
    quarterly URBAN_RENTAL count/base; annual summary modelos consume the same
    family store for their distinct-NIF count. Modelo 190's percepciones count is
    handled by :class:`~.withholding_source.WithholdingSourceResolver`.
    """

    resolver_id: ClassVar[str] = "retenciones_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.RETENCIONES_AGGREGATION,)

    def __init__(
        self,
        *,
        ports: RetencionObservationPorts,
        m115_no_relevant_payment_periods: frozenset[tuple[int, str]] = frozenset(),
    ) -> None:
        """Use the required retención-observation capability bundle."""
        self._ports = ports
        self._m115_no_relevant_payment_periods = m115_no_relevant_payment_periods

    @staticmethod
    def aggregate(
        modelo: str,
        observations: tuple[RetencionObservation, ...],
        *,
        period: Period,
        operation: PinnedAuthorityOperation,
    ) -> RetencionesAggregation:
        """Aggregate per-perceptor retención observations for ``modelo``.

        The ONE canonical retenciones aggregation entry point. Both this
        resolver's live calculate path (:meth:`resolve`) and the per-modelo
        aggregation service (:func:`~.service.aggregate_per_modelo`, the CLI
        ``aggregate`` / pull surface) route through this single method over the
        shared :data:`_RETENCIONES_AGGREGATORS` dispatch, so the calculate and
        pull surfaces produce byte-identical aggregation and cannot drift
        (``aeat-calculation-aggregation``). Raises ``KeyError``
        for a non-retenciones modelo, matching the prior service dispatch.
        """
        return _RETENCIONES_AGGREGATORS[modelo](tuple(observations), period=period, operation=operation)

    @staticmethod
    def supports_modelo(modelo: str) -> bool:
        """Return whether this canonical retenciones dispatcher owns ``modelo``."""
        return modelo in _RETENCIONES_AGGREGATORS

    def load_calculation_observations(
        self,
        *,
        modelo: str,
        period: Period,
        revision: ModeloRevision,
    ) -> tuple[RetencionObservation, ...] | None:
        """Return the stored retención rows the calculation reads for ``modelo`` in ``period``.

        ``None`` when ``revision`` declares no ``retenciones_aggregation``
        binding, or declares one for a modelo with no retenciones aggregator:
        the calculation then reads nothing from this store, which is a different
        fact from reading an empty window. Modelo 180 reads the year's active
        Modelo 115 windows; every other modelo reads its own window.

        :meth:`resolve` and the per-modelo aggregate report both read through
        here, so the report summarises exactly the rows the calculation
        materialises rather than a window of its own choosing.

        Parameter types: ``revision`` (:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`).
        """
        if (
            not revision_has_binding_source(revision, "retenciones_aggregation")
            or modelo not in _RETENCIONES_AGGREGATORS
        ):
            return None
        if (source_modelo := annual_source_observations_modelo(modelo)) is not None:
            return self._ports.repository.load_annual_source_observations(source_modelo, period.filing_year)
        return self._ports.repository.load_observations(modelo, period)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the retenciones binding values for the declared modelo context."""
        try:
            observations = self.load_calculation_observations(
                modelo=context.modelo,
                period=context.period,
                revision=context.revision,
            )
        except (RetencionObservationPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if observations is None:
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        if not observations:
            is_m115 = context.modelo == form_for_role("withholding.lease_periodic")
            is_m115_no_relevant_payment = is_m115 and is_m115_no_relevant_payment_period(
                filing_year=context.filing_year,
                period_token=context.period.registry_token,
                attested_periods=self._m115_no_relevant_payment_periods,
            )
            if is_m115_no_relevant_payment:
                with source_context_operation(context) as operation:
                    aggregation = self.aggregate(context.modelo, (), period=context.period, operation=operation)
                return CalculationSourceResolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
                    row_binding_values=resolve_retenciones_aggregation_binding_row_values(
                        context.revision, aggregation
                    ),
                    diagnostics=(
                        CalculationSourceDiagnostic(
                            reason="source_issue",
                            source_kind="retenciones_aggregation",
                            resolver_id=self.resolver_id,
                            message=(
                                f"Modelo 115 {context.filing_year} {context.period.registry_token} has an explicit "
                                "no-relevant-payment attestation; its retention values are materialised as zero. "
                                "This is local preparation evidence, not AEAT submission evidence."
                            ),
                        ),
                    ),
                )
            raise _empty_window_refusal(context)
        with source_context_operation(context) as operation:
            aggregation = self.aggregate(
                context.modelo,
                tuple(observations),
                period=context.period,
                operation=operation,
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
            row_binding_values=resolve_retenciones_aggregation_binding_row_values(context.revision, aggregation),
            diagnostics=administrador_retencion_rate_advisory_observations(
                observations, effective_date=context.period.end_date
            ),
            provenance=source_provenance_for(
                aggregation.rollups,
                lambda rollup: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.RETENCIONES_AGGREGATION,
                    contributor_source_kind="retenciones_aggregation",
                    contributor_binding_source=BindingSourceKind.RETENCIONES_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"perceptor:{rollup.perceptor_nif}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.PERCEPTOR_OBSERVATION,
                ),
            ),
        )


def _empty_window_refusal(context: CalculationSourceContext) -> RetencionesWindowEmptyError:
    """Refuse a withholding period that holds no retención, offering the profile detail that records none.

    Modelo 111 and Modelo 115 each have a profile detail saying the period paid
    nothing subject to retención; a period recorded there is never filed blank,
    so it is the door. Any other withholding modelo has no such detail, and its
    words say only what is missing.
    """
    from ..calculations.m111_no_retenciones import M111_NO_RETENCIONES_PROFILE_PATH
    from ..calculations.m115_no_relevant_payments import M115_NO_RELEVANT_PAYMENT_PROFILE_PATH
    from ..modelo.profile_readiness_gate import open_profile_path_step
    from ..modelo.work_form_wording import period_words
    from ..operations.error_detail import served_words_language

    if context.modelo == form_for_role("withholding.work_periodic"):
        message = tr("application.aggregation.retenciones.window_empty_work")
        profile_path: str | None = M111_NO_RETENCIONES_PROFILE_PATH
    elif context.modelo == form_for_role("withholding.lease_periodic"):
        message = tr("application.aggregation.retenciones.window_empty_lease")
        profile_path = M115_NO_RELEVANT_PAYMENT_PROFILE_PATH
    else:
        message = tr("application.aggregation.retenciones.window_empty")
        profile_path = None
    return RetencionesWindowEmptyError(
        message,
        context={"modelo": str(context.modelo), "period": period_words(context.period, served_words_language())},
        precondition_verdict=aggregation_no_recovery_verdict(
            AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT,
            facts={
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "retenciones_aggregation",
            },
        ),
        next_step=None if profile_path is None else open_profile_path_step(profile_path),
    )
