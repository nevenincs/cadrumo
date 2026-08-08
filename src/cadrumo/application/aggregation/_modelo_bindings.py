"""Repository-backed source-mesh resolvers for modelo registry bindings.

This module is the calculation-facing bridge from bucket-local stores to
:class:`~._source_mesh.CalculationSourceResolution`. Each resolver owns one
:class:`~core.BindingSourceKind`, reads the active
:class:`~._source_mesh.CalculationSourceContext`, and materialises binding
values declared on the snapshot's
:class:`~domain.calculations.registry.ModeloRevision`.

The IVA, Renta income, Renta expense, and M130 gasto resolvers delegate their
ledger projection to :mod:`~._iva_ledger`, :mod:`~._renta_income_ledger`,
:mod:`~._renta_ledger`, and :mod:`~._renta_gasto_ledger`. The retenciones
resolver reads the dedicated per-perceptor store through
:mod:`~._retencion_observations_repository`. The separate
:mod:`~._oss_ioss` and :mod:`~._withholding_source` modules follow the same
source-mesh contract for Modelo 369 and Modelo 190 detail counts.

Invoice-backed checks use
:class:`~domain.invoices.InvoiceCatalogueRepository` only as supporting
evidence: Modelo 303 domestic IVA remains ledger-owned, while Renta expense
aggregation can attach purchase-invoice evidence to transaction rows before
producing the shared :class:`~._source_mesh.CalculationSourceResolution`.

Declarable observations that no registry binding consumes are reported as
source diagnostics rather than silently blanking the filed calculation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.usage_ratios import load_usage_ratios
from ...adapters.persistence.storage import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core import BindingSourceKind, M210GrossIncomeSourceMode, Modelo, Period, PeriodError, StandardPeriodCode
from ...domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    IvaLedgerObservation,
    ModeloRevision,
    UngroundedRentaIncome,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    resolve_ledger_irnr_income_aggregation_binding_values,
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    resolve_retenciones_aggregation_binding_values,
    structurally_unroutable_iva_base_categories,
    ungrounded_ledger_renta_income_observations,
    unrouted_ledger_iva_quantities,
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_impatriado_income_observations,
    unsupported_ledger_irnr_income_observations,
    unsupported_ledger_iva_observations,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
    unsupported_ledger_renta_income_observations,
    validated_casilla_id,
)
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceLine,
    InvoicePersistenceError,
    IvaRate,
    invoice_line_to_iva_observation,
    iva_rate_kind,
)
from ...core.money import round_to_cents
from ...domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
    derive_flow_for_classification,
    recargo_rate_for_applied_rate,
)
from ...domain.modelos import Modelo210AgrupacionRentaRow
from ...domain.renta import (
    RENTA_130_RETENCIONES_BINDING_ID,
    RENTA_130_RETENCIONES_OUTPUT_CASILLA,
    RentaDeductibleExpenseObservation,
)
from ...domain.transactions import (
    OutOfWindowTransactionSummary,
    TransactionCatalogueRepositoryProtocol,
    TransactionPersistenceError,
)
from ...domain.usage_ratios import UsageRatioPersistenceError
from ._errors import AggregationValidationError, t
from ._impatriado_income_ledger import aggregate_impatriado_income_ledger_from_repositories
from ._invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from ._irnr_income_ledger import IrnrIncomeObservation, aggregate_irnr_income_ledger_from_repositories
from ._iva_ledger import (
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    aggregate_iva_ledger_observations_from_repositories,
    resolve_iva_ledger_binding_values,
)
from ._renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from ._renta_income_ledger import (
    RentaIncomeObservation,
    SalesInvoiceEvidenceRefusal,
    aggregate_renta_income_ledger_from_repositories,
    aggregate_renta_m100_income_ledger_from_repositories,
    aggregate_renta_m131_agrario_income_ledger_from_repositories,
)
from ._renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from ._retencion_observations_repository import RetencionObservationRepository
from ._retencion_rate_advisory import (
    administrador_retencion_rate_advisory_observations,
    inferred_actividad_retencion_rate_advisory_observations,
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
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    out_of_window_summary_source_diagnostic,
    storage_degradation_resolution,
)

_STORAGE_DEGRADATION_ERRORS = (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    InvoicePersistenceError,
    StorageValidationError,
    TransactionPersistenceError,
    UsageRatioPersistenceError,
)
_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
    },
)


def _residue_categories(observations: Sequence[IvaLedgerObservation]) -> str:
    """Return the sorted distinct IVA categories carrying an undrawn quantity.

    The screen detects per fact AND per selector, so a fact can be drawn for some
    categories and undrawn for others -- Modelo 390 draws ``base_amount_sum`` for
    the domestic tiers while import and the two reverse-charge categories carry it
    undrawn. Reporting only the fact would tell an operator that base is missing
    without saying where, which is the reading that makes a partially-closed gap
    look wholly open (or, once the domestic half landed, wholly closed).

    Naming the categories is what makes the residue attributable: it states which
    set is still open, so a later reader can tell a genuine remainder from a
    regression.
    """
    categories = sorted({observation.category.value for observation in observations})
    return "[" + ", ".join(categories) + "]"


_M210_RENDIMIENTOS_INTEGROS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_M210_RENDIMIENTOS_INTEGROS_CASILLA",
)

_INVOICE_LEDGER_SCREEN_BINDINGS: dict[str, tuple[BindingId, ...]] = {
    # ONE screen, a binding set per modelo -- deliberately not a second
    # screen per modelo. M390 declares the same seven concepts M303 does,
    # differing only in the id prefix, so a parallel function would be two
    # implementations of one comparison free to drift: a widening applied to
    # one and not the other is invisible until a filing is wrong.
    Modelo.M303.value: (
        "modelo-303-iva-repercutido-general-cuota",
        "modelo-303-iva-repercutido-reducido-cuota",
        "modelo-303-iva-repercutido-super-reducido-cuota",
        "modelo-303-iva-soportado-interiores-cuota",
        # The recargo de equivalencia tiers (LIVA art. 161). A supplier to a
        # recargo-regime retailer charges it ON TOP of the cuota, so an invoice
        # carrying one and a ledger missing it under-declare by exactly the
        # surcharge.
        "modelo-303-recargo-equivalencia-general-cuota",
        "modelo-303-recargo-equivalencia-reducido-cuota",
        "modelo-303-recargo-equivalencia-super-reducido-cuota",
    ),
    Modelo.M390.value: (
        "modelo-390-iva-repercutido-general-cuota",
        "modelo-390-iva-repercutido-reducido-cuota",
        "modelo-390-iva-repercutido-super-reducido-cuota",
        "modelo-390-iva-soportado-interiores-cuota",
        "modelo-390-iva-recargo-equivalencia-general-cuota",
        "modelo-390-iva-recargo-equivalencia-reducido-cuota",
        "modelo-390-iva-recargo-equivalencia-super-reducido-cuota",
    ),
}
_M303_INVOICE_EVIDENCE_SAMPLE_LIMIT = 5


class LedgerIvaAggregationSourceResolver:
    """Resolve ``ledger_iva_aggregation`` bindings from the transaction ledger.

    Owns :attr:`BindingSourceKind.LEDGER_IVA_AGGREGATION`, projects IVA
    observations through :func:`~._iva_ledger.aggregate_iva_ledger_observations_from_repositories`,
    and returns a :class:`~._source_mesh.CalculationSourceResolution` with
    source issues, unrouted-observation diagnostics, and transaction provenance.
    """

    resolver_id = "ledger_iva_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IVA_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_iva_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        transaction_ids = {observation.ledger_id for observation in aggregation.observations}
        transaction_ids.update(reference.transaction_id for reference in aggregation.prorrata_references)
        binding_values = resolve_iva_ledger_binding_values(
            context.revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )
        silence_report = _raise_if_invoice_iva_would_be_silent(
            context=context,
            period=aggregation_period,
            transaction_binding_values=binding_values,
            invoice_repository=self._invoice_repository,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )
        # Reuse the fail-closed candidate-path screen as a NON-blocking advisory on
        # the calculate path: a declarable IVA observation whose category/rate/flow
        # triple no ``ledger_iva_aggregation`` binding selects would otherwise be
        # silently dropped. Surface it (calculate still succeeds) so the operator
        # sees the unrouted IVA rather than filing an under-declared form
        # (no-silent-under-declaration). The category/rate/flow axes are the
        # observation's own provenance — no legal_ref is fabricated.
        unconsumed = unsupported_ledger_iva_observations(context.revision, aggregation.observations)
        # Second, distinct screen, on the axis the one above cannot see. That one
        # keys on the ROW, and every IVA row carries three independent quantities
        # -- base, cuota, recargo -- so a row consumed for its cuota reads as
        # routed while its base imponible reaches no binding at all. Modelo 390
        # is the live instance: it draws cuota and recargo and declares no base
        # binding, so without this the annual return's missing base boxes are
        # silent with the row screen clean.
        unrouted_quantities = unrouted_ledger_iva_quantities(context.revision, aggregation.observations)
        # Fourth, structural axis, observation-INDEPENDENT unlike the two above:
        # it asks whether the revision's bindings could EVER route a category's
        # base, not whether a particular row's base was reached. Scoped to
        # categories this taxpayer's ledger actually carries this period, so it
        # reads as taxpayer-relevant rather than a blanket registry dump, and to
        # Modelo 303 only pending Modelo 390 coordination (#80). Advisory, never
        # blocking: several of these categories are cuota-less BY LAW, so no tax
        # is lost -- only the base itself has nowhere on this revision to land.
        unroutable_categories: tuple[IvaCategory, ...] = ()
        if str(context.modelo) == Modelo.M303.value:
            present_categories = {observation.category for observation in aggregation.observations}
            unroutable_categories = tuple(
                category
                for category in structurally_unroutable_iva_base_categories(context.revision)
                if category in present_categories
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(sorted(transaction_ids)),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + devengo_proxy_attribution_diagnostics(
                silence_report.compared,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + _reverse_charge_underivable_diagnostics(
                silence_report.reverse_charge_underivable,
                resolver_id=self.resolver_id,
            )
            + _category_counterparty_mismatch_diagnostics(
                silence_report.category_counterparty_mismatches,
                resolver_id=self.resolver_id,
            )
            + _recargo_rate_mismatch_diagnostics(
                silence_report.recargo_rate_divergences,
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
                if issue.reason not in _IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable IVA observation {observation.ledger_id!r} "
                        f"(category={observation.category.value!r}, rate_kind={observation.rate_kind.value!r}, "
                        f"flow_direction={observation.flow_direction.value!r}) is not consumed by any "
                        f"ledger_iva_aggregation binding on revision {context.revision.id!r}; "
                        "its base/cuota is not declared on this calculation"
                    ),
                )
                for observation in unconsumed
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_declarable_quantity",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"{len(quantity.observations)} IVA row(s) carry {quantity.total} EUR of "
                        f"{quantity.fact!r} in categories "
                        f"{_residue_categories(quantity.observations)}, which no ledger_iva_aggregation "
                        f"binding on revision {context.revision.id!r} draws for those categories; that "
                        f"amount is not declared on this calculation. The rows themselves ARE consumed "
                        f"for their other quantities, so no other screen reports them"
                    ),
                )
                for quantity in unrouted_quantities
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="structurally_unroutable_base_category",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"IVA category {category.value!r} appears on this period's ledger, and no "
                        f"ledger_iva_aggregation binding on revision {context.revision.id!r} could ever draw "
                        "its taxable base, for any row of that category -- not merely for the rows seen this "
                        "period. Cuota is legitimately zero or already declared elsewhere for this category, "
                        "so no tax is lost, but the base amount itself is not represented in this filing"
                    ),
                )
                for category in unroutable_categories
            ),
            provenance=(
                tuple(
                    CalculationSourceProvenance(
                        source_kind="ledger_iva_aggregation",
                        source_ref=f"transaction:{observation.ledger_id}",
                    )
                    for observation in aggregation.observations
                )
                + tuple(
                    CalculationSourceProvenance(
                        source_kind="ledger_iva_aggregation",
                        source_ref=f"prorrata:{reference.transaction_id}",
                    )
                    for reference in aggregation.prorrata_references
                )
                + _iva_prorrata_apportionment_provenance(
                    context.revision,
                    aggregation_period,
                    aggregation.prorrata_apportionment,
                )
            ),
        )


class LedgerRentaGastosEstimacionDirectaAggregationSourceResolver:
    """Resolve ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~._renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~._source_mesh.CalculationSourceResolution`.
    """

    resolver_id = "ledger_renta_gastos_estimacion_directa_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
    )

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

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
                usage_ratios=load_usage_ratios(bucket_id=context.bucket_id).ratios,
                modelo=context.modelo,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # expense whose (modelo, period, target_casilla_id) matches no
        # ledger_renta_gastos_estimacion_directa_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
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
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
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
            provenance=tuple(
                provenance
                for observation in aggregation.observations
                for provenance in _renta_observation_provenance(observation)
            ),
        )


#: Which projection a renta-income binding's modelo routes to. Absent means the
#: Modelo 130 cumulative-quarter path, which is the shape every other consumer of
#: this source kind has.
_RENTA_INCOME_AGGREGATOR_BY_MODELO = {
    Modelo.M100.value: aggregate_renta_m100_income_ledger_from_repositories,
    Modelo.M131.value: aggregate_renta_m131_agrario_income_ledger_from_repositories,
}


class LedgerRentaIncomeAggregationSourceResolver:
    """Resolve ``ledger_renta_income_aggregation`` actividad-income bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION`. Modelo 130
    uses the cumulative-quarter income path, while Modelo 100 uses the annual
    activity-income path over the same ledger eligibility rules.
    """

    resolver_id = "ledger_renta_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

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
        income_aggregator = _RENTA_INCOME_AGGREGATOR_BY_MODELO.get(
            str(context.modelo),
            aggregate_renta_income_ledger_from_repositories,
        )
        try:
            aggregation = income_aggregator(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
                invoice_repository=self._invoice_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_ledger_renta_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
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
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_m130_retenciones_backend_inputs(context, binding_values),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta income observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                        f"is not consumed by any ledger_renta_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            )
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
            + _ungrounded_income_diagnostics(ungrounded, resolver_id=self.resolver_id)
            + _unusable_sales_invoice_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + inferred_actividad_retencion_rate_advisory_observations(
                aggregation.observations,
                bucket_id=context.bucket_id,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


# The character budget an advisory message must fit, read from the field that
# enforces it rather than restated as a literal -- a hardcoded copy silently
# stops matching the moment the model's own limit moves, and the failure lands
# as a ValidationError raised from inside the diagnostic that was supposed to
# keep the operator informed.
#
# An operator needs a handle on the offending rows, not the whole list, so the
# id sample is fitted to whatever budget the prose leaves. The count and the
# summed cash are always exact and the omission is always stated, so the list
# shortens but never becomes a silent cap.
_DIAGNOSTIC_MESSAGE_MAX: int = next(
    meta.max_length
    for meta in CalculationSourceDiagnostic.model_fields["message"].metadata
    if getattr(meta, "max_length", None) is not None
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
    :data:`_DIAGNOSTIC_MESSAGE_MAX`, transaction ids are long and
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
    ``withheld_amount_sum`` binding, silently dropping the ISSUED-side
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
        f"credit is also lost, since it needs the same missing base. Record with 'aeat app "
        f"ledger classify <transaction-id> --taxable-base <amount>'. Transactions: "
    )
    return (
        CalculationSourceDiagnostic(
            reason="ungrounded_income_substrate",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=preamble + _fitted_id_list(sampled, budget=_DIAGNOSTIC_MESSAGE_MAX - len(preamble)),
        ),
    )


def _unusable_sales_invoice_diagnostics(
    observations: Sequence[RentaIncomeObservation],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Surface rows whose linked sales invoice could not be trusted.

    These rows are NOT excluded -- they contribute their bank cash, because the
    taxpayer was paid and that income is declarable whatever state its paperwork
    is in. What they lost is the invoice's base, cuota and retención, so the
    figure they contribute is the credited cash rather than the ingresos
    íntegros the casilla asks for. Without this advisory that downgrade is
    invisible: the row looks exactly like one that never had an invoice at all.

    One advisory per refusal reason, not per row: the actionable unit is "these
    links are unusable, and this is what is wrong with them", and a per-row
    advisory trains operators to ignore the channel. The id sample is fitted to
    the message budget by the same helper the ungrounded advisory uses, so a
    long list degrades to a count instead of raising out of the diagnostic and
    taking the calculation down with it.
    """
    by_reason: dict[SalesInvoiceEvidenceRefusal, list[RentaIncomeObservation]] = defaultdict(list)
    for observation in observations:
        if observation.sales_invoice_refusal is not None:
            by_reason[observation.sales_invoice_refusal].append(observation)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for reason in sorted(by_reason, key=lambda member: member.value):
        rows = by_reason[reason]
        total = sum((row.gross_amount for row in rows), Decimal("0"))
        preamble = (
            f"{len(rows)} income row(s) totalling {total} EUR link a sales invoice that could not be "
            f"trusted ({reason.value}), so they declare bank cash instead of the invoice base and their "
            f"retención credit is lost. Repair the link or record the base directly. Transactions: "
        )
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unusable_sales_invoice_evidence",
                source_kind="ledger_renta_income_aggregation",
                resolver_id=resolver_id,
                message=preamble
                + _fitted_id_list(
                    sorted(row.transaction_id for row in rows),
                    budget=_DIAGNOSTIC_MESSAGE_MAX - len(preamble),
                ),
            ),
        )
    return tuple(diagnostics)


