"""Repository-backed source-mesh resolvers for modelo registry bindings.

This module is the calculation-facing bridge from bucket-local stores to
:class:`~.source_mesh.CalculationSourceResolution`. Each resolver owns one
:class:`~core.aggregation.BindingSourceKind`, reads the active
:class:`~.source_mesh.CalculationSourceContext`, and materialises binding
values declared on the snapshot's
:class:`~domain.calculations.registry.schema.ModeloRevision`.

The IVA, Renta income, Renta expense, and M130 gasto resolvers delegate their
ledger projection to :mod:`~.iva_ledger`, :mod:`~.renta_income_ledger`,
:mod:`~.renta_ledger`, and :mod:`~.renta_gasto_ledger`. The retenciones
resolver reads the dedicated per-perceptor store through
:mod:`~.retencion_observations_repository`. The separate
:mod:`~.oss_ioss` and :mod:`~.withholding_source` modules follow the same
source-mesh contract for Modelo 369 and Modelo 190 detail counts.

Invoice-backed checks use
:class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository` only as supporting
evidence: Modelo 303 domestic IVA remains ledger-owned, while Renta expense
aggregation can attach purchase-invoice evidence to transaction rows before
producing the shared :class:`~.source_mesh.CalculationSourceResolution`.

Declarable observations that no registry binding consumes are reported as
source diagnostics rather than silently blanking the filed calculation;
:class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, BindingValueOutcome, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.i18n.translatable import Translatable as tr
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.period import Period, PeriodError, StandardPeriodCode
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.binding_temporal import NonCalculation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.irnr_ledger_bindings import (
    LedgerIrnrIncomeProvider,
    resolve_ledger_irnr_income_aggregation_binding_values,
    unsupported_ledger_irnr_income_observations,
)
from ...domain.calculations.registry.ledger_renta_income_bindings import (
    LedgerRentaIncomeProvider,
    RentaIncomeObservationProtocol,
    UngroundedRentaIncome,
    WithholdingDerivationPartition,
    declared_withholding_binding_ids,
    ledger_renta_withholding_derivation_partition,
    ledger_renta_withholding_value_outcomes,
    renta_income_target_casilla,
    resolve_ledger_renta_income_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_renta_income_observations,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.iva.schema import InvoiceKind
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow
from ...domain.renta.retencion_soportada_applicability import (
    RetencionSoportadaApplicability,
    arrendamiento_actividad_applicability,
)
from ...domain.renta.retenciones_routing_integrity import resolve_m130_retenciones_route
from ...domain.transactions.irpf_categories import has_activity_irpf_category, has_employment_irpf_category
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import (
    agrarian_instalment_activity_codes,
    tipo_actividad_code_set,
)
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..invoices.catalogue_reads_ports import (
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from .errors import AggregationValidationError
from .irnr_income_ledger import IrnrIncomeObservation, aggregate_irnr_income_ledger_from_repositories
from .modelo_bindings_actividad_assets import (
    ActivityAssetDisposalExcess,
    activity_asset_disposal_excess,
    activity_asset_disposal_excess_m131_findings,
)
from .modelo_bindings_invoice_iva import (
    out_of_window_summary_diagnostics,
)
from .modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationFilingHistory,
    ImputationUnresolved,
    accruing_invoices,
    declared_imputation_criteria,
    imputation_blocking_diagnostics,
    ledger_sum_outcome,
)
from .renta_income_diagnostics import (
    accrued_withholding_unpaid_diagnostics,
    fitted_diagnostic_id_list,
    paid_after_cut_off_diagnostics,
    part_payment_diagnostics,
    rectification_diagnostics,
    rectificativa_netting_diagnostics,
    rental_activity_component_diagnostics,
    unusable_sales_invoice_diagnostics,
)
from .renta_income_ledger import (
    RentaIncomeLedgerAggregation,
    RentalActivityScreen,
    aggregate_renta_income_ledger_from_repositories,
    aggregate_renta_m100_income_ledger_from_repositories,
    aggregate_renta_m131_agrario_income_ledger_from_repositories,
    instalment_basis_observations,
    payment_dated_renta_m100_income_observations,
)
from .renta_income_models import RentaIncomeLedgerAggregationIssue, RentaIncomeLedgerAggregationIssueReason
from .retencion_rate_advisory import (
    inferred_actividad_retencion_rate_advisory_observations,
)
from .retencion_soportada_source import declared_activity_epigraphs
from .source_mesh import (
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import sorted_source_ids as sorted_ids
from .source_resolution_operations import (
    source_context_operation,
    source_issue_diagnostics,
    source_provenance_for,
    storage_degradation_resolution,
    unresolved_binding_diagnostics,
)
from .undeclared_activity_advisory import undeclared_activity_income_advisory_observations

_M131_AGRARIAN_ACTIVITY_SELECTOR = "modelo-131:selector-m036-volumen-ingresos-agrario"
_M100_RENTAL_ACTIVITY_SELECTOR = "modelo-100:selector-m036-arrendadores-inmuebles"


def _agrarian_quarter_target_casilla(context: CalculationSourceContext) -> CasillaId | None:
    """Return the box a revision declares for its agrarian activities' quarter, when it splits them out."""
    return next(
        (
            binding.provider.target_casilla_id
            for binding in context.revision.bindings
            if isinstance(binding.provider, LedgerRentaIncomeProvider) and binding.provider.agrarian_quarter
        ),
        None,
    )


