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
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.modelo import Modelo
from ...core.period import Period, PeriodError, StandardPeriodCode
from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.irnr_ledger_bindings import (
    resolve_ledger_irnr_income_aggregation_binding_values,
    unsupported_ledger_irnr_income_observations,
)
from ...domain.calculations.registry.ledger_impatriado_bindings import (
    resolve_ledger_impatriado_income_aggregation_binding_values,
    unsupported_ledger_impatriado_income_observations,
)
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    structurally_unroutable_iva_base_categories,
    unrouted_ledger_iva_quantities,
    unsupported_ledger_iva_observations,
)
from ...domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
)
from ...domain.calculations.registry.ledger_renta_income_bindings import (
    UngroundedRentaIncome,
    resolve_ledger_renta_income_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_renta_income_observations,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow
from ...domain.prorrata_register._protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.retenciones_routing_integrity import (
    RENTA_130_RETENCIONES_BINDING_ID,
    RENTA_130_RETENCIONES_OUTPUT_CASILLA,
)
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ._impatriado_income_ledger import aggregate_impatriado_income_ledger_from_repositories
from ._invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
)
from ._irnr_income_ledger import IrnrIncomeObservation, aggregate_irnr_income_ledger_from_repositories
from ._iva_ledger import (
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    aggregate_iva_ledger_observations_from_repositories,
    resolve_iva_ledger_binding_values,
)
from ._modelo_bindings_invoice_iva import (
    _category_counterparty_mismatch_diagnostics,
    _missing_invoice_deduction_authority_diagnostics,
    _out_of_window_summary_diagnostics,
    _recargo_rate_mismatch_diagnostics,
    _reverse_charge_underivable_diagnostics,
)
from ._modelo_bindings_invoice_iva_refusal import _raise_if_invoice_iva_would_be_silent
from ._modelo_bindings_support import (
    _STORAGE_DEGRADATION_ERRORS,
    _empty_source_resolution,
    _revision_has_binding_source,
)
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
from ._retencion_rate_advisory import (
    inferred_actividad_retencion_rate_advisory_observations,
)
from ._source_mesh import (
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ._undeclared_activity_advisory import undeclared_activity_income_advisory_observations
from .errors import AggregationValidationError, t
from .source_resolution_operations import (
    sorted_source_ids as _sorted_ids,
)
from .source_resolution_operations import (
    source_diagnostics_for as _diagnostics_for,
)
from .source_resolution_operations import (
    source_issue_diagnostics,
    storage_degradation_resolution,
)
from .source_resolution_operations import (
    source_provenance_for as _provenance_for,
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
    time (`domain.renta.retenciones_routing_integrity`), the same mechanism
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
__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "aggregation_period_for_modelo",
]
