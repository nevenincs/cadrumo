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
:class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository` only as supporting
evidence: Modelo 303 domestic IVA remains ledger-owned, while Renta expense
aggregation can attach purchase-invoice evidence to transaction rows before
producing the shared :class:`~._source_mesh.CalculationSourceResolution`.

Declarable observations that no registry binding consumes are reported as
source diagnostics rather than silently blanking the filed calculation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core import M210GrossIncomeSourceMode
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.modelo import Modelo
from ...core.money import round_to_cents
from ...core.period import Period, PeriodError, StandardPeriodCode
from ...domain.bienes_inversion import BienesInversionIvaRegister
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.irnr_ledger_bindings import (
    resolve_ledger_irnr_income_aggregation_binding_values,
    unsupported_ledger_irnr_income_observations,
)
from ...domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    UngroundedRentaIncome,
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    structurally_unroutable_iva_base_categories,
    ungrounded_ledger_renta_income_observations,
    unrouted_ledger_iva_quantities,
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_iva_observations,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
    unsupported_ledger_renta_income_observations,
)
from ...domain.calculations.registry.ledger_impatriado_bindings import (
    resolve_ledger_impatriado_income_aggregation_binding_values,
    unsupported_ledger_impatriado_income_observations,
)
from ...domain.calculations.registry.retenciones_bindings import resolve_retenciones_aggregation_binding_values
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.invoices.enums import IvaRate, iva_rate_kind, iva_rate_slot_percentage
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.flow import IvaFlowDirection, derive_flow_for_classification, is_deducible_flow
from ...domain.iva.invoice_classification import invoice_line_to_iva_observation
from ...domain.iva.recargo_equivalencia import recargo_rate_for_applied_rate
from ...domain.iva.schema import EUMemberState, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow
from ...domain.prorrata_register import ProrrataRegisterRepositoryProtocol
from ...domain.renta import (
    RENTA_130_RETENCIONES_BINDING_ID,
    RENTA_130_RETENCIONES_OUTPUT_CASILLA,
    RentaDeductibleExpenseObservation,
)
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.transactions.models import OutOfWindowTransactionSummary
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.usage_ratios import UsageRatioPersistenceError
from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios
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
from ._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from ._renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from ._renta_income_ledger import (
    aggregate_renta_income_ledger_from_repositories,
    aggregate_renta_m100_income_ledger_from_repositories,
    aggregate_renta_m131_agrario_income_ledger_from_repositories,
)
from ._renta_income_ledger import (
    fitted_diagnostic_id_list as _fitted_id_list,
)
from ._renta_income_ledger import (
    unusable_sales_invoice_diagnostics as _unusable_sales_invoice_diagnostics,
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
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    out_of_window_summary_source_diagnostic,
    source_issue_diagnostics,
    storage_degradation_resolution,
)
from ._source_mesh import (
    flatten_source_provenance_for as _flattened_provenance_for,
)
from ._source_mesh import (
    sorted_source_ids as _sorted_ids,
)
from ._source_mesh import (
    source_diagnostics_for as _diagnostics_for,
)
from ._source_mesh import (
    source_provenance_for as _provenance_for,
)
from ._undeclared_activity_advisory import undeclared_activity_income_advisory_observations
from .errors import AggregationValidationError, t

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

    resolver_id: ClassVar[str] = "ledger_iva_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IVA_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        investment_asset_register: BienesInversionIvaRegister | None = None,
        investment_asset_profile_id: str | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository
        self._prorrata_register_repository = prorrata_register_repository
        self._investment_asset_register = investment_asset_register
        self._investment_asset_profile_id = investment_asset_profile_id

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
                prorrata_register_repository=self._prorrata_register_repository,
                investment_asset_register=self._investment_asset_register,
                investment_asset_profile_id=self._investment_asset_profile_id,
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
            ledger_observations=aggregation.observations,
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
            + _missing_invoice_deduction_authority_diagnostics(
                silence_report.deduction_authority_missing,
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
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                suppressed_reasons=_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS,
            )
            + _diagnostics_for(
                unconsumed,
                reason="unrouted_observation",
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                message=lambda observation: (
                    f"declarable IVA observation {observation.ledger_id!r} "
                    f"(category={observation.category.value!r}, rate_kind={observation.rate_kind.value!r}, "
                    f"flow_direction={observation.flow_direction.value!r}) is not consumed by any "
                    f"ledger_iva_aggregation binding on revision {context.revision.id!r}; "
                    "its base/cuota is not declared on this calculation"
                ),
            )
            + _diagnostics_for(
                unrouted_quantities,
                reason="unrouted_declarable_quantity",
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                message=lambda quantity: (
                    f"{len(quantity.observations)} IVA row(s) carry {quantity.total} EUR of "
                    f"{quantity.fact!r} in categories "
                    f"{_residue_categories(quantity.observations)}, which no ledger_iva_aggregation "
                    f"binding on revision {context.revision.id!r} draws for those categories; that "
                    f"amount is not declared on this calculation. The rows themselves ARE consumed "
                    f"for their other quantities, so no other screen reports them"
                ),
            )
            + _diagnostics_for(
                unroutable_categories,
                reason="structurally_unroutable_base_category",
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                message=lambda category: (
                    f"IVA category {category.value!r} appears on this period's ledger, and no "
                    f"ledger_iva_aggregation binding on revision {context.revision.id!r} could ever draw "
                    "its taxable base, for any row of that category -- not merely for the rows seen this "
                    "period. Cuota is legitimately zero or already declared elsewhere for this category, "
                    "so no tax is lost, but the base amount itself is not represented in this filing"
                ),
            ),
            provenance=(
                _provenance_for(
                    aggregation.observations,
                    lambda observation: CalculationSourceProvenance(
                        resolver_id=self.resolver_id,
                        resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                        contributor_source_kind="ledger_iva_aggregation",
                        contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                        lineage_role=CalculationSourceLineageRole.PRIMARY,
                        source_ref=f"transaction:{observation.ledger_id}",
                        parent_source_ref=None,
                    ),
                )
                + _provenance_for(
                    aggregation.prorrata_references,
                    lambda reference: CalculationSourceProvenance(
                        resolver_id=self.resolver_id,
                        resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                        contributor_source_kind="ledger_iva_aggregation",
                        contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                        lineage_role=CalculationSourceLineageRole.PRIMARY,
                        source_ref=f"prorrata:{reference.transaction_id}",
                        parent_source_ref=None,
                    ),
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

    resolver_id: ClassVar[str] = "ledger_renta_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,)

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
            source_transaction_ids=_sorted_ids(
                aggregation.observations, lambda observation: observation.transaction_id
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
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
            ),
            provenance=_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_renta_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                ),
            ),
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
        f"credit is also lost, since it needs the same missing base. Classify each transaction "
        f"in the ledger with its taxable base. Transactions: "
    )
    return (
        CalculationSourceDiagnostic(
            reason="ungrounded_income_substrate",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=preamble + _fitted_id_list(sampled, budget=DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(preamble)),
        ),
    )


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

    resolver_id: ClassVar[str] = "ledger_impatriado_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,)

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
            source_transaction_ids=_sorted_ids(
                aggregation.observations, lambda observation: observation.transaction_id
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
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
            provenance=_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_impatriado_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                ),
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

    resolver_id: ClassVar[str] = "ledger_irnr_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,)

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
            source_transaction_ids=_sorted_ids(
                aggregation.observations, lambda observation: observation.transaction_id
            ),
            diagnostics=_out_of_window_summary_diagnostics(
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
            provenance=_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_irnr_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
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


class LedgerRentaGastosPagoFraccionadoAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 deductible-expense (gasto) bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION`. This is the
    OUTGOING sibling of :class:`LedgerRentaIncomeAggregationSourceResolver`: it
    folds deductible business expenses into Modelo 130 casilla 02 over the same
    cumulative year-to-date quarterly window and emits an unrouted-observation
    diagnostic for declarable gastos no binding consumes.
    """

    resolver_id: ClassVar[str] = "ledger_renta_gastos_pago_fraccionado_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
    )

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._prorrata_register_repository = prorrata_register_repository

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
                prorrata_register_repository=self._prorrata_register_repository,
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
            source_transaction_ids=_sorted_ids(
                aggregation.observations, lambda observation: observation.transaction_id
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
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
            provenance=_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
                    contributor_source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                ),
            ),
        )


def _uncovered_withheld_invoice_cuota(
    invoices: Sequence[Invoice],
    *,
    screened_bindings: tuple[BindingId, ...],
    transaction_binding_values: Mapping[BindingId, Decimal],
) -> Decimal:
    """Return the withheld invoices' cuota that the transaction ledger does not carry.

    These invoices were withheld because no linked frozen ledger observation
    supplies their deduction identity, so they contribute no
    :class:`IvaLedgerObservation` and cannot be compared binding-by-binding the
    way a projected invoice is. Their cuota is therefore weighed against the
    transaction-ledger total across the screened cuota bindings.

    That total is the right comparator rather than a per-binding one: the
    withheld invoice has no resolved binding to be compared against, and the
    question being asked is the coarse one -- is this cuota already somewhere in
    the ledger the filing is about to use, or is it absent from it entirely? A
    positive result means the ledger is genuinely short by at least this much and
    the filing would under-declare; zero means the operation is already recorded
    and the invoice merely is not linked to it.
    """
    if not invoices:
        return Decimal("0")
    evidence = sum(
        (
            line.iva_amount
            for invoice in invoices
            for line in invoice.lines
            if _line_contributes_to_the_iva_screen(line.subtotal, line.iva_amount)
        ),
        Decimal("0"),
    )
    ledger_total = sum(
        (transaction_binding_values.get(binding_id, Decimal("0")) for binding_id in screened_bindings),
        Decimal("0"),
    )
    return max(evidence - ledger_total, Decimal("0"))


def _raise_if_invoice_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    period: Period,
    transaction_binding_values: Mapping[BindingId, Decimal],
    ledger_observations: Sequence[IvaLedgerObservation] = (),
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
        ledger_observations=ledger_observations,
        invoice_repository=invoice_repository,
    )
    return _raise_if_screened_invoice_iva_would_be_silent(
        context=context,
        screened_bindings=screened_bindings,
        screened=screened,
        transaction_binding_values=transaction_binding_values,
        prorrata_apportionment=prorrata_apportionment,
    )


def _raise_if_screened_invoice_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    screened_bindings: tuple[BindingId, ...],
    screened: _ScreenedInvoiceIva,
    transaction_binding_values: Mapping[BindingId, Decimal],
    prorrata_apportionment: IvaLedgerProrrataApportionment | None,
) -> _InvoiceIvaSilenceReport:
    """Compare screened invoice facts with the canonical ledger projection.

    The repository-backed wrapper owns acquisition and period screening. This
    deterministic half owns the one refusal policy over that frozen result, so
    callers and proofs use the same IVA binding projector and terminal facts.
    """
    # Withholding an unauthorised input row is unconditional; REFUSING the whole
    # filing over it is not. This guard's criterion, stated in its own docstring,
    # is invoice IVA that would EXCEED the transaction-ledger cuota -- that is the
    # under-declaration. An unlinked purchase invoice whose cuota the ledger
    # already carries is corroborating evidence of an operation that IS declared,
    # so refusing there blocks a filing whose totals are correct. It stays
    # withheld (no invented deduction family reaches a casilla) and the operator
    # is told through the diagnostic channel instead.
    uncovered_authority_evidence = _uncovered_withheld_invoice_cuota(
        screened.deduction_authority_missing,
        screened_bindings=screened_bindings,
        transaction_binding_values=transaction_binding_values,
    )
    if uncovered_authority_evidence > Decimal("0"):
        missing_invoice_ids = tuple(sorted(invoice.invoice_id for invoice in screened.deduction_authority_missing))
        raise AggregationValidationError(
            t("errors.error.error_modelo_aggregation_binding"),
            context={
                "reason": "invoice_deduction_authority_missing_from_transaction_ledger",
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "ledger_iva_aggregation",
                "invoice_ids": missing_invoice_ids[:_M303_INVOICE_EVIDENCE_SAMPLE_LIMIT],
                "invoice_count": str(len(missing_invoice_ids)),
                "invoice_cuota_exceeding_ledger": str(uncovered_authority_evidence),
            },
            precondition_verdict=aggregation_no_recovery_verdict(
                AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
                facts={
                    "modelo": str(context.modelo),
                    "filing_year": str(context.filing_year),
                    "period": context.period.registry_token,
                    "source_kind": "ledger_iva_aggregation",
                    "invoice_count": len(missing_invoice_ids),
                    "missing_binding_count": 0,
                },
            ),
        )
    if not screened.observations:
        return _InvoiceIvaSilenceReport(
            category_counterparty_mismatches=screened.category_counterparty_mismatches,
            reverse_charge_underivable=screened.reverse_charge_underivable,
            deduction_authority_missing=screened.deduction_authority_missing,
            recargo_rate_divergences=screened.recargo_rate_divergences,
            storage_degraded=screened.storage_degraded,
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
            deduction_authority_missing=screened.deduction_authority_missing,
            recargo_rate_divergences=screened.recargo_rate_divergences,
            storage_degraded=screened.storage_degraded,
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
        precondition_verdict=aggregation_no_recovery_verdict(
            AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
            facts={
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "ledger_iva_aggregation",
                "invoice_count": len(screened.invoice_ids),
                "missing_binding_count": len(missing_binding_values),
            },
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
    intra-community supply on the acquirer holding an IVA IDENTIFICATION assigned
    by another Member State, so that arm reads
    ``counterparty_identification_state``. The export arm is the one genuinely
    about place -- an export leaves the Union -- so it keeps reading the
    counterparty's country of establishment.

    Reading the country for BOTH was a defect that landed in money in both
    directions: a Spanish-established acquirer holding a German IVA number had
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
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
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
        deduction_authority: Exact frozen transaction-ledger authority linked
            to a received invoice, or ``None`` for an issued invoice.
        category: The invoice's own declared category, already read and
            confirmed non-``None`` by the caller -- it is what keyed the
            ``_DECLARED_CATEGORY_BASE_ONLY_FLOWS`` lookup that selected
            *flow_direction*.
        flow_direction: The flow this category implies, from the table above.
        base_amount_eur: ``line.subtotal`` already converted to EUR by the
            caller (see :func:`_invoice_line_iva_observation`).
        iva_amount_eur: ``line.iva_amount`` already converted to EUR, same
            shape as *base_amount_eur*.

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
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
        deduction_fact_kind=None,
        deduction_provenance=None,
        recargo_amount=recargo_amount,
    )
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=devengo_date,
        category=category,
        rate_kind=measured.rate_kind,
        applied_rate=measured.applied_rate,
        flow_direction=flow_direction,
        base_amount=base_amount_eur,
        iva_amount=Decimal("0"),
        recargo_amount=recargo_amount,
        deduction_fact_kind=None,
        deduction_provenance=None,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _invoice_line_iva_observation(
    *,
    invoice: Invoice,
    line: InvoiceLine,
    line_index: int,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: IvaLedgerObservation | None = None,
) -> IvaLedgerObservation | None:
    """Project one invoice line into the observation the screen declares from.

    Received invoice evidence never supplies its own deduction identity. Both
    SOPORTADO and INVERSION_SUJETO_PASIVO observations require the exact
    statutory deduction family and immutable classification provenance, and an
    invoice aggregate owns neither. They arrive as ``deduction_authority`` --
    the frozen transaction-ledger observation the invoice is linked to -- and
    are copied across unchanged. When no such authority is linked, or the
    linked ones disagree, the enclosing screen withholds the invoice entirely
    rather than invite an invented domestic-current default.

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
    category. Both cases are withheld rather than mis-routed.

    Args:
        invoice: The invoice the line belongs to, read for its declared
            category and counterparty country.
        line: The line being projected.
        line_index: Position of the line, folded into the observation id.
        devengo_date: The date the observation is declared on.
        recargo_amount: Recargo attributable to this line, already resolved.
        base_amount_eur: ``line.subtotal`` already converted to EUR via
            :meth:`~domain.invoices.Invoice.line_amount_eur` -- the caller
            gates on a resolvable EUR amount before this is ever invoked, so
            every downstream construction reads this instead of the line's
            own native-currency field.
        iva_amount_eur: ``line.iva_amount`` already converted to EUR, same
            shape as *base_amount_eur*.
        deduction_authority: Exact frozen transaction-ledger authority linked
            to a received invoice, or ``None`` for an issued invoice.

    Returns:
        The observation to declare from, or ``None`` when the line routes
        nowhere.
    """
    ledger_id = f"invoice:{invoice.invoice_id}:{line_index}"
    if iva_amount_eur > Decimal("0"):
        return _standard_invoice_line_iva_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
            deduction_authority=deduction_authority,
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
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
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
        return _declared_category_unrouted_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            category=category,
            deduction_authority=deduction_authority,
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
        )
    if category is None or category not in _BASE_ONLY_ROUTED_CATEGORIES:
        # No declared treatment at all: the rate slot is the only signal there
        # is, and the standard-case classification is the right reading of it.
        # ``category is None`` is folded into this membership test rather than
        # left implicit -- ``None`` is never a member of
        # ``_BASE_ONLY_ROUTED_CATEGORIES`` so the outcome is unchanged, but the
        # explicit check is what lets every use of ``category`` from here on
        # narrow to non-``None``.
        return _standard_invoice_line_iva_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
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
        base_amount=base_amount_eur,
        iva_amount=Decimal("0"),
        recargo_amount=recargo_amount,
        deduction_fact_kind=None,
        deduction_provenance=None,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _standard_invoice_line_iva_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: IvaLedgerObservation | None = None,
) -> IvaLedgerObservation:
    """Project a rate-classified line, preserving linked ledger deduction facts."""
    return invoice_line_to_iva_observation(
        invoice_id=ledger_id,
        issued_at=devengo_date,
        invoice_kind=invoice.kind,
        iva_rate=line.iva_rate,
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
        recargo_amount=recargo_amount,
        deduction_fact_kind=(deduction_authority.deduction_fact_kind if deduction_authority is not None else None),
        deduction_provenance=(deduction_authority.deduction_provenance if deduction_authority is not None else None),
        investment_asset_id=(deduction_authority.investment_asset_id if deduction_authority is not None else None),
        rectifies_ledger_id=(deduction_authority.rectifies_ledger_id if deduction_authority is not None else None),
    )


def _declared_category_unrouted_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    category: IvaCategory,
    deduction_authority: IvaLedgerObservation | None,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
) -> IvaLedgerObservation | None:
    """Retain a declared non-base-only category without inventing a rate.

    Returns ``None`` for an INPUT-side flow carrying no linked ledger authority.
    The observation model refuses such a row outright -- an input fact must name
    its exact deduction family and evidence provenance -- so building one here
    would surface as a validation crash rather than the withholding the enclosing
    contract promises. The screen already classifies this invoice as
    ``deduction_authority_missing`` and the silence guard refuses on it, so the
    honest local answer is that the line routes nowhere.
    """
    flow_direction = derive_flow_for_classification(category=category, invoice_direction=invoice.kind)
    # Mirrors the observation model's own admission rule exactly, via the
    # canonical settlement-side predicate rather than a re-listed flow set:
    # recargo de equivalencia is borne, not deducted, so it is an output fact
    # and must NOT carry deduction authority (LIVA art. 161).
    requires_deduction_authority = (
        is_deducible_flow(flow_direction) and category is not IvaCategory.RECARGO_EQUIVALENCIA
    )
    if requires_deduction_authority and deduction_authority is None:
        return None
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=devengo_date,
        category=category,
        rate_kind=_rate_kind_for_slot(line.iva_rate),
        applied_rate=None,
        flow_direction=flow_direction,
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
        recargo_amount=recargo_amount,
        deduction_fact_kind=(deduction_authority.deduction_fact_kind if deduction_authority is not None else None),
        deduction_provenance=(deduction_authority.deduction_provenance if deduction_authority is not None else None),
        investment_asset_id=(deduction_authority.investment_asset_id if deduction_authority is not None else None),
        rectifies_ledger_id=(deduction_authority.rectifies_ledger_id if deduction_authority is not None else None),
        # A monetary projection, so the settlement role. The informational role
        # is reserved for the criterio-de-caja art. 75 operation rows, which
        # this producer never emits.
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
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
    return _diagnostics_for(
        invoices,
        reason="invoice_category_counterparty_mismatch",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            f"{invoice.iva_category.value if invoice.iva_category else 'no category'} but its "
            f"counterparty country {invoice.counterparty_country!r} cannot bear it, so its base "
            "is NOT declared on this modelo"
        ),
        remedy=lambda _invoice: (
            "Correct either the invoice's IVA category or its counterparty country so the two "
            "agree, then recalculate so the operation reaches its casilla"
        ),
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
    return _diagnostics_for(
        invoices,
        reason="invoice_reverse_charge_cuota_not_derivable",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            f"{invoice.iva_category.value if invoice.iva_category else 'no category'}, so the "
            "recipient owes the self-assessed cuota, but no line states a rated tier to compute "
            "it from -- the cuota is NOT declared on this modelo"
        ),
        remedy=lambda _invoice: (
            "Record the rate the supply bore on the invoice line, keeping its cuota at zero, "
            "then recalculate so the self-assessment reaches its casilla"
        ),
    )


def _missing_invoice_deduction_authority_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report received invoice evidence that reached no IVA input row.

    An invoice has an amount and a direction, but not the statutory deduction
    fact family nor the immutable evidence provenance that distinguishes a
    domestic current expense from an investment, import, acquisition, or
    rectification. Treating every received invoice as domestic-current would
    invent that authority, so the invoice is withheld instead.

    Non-blocking by the time it reaches here: the enclosing guard has already
    established that the transaction ledger carries this cuota, so the filing's
    totals are correct and only the invoice-to-transaction link is absent. Where
    the ledger does NOT carry it the guard refuses outright and this diagnostic
    is never reached.
    """
    return _diagnostics_for(
        invoices,
        reason="source_issue",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"received invoice {invoice.invoice_number!r} carries IVA input evidence but no exact "
            "deduction fact kind or immutable evidence provenance, so it is declared from the "
            "transaction ledger rather than from the invoice"
        ),
        remedy=lambda _invoice: (
            "Link this invoice to its classified ledger transaction, so its deduction family and "
            "evidence provenance are recorded against the operation"
        ),
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
    # The line carries a rate SLOT, not a number, and the table is keyed on the
    # number. Converted through the UNDATED derivation on purpose: the dated one
    # re-asks whether the slot was in force, which the invoice validator has
    # already established at construction, and asking it again here against a
    # different date would refuse a line the record legitimately holds.
    applied_rate = iva_rate_slot_percentage(line.iva_rate)
    if applied_rate is None:
        # Exempt and not-subject slots name no percentage, so there is no
        # pairing to look up and nothing to disagree with.
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
            # No casilla is addressable here -- the comparison is per invoice,
            # not per casilla -- so the LIVA art. 161 provision the message
            # names is declared rather than read off a registry object.
            asserted_legal_refs=("ley-37-1992:art-161",),
        )
        for divergence in divergences
    )