def _irnr_handoff_bound_inputs(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Hand each ledger IRNR handoff binding's resolved value to the casilla its provider targets.

    The casilla is a manual box the filer types outside ledger mode, so no casilla
    binds it; the binding declares itself an application handoff and this resolver,
    reached only in ledger mode, writes its value there.
    """
    inputs: dict[CasillaId, Decimal] = {}
    for binding in revision.bindings:
        if not isinstance(binding.provider, LedgerIrnrIncomeProvider):
            continue
        if not isinstance(binding.applicability, NonCalculation):
            continue
        value = binding_values.get(binding.id)
        if value is None:
            continue
        target = binding.provider.target_casilla_id
        inputs[target] = inputs.get(target, Decimal("0")) + value
    return inputs


def _irnr_income_target_casilla(context: CalculationSourceContext) -> CasillaId:
    providers = tuple(
        binding.provider
        for binding in context.revision.bindings
        if isinstance(binding.provider, LedgerIrnrIncomeProvider) and str(binding.provider.modelo) == context.modelo
    )
    targets = {provider.target_casilla_id for provider in providers}
    if len(targets) != 1:
        raise RegistryError(
            "selected revision must declare exactly one IRNR income aggregation target",
            context={"modelo": context.modelo, "target_count": len(targets)},
        )
    return next(iter(targets))


def modelo_bindings_activity_category_matcher(operation: PinnedAuthorityOperation) -> Callable[[Transaction], bool]:
    """Build a predicate matching transactions with an activity IRPF category."""

    def matcher(transaction: Transaction) -> bool:
        return has_activity_irpf_category(
            transaction.irpf_category,
            direction=transaction.direction,
            authority=operation,
        )

    return matcher


def modelo_bindings_employment_category_matcher(operation: PinnedAuthorityOperation) -> Callable[[Transaction], bool]:
    """Build a predicate matching transactions with an employment IRPF category."""

    def matcher(transaction: Transaction) -> bool:
        return has_employment_irpf_category(
            transaction.irpf_category,
            direction=transaction.direction,
            authority=operation,
        )

    return matcher


def _rental_activity_screen(
    context: CalculationSourceContext, period: Period, operation: PinnedAuthorityOperation
) -> RentalActivityScreen:
    """Read which tipos de actividad are rentals, and whether the profile declares one for the ejercicio."""
    return RentalActivityScreen(
        codes=tipo_actividad_code_set(
            _M100_RENTAL_ACTIVITY_SELECTOR, effective_date=period.end_date, authority=operation
        ),
        declared=arrendamiento_actividad_applicability(
            declared_activity_epigraphs(context), effective_date=period.end_date, authority=operation
        )
        is RetencionSoportadaApplicability.DECLARED,
    )


def _rental_tag_missing_diagnostics(
    context: CalculationSourceContext, aggregation: RentaIncomeLedgerAggregation, *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Withhold the activity credit while a rental year holds withholding-bearing rows with no tipo de actividad."""
    untagged = aggregation.rental_tag_missing
    if not untagged:
        return ()
    return unresolved_binding_diagnostics(
        revision=context.revision,
        source_kind="ledger_renta_income_aggregation",
        binding_ids=tuple(sorted(declared_withholding_binding_ids(context.revision))),
        resolver_id=resolver_id,
        message=(
            f"ejercicio {context.filing_year} includes a rental activity, and {len(untagged)} receipt(s) bearing "
            "a retencion record no tipo de actividad, so whether their withholding is the activity's or the "
            "rental's is unknown; set tipo_actividad on each (A01 for the rental): "
            + fitted_diagnostic_id_list(sorted(untagged), budget=DIAGNOSTIC_MESSAGE_MAX_LENGTH // 2)
        )[:DIAGNOSTIC_MESSAGE_MAX_LENGTH],
    )


class LedgerRentaIncomeAggregationSourceResolver:
    """Resolve ``ledger_renta_income_aggregation`` actividad-income bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION`. Modelo 130
    uses the cumulative-quarter income path, while Modelo 100 uses the annual
    activity-income path over the same ledger eligibility rules.
    """

    resolver_id: ClassVar[str] = "ledger_renta_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,)

    def __init__(
        self,
        *,
        ports: InvoiceCatalogueReadPorts,
        activity_asset_history_repository: ActivityAssetHistoryRepository,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        imputation_filings: Callable[[CalculationSourceContext], ImputationFilingHistory] | None = None,
    ) -> None:
        """Bind the catalogue ports and the register, whose bajas can add income to Modelos 130 and 131."""
        self._ports = ports
        self._imputation_filings = imputation_filings
        self._activity_asset_history_repository = activity_asset_history_repository
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve Renta activity-income observations for one context."""
        if not revision_has_binding_source(context.revision, "ledger_renta_income_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        # One source kind, three windows and three targets. Modelo 100 (annual
        # IRPF) folds actividad income over the full ejercicio into casilla 0171;
        # Modelo 130 uses the cumulative-quarter path into casilla 01; Modelo 131
        # takes the quarter alone into casilla 05 and, unlike the other two,
        # narrows the rows first -- to the art. 110.1.c activity set, and away from
        # the subvenciones de capital and indemnizaciones that article excludes.
        target_casilla_id = renta_income_target_casilla(context.revision, modelo=context.modelo)
        criteria = declared_imputation_criteria(
            context.profile.record if context.profile is not None else None,
            self._imputation_filings(context) if self._imputation_filings is not None else None,
        )
        payment_year_values: dict[BindingId, Decimal] = {}
        instalment_basis_values: dict[BindingId, Decimal] = {}
        with source_context_operation(context) as operation:
            profile_decode_context = operation.profile_decode_context()
            activity_category_matcher = modelo_bindings_activity_category_matcher(operation)
            employment_category_matcher = modelo_bindings_employment_category_matcher(operation)
            try:
                if context.modelo == form_for_role("renta.annual"):
                    rental = _rental_activity_screen(context, aggregation_period, operation)
                    aggregation = self._aggregate_annual(
                        context,
                        aggregation_period,
                        target_casilla_id,
                        criteria,
                        rental=rental,
                        activity_category_matcher=activity_category_matcher,
                        employment_category_matcher=employment_category_matcher,
                    )
                    payment_year_values = self._payment_year_withholding(
                        context,
                        aggregation_period,
                        criteria,
                        rental=rental,
                        target_casilla_id=target_casilla_id,
                        activity_category_matcher=activity_category_matcher,
                        employment_category_matcher=employment_category_matcher,
                    )
                    instalment_basis_values = self._instalment_basis_withholding(context, aggregation)
                elif context.modelo == form_for_role("renta.objective_instalment"):
                    aggregation = self._aggregate_objective_instalment(
                        context,
                        aggregation_period,
                        target_casilla_id,
                        operation=operation,
                        activity_category_matcher=activity_category_matcher,
                        employment_category_matcher=employment_category_matcher,
                    )
                else:
                    aggregation = self._aggregate_quarter(
                        context,
                        aggregation_period,
                        target_casilla_id,
                        criteria,
                        operation=operation,
                        activity_category_matcher=activity_category_matcher,
                        employment_category_matcher=employment_category_matcher,
                    )
                disposal_excess = (
                    ()
                    if context.modelo == form_for_role("renta.annual")
                    else activity_asset_disposal_excess(
                        self._activity_asset_history_repository.load(),
                        context=context,
                        period=aggregation_period,
                        transactions=self._transaction_repository,
                        operation=operation,
                    )
                )
            except (InvoiceCatalogueReadPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
                return storage_degradation_resolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    source_kinds=self.owned_sources,
                    error=exc,
                )
        return self._assemble_resolution(
            context, aggregation, profile_decode_context, disposal_excess, criteria
        ).model_copy(
            update={
                "payment_year_binding_values": payment_year_values,
                "instalment_basis_binding_values": instalment_basis_values,
            }
        )

    def _aggregate_annual(
        self,
        context: CalculationSourceContext,
        period: Period,
        target_casilla_id: CasillaId,
        criteria: ImputationCriteria,
        *,
        rental: RentalActivityScreen,
        activity_category_matcher: Callable[[Transaction], bool],
        employment_category_matcher: Callable[[Transaction], bool],
    ) -> RentaIncomeLedgerAggregation:
        """Aggregate the Modelo 100 activity income over the full ejercicio."""
        return aggregate_renta_m100_income_ledger_from_repositories(
            bucket_id=context.bucket_id,
            period=period,
            modelo=context.modelo,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            ports=self._ports,
            criteria=criteria,
            rental=rental,
        )

    def _aggregate_objective_instalment(
        self,
        context: CalculationSourceContext,
        period: Period,
        target_casilla_id: CasillaId,
        *,
        operation: PinnedAuthorityOperation,
        activity_category_matcher: Callable[[Transaction], bool],
        employment_category_matcher: Callable[[Transaction], bool],
    ) -> RentaIncomeLedgerAggregation:
        """Aggregate the Modelo 131 quarter, narrowed to the agrarian activity set."""
        agrarian_activity_codes = frozenset(
            TipoActividad(code)
            for code in tipo_actividad_code_set(
                _M131_AGRARIAN_ACTIVITY_SELECTOR,
                effective_date=period.end_date,
                authority=operation,
            )
        )
        return aggregate_renta_m131_agrario_income_ledger_from_repositories(
            bucket_id=context.bucket_id,
            period=period,
            modelo=context.modelo,
            target_casilla_id=target_casilla_id,
            agrarian_activity_codes=agrarian_activity_codes,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            ports=self._ports,
            operation=operation,
        )

    def _aggregate_quarter(
        self,
        context: CalculationSourceContext,
        period: Period,
        target_casilla_id: CasillaId,
        criteria: ImputationCriteria,
        *,
        operation: PinnedAuthorityOperation,
        activity_category_matcher: Callable[[Transaction], bool],
        employment_category_matcher: Callable[[Transaction], bool],
    ) -> RentaIncomeLedgerAggregation:
        """Aggregate the cumulative-quarter income, adding the agrarian rows its own box takes."""
        agrarian_target = _agrarian_quarter_target_casilla(context)
        agrarian_codes = frozenset[TipoActividad]()
        if agrarian_target is not None:
            agrarian_codes = agrarian_instalment_activity_codes(
                effective_date=period.end_date,
                authority=operation,
            )
        aggregation = aggregate_renta_income_ledger_from_repositories(
            bucket_id=context.bucket_id,
            period=period,
            modelo=context.modelo,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            ports=self._ports,
            criteria=criteria,
            excluded_activity_codes=agrarian_codes,
        )
        if agrarian_target is None:
            return aggregation
        agrarian = aggregate_renta_m131_agrario_income_ledger_from_repositories(
            bucket_id=context.bucket_id,
            period=period,
            modelo=context.modelo,
            target_casilla_id=agrarian_target,
            agrarian_activity_codes=agrarian_codes,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            ports=self._ports,
            operation=operation,
            criteria=criteria,
        )
        return aggregation.model_copy(
            update={
                "observations": (*aggregation.observations, *agrarian.observations),
                "issues": (*aggregation.issues, *agrarian.issues),
            }
        )

    def _instalment_basis_withholding(
        self, context: CalculationSourceContext, aggregation: RentaIncomeLedgerAggregation
    ) -> dict[BindingId, Decimal]:
        """State each declared retención binding as the year's last pago fraccionado would credit it."""
        withholding_ids = declared_withholding_binding_ids(context.revision)
        if not withholding_ids:
            return {}
        restated = instalment_basis_observations(
            aggregation.observations,
            self._ports.transaction_reader.load(),
            cut_off=context.period.end_date,
        )
        values = resolve_ledger_renta_income_aggregation_binding_values(context.revision, restated)
        return {binding_id: value for binding_id, value in values.items() if binding_id in withholding_ids}

    def _payment_year_withholding(
        self,
        context: CalculationSourceContext,
        period: Period,
        criteria: ImputationCriteria,
        *,
        rental: RentalActivityScreen,
        target_casilla_id: CasillaId,
        activity_category_matcher: Callable[[Transaction], bool],
        employment_category_matcher: Callable[[Transaction], bool],
    ) -> dict[BindingId, Decimal]:
        """State each declared retención binding's figure by payment year, when accrual can move a receipt."""
        withholding_ids = declared_withholding_binding_ids(context.revision)
        if not withholding_ids or criteria.usable(context.filing_year) is not ActivityImputationCriterion.DEVENGO:
            return {}
        paid = payment_dated_renta_m100_income_observations(
            bucket_id=context.bucket_id,
            period=period,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            ports=self._ports,
            rental=rental,
        )
        values = resolve_ledger_renta_income_aggregation_binding_values(context.revision, paid)
        return {binding_id: value for binding_id, value in values.items() if binding_id in withholding_ids}

    def _assemble_resolution(
        self,
        context: CalculationSourceContext,
        aggregation: RentaIncomeLedgerAggregation,
        profile_decode_context: ProfileDecodeContext,
        disposal_excess: tuple[ActivityAssetDisposalExcess, ...],
        criteria: ImputationCriteria,
    ) -> CalculationSourceResolution:
        declared_excess = _declared_disposal_excess(context, disposal_excess)
        binding_values = resolve_ledger_renta_income_aggregation_binding_values(
            context.revision,
            (
                *aggregation.observations,
                *declared_excess,
                *aggregation.accrued_unpaid,
                *aggregation.rectificativa_corrections,
            ),
        )
        unresolved_rows = tuple(
            issue
            for issue in aggregation.issues
            if issue.reason is RentaIncomeLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED
        )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # income whose target_casilla_id matches no ledger_renta_income_aggregation
        # binding would otherwise be silently dropped (no-silent-under-declaration).
        unrouted = unsupported_ledger_renta_income_observations(context.revision, aggregation.observations)
        # Second, distinct screen: rows a binding DOES consume but whose
        # contribution rests on bank cash because no invoice substrate was
        # recorded. The fallback is deliberately kept (dropping an untagged
        # income row under-declares by its whole value), so this is the only
        # thing standing between the operator and a silently mis-measured
        # income casilla.
        ungrounded = ungrounded_ledger_renta_income_observations(context.revision, aggregation.observations)
        # Third screen, on the axis the two above cannot see. Both of those key
        # on the ROW, and every observation is built with target_casilla_id="01"
        # whatever fact a binding reads off it -- so a row consumed for its
        # income reads as routed while a SECOND, independent quantity it carries
        # (the retención suffered) reaches no binding at all. Without this the
        # taxpayer's whole retención credit can disappear with both other
        # screens clean.
        unrouted_quantities = unrouted_ledger_renta_income_quantities(context.revision, aggregation.observations)
        # Fourth screen, reading the one axis the three above cannot: a row the
        # retención binding DOES consume, by a binding that deliberately leaves
        # its figure out. An excluded row and a row that suffered nothing both
        # contribute nothing, so the difference has to travel beside the value.
        derivation = ledger_renta_withholding_derivation_partition(context.revision, aggregation.observations)
        bound_inputs = _m130_retenciones_backend_inputs(context, binding_values)
        source_transaction_ids = sorted_ids(aggregation.observations, lambda observation: observation.transaction_id)
        diagnostics = (
            self._ledger_screening_diagnostics(context, aggregation, criteria)
            + self._imputation_diagnostics(context, aggregation, criteria, binding_values, unresolved_rows)
            + _unrouted_observation_diagnostics(context, unrouted, resolver_id=self.resolver_id)
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_declarable_quantity",
                    source_kind="ledger_renta_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"{len(quantity.observations)} income row(s) carry {quantity.total} EUR of "
                        f"{quantity.fact!r}, which no ledger_renta_income_aggregation binding on revision "
                        f"{context.revision.id!r} draws; that amount is not declared on this calculation. "
                        f"The rows themselves ARE consumed for their income, so no other screen reports them"
                    ),
                )
                for quantity in unrouted_quantities
            )
            + self._advisory_diagnostics(
                context,
                aggregation,
                profile_decode_context,
                disposal_excess,
                ungrounded=ungrounded,
                derivation=derivation,
            )
        )
        value_outcomes = _resolved_income_value_outcomes(
            context, aggregation, binding_values, invoices=self._ports.invoice_reader.load(), criteria=criteria
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=bound_inputs,
            source_transaction_ids=source_transaction_ids,
            diagnostics=diagnostics,
            value_outcomes=value_outcomes,
            provenance=self._income_provenance(declared_excess, aggregation),
        )

    def _ledger_screening_diagnostics(
        self,
        context: CalculationSourceContext,
        aggregation: RentaIncomeLedgerAggregation,
        criteria: ImputationCriteria,
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        """Report the window, issue, unpaid-withholding, part-payment and late-payment findings."""
        return (
            out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
                suppressed_reasons=frozenset({RentaIncomeLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED}),
            )
            + accrued_withholding_unpaid_diagnostics(aggregation.accrued_unpaid, resolver_id=self.resolver_id)
            + part_payment_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + paid_after_cut_off_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + rental_activity_component_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + _rental_tag_missing_diagnostics(context, aggregation, resolver_id=self.resolver_id)
            + rectificativa_netting_diagnostics(aggregation.rectificativa_corrections, resolver_id=self.resolver_id)
            + rectification_diagnostics(
                self._ports.transaction_reader.load(),
                self._ports.invoice_reader.load(),
                bucket_id=context.bucket_id,
                year=context.filing_year,
                criteria=criteria,
                resolver_id=self.resolver_id,
            )
        )

    def _imputation_diagnostics(
        self,
        context: CalculationSourceContext,
        aggregation: RentaIncomeLedgerAggregation,
        criteria: ImputationCriteria,
        binding_values: Mapping[BindingId, Decimal],
        unresolved_rows: tuple[RentaIncomeLedgerAggregationIssue, ...],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        """Report what blocks the imputation election, except for the objective-estimation modelo."""
        if context.modelo == form_for_role("renta.objective_instalment"):
            return ()
        return imputation_blocking_diagnostics(
            source_kind="ledger_renta_income_aggregation",
            resolver_id=self.resolver_id,
            revision=context.revision,
            binding_ids=binding_values,
            criteria=criteria,
            year=context.filing_year,
            activity_present=bool(
                aggregation.observations
                or unresolved_rows
                or accruing_invoices(
                    self._ports.invoice_reader.load().values(),
                    kind=InvoiceKind.ISSUED,
                    bucket_id=context.bucket_id,
                    start=date(context.filing_year, 1, 1),
                    end=context.period.end_date,
                    criteria=criteria,
                )
            ),
            unresolved_details=(
                *(issue.detail for issue in unresolved_rows),
                *(
                    f"{ImputationUnresolved.EUR_VALUE_UNKNOWN.value}: issued invoice {number} accrues with no "
                    "EUR value; stamp its rate"
                    for number in aggregation.accrued_without_eur_value
                ),
                *aggregation.rectificativa_refused,
            ),
        )

    def _advisory_diagnostics(
        self,
        context: CalculationSourceContext,
        aggregation: RentaIncomeLedgerAggregation,
        profile_decode_context: ProfileDecodeContext,
        disposal_excess: tuple[ActivityAssetDisposalExcess, ...],
        *,
        ungrounded: UngroundedRentaIncome,
        derivation: WithholdingDerivationPartition,
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        """Report the grounding, derivation, invoice, rate, silence and disposal advisories."""
        return (
            _ungrounded_income_diagnostics(ungrounded, resolver_id=self.resolver_id)
            + _withholding_derivation_diagnostics(derivation, resolver_id=self.resolver_id)
            + unusable_sales_invoice_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + inferred_actividad_retencion_rate_advisory_observations(
                aggregation.observations,
                bucket_id=context.bucket_id,
                profile_decode_context=profile_decode_context,
                resolver_id=self.resolver_id,
                profile=context.profile,
            )
            # Fourth screen, and the only one that can speak when there are NO
            # observations at all. Every screen above reasons about rows that
            # reached the aggregation; an activity-narrowed projection whose rows
            # were all excluded produces an empty set, so each of them is silent
            # by construction and their silence must not read as confirmation
            # that the casilla is legitimately zero.
            + undeclared_activity_income_advisory_observations(
                aggregation,
                context.revision,
                resolver_id=self.resolver_id,
            )
            + (
                activity_asset_disposal_excess_m131_findings(disposal_excess, resolver_id=self.resolver_id)
                if context.modelo == form_for_role("renta.objective_instalment")
                else ()
            )
        )

    def _income_provenance(
        self,
        declared_excess: tuple[ActivityAssetDisposalExcess, ...],
        aggregation: RentaIncomeLedgerAggregation,
    ) -> tuple[CalculationSourceProvenance, ...]:
        """Trace the disposal excess, the unpaid accrued invoices and each income row to their source."""
        return (
            _disposal_excess_provenance(declared_excess, resolver_id=self.resolver_id)
            + tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_renta_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=accrued.transaction_id,
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                )
                for accrued in (*aggregation.accrued_unpaid, *aggregation.rectificativa_corrections)
            )
            + source_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_renta_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                ),
            )
        )