def _fitted_id_list(identifiers: Sequence[str], *, budget: int) -> str:
    """Render ``identifiers`` into at most ``budget`` characters, stating omissions.

    Shows as many ids as fit alongside the "(and N more)" suffix that describes
    the ones it dropped -- the suffix is part of the budget, because a truncation
    notice that itself overflows would defeat the cap it exists to respect.

    Degrades rather than raises: when even one id plus its suffix cannot fit, it
    reports the bare count. The caller is an advisory about a measurement risk,
    so losing the id sample is acceptable where losing the whole diagnostic --
    and with it the calculation -- is not.
    """
    total = len(identifiers)
    for shown in range(total, 0, -1):
        remainder = total - shown
        candidate = ", ".join(identifiers[:shown]) + (f" (and {remainder} more)" if remainder else "")
        if len(candidate) <= budget:
            return candidate
    fallback = f"{total} transaction(s), ids omitted to fit the diagnostic length limit"
    return fallback if len(fallback) <= budget else ""


def _m130_retenciones_backend_inputs(
    context: CalculationSourceContext,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Redirect the retenciones binding's resolved value to its output casilla.

    This is the OUTPUT half of a fact that is declared with
    `target_casilla_id = "01"` in the registry (see the comment on the
    `modelo-130-actividad-economica-retenciones-cumulative` binding in
    `_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/
    0003-m130-income-cumulative.toml`). That selector field is the
    OBSERVATION-MATCH key -- it must stay "01" for the aggregation to see any
    rows at all -- not a declaration of where the aggregate lands.
    `RENTA_130_RETENCIONES_OUTPUT_CASILLA` is hardcoded here because this
    binding family has no schema field to express "match on X's
    observations, output to Y's casilla" honestly; do not "fix" the selector
    to that casilla without reading that TOML comment first, since doing so
    silently zeroes this value instead of redirecting it.

    A schema field expressing that divergence honestly was tried and
    reverted: it would reopen the cross-domain routing-table design this
    redirect depends on, which needs a deliberate redesign of that table, not
    an implementation choice made in passing. Following the established remedy
    instead: the hardcoded casilla constant lives in `domain.renta` and is
    validated against every
    M130 revision by a `CrossDomainSnapshotCheck` registered at snapshot-build
    time (`domain.renta._retenciones_routing_integrity`), the same mechanism
    that already validates the Modelo 100 first-slice routing table. A
    revision that dropped or renumbered the output casilla would fail loudly
    at snapshot build, before this function ever runs -- it does not
    re-validate that guarantee itself.
    """
    if str(context.modelo) != Modelo.M130.value:
        return {}
    value = binding_values.get(RENTA_130_RETENCIONES_BINDING_ID)
    if value is None:
        return {}
    return {RENTA_130_RETENCIONES_OUTPUT_CASILLA: value}


class LedgerImpatriadoIncomeAggregationSourceResolver:
    """Resolve ``ledger_impatriado_income_aggregation`` Modelo 151 base bindings.

    Owns :attr:`BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION`. Modelo
    151 (régimen especial de impatriados, Ley Beckham) folds only Spanish-source
    (``source_jurisdiction == "ES"``) income into
    ``impatriado.base-liquidable-general`` over the full ejercicio; every
    foreign-source or jurisdiction-unresolved row is segregated by the classifier
    into a typed ``BECKHAM_FOREIGN_SOURCE_SEGREGATED`` issue and surfaced as a
    non-blocking source diagnostic rather than silently admitted or silently
    dropped (art. 93.2 LIRPF / art. 25.1.f TRLIRNR).
    """

    resolver_id = "ledger_impatriado_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_impatriado_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_impatriado_income_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_ledger_impatriado_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        # Fail-closed advisory: a non-zero ES-source income whose target casilla
        # matches no ledger_impatriado_income_aggregation binding would otherwise
        # be silently dropped from the base (no-silent-under-declaration).
        unrouted = unsupported_ledger_impatriado_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_impatriado_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_impatriado_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable impatriado ES-source income observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                        f"is not consumed by any ledger_impatriado_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_impatriado_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


class LedgerIrnrIncomeAggregationSourceResolver:
    """Resolve the selected-code M210 ``ledger_irnr_income_aggregation`` source.

    This resolver owns M210 ``rendimientos_integros`` only when the persisted
    gross-income source mode is ``ledger``.
    It passes the durable official tipo-renta selection through to the classifier
    rather than using the conceptual rate token, so codes such as ``01`` and
    ``03`` cannot be merged merely because they share a rate concept.
    """

    resolver_id = "ledger_irnr_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if context.m210_gross_income_source_mode is not M210GrossIncomeSourceMode.LEDGER:
            # The registry declares the optional M210 source unconditionally so
            # its selector remains validated.  Manual mode deliberately elects
            # not to produce a value, though, and that is a handled source
            # state—not an unenrolled-source advisory on every manual M210 run.
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        if not _revision_has_binding_source(context.revision, "ledger_irnr_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        selected_official_tipo_renta_code = context.m210_official_tipo_renta_code
        if selected_official_tipo_renta_code is None:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                diagnostics=(
                    CalculationSourceDiagnostic(
                        reason="source_issue",
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
        try:
            aggregation = aggregate_irnr_income_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                revision=context.revision,
                selected_official_tipo_renta_code=selected_official_tipo_renta_code,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
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
            bound_inputs_by_casilla_id={
                _M210_RENDIMIENTOS_INTEGROS_CASILLA: aggregation.casilla_aggregation.casilla_values.get(
                    _M210_RENDIMIENTOS_INTEGROS_CASILLA,
                    Decimal("0"),
                ),
            },
            detail_rows=_irnr_annual_agrupacion_renta_rows(context, aggregation.observations),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_irnr_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_irnr_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
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
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_irnr_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
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


class LedgerRentaGastosPagoFraccionadoAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 deductible-expense (gasto) bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION`. This is the
    OUTGOING sibling of :class:`LedgerRentaIncomeAggregationSourceResolver`: it
    folds deductible business expenses into Modelo 130 casilla 02 over the same
    cumulative year-to-date quarterly window and emits an unrouted-observation
    diagnostic for declarable gastos no binding consumes.
    """

    resolver_id = "ledger_renta_gastos_pago_fraccionado_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_gastos_pago_fraccionado_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_renta_gasto_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        # Fail-closed advisory parity with the income screen: a non-zero
        # declarable gasto whose target_casilla_id matches no
        # ledger_renta_gastos_pago_fraccionado_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
        unrouted = unsupported_ledger_renta_gastos_pago_fraccionado_observations(
            context.revision, aggregation.observations
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta gasto observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, deductible_amount={observation.deductible_amount}) "
                        f"is not consumed by any ledger_renta_gastos_pago_fraccionado_aggregation binding on revision "
                        f"{context.revision.id!r}; its deductible expense is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


def _raise_if_invoice_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    period: Period,
    transaction_binding_values: Mapping[BindingId, Decimal],
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None,
) -> _InvoiceIvaSilenceReport:
    """Refuse a filing whose invoice IVA would be absent from its ledger totals.

    The IVA cuota boxes are sourced from ``ledger_iva_aggregation``: the
    transaction ledger is the filing authority. A bucket can also carry real
    invoice catalogue evidence, and there is no invoice binding family for
    these boxes. If invoice IVA exists for the period and would exceed the
    transaction-ledger cuota the filing is about to use, calculating a
    zero/subtotal filing would silently under-declare. Refuse, and require the
    operator to link and classify the transactions that feed the canonical
    ledger path.

    **Applies to every modelo in the screened-binding table, by design.** M390
    declares the same seven concepts M303 does under its own id prefix, so it
    is an entry in that table rather than a second screen. Two implementations
    of one comparison would be free to drift, and a widening applied to one and
    not the other is invisible until a filing is wrong -- which is exactly how
    the ES-only counterparty filter and the missing recargo tiers survived on
    the M303 side.

    The annual modelo needs this more than the quarterly one, not less. Its
    390-to-303 reconciliation BLOCKING_RULE compares two figures that both root
    in the same ledger, so it detects a transaction booked into the wrong
    quarter and cannot detect one that was never recorded at all: both sides
    are equally short and the rule passes.

    Returns:
        A pair. First, the invoices whose IVA was compared against the ledger,
        so the caller can disclose how their period placement was arrived at.
        Second, the invoices withheld because their declared category and their
        counterparty country contradict each other -- carried out separately
        because they reached NO casilla, so the caller must report them rather
        than describe their placement. Both empty when the modelo is not
        screened or there was nothing to compare.

        The second element survives the early return below: a period whose
        every invoice was withheld produces no observations at all, and that is
        precisely the case where staying silent would be worst.
    """
    screened_bindings = _INVOICE_LEDGER_SCREEN_BINDINGS.get(str(context.modelo))
    if screened_bindings is None:
        return _InvoiceIvaSilenceReport()
    screened = _screened_invoice_iva_observations(
        context=context,
        period=period,
        invoice_repository=invoice_repository,
    )
    if not screened.observations:
        return _InvoiceIvaSilenceReport(
            category_counterparty_mismatches=screened.category_counterparty_mismatches,
            reverse_charge_underivable=screened.reverse_charge_underivable,
            recargo_rate_divergences=screened.recargo_rate_divergences,
        )
    invoice_binding_values = resolve_iva_ledger_binding_values(
        context.revision,
        screened.observations,
        prorrata_apportionment=prorrata_apportionment,
    )
    missing_binding_values = {
        binding_id: invoice_value - transaction_value
        for binding_id in screened_bindings
        if (invoice_value := invoice_binding_values.get(binding_id, Decimal("0")))
        > (transaction_value := transaction_binding_values.get(binding_id, Decimal("0")))
    }
    if not missing_binding_values:
        return _InvoiceIvaSilenceReport(
            compared=screened.compared,
            category_counterparty_mismatches=screened.category_counterparty_mismatches,
            reverse_charge_underivable=screened.reverse_charge_underivable,
            recargo_rate_divergences=screened.recargo_rate_divergences,
        )
    raise AggregationValidationError(
        t("errors.error.error_modelo_aggregation_binding"),
        context={
            "reason": "invoice_domestic_iva_not_in_transaction_ledger",
            "modelo": str(context.modelo),
            "filing_year": str(context.filing_year),
            "period": context.period.registry_token,
            "source_kind": "ledger_iva_aggregation",
            "invoice_domestic_iva_excess_by_binding": {
                str(binding_id): str(amount) for binding_id, amount in missing_binding_values.items()
            },
            "invoice_ids": tuple(sorted(screened.invoice_ids)[:_M303_INVOICE_EVIDENCE_SAMPLE_LIMIT]),
            "invoice_count": str(len(screened.invoice_ids)),
        },
        suggestion=(
            "Link and classify the domestic IVA invoices into the transaction ledger "
            "before calculating Modelo 303; invoice-only IVA evidence is not a Modelo 303 filing source."
        ),
    )