@dataclass(frozen=True, slots=True)
class _ScreenedInvoiceIva:
    """What the invoice IVA screen found, named rather than positional.

    Several fields are ``tuple[Invoice, ...]`` and one more is a tuple of ids,
    so as a positional return they would be mutually substitutable and a type
    checker could not tell a mis-ordering from correct code. That is not
    hypothetical: the tuple was widened repeatedly as findings landed, the
    annotation fell out of step with the returns on the way, and every widening
    broke unpack sites in unrelated test modules.

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
        deduction_authority_missing: received invoices whose lines contribute
            IVA evidence but which are linked to no frozen transaction-ledger
            observation carrying the exact deduction family and immutable
            evidence provenance an input row requires, or whose linked
            observations disagree about it.
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
    deduction_authority_missing: tuple[Invoice, ...] = ()
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()
    #: The catalogue could not be READ, as distinct from holding no invoices.
    #: Without this the two are the same value downstream, and the silence guard
    #: returns as though it had compared a catalogue it never saw.
    storage_degraded: bool = False


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
    #: Received invoices withheld for want of a linked ledger deduction
    #: authority, whose cuota the transaction ledger nonetheless already carries.
    #: Not a refusal -- the filing's totals are right -- but the operator still
    #: needs telling, or the unlinked invoice looks reconciled when it is not.
    deduction_authority_missing: tuple[Invoice, ...] = ()
    #: Carried on every return path, including the two early ones. A divergence
    #: is a fact about the recorded figure, not about whether the screen went on
    #: to build an observation, so dropping it when the screen returns early
    #: would silence the advisory exactly when the invoice is least examined.
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()
    #: The screen could not read the invoice catalogue, so it reached NO verdict
    #: about whether invoice IVA is absent from the ledger totals. Distinct from
    #: a clean pass, which is what a silent empty return looked like.
    storage_degraded: bool = False


@dataclass(frozen=True, slots=True)
class _ScreenedInvoiceIvaResult:
    """One invoice's screen facts, kept separate from the aggregate result."""

    observations: tuple[IvaLedgerObservation, ...]
    reverse_charge_underivable: bool
    recargo_rate_divergence: _RecargoRateDivergence | None
    deduction_authority_missing: bool
    category_counterparty_mismatch: bool


