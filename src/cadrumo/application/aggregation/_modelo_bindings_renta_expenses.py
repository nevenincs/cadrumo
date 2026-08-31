"""Modelo 100 estimación-directa expense source resolver.

This module owns the repository-backed Renta expense projection and the
provenance it emits.  The remaining modelo-binding resolvers stay in
:mod:`._modelo_bindings`; shared source-mesh helpers remain there until their
own owning concern moves.
"""

from __future__ import annotations

from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
)
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.prorrata_register._protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta._ledger_expenses import RentaDeductibleExpenseObservation
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios
from ._modelo_bindings import (
    _sorted_ids,
    aggregation_period_for_modelo,
)
from ._modelo_bindings_support import (
    _STORAGE_DEGRADATION_ERRORS,
    _empty_source_resolution,
    _revision_has_binding_source,
)
from ._renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    flatten_source_provenance_for as _flattened_provenance_for,
)
from .source_resolution_operations import (
    source_issue_diagnostics,
    storage_degradation_resolution,
)


class LedgerRentaGastosEstimacionDirectaAggregationSourceResolver:
    """Resolve ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~._renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~._source_mesh.CalculationSourceResolution`.
    """

    resolver_id: ClassVar[str] = "ledger_renta_gastos_estimacion_directa_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
    )

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository
        self._prorrata_register_repository = prorrata_register_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_gastos_estimacion_directa_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            aggregation = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(
                    filing_year=context.filing_year,
                    code=context.period.registry_token,
                ),
                transaction_repository=self._transaction_repository,
                invoice_repository=self._invoice_repository,
                profile_year=context.filing_year,
                usage_ratios=resolve_effective_usage_ratios(
                    bucket_id=context.bucket_id,
                    year=context.filing_year,
                ),
                modelo=context.modelo,
                prorrata_register_repository=self._prorrata_register_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        unrouted = unsupported_ledger_renta_gastos_estimacion_directa_observations(
            context.revision, aggregation.observations
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=_sorted_ids(
                aggregation.observations, lambda observation: observation.transaction_id
            ),
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
            ),
        )
    return tuple(provenance)