def _line_contributes_to_the_iva_screen(base_amount: Decimal, iva_amount: Decimal) -> bool:
    """Return whether one invoice line has anything the IVA screen can declare.

    A line contributes when it carries a base OR a cuota. Screening on the cuota
    alone reads as a sensible "nothing to declare" filter and is not one: an
    exempt operation (LIVA art. 20), an intra-community supply (art. 25) and an
    issued-side reverse charge all carry a real base with a cuota that is zero
    BY LAW. The component table says so outright -- both categories are
    ``base=required, cuota=zero_by_law`` -- and Modelo 303 declares those bases
    in its own base-only casillas.

    So a cuota-only filter dropped exactly the lines whose base was the only
    thing they were ever going to contribute, and the declaration understated
    the exempt base by the whole amount with nothing reporting it.

    A line carrying neither is the only shape that genuinely contributes
    nothing, and is the only one this predicate declines.

    **This predicate alone does not make an exempt base reach Modelo 303, and
    was mistakenly reported as doing so.** The loop classifies from the RATE
    SLOT, so an exempt line becomes ``domestic_exempt``/``exempt`` while casilla
    59 selects ``intra_community_supply``/``zero`` and casilla 60 the two export
    categories -- a miss on both axes. No M303 binding selects
    ``domestic_exempt`` or ``domestic_zero``, so such an observation routes
    nowhere rather than into a wrong casilla; the effect is inert, not harmful.

    Keeping the line is a PRECONDITION of the real fix, not the fix. The real
    fix is to construct the observation from the invoice's own
    ``iva_category`` the way the bank-transaction path already does
    (``_iva_ledger.py``: explicit category first, rate-derived domestic
    category only as a fallback, with the intracom/export counterparty gate).
    Two feeds populating one binding source with divergent logic is what
    ``one-aggregation-path-pull-equals-calculate`` exists to prevent.
    """
    return base_amount > Decimal("0") or iva_amount > Decimal("0")