def _screened_invoice_iva_observations(
    *,
    context: CalculationSourceContext,
    period: Period,
    ledger_observations: Sequence[IvaLedgerObservation] = (),
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> _ScreenedInvoiceIva:
    try:
        repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        catalogue = repository.load()
    except _STORAGE_DEGRADATION_ERRORS:
        # Degrading is right: a bucket whose invoice catalogue is temporarily
        # unreadable should not hard-fail every calculation, and the five
        # sibling catches in this module degrade too. What they also do, and
        # this one did not, is SAY SO -- they bind the error and return a
        # resolution carrying a storage_degraded diagnostic. Returning an empty
        # result here made an unreadable catalogue indistinguishable from an
        # empty one, which switched the silence guard off without a signal.
        return _ScreenedInvoiceIva(storage_degraded=True)
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    compared_invoices: list[Invoice] = []
    category_counterparty_mismatches: list[Invoice] = []
    reverse_charge_underivable: list[Invoice] = []
    deduction_authority_missing: list[Invoice] = []
    recargo_rate_divergences: list[_RecargoRateDivergence] = []
    for invoice in catalogue.values():
        if not _screened_invoice_in_period(invoice, context=context, period=period):
            continue
        screened = _screened_invoice_iva_result(
            invoice,
            ledger_observations=ledger_observations,
        )
        if screened.reverse_charge_underivable:
            reverse_charge_underivable.append(invoice)
        if screened.recargo_rate_divergence is not None:
            recargo_rate_divergences.append(screened.recargo_rate_divergence)
        if screened.deduction_authority_missing:
            deduction_authority_missing.append(invoice)
            continue
        if screened.observations:
            observations.extend(screened.observations)
            invoice_ids.add(invoice.invoice_id)
            compared_invoices.append(invoice)
        elif screened.category_counterparty_mismatch:
            category_counterparty_mismatches.append(invoice)
    return _ScreenedInvoiceIva(
        observations=tuple(observations),
        invoice_ids=tuple(invoice_ids),
        compared=tuple(compared_invoices),
        category_counterparty_mismatches=tuple(category_counterparty_mismatches),
        reverse_charge_underivable=tuple(reverse_charge_underivable),
        deduction_authority_missing=tuple(deduction_authority_missing),
        recargo_rate_divergences=tuple(recargo_rate_divergences),
    )


def _screened_invoice_iva_result(
    invoice: Invoice,
    *,
    ledger_observations: Sequence[IvaLedgerObservation],
) -> _ScreenedInvoiceIvaResult:
    """Resolve one already-period-selected invoice into its IVA screen facts."""
    reverse_charge_underivable = _reverse_charge_cuota_not_derivable(invoice)
    # The date the observation carries must be the date it was SELECTED on,
    # or the record would state one quarter while being declared in another.
    devengo = resolve_invoice_devengo(invoice)
    # Read independently of the line projection: comparison is about the
    # recorded figure, not whether a line goes on to contribute an observation.
    recargo_rate_divergence = _recargo_rate_divergence(invoice, devengo_date=devengo.devengo_date)
    deduction_authority = _linked_invoice_deduction_authority(
        invoice,
        ledger_observations=ledger_observations,
    )
    deduction_authority_missing = (
        invoice.kind is InvoiceKind.RECEIVED
        and any(line.iva_amount > Decimal("0") for line in invoice.lines)
        and deduction_authority is None
    )
    observations: tuple[IvaLedgerObservation, ...] = ()
    if not deduction_authority_missing:
        observations = _screened_invoice_line_observations(
            invoice,
            devengo_date=devengo.devengo_date,
            deduction_authority=deduction_authority,
        )
    return _ScreenedInvoiceIvaResult(
        observations=observations,
        reverse_charge_underivable=reverse_charge_underivable,
        recargo_rate_divergence=recargo_rate_divergence,
        deduction_authority_missing=deduction_authority_missing,
        category_counterparty_mismatch=(
            not observations
            and not deduction_authority_missing
            and _claims_a_base_only_category(invoice)
            and not _counterparty_supports_the_declared_category(invoice)
        ),
    )


def _screened_invoice_line_observations(
    invoice: Invoice,
    *,
    devengo_date: date,
    deduction_authority: IvaLedgerObservation | None,
) -> tuple[IvaLedgerObservation, ...]:
    """Return the line observations eligible for one invoice comparison."""
    recargo_line_index = _sole_recargo_bearing_line_index(invoice)
    observations: list[IvaLedgerObservation] = []
    for line_index, line in enumerate(invoice.lines):
        if not _line_contributes_to_the_iva_screen(line.subtotal, line.iva_amount):
            continue
        if invoice.kind is InvoiceKind.RECEIVED and line.iva_amount == Decimal("0"):
            continue
        # line.subtotal / line.iva_amount are denominated in invoice.currency
        # (InvoiceLine carries no currency of its own); IvaLedgerObservation's
        # base_amount/iva_amount are EUR-denominated (they feed M303 casillas
        # directly), so this converts through the same fx_rate resolution the
        # invoice-level totals already use, rather than folding the invoice's
        # native fields straight in. A line whose invoice cannot itself resolve
        # a EUR amount (foreign currency, unconverted) REFUSES -- by operator
        # ruling ("aim for explicit red signals... until schema and api
        # converges"), a would-be-silently-dropped declarable line is a hard
        # stop, not an advisory beside a smaller-but-green figure. Fail-closed
        # AND loud, not fail-closed-and-quiet.
        base_amount_eur = invoice.line_amount_eur(line.subtotal)
        iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
        if base_amount_eur is None or iva_amount_eur is None:
            raise AggregationValidationError(
                t("aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"),
                context={
                    "invoice_id": invoice.invoice_id,
                    "invoice_number": invoice.invoice_number,
                    "currency": invoice.currency,
                    "line_index": str(line_index),
                },
            )
        # recargo_amount_eur is None both for "no recargo declared" and for
        # "unconverted" (same shape as the six sibling _eur properties), but
        # the base/iva check above already proved this invoice resolves a EUR
        # rate, so a None here can only mean the former -- defaulting to zero
        # is the genuine-absence case, not a silently dropped recargo.
        recargo_amount_eur = invoice.recargo_amount_eur or Decimal("0")
        observation = _invoice_line_iva_observation(
            invoice=invoice,
            line=line,
            line_index=line_index,
            devengo_date=devengo_date,
            recargo_amount=(recargo_amount_eur if line_index == recargo_line_index else Decimal("0")),
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
            deduction_authority=deduction_authority,
        )
        if observation is not None:
            observations.append(observation)
    return tuple(observations)


def _linked_invoice_deduction_authority(
    invoice: Invoice,
    *,
    ledger_observations: Sequence[IvaLedgerObservation],
) -> IvaLedgerObservation | None:
    """Return one exact linked ledger authority for a received invoice.

    Invoice amounts are evidence for the silence comparison, but the invoice
    aggregate does not own the current/investment/import/rectification decision.
    That authority lives on the frozen transaction-ledger observation. Every
    linked observation must therefore agree on the complete deduction identity;
    absence or disagreement is ambiguity and remains unprojected.
    """
    if invoice.kind is not InvoiceKind.RECEIVED:
        return None
    linked_ids = frozenset(invoice.linked_transaction_ids)
    authorities = tuple(
        observation
        for observation in ledger_observations
        if observation.ledger_id in linked_ids
        and observation.deduction_fact_kind is not None
        and observation.deduction_provenance is not None
    )
    if not authorities:
        return None
    first = authorities[0]
    identity = (
        first.deduction_fact_kind,
        first.deduction_provenance,
        first.investment_asset_id,
        first.rectifies_ledger_id,
    )
    if any(
        (
            observation.deduction_fact_kind,
            observation.deduction_provenance,
            observation.investment_asset_id,
            observation.rectifies_ledger_id,
        )
        != identity
        for observation in authorities[1:]
    ):
        return None
    return first


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
            resolver_id=LedgerIvaAggregationSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            contributor_source_kind="ledger_iva_aggregation",
            contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=_iva_prorrata_apportionment_source_ref(period, apportionment),
            parent_source_ref=None,
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


__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "aggregation_period_for_modelo",
]
