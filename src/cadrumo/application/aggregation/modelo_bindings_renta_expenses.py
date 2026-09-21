"""Modelo 100 estimación-directa expense source resolver.

This module owns the repository-backed Renta expense projection and the
provenance it emits.  The remaining modelo-binding resolvers stay in
:mod:`.modelo_bindings`; shared source-mesh helpers remain there until their
own owning concern moves.
"""

from __future__ import annotations

from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import RentaDeductibleExpenseObservation
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError, InvoiceCatalogueReadPorts
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios
from ._modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .modelo_bindings import aggregation_period_for_modelo
from .modelo_bindings_actividad_assets import (
    CompetingDepreciationTreatment,
    activity_asset_expense_observations,
    refuse_competing_depreciation_treatments,
)
from .renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    flatten_source_provenance_for as _flattened_provenance_for,
)
from .source_resolution_operations import sorted_source_ids as sorted_ids
from .source_resolution_operations import (
    source_issue_diagnostics,
    storage_degradation_resolution,
)


class LedgerRentaGastosEstimacionDirectaAggregationSourceResolver:
    """Resolve ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~.renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~.source_mesh.CalculationSourceResolution`.
    """

    resolver_id: ClassVar[str] = "ledger_renta_gastos_estimacion_directa_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
    )

    def __init__(
        self,
        *,
        ports: InvoiceCatalogueReadPorts,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        usage_ratio_profile_loader: UsageRatioProfileLoader,
        activity_asset_history_repository: ActivityAssetHistoryRepository,
    ) -> None:
        """Initialize the resolver with its required catalogue read capabilities."""
        self._ports = ports
        self._prorrata_register_repository = prorrata_register_repository
        self._usage_ratio_profile_loader = usage_ratio_profile_loader
        self._activity_asset_history_repository = activity_asset_history_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the ledger Renta gastos estimación directa aggregation binding for ``context``.

        Returns:
            An empty resolution when the revision declares no such binding
            source, a degraded resolution on repository failure, or the
            aggregated :class:`~.source_mesh.CalculationSourceResolution`
            with its binding values, diagnostics, and provenance.
        """
        if not revision_has_binding_source(context.revision, "ledger_renta_gastos_estimacion_directa_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            profile = context.profile
            with bundled_indexed_authority().operation() as operation:
                usage_ratios = resolve_effective_usage_ratios(
                    bucket_id=context.bucket_id,
                    year=context.filing_year,
                    usage_ratio_profile_loader=self._usage_ratio_profile_loader,
                    operation=operation,
                    profile_record=profile.record if profile is not None else None,
                )
            aggregation = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(
                    filing_year=context.filing_year,
                    code=context.period.registry_token,
                ),
                ports=self._ports,
                profile_year=context.filing_year,
                usage_ratios=usage_ratios,
                modelo=context.modelo,
                profile_record=profile.record if profile is not None else None,
                prorrata_register_repository=self._prorrata_register_repository,
                profile_decode_context=profile.profile_decode_context if profile is not None else None,
            )
        except (InvoiceCatalogueReadPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        asset_history = self._activity_asset_history_repository.load()
        refuse_competing_depreciation_treatments(
            asset_history.revisions,
            asset_history.claims,
            tuple(
                CompetingDepreciationTreatment(
                    asset_id=asset.asset_id,
                    transaction_id=observation.transaction_id,
                    category=str(observation.category),
                    tax_year=observation.tax_year,
                )
                for observation in aggregation.observations
                for asset in asset_history.revisions
                if observation.transaction_id == asset.acquisition.observed_transaction_id
                and str(observation.target_casilla_id) in {"0208", "0227"}
            ),
        )
        asset_observations = activity_asset_expense_observations(
            asset_history.claims,
            modelo="100",
            period=aggregation.period,
        )
        all_observations = (*aggregation.observations, *asset_observations)
        unrouted = unsupported_ledger_renta_gastos_estimacion_directa_observations(
            context.revision, all_observations
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                context.revision,
                all_observations,
            ),
            source_transaction_ids=sorted_ids(aggregation.observations, lambda observation: observation.transaction_id),
            diagnostics=source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta gastos observation "
                        f"(modelo={str(observation.modelo)!r}, period={observation.period!r}, "
                        f"target_casilla_id={observation.target_casilla_id!r}, "
                        f"deductible_amount={observation.deductible_amount}) is not consumed by any "
                        f"ledger_renta_gastos_estimacion_directa_aggregation binding "
                        f"on revision {context.revision.id!r}; "
                        "its deductible amount is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=_flattened_provenance_for(
                aggregation.observations,
                _renta_observation_provenance,
            )
            + tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                    contributor_source_kind="activity_asset_claim",
                    contributor_binding_source=None,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"activity-asset-claim:{observation.claim_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                )
                for observation in asset_observations
            ),
        )


def _renta_observation_provenance(
    observation: RentaDeductibleExpenseObservation,
) -> tuple[CalculationSourceProvenance, ...]:
    provenance = [
        CalculationSourceProvenance(
            resolver_id=LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            contributor_source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
            contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"transaction:{observation.transaction_id}",
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        ),
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                resolver_id=LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                contributor_source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
                parent_source_ref=None,
                terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
            ),
        )
    return tuple(provenance)


__all__ = ["LedgerRentaGastosEstimacionDirectaAggregationSourceResolver"]