# The base-only categories a live Modelo 303 binding actually selects: casilla
# 59 takes the intra-community supply (LIVA art. 25) and casilla 60 the two
# export families (arts. 21-22). Deliberately NOT every cuota-less category --
# a domestic exemption under art. 20 is equally cuota-less and has no base-only
# casilla, so routing it anywhere would over-declare a volume the taxpayer never
# supplied abroad.
_BASE_ONLY_ROUTED_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    },
)

_EU_MEMBER_STATE_CODES: frozenset[str] = frozenset(member.value.upper() for member in EUMemberState)


def _counterparty_supports_the_declared_category(invoice: Invoice) -> bool:
    """Whether the counterparty can bear the category the invoice claims.

    The same coupling the bank-transaction path gates, and reading the same two
    facts it reads -- which are NOT one fact. Ley 37/1992 art. 25 exempts an
    intra-community supply on the acquirer holding a VAT IDENTIFICATION assigned
    by another Member State, so that arm reads
    ``counterparty_identification_state``. The export arm is the one genuinely
    about place -- an export leaves the Union -- so it keeps reading the
    counterparty's country of establishment.

    Reading the country for BOTH was a defect that landed in money in both
    directions: a Spanish-established acquirer holding a German VAT number had
    its exempt supply withheld from casilla 59 (over-declaration), and a
    German-established acquirer purchasing under a Spanish NIF-IVA had a
    domestic supply routed there (silent under-declaration). Absent
    identification is absent -- it withholds rather than falling back to the
    address.

    Returns ``False`` rather than raising, which leaves the line unrouted. The
    withholding is REPORTED: the screen collects each mismatched invoice and the
    resolver raises an ``invoice_category_counterparty_mismatch`` advisory
    naming it, so the operator learns the volume was withheld and why. The bank
    path returns a typed gate issue for the same shape; this projector returns
    observations, so it reports through the resolution's diagnostics instead.
    """
    if invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
        identification = invoice.counterparty_identification_state
        return identification is not None and identification is not EUMemberState.ES
    country = (invoice.counterparty_country or "").strip().upper()
    return country not in _EU_MEMBER_STATE_CODES