def _unrouted_observation_diagnostics(
    context: CalculationSourceContext,
    unrouted: Sequence[RentaIncomeObservationProtocol],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name each income observation that no income binding consumes."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="unrouted_observation",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=(
                f"declarable renta income observation (target_casilla_id="
                f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                f"is not consumed by any ledger_renta_income_aggregation binding on revision "
                f"{context.revision.id!r}; its income is not declared on this calculation"
            ),
        )
        for observation in unrouted
    )


def _declared_disposal_excess(
    context: CalculationSourceContext,
    disposal_excess: tuple[ActivityAssetDisposalExcess, ...],
) -> tuple[ActivityAssetDisposalExcess, ...]:
    """Keep the disposal excess a direct-estimation calculation declares as income."""
    if context.modelo != form_for_role("renta.direct_instalment"):
        return ()
    return tuple(row for row in disposal_excess if not row.agrarian and row.error is None)


def _resolved_income_value_outcomes(
    context: CalculationSourceContext,
    aggregation: RentaIncomeLedgerAggregation,
    binding_values: Mapping[BindingId, Decimal],
    *,
    invoices: InvoiceCatalogue,
    criteria: ImputationCriteria,
) -> dict[BindingId, BindingValueOutcome]:
    """State what each resolved income-source value rests on, withholding and income alike.

    An issued invoice accruing in the window with its money banked outside it
    leaves no row here, so it counts against a zero as a row would; for a
    withholding binding only an invoice stating a retencion does.
    """
    with source_context_operation(context):
        accruing = accruing_invoices(
            invoices.values(),
            kind=InvoiceKind.ISSUED,
            bucket_id=context.bucket_id,
            start=date(aggregation.period.filing_year, 1, 1),
            end=aggregation.period.end_date,
            criteria=criteria,
        )
    withholding = ledger_renta_withholding_value_outcomes(context.revision, aggregation.observations)
    bearing_invoice = any(invoice.retention_amount for invoice in accruing)
    outcomes: dict[BindingId, BindingValueOutcome] = {}
    for binding_id, value in binding_values.items():
        stated = withholding.get(binding_id)
        if stated is None:
            outcomes[binding_id] = ledger_sum_outcome(
                value,
                rows_present=bool(aggregation.observations or aggregation.accrued_unpaid),
                accruing_invoice_present=bool(accruing),
            )
        else:
            outcomes[binding_id] = BindingValueOutcome.FROM_BEARING_ROWS if bearing_invoice else stated
    return outcomes