#: Cuota-less ISSUED categories whose base is declared under the invoice's OWN
#: declared category, each with the flow that category implies.
#:
#: Distinct from ``_BASE_ONLY_ROUTED_CATEGORIES`` below, and the difference is
#: the point. That set feeds a branch which stamps ``rate_kind = ZERO`` and
#: applies the intracom/export counterparty gate, both correct for a genuinely
#: zero-rated cross-border supply and both FALSE here:
#:
#: * ``domestic_reverse_charge`` is sujeta y no exenta -- the recipient
#:   self-assesses at the ordinary tier -- so it is not zero-rated, and its
#:   counterparty is Spanish, so the EU-identification gate would withhold it
#:   every time.
#: * ``intra_community_service_supply`` is NOT SUBJECT in Spain by art.
#:   69.Uno.1 rather than exempt, so it is not zero-rated either, and its
#:   counterparty IS EU-established, which the gate's export arm rejects.
_DECLARED_CATEGORY_BASE_ONLY_FLOWS: Mapping[IvaCategory, IvaFlowDirection] = {
    # The SUPPLIER's side of a domestic reverse charge (LIVA art. 84.Uno.2.o).
    # OPERACION_CON_INVERSION, never REPERCUTIDO: that distinction is the whole
    # reason the fourth flow member exists, and collapsing them puts the
    # supplier's turnover on the recipient's self-assessment line.
    IvaCategory.DOMESTIC_REVERSE_CHARGE: IvaFlowDirection.OPERACION_CON_INVERSION,
    # A B2B service located where the EU recipient is established (art.
    # 69.Uno.1). REPERCUTIDO is correct: the taxpayer SUPPLIES, and unlike the
    # reverse-charge case there is no separate supplier-side flow member,
    # because the operation is simply outside the Spanish hecho imponible.
    IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY: IvaFlowDirection.REPERCUTIDO,
}


def _declared_category_base_only_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    category: IvaCategory,
    flow_direction: IvaFlowDirection,
) -> IvaLedgerObservation:
    """Project a cuota-less line under the category the INVOICE declares.

    Both members of ``_DECLARED_CATEGORY_BASE_ONLY_FLOWS`` reached nothing
    before this arm, for one shared reason: the line carries no cuota, so it
    fell past the standard branch, which classifies from the RATE SLOT and
    therefore replaced the declared category with whatever tier the slot
    printed. The identity the casilla binding selects on was destroyed upstream
    of the binding, so adding a binding alone would have left the box blank and
    looked like the registry was at fault.

    ``rate_kind`` and ``applied_rate`` are measured off the line's own slot
    rather than stated. Neither category is zero-rated, so forcing ``ZERO``
    would assert a legal treatment that does not apply; and the destination
    casillas select on category and flow, not on rate, so nothing depends on a
    fabricated tier. Measuring also means this producer invents no rate, which
    the rate-less-row gate requires.

    Args:
        ledger_id: Identity already derived for this invoice line.
        invoice: The invoice the line belongs to.
        line: The line being projected.
        devengo_date: The date the observation is declared on.
        recargo_amount: Recargo attributable to this line, already resolved.
        category: The invoice's own declared category, already read and
            confirmed non-``None`` by the caller -- it is what keyed the
            ``_DECLARED_CATEGORY_BASE_ONLY_FLOWS`` lookup that selected
            *flow_direction*.
        flow_direction: The flow this category implies, from the table above.

    Returns:
        The observation, carrying a real base and no cuota.
    """
    # Built through the standard projection first purely to measure rate_kind
    # and applied_rate off the line's own slot, then re-stated with the two axes
    # the slot cannot know: the declared category and its flow.
    measured = invoice_line_to_iva_observation(
        invoice_id=ledger_id,
        issued_at=devengo_date,
        invoice_kind=invoice.kind,
        iva_rate=line.iva_rate,
        base_amount=line.subtotal,
        iva_amount=line.iva_amount,
        recargo_amount=recargo_amount,
    )
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=devengo_date,
        category=category,
        rate_kind=measured.rate_kind,
        applied_rate=measured.applied_rate,
        flow_direction=flow_direction,
        base_amount=line.subtotal,
        iva_amount=Decimal("0"),
        recargo_amount=recargo_amount,
    )


def _invoice_line_iva_observation(
    *,
    invoice: Invoice,
    line: InvoiceLine,
    line_index: int,
    devengo_date: date,
    recargo_amount: Decimal,
) -> IvaLedgerObservation | None:
    """Project one invoice line into the observation the screen declares from.

    A line carrying a cuota takes the standard-case classification, which
    derives the domestic category from the line's rate slot.

    A line carrying NO cuota cannot be classified that way, and that is the
    defect this branch closes. An intra-community supply, an export and a
    domestic exemption all print the same exempt slot, so the rate alone
    collapses three different declarations into ``domestic_exempt`` -- which
    casilla 59 and 60 do not select, on either category or rate kind. The base
    then reached no casilla at all while the line looked handled.

    The invoice's OWN declared category is what distinguishes them, which is
    exactly how the bank-transaction path resolves the same question: explicit
    category first, rate-derived domestic category only as a fallback. Two feeds
    of one binding source reading it differently is what
    ``one-aggregation-path-pull-equals-calculate`` exists to prevent.

    Returns ``None`` when the line has no cuota and its category is not one a
    base-only casilla selects, or when the counterparty contradicts that
    category. Both cases are unrouted rather than mis-routed.

    Args:
        invoice: The invoice the line belongs to, read for its declared
            category and counterparty country.
        line: The line being projected.
        line_index: Position of the line, folded into the observation id.
        devengo_date: The date the observation is declared on.
        recargo_amount: Recargo attributable to this line, already resolved.

    Returns:
        The observation to declare from, or ``None`` when the line routes
        nowhere.
    """
    ledger_id = f"invoice:{invoice.invoice_id}:{line_index}"
    if line.iva_amount > Decimal("0"):
        return invoice_line_to_iva_observation(
            invoice_id=ledger_id,
            issued_at=devengo_date,
            invoice_kind=invoice.kind,
            iva_rate=line.iva_rate,
            base_amount=line.subtotal,
            iva_amount=line.iva_amount,
            recargo_amount=recargo_amount,
        )
    category = invoice.iva_category
    declared_flow = _DECLARED_CATEGORY_BASE_ONLY_FLOWS.get(category) if category is not None else None
    if category is not None and declared_flow is not None and invoice.kind is InvoiceKind.ISSUED:
        return _declared_category_base_only_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            category=category,
            flow_direction=declared_flow,
        )
    if category is not None and category not in _BASE_ONLY_ROUTED_CATEGORIES:
        # The declared treatment wins over the rate slot, which is what the
        # bank-transaction path has always done and what this path did not. The
        # slot cannot express a reverse charge at all: the supplier charges
        # nothing, so the line is exempt-slotted, and deriving from it relabelled
        # a declared `domestic_reverse_charge` as `domestic_exempt` at flow
        # `soportado` -- describing the recipient as merely bearing input tax
        # where the law has them self-assess output tax.
        #
        # The flow comes from `derive_flow_for_classification` rather than from a
        # membership test, because the families genuinely differ: an
        # intra-community acquisition self-assesses on either direction, while a
        # domestic reverse charge resolves BY direction since both sides are
        # Spanish and the form asks for them separately. One call routes both.
        #
        # This makes the RECORD correct. It does not make the operation declare:
        # the recipient-side selector is a triple and the rate kind is still
        # `exempt`, so a cuota-less line reaches no binding. The shortfall is
        # reported through `_reverse_charge_cuota_not_derivable` rather than
        # closed here, because closing it means asserting a rate the record does
        # not carry.
        return IvaLedgerObservation(
            ledger_id=ledger_id,
            transaction_date=devengo_date,
            category=category,
            rate_kind=_rate_kind_for_slot(line.iva_rate),
            flow_direction=derive_flow_for_classification(category=category, invoice_direction=invoice.kind),
            base_amount=line.subtotal,
            iva_amount=line.iva_amount,
            recargo_amount=recargo_amount,
        )
    if category is None or category not in _BASE_ONLY_ROUTED_CATEGORIES:
        # No declared treatment at all: the rate slot is the only signal there
        # is, and the standard-case classification is the right reading of it.
        # ``category is None`` is folded into this membership test rather than
        # left implicit -- ``None`` is never a member of
        # ``_BASE_ONLY_ROUTED_CATEGORIES`` so the outcome is unchanged, but the
        # explicit check is what lets every use of ``category`` from here on
        # narrow to non-``None``.
        return invoice_line_to_iva_observation(
            invoice_id=ledger_id,
            issued_at=devengo_date,
            invoice_kind=invoice.kind,
            iva_rate=line.iva_rate,
            base_amount=line.subtotal,
            iva_amount=line.iva_amount,
            recargo_amount=recargo_amount,
        )
    if invoice.kind is not InvoiceKind.ISSUED:
        # Both base-only casillas select the repercutido flow: these are
        # operations the taxpayer SUPPLIES. A received invoice claiming one is a
        # mis-tag, not a purchase to declare there.
        return None
    if not _counterparty_supports_the_declared_category(invoice):
        return None
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=devengo_date,
        category=category,
        # Zero rather than the exempt tier: the casillas select rate kind
        # "zero", and these operations are exempt WITH a zero rate applied to a
        # real base, which is what a base-only casilla declares.
        rate_kind=IvaRateKind.ZERO,
        # Stated, not left unset. These operations carry a real zero rate on a
        # real base, and a rate-specific binding takes only rows that say what
        # they were charged: leaving it None would make this producer's rows
        # invisible to any zero-rate box, which is the shape that made a
        # narrowed reducido binding look like a silent under-declaration.
        applied_rate=Decimal("0"),
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=line.subtotal,
        iva_amount=Decimal("0"),
        recargo_amount=recargo_amount,
    )