def _disposal_excess_provenance(
    declared_excess: tuple[ActivityAssetDisposalExcess, ...],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceProvenance, ...]:
    """Name the register disposals whose excess the income binding drew on."""
    return tuple(
        CalculationSourceProvenance(
            resolver_id=resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            contributor_source_kind="activity_asset_disposal_excess",
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=row.source_ref,
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        )
        for row in declared_excess
    )


def _ungrounded_income_consequence(facts: frozenset[str]) -> str:
    """Describe what a missing base does to the income casilla, per declared fact.

    The two base-reading facts fail in opposite directions, so naming the
    consequence precisely is what makes the advisory actionable: an operator
    who reads "contributed nothing" knows the return is under-declared, while
    "bank cash stood in for the base" warns the figure may be wrong either way.

    Kept short deliberately: this text shares its 512-character diagnostic
    budget with the dropped-retención-credit clause added in
    :func:`_ungrounded_income_diagnostics`, so headroom here is headroom for
    the transaction-id sample, not free prose.
    """
    folds_cash = "ingresos_integros_sum" in facts
    contributes_zero = "taxable_base_sum" in facts
    if folds_cash and contributes_zero:
        return "bank cash filled the ingresos_integros_sum binding while taxable_base_sum got nothing"
    if contributes_zero:
        return "these rows contributed nothing to taxable_base_sum, under-declaring by their full base"
    return "bank cash stood in for the base imponible, which is not the ingresos íntegros this casilla declares"