# The tiers that state a rate a self-assessment could be computed against.
# EXEMPT and ZERO are tiers too, but neither names a percentage to apply.
_RATED_TIERS: frozenset[IvaRateKind] = frozenset(
    {IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED},
)

# Categories where the RECIPIENT settles the cuota, so a received invoice in one
# of them owes a self-assessment the record must be able to support. Derived
# from the flow authority rather than hand-listed: a category self-assesses on
# the received side exactly when its received-side flow is the self-assessment
# one, which keeps this complete if the taxonomy grows another member.
_SELF_ASSESSED_RECIPIENT_CATEGORIES: frozenset[IvaCategory] = frozenset(
    category
    for category in IvaCategory
    if derive_flow_for_classification(category=category, invoice_direction=InvoiceKind.RECEIVED)
    is IvaFlowDirection.INVERSION_SUJETO_PASIVO
)


def _rate_kind_for_slot(slot: IvaRate) -> IvaRateKind:
    """Return the tier a line's rate slot denotes, defaulting to the exempt tier.

    Reads the shipped slot-to-tier accessor rather than re-deriving it. Only the
    not-subject slot has no tier, and an observation for it carries the exempt
    tier -- the same value the standard-case classifier produces -- so a
    declared-category observation and a rate-derived one describe the same line
    identically on this axis.
    """
    return iva_rate_kind(slot) or IvaRateKind.EXEMPT


def _reverse_charge_cuota_not_derivable(invoice: Invoice) -> bool:
    """Whether a declared reverse charge carries no rate to self-assess against.

    A reverse charge obliges the RECIPIENT to settle the cuota (LIVA art.
    84.Uno.2 for the domestic case, art. 84.Uno.2.o for an intra-community
    acquisition), and the supplier charges nothing -- so the line legitimately
    carries no cuota. What the record must still carry is the RATE the
    self-assessment applies, and an exempt-slotted line does not.

    Refusing to invent that rate is correct: it decides how much tax is owed, and
    the invoice as recorded does not state it. Refusing SILENTLY is not, which is
    why this predicate exists -- the operator is told the self-assessment could
    not be derived instead of filing a return that is quietly short.

    Scoped to the recipient side. On the supplier side the same category carries
    no self-assessment at all, and its base already reaches its own casilla.

    Args:
        invoice: The invoice being screened.

    Returns:
        ``True`` when a self-assessment is owed and the record cannot support
        computing it.
    """
    if invoice.kind is not InvoiceKind.RECEIVED:
        return False
    if invoice.iva_category not in _SELF_ASSESSED_RECIPIENT_CATEGORIES:
        return False
    # A rated slot makes the cuota derivable, whether or not it was stated: the
    # tier is on the record, which is the fact the derivation needs. An exempt or
    # zero slot is a tier without a percentage, so it supports nothing.
    return all(iva_rate_kind(line.iva_rate) not in _RATED_TIERS for line in invoice.lines)


def _claims_a_base_only_category(invoice: Invoice) -> bool:
    """Whether this invoice claims a category that a base-only casilla declares.

    Narrows the mismatch advisory to invoices that were ACTUALLY withheld from a
    casilla. A domestic exemption routes nowhere either, but it has no base-only
    casilla to reach, so reporting it would be noise about an operation that was
    never going to be declared there.
    """
    return invoice.kind is InvoiceKind.ISSUED and invoice.iva_category in _BASE_ONLY_ROUTED_CATEGORIES


def _category_counterparty_mismatch_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per invoice withheld for a category the counterparty contradicts.

    Withholding the volume is correct: an intra-community supply to a third
    country is not an intra-community supply whatever it claims, and routing it
    on the category alone would declare volume the taxpayer never supplied that
    way. What was missing is the operator being told, so a real operation left a
    declaration with nothing on any surface saying so.

    The remedy names both fields, because either could be the wrong one -- the
    category may be mis-tagged, or the counterparty country may be. The record
    does not know which, and guessing would point the operator at the wrong fix.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="invoice_category_counterparty_mismatch",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=f"invoice:{invoice.invoice_id}",
            message=(
                f"invoice {invoice.invoice_number!r} declares "
                f"{invoice.iva_category.value if invoice.iva_category else 'no category'} but its "
                f"counterparty country {invoice.counterparty_country!r} cannot bear it, so its base "
                "is NOT declared on this modelo"
            ),
            remedy=(
                "Correct either the invoice's IVA category or its counterparty country so the two "
                "agree, then recalculate so the operation reaches its casilla"
            ),
        )
        for invoice in invoices
    )


def _reverse_charge_underivable_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per received reverse charge whose cuota cannot be derived.

    The operation IS declarable and the operator is liable for the cuota; what
    is missing is the rate to compute it against. Naming the invoice and the
    missing fact is what turns a silently short return into one the operator can
    correct, and it makes the population countable -- which is what a decision
    about whether an invoice line may carry a rated slot with a zero cuota needs
    in order to be made on evidence.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="invoice_reverse_charge_cuota_not_derivable",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=f"invoice:{invoice.invoice_id}",
            message=(
                f"invoice {invoice.invoice_number!r} declares "
                f"{invoice.iva_category.value if invoice.iva_category else 'no category'}, so the "
                "recipient owes the self-assessed cuota, but no line states a rated tier to compute "
                "it from -- the cuota is NOT declared on this modelo"
            ),
            remedy=(
                "Record the rate the supply bore on the invoice line, keeping its cuota at zero, "
                "then recalculate so the self-assessment reaches its casilla"
            ),
        )
        for invoice in invoices
    )


@dataclass(frozen=True, slots=True)
class _RecargoRateDivergence:
    """One invoice whose recorded recargo departs from the published rate.

    Carries both figures and the rate that produced the expected one, because
    an advisory that states only "these disagree" cannot be acted on: the
    operator needs to see which of the two to go and check.
    """

    invoice: Invoice
    recorded: Decimal
    expected: Decimal
    applied_rate: Decimal
    recargo_rate: Decimal


def _recargo_rate_divergence(invoice: Invoice, *, devengo_date: date) -> _RecargoRateDivergence | None:
    """Compare the recorded recargo against the rate art. 161 publishes for that slot.

    The invoice stays authoritative: this reads the recorded figure and never
    replaces it. What it adds is the other half of that posture -- when the
    supplier's figure departs from the published pairing, say so.

    Silent in three cases, each for its own reason and none of them a pass:

    * no recargo recorded at all, which is the ordinary invoice and not this
      screen's business;
    * no line identifiable as the one bearing it, so there is no base to
      compare against and a guess would be worse than silence;
    * the table resolving no rate for that (applied rate, date) pairing. An
      unmodelled window must NOT read as a mismatch -- that would turn a gap in
      our own data into an accusation about the supplier's invoice.
    """
    recorded = invoice.recargo_amount
    if recorded is None or recorded == 0:
        return None
    line_index = _sole_recargo_bearing_line_index(invoice)
    if line_index is None:
        return None
    line = invoice.lines[line_index]
    applied_rate = line.iva_rate
    if applied_rate is None:
        return None
    recargo_rate = recargo_rate_for_applied_rate(applied_rate, devengo_date)
    if recargo_rate is None:
        return None
    expected = round_to_cents(line.subtotal * recargo_rate)
    if round_to_cents(recorded) == expected:
        return None
    return _RecargoRateDivergence(
        invoice=invoice,
        recorded=round_to_cents(recorded),
        expected=expected,
        applied_rate=applied_rate,
        recargo_rate=recargo_rate,
    )


def _recargo_rate_mismatch_diagnostics(
    divergences: Sequence[_RecargoRateDivergence],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per invoice whose recargo departs from the published rate.

    Advisory, never a refusal, and the filed figure is unchanged whether or not
    this fires. A legitimate invoice can carry a figure the table does not
    predict, so refusing here would block a correct filing on a correct
    invoice.

    The message names both figures and the provision. Without the provision the
    advisory reads as the application second-guessing the supplier, and an
    operator who cannot see what authority is being cited will learn to dismiss
    it -- which costs more than never having emitted it.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="invoice_recargo_departs_from_published_rate",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=f"invoice:{divergence.invoice.invoice_id}",
            message=(
                f"invoice {divergence.invoice.invoice_number!r} records a recargo de equivalencia of "
                f"{divergence.recorded}, while LIVA art. 161 pairs the {divergence.applied_rate} IVA rate "
                f"with a recargo of {divergence.recargo_rate} on that date, which would give "
                f"{divergence.expected}. The recorded figure is the one declared -- this does not change it"
            ),
            remedy=(
                "Check the supplier invoice. Where the printed recargo is right, no action is needed and "
                "the declared figure already matches it; where it was mistyped, correct the transaction "
                "and recalculate"
            ),
        )
        for divergence in divergences
    )


@dataclass(frozen=True, slots=True)
class _ScreenedInvoiceIva:
    """What the invoice IVA screen found, named rather than positional.

    Three of these five fields are ``tuple[Invoice, ...]`` and one more is a
    tuple of ids, so as a positional return they were mutually substitutable
    and a type checker could not tell a mis-ordering from correct code. That is
    not hypothetical: the tuple was widened from three slots to four and then to
    five as findings landed, the annotation fell out of step with the returns on
    the way, and every widening broke unpack sites in unrelated test modules.

    Fields:
        observations: the IVA observations the screen built.
        invoice_ids: source invoice ids behind those observations.
        compared: invoices whose IVA was compared against the ledger, so the
            caller can disclose how their period placement was arrived at.
        category_counterparty_mismatches: invoices withheld because the declared
            category and the counterparty country contradict each other.
        reverse_charge_underivable: invoices declaring a reverse charge whose
            line carries no rate slot, so no cuota can be derived without
            inventing one.
        recargo_rate_divergences: invoices whose recorded recargo departs from
            the rate art. 161 publishes for that slot. Unlike the two above,
            these are NOT withheld -- the figure is declared exactly as
            recorded and the advisory is a cross-check beside it.
    """

    observations: tuple[IvaLedgerObservation, ...] = ()
    invoice_ids: tuple[str, ...] = ()
    compared: tuple[Invoice, ...] = ()
    category_counterparty_mismatches: tuple[Invoice, ...] = ()
    reverse_charge_underivable: tuple[Invoice, ...] = ()
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()


@dataclass(frozen=True, slots=True)
class _InvoiceIvaSilenceReport:
    """The advisory surfaces the silence screen hands back to the resolver.

    Same reasoning as :class:`_ScreenedInvoiceIva`: all three fields are
    ``tuple[Invoice, ...]``, so positionally they were interchangeable. The
    annotation on the previous tuple form had already drifted to two slots while
    the code returned three, which is what an unchecked positional widening
    looks like just before it goes wrong.
    """

    compared: tuple[Invoice, ...] = ()
    category_counterparty_mismatches: tuple[Invoice, ...] = ()
    reverse_charge_underivable: tuple[Invoice, ...] = ()
    #: Carried on every return path, including the two early ones. A divergence
    #: is a fact about the recorded figure, not about whether the screen went on
    #: to build an observation, so dropping it when the screen returns early
    #: would silence the advisory exactly when the invoice is least examined.
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()