INFERRED_RETENCION_EXCLUDED_SOURCE_KIND = "inferred_actividad_retencion_excluded"
"""Source kind for the retención rows a declared-only credit leaves out."""

UNRESOLVED_RETENCION_SOURCE_KIND = "unresolved_actividad_retencion"
"""Source kind for the retención rows whose figure is unknown rather than zero."""


def _withholding_derivation_diagnostics(
    derivation: WithholdingDerivationPartition,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report what the declared-only retención credit left out.

    Two findings, each about a distinct state the resolved value cannot carry.

    An INFERRED row holds a figure reconstructed from invoice gross minus cash
    received. It is excluded on purpose, and it is also recoverable: the operator
    records the retención on the invoice and the figure becomes a declared one.
    So the count and the amount are both reported, because the amount is what
    the taxpayer is currently not claiming.

    An UNRESOLVED row has no determinable figure at all: no substrate to derive
    one from, or an inference the registry's maximum supported rate refused.
    Reporting it as zero would assert a proven nothing-withheld, which is exactly
    the collapse ``no-silent-under-declaration`` forbids.

    How far the credit itself reaches is not this resolver's statement: a
    binding that reads it declares its own grade cap, and the canonical
    resolution step reports a capped value for every resolver together.

    Returns an empty tuple when the revision declares no declared-only retención
    binding and the rows carried nothing, which is how a revision without the
    credit stays silent.
    """
    findings: list[CalculationSourceDiagnostic] = []
    if derivation.inferred_observations:
        sampled = sorted(observation.transaction_id for observation in derivation.inferred_observations)
        findings.append(
            CalculationSourceDiagnostic(
                reason="inferred_retencion_excluded_from_credit",
                resolver_id=resolver_id,
                source_kind=INFERRED_RETENCION_EXCLUDED_SOURCE_KIND,
                message=(
                    f"{len(derivation.inferred_observations)} issued-invoice row(s) carry "
                    f"{derivation.inferred_total} EUR of retención reconstructed from invoice gross minus "
                    f"cash received. A reconstruction is not the recorded figure a credit against the cuota "
                    f"rests on, so that amount is NOT claimed. Transactions: {', '.join(sampled)}"
                ),
                remedy=(
                    "Record the retención the client practised on each issued invoice, or obtain the "
                    "payer's certificate, and recalculate; the figure then enters the credit as a "
                    "declared one."
                ),
            ),
        )
    if derivation.unresolved_observations:
        sampled = sorted(observation.transaction_id for observation in derivation.unresolved_observations)
        findings.append(
            CalculationSourceDiagnostic(
                reason="unresolved_retencion_substrate",
                resolver_id=resolver_id,
                source_kind=UNRESOLVED_RETENCION_SOURCE_KIND,
                message=(
                    f"{len(derivation.unresolved_observations)} issued-invoice row(s) leave the retención "
                    f"UNKNOWN rather than absent: the substrate does not determine one, or the implied rate "
                    f"exceeded the maximum the registry supports and the figure was refused. Neither is a "
                    f"proven nothing withheld. Transactions: {', '.join(sampled)}"
                ),
                remedy=(
                    "Record the invoice base and the retención for each transaction, then recalculate; "
                    "until then the credit is incomplete by an unknown amount."
                ),
            ),
        )
    return tuple(findings)


def _ungrounded_income_diagnostics(
    ungrounded: UngroundedRentaIncome,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project base-less income contributions into ONE advisory per aggregation.

    Deliberately aggregate rather than per-row: an advisory that fires once per
    transaction trains operators to ignore it, and the actionable unit here is
    "how much of my declared income has no invoice behind it", not each row.
    The count and the summed cash are always exact; only the transaction-id
    list is abbreviated, and the omitted count is stated so the truncation is
    visible rather than silent.

    The id list is fitted to the diagnostic's own character budget rather than
    to a fixed number of ids. Bounding by id COUNT was a proxy for the real
    constraint: :class:`CalculationSourceDiagnostic` caps ``message`` at
    :data:`DIAGNOSTIC_MESSAGE_MAX_LENGTH`, transaction ids are long and
    variable-length, and three of them already overflowed a five-id sample --
    raising ``ValidationError`` from inside the advisory and taking down the
    whole calculation. A safety net that crashes as soon as it has several
    things to report is worse than none, so the budget is now measured, not
    assumed.

    The message names both halves of the harm, not just the income
    mis-measurement. Every row this screen catches has grounding
    ``CASH_FALLBACK`` (no declared ``taxable_base``), and the withheld-amount
    inference in ``_renta_income_ledger`` refuses to run without that same
    base -- so each of these rows *also* contributes zero to the
    ``declared_withheld_amount_sum`` binding, silently dropping the ISSUED-side
    retención credit (RIRPF art. 110.3.a) alongside the income figure. This is
    the credit the taxpayer is owed on income already invoiced to a client; it
    is unrelated to the per-perceptor retenedor-liability store a RECEIVED
    invoice routes into, which this screen never reads. The count and summed
    cash reused below are the same values the income clause already computed,
    not a second derivation.

    Returns an empty tuple when every consumed row declared its substrate.
    """
    observations = ungrounded.observations
    if not observations:
        return ()
    total = sum((observation.gross_amount for observation in observations), Decimal("0"))
    sampled = sorted(observation.transaction_id for observation in observations)
    preamble = (
        f"{len(observations)} actividad-económica income row(s) totalling {total} EUR lack a "
        f"taxable_base, so {_ungrounded_income_consequence(ungrounded.facts)}. Their retención "
        f"credit is also lost, since it needs the same missing base. Classify each transaction "
        f"in the ledger with its taxable base. Transactions: "
    )
    return (
        CalculationSourceDiagnostic(
            reason="ungrounded_income_substrate",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=preamble + fitted_diagnostic_id_list(sampled, budget=DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(preamble)),
        ),
    )


def _m130_retenciones_backend_inputs(
    context: CalculationSourceContext,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Redirect the selected registry binding route to its declared endpoint."""
    route = resolve_m130_retenciones_route(effective_date=context.period.end_date, authority=context.operation)
    if context.modelo != route.modelo_id:
        return {}
    value = binding_values.get(route.binding_id)
    if value is None:
        return {}
    return {route.output_casilla: value}


class LedgerIrnrIncomeAggregationSourceResolver:
    """Resolve the selected-code M210 ``ledger_irnr_income_aggregation`` source.

    This resolver owns M210 ``rendimientos_integros`` only when the persisted
    gross-income source mode is ``ledger``.
    It passes the durable official tipo-renta selection through to the classifier
    rather than using the conceptual rate token, so codes such as ``01`` and
    ``03`` cannot be merged merely because they share a rate concept.
    """

    resolver_id: ClassVar[str] = "ledger_irnr_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol) -> None:
        """Bind the transaction repository for this source."""
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve IRNR income for the calculation context."""
        if context.m210_gross_income_source_mode is not M210GrossIncomeSourceMode.LEDGER:
            # The registry declares the optional M210 source unconditionally so
            # its selector remains validated.  Manual mode deliberately elects
            # not to produce a value, though, and that is a handled source
            # state—not an unenrolled-source advisory on every manual M210 run.
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        if not revision_has_binding_source(context.revision, "ledger_irnr_income_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        selected_official_tipo_renta_code = context.m210_official_tipo_renta_code
        if selected_official_tipo_renta_code is None:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                diagnostics=(
                    CalculationSourceDiagnostic(
                        reason="source_domain_not_ready",
                        source_kind="ledger_irnr_income_aggregation",
                        resolver_id=self.resolver_id,
                        message=(
                            "M210 ledger income binding requires the durable official tipo-renta code selection; "
                            "the conceptual formula token cannot select a ledger source"
                        ),
                    ),
                ),
            )

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        target_casilla_id = _irnr_income_target_casilla(context)
        with source_context_operation(context) as operation:
            try:
                aggregation = aggregate_irnr_income_ledger_from_repositories(
                    bucket_id=context.bucket_id,
                    period=aggregation_period,
                    revision=context.revision,
                    modelo=context.modelo,
                    target_casilla_id=target_casilla_id,
                    selected_official_tipo_renta_code=selected_official_tipo_renta_code,
                    transaction_repository=self._transaction_repository,
                    operation=operation,
                )
            except STORAGE_DEGRADATION_ERRORS as exc:
                return storage_degradation_resolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    source_kinds=self.owned_sources,
                    error=exc,
                )

        binding_values = resolve_ledger_irnr_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        unrouted = unsupported_ledger_irnr_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_irnr_handoff_bound_inputs(context.revision, binding_values),
            detail_rows=_irnr_annual_agrupacion_renta_rows(context, aggregation.observations),
            source_transaction_ids=sorted_ids(aggregation.observations, lambda observation: observation.transaction_id),
            diagnostics=out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_irnr_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_irnr_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_irnr_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        "declarable M210 IRNR gross-income observation "
                        f"(target_casilla_id={observation.target_casilla_id!r}, "
                        f"gross_income_amount={observation.gross_income_amount}) is not consumed by any "
                        "ledger_irnr_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=source_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_irnr_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                ),
            ),
        )