def _screened_invoice_iva_observations(
    *,
    context: CalculationSourceContext,
    period: Period,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> _ScreenedInvoiceIva:
    try:
        repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        catalogue = repository.load()
    except _STORAGE_DEGRADATION_ERRORS:
        return _ScreenedInvoiceIva()
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    compared_invoices: list[Invoice] = []
    category_counterparty_mismatches: list[Invoice] = []
    reverse_charge_underivable: list[Invoice] = []
    recargo_rate_divergences: list[_RecargoRateDivergence] = []
    for invoice in catalogue.values():
        if not _screened_invoice_in_period(invoice, context=context, period=period):
            continue
        if _reverse_charge_cuota_not_derivable(invoice):
            # Collected regardless of whether the line still produces an
            # observation: the record is now correct about the treatment and
            # still short of the cuota, so the advisory is about the missing
            # figure, not about a withheld line.
            reverse_charge_underivable.append(invoice)
        # The date the observation carries must be the date it was SELECTED on,
        # or the record would state one quarter while being declared in another.
        devengo = resolve_invoice_devengo(invoice)
        # Read before the observation loop and independently of it: the
        # comparison is about the figure the operator recorded, so it must not
        # depend on whether a line went on to contribute an observation.
        divergence = _recargo_rate_divergence(invoice, devengo_date=devengo.devengo_date)
        if divergence is not None:
            recargo_rate_divergences.append(divergence)
        recargo_line_index = _sole_recargo_bearing_line_index(invoice)
        contributed = False
        for line_index, line in enumerate(invoice.lines):
            if not _line_contributes_to_the_iva_screen(line.subtotal, line.iva_amount):
                continue
            observation = _invoice_line_iva_observation(
                invoice=invoice,
                line=line,
                line_index=line_index,
                devengo_date=devengo.devengo_date,
                recargo_amount=(
                    invoice.recargo_amount or Decimal("0") if line_index == recargo_line_index else Decimal("0")
                ),
            )
            if observation is None:
                continue
            observations.append(observation)
            invoice_ids.add(invoice.invoice_id)
            contributed = True
        if contributed:
            compared_invoices.append(invoice)
        elif _claims_a_base_only_category(invoice) and not _counterparty_supports_the_declared_category(invoice):
            # Withheld because the category and the counterparty disagree.
            # Collected so the resolver can say so: an operation removed from a
            # declaration without the operator being told is the shape this
            # whole screen exists to prevent.
            category_counterparty_mismatches.append(invoice)
    return _ScreenedInvoiceIva(
        observations=tuple(observations),
        invoice_ids=tuple(invoice_ids),
        compared=tuple(compared_invoices),
        category_counterparty_mismatches=tuple(category_counterparty_mismatches),
        reverse_charge_underivable=tuple(reverse_charge_underivable),
        recargo_rate_divergences=tuple(recargo_rate_divergences),
    )


def _sole_recargo_bearing_line_index(invoice: Invoice) -> int | None:
    """Which line the invoice-level recargo belongs to, or ``None`` if unknowable.

    The recargo is recorded once on the invoice while the M303 recargo casillas
    are per rate TIER, so attributing it needs a tier. When every cuota-bearing
    line sits at the same rate the tier is unambiguous and the recargo lands
    there.

    When the invoice spans several tiers the invoice-level field cannot say how
    the surcharge divides, and this returns ``None`` rather than guessing.
    Picking a tier would place a real amount in the wrong casilla, which is
    worse than the screen not seeing it: a mis-tiered recargo is a wrong figure
    declared confidently, where an unscreened one is only an unscreened one.
    That gap is a limit of the invoice-level field, not of this screen.
    """
    if not invoice.recargo_amount:
        return None
    cuota_lines = [index for index, line in enumerate(invoice.lines) if line.iva_amount > Decimal("0")]
    if not cuota_lines:
        return None
    tiers = {invoice.lines[index].iva_rate for index in cuota_lines}
    if len(tiers) != 1:
        return None
    return cuota_lines[0]


def _screened_invoice_in_period(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    period: Period,
) -> bool:
    """Whether this invoice's IVA belongs in the screen's ledger comparison.

    The counterparty's COUNTRY is deliberately not consulted. It was serving as
    a proxy for "carries Spanish IVA", and it is a poor one in both directions:
    an invoice to a foreign customer can carry ordinary Spanish cuota -- goods
    that never leave the país, a service localised here, a non-established
    consumer -- and those were silently exempt from the screen, which is the
    under-declaration it exists to catch. Meanwhile an exempt entrega
    intracomunitaria to an EU customer carries no cuota at all, so including it
    costs nothing.

    The property the screen actually needs is "does this line carry a positive
    cuota", and the caller already tests exactly that per line. Removing the
    country proxy therefore widens the screen without widening what it
    compares: a zero-cuota invoice contributes no observation whatever its
    counterparty's country, so no false refusal is introduced.

    Bucket attribution follows the same rule the invoice source resolver uses:
    only a POPULATED, mismatching bucket excludes. An unattributed invoice
    belongs to the store it was loaded from, and comparing on the bucket id
    alone dropped it from the screen silently -- the same shape, in the guard
    rather than in the projection.
    """
    return (invoice.bucket_id is None or invoice.bucket_id == context.bucket_id) and invoice_devengo_in_period(
        invoice, period=period
    )


def _out_of_window_summary_diagnostics(
    summary: OutOfWindowTransactionSummary | None,
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if summary is None:
        return ()
    return (
        out_of_window_summary_source_diagnostic(
            source_kind=source_kind,
            resolver_id=resolver_id,
            count=summary.count,
            min_filing_date=summary.min_filing_date,
            max_filing_date=summary.max_filing_date,
        ),
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
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        ) from exc
    if not resolved.has_date_span():
        raise AggregationValidationError(
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        )
    return resolved


def _iva_prorrata_apportionment_provenance(
    revision: ModeloRevision,
    period: Period,
    apportionment: IvaLedgerProrrataApportionment | None,
) -> tuple[CalculationSourceProvenance, ...]:
    if apportionment is None:
        return ()
    casillas = _iva_deducible_cuota_casillas(revision)
    return (
        CalculationSourceProvenance(
            source_kind="ledger_iva_aggregation",
            source_ref=_iva_prorrata_apportionment_source_ref(period, apportionment),
            legal_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.legal_refs)),
            source_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.source_refs)),
        ),
    )


def _iva_prorrata_apportionment_source_ref(
    period: Period,
    apportionment: IvaLedgerProrrataApportionment,
) -> str:
    source_ref = (
        f"prorrata-apportionment:{period.filing_year}:{apportionment.regime.value}:"
        f"percentage:{apportionment.percentage}:provenance:{apportionment.provenance.value}"
    )
    if apportionment.source_observation_ref is not None:
        source_ref = f"{source_ref}:source-observation:{apportionment.source_observation_ref}"
    return source_ref


def _iva_deducible_cuota_casillas(revision: ModeloRevision) -> tuple[CasillaDefinition, ...]:
    ledger_iva_amount_bindings = {
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        and getattr(binding.selector, "fact", "iva_amount_sum") == "iva_amount_sum"
    }
    return tuple(
        casilla
        for casilla in revision.casillas
        if "deducible" in casilla.section
        and any(
            binding_id is not None and binding_id in ledger_iva_amount_bindings
            for binding_id in (casilla.binding, *casilla.alternate_bindings)
        )
    )


def _revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def _empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)


#: The ONE canonical retenciones aggregation dispatch: every retenciones modelo
#: mapped to its validated per-perceptor aggregator. This single table is shared by
#: BOTH the live calculate mesh (:meth:`RetencionesAggregationSourceResolver.resolve`)
#: and the per-modelo aggregation service (:func:`~._service.aggregate_per_modelo`,
#: the CLI ``aggregate`` / pull surface), so the two paths cannot drift
#: (``aeat-calculation-aggregation``).
#:
#: The calculate path is scoped to the modelos whose registry declares a
#: ``retenciones_aggregation`` binding (111/115/180/193 today) by the resolver's
#: binding-guard (:func:`_revision_has_binding_source`), NOT by membership of this
#: table — so the scoping tracks the registry, not a hand-maintained sub-list.
#: Modelo 115 uses the quarterly URBAN_RENTAL aggregate for casillas 01/02; modelos
#: 180/193 use the annual aggregate for the distinct-NIF perceptor count (their
#: monetary totals remain on relation-prefill). Modelos 123 and 190 declare no
#: ``retenciones_aggregation`` binding, so they never resolve on the calculate path;
#: they are pull/service-only here. Modelo 190's calculate-path count is
#: "percepciones", a distinct perceptor/clave/subclave figure handled by
#: :class:`~._withholding_source.WithholdingSourceResolver`.
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

    resolver_id = "retenciones_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.RETENCIONES_AGGREGATION,)

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
            suggestion = (
                "Supply the per-perceptor retención observations "
                "(`aeat app modelo aggregate --retencion-observation`) before calculating."
            )
            if str(context.modelo) == Modelo.M111.value:
                suggestion = (
                    "Supply the per-perceptor retención observations "
                    "(`aeat app modelo aggregate --retencion-observation`) if any renta subject to "
                    "retención or ingreso a cuenta was paid. If none was paid, do not file an all-blank "
                    "Modelo 111; record the no-obligation period with "
                    f"`aeat config profile edit PROFILE --quiet --modelo-111-no-retenciones-periods "
                    f"{context.filing_year}:{context.period.registry_token}` before verifying M190."
                )
            raise AggregationValidationError(
                t("aggregation.retenciones.errors.perceptor_observations_missing"),
                context={
                    "modelo": str(context.modelo),
                    "filing_year": str(context.filing_year),
                    "period": context.period.registry_token,
                    "source_kind": "retenciones_aggregation",
                },
                suggestion=suggestion,
            )
        aggregation = self.aggregate(str(context.modelo), tuple(observations), period=context.period)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
            diagnostics=administrador_retencion_rate_advisory_observations(observations),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="retenciones_aggregation",
                    source_ref=f"perceptor:{rollup.perceptor_nif}",
                )
                for rollup in aggregation.rollups
            ),
        )


def _renta_observation_provenance(
    observation: RentaDeductibleExpenseObservation,
) -> tuple[CalculationSourceProvenance, ...]:
    provenance = [
        CalculationSourceProvenance(
            source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
            source_ref=f"transaction:{observation.transaction_id}",
        ),
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
            ),
        )
    return tuple(provenance)


__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "aggregation_period_for_modelo",
]