def _irnr_annual_agrupacion_renta_rows(
    context: CalculationSourceContext,
    observations: Sequence[IrnrIncomeObservation],
) -> tuple[Modelo210AgrupacionRentaRow, ...]:
    """Derive annual M210 grouping evidence from the admitted classifications."""
    if context.period.standard_code is not StandardPeriodCode.ANNUAL:
        return ()
    return tuple(
        Modelo210AgrupacionRentaRow(
            source_id=observation.transaction_id,
            tipo_renta_code=observation.official_tipo_renta_code,
            importe=observation.gross_income_amount,
            tipo_gravamen=observation.applicable_rate,
            pagador_mode=observation.payer_mode,
            pagador_id=observation.payer_id,
            deriva_de_bien_derecho=observation.asset_or_right_id is not None,
            bien_derecho_id=observation.asset_or_right_id,
        )
        for observation in observations
    )


def aggregation_period_for_modelo(*, filing_year: int, code: str) -> Period:
    """Translate a canonical ``StandardPeriodCode`` token to a core period.

    Accepts only the span-shaped canonical AEAT tokens the calc engine and the
    CLI ledger filter share: quarters (``1T``-``4T``), the annual period
    (``0A``), and months (``01``-``12``). The result is the typed core
    :class:`Period` consumed by ledger filters. Any other token raises
    :class:`AggregationValidationError`.
    """
    normalized = code.strip().upper()
    try:
        resolved = Period.from_year_and_code(filing_year, normalized)
    except PeriodError as exc:
        raise AggregationValidationError(
            tr("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        ) from exc
    if not resolved.has_date_span():
        raise AggregationValidationError(
            tr("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        )
    return resolved
