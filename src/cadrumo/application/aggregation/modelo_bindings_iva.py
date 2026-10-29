"""IVA ledger binding source resolution.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_binding_selector_support import LedgerIvaFact
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    structurally_unroutable_iva_base_categories,
    unrouted_ledger_iva_quantities,
    unsupported_ledger_iva_observations,
)
from ...domain.calculations.registry.ledger_iva_screen_bindings import invoice_ledger_screen_binding_ids
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.iva.schema import IvaCategory
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ._modelo_bindings_invoice_iva import (
    InvoiceIvaSilenceReport,
    category_counterparty_mismatch_diagnostics,
    missing_invoice_deduction_authority_diagnostics,
    out_of_window_summary_diagnostics,
    recargo_rate_mismatch_diagnostics,
    recargo_unattributable_diagnostics,
    reverse_charge_underivable_diagnostics,
)
from ._modelo_bindings_invoice_iva_refusal import raise_if_invoice_iva_would_be_silent
from ._modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
)
from .iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    aggregate_iva_ledger_observations_from_repositories,
)
from .iva_ledger_apportionment import resolve_iva_ledger_binding_values
from .modelo_bindings import aggregation_period_for_modelo
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    source_context_operation,
    source_issue_diagnostics,
    storage_degradation_resolution,
)
from .source_resolution_operations import (
    source_diagnostics_for as _diagnostics_for,
)
from .source_resolution_operations import (
    source_provenance_for as _provenance_for,
)

_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
        IvaLedgerAggregationIssueReason.NON_DEDUCTIBLE_MIXED_USE,
    },
)

_IVA_SELECTED_SCOPE_EVIDENCE_FAILURE_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT,
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
        IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
        IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW,
        IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY,
        IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
        IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT,
    }
)

# Reasons whose marker also carries the issue's own sentence. Their detail names
# a registry field and token, never a taxpayer figure, and without it the marker
# could not say which stored value to correct.
_IVA_SELECTED_SCOPE_DETAILED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT,
    }
)


def _selected_scope_iva_evidence_message(issue: IvaLedgerAggregationIssue) -> str:
    marker = f"selected-scope IVA evidence failure: {issue.reason.value}"
    if issue.reason in _IVA_SELECTED_SCOPE_DETAILED_REASONS:
        return f"{marker}: {issue.detail}"
    return marker


def _selected_scope_iva_evidence_diagnostics(
    issues: Sequence[IvaLedgerAggregationIssue],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return sanitized durable markers for selected-scope IVA evidence failures."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="iva_selected_scope_evidence_failure",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=f"transaction:{issue.transaction_id}",
            message=_selected_scope_iva_evidence_message(issue),
        )
        for issue in issues
        if issue.reason in _IVA_SELECTED_SCOPE_EVIDENCE_FAILURE_REASONS
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


class LedgerIvaAggregationSourceResolver:
    """Resolve ``ledger_iva_aggregation`` bindings from the transaction ledger.

    Owns :attr:`BindingSourceKind.LEDGER_IVA_AGGREGATION`, projects IVA
    observations through :func:`~._iva_ledger.aggregate_iva_ledger_observations_from_repositories`,
    and returns a :class:`~.source_mesh.CalculationSourceResolution` with
    source issues, unrouted-observation diagnostics, and transaction provenance.
    """

    resolver_id: ClassVar[str] = "ledger_iva_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IVA_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        invoice_catalogue_read_ports: InvoiceCatalogueReadPorts,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        investment_asset_register: BienesInversionIvaRegister | None = None,
        investment_asset_profile_id: str | None = None,
    ) -> None:
        """Bind repositories used to resolve IVA ledger sources."""
        self._transaction_repository = transaction_repository
        self._invoice_catalogue_read_ports = invoice_catalogue_read_ports
        self._prorrata_register_repository = prorrata_register_repository
        self._investment_asset_register = investment_asset_register
        self._investment_asset_profile_id = investment_asset_profile_id

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve IVA ledger observations for one calculation context."""
        if not revision_has_binding_source(context.revision, "ledger_iva_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        with source_context_operation(context) as operation:
            try:
                aggregation = aggregate_iva_ledger_observations_from_repositories(
                    bucket_id=context.bucket_id,
                    period=aggregation_period,
                    transaction_repository=self._transaction_repository,
                    prorrata_register_repository=self._prorrata_register_repository,
                    investment_asset_register=self._investment_asset_register,
                    investment_asset_profile_id=self._investment_asset_profile_id,
                    operation=operation,
                )
            except STORAGE_DEGRADATION_ERRORS as exc:
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
                operation=operation,
            )
            screened_bindings = invoice_ledger_screen_binding_ids(
                context.revision,
                modelo=context.modelo,
            )
            silence_report = raise_if_invoice_iva_would_be_silent(
                context=context,
                period=aggregation_period,
                operation=operation,
                transaction_binding_values=binding_values,
                ledger_observations=aggregation.observations,
                ports=self._invoice_catalogue_read_ports,
                prorrata_apportionment=aggregation.prorrata_apportionment,
                screened_bindings=screened_bindings,
            )
        return self._assemble_resolution(
            context, aggregation_period, aggregation, binding_values, transaction_ids, silence_report
        )

    def _assemble_resolution(
        self,
        context: CalculationSourceContext,
        aggregation_period: Period,
        aggregation: IvaLedgerAggregation,
        binding_values: Mapping[BindingId, Decimal],
        transaction_ids: set[str],
        silence_report: InvoiceIvaSilenceReport,
    ) -> CalculationSourceResolution:
        # Report declarable observations that no binding consumes.
        unconsumed = unsupported_ledger_iva_observations(context.revision, aggregation.observations)
        # A consumed row can still carry an unrouted quantity.
        unrouted_quantities = unrouted_ledger_iva_quantities(context.revision, aggregation.observations)
        # Check taxpayer-relevant categories that cannot route a base.
        unroutable_categories = _present_unroutable_iva_categories(context, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(sorted(transaction_ids)),
            diagnostics=out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + devengo_proxy_attribution_diagnostics(
                silence_report.compared,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + reverse_charge_underivable_diagnostics(
                silence_report.reverse_charge_underivable,
                resolver_id=self.resolver_id,
            )
            + missing_invoice_deduction_authority_diagnostics(
                silence_report.deduction_authority_missing,
                resolver_id=self.resolver_id,
            )
            + category_counterparty_mismatch_diagnostics(
                silence_report.category_counterparty_mismatches,
                resolver_id=self.resolver_id,
            )
            + recargo_rate_mismatch_diagnostics(
                silence_report.recargo_rate_divergences,
                resolver_id=self.resolver_id,
            )
            + recargo_unattributable_diagnostics(
                silence_report.recargo_unattributable,
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                tuple(
                    issue
                    for issue in aggregation.issues
                    if issue.reason not in _IVA_SELECTED_SCOPE_EVIDENCE_FAILURE_REASONS
                ),
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                suppressed_reasons=_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS,
                held_back_reasons=frozenset(
                    {
                        IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
                        IvaLedgerAggregationIssueReason.IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE,
                    }
                ),
                source_ref=lambda issue: f"transaction:{issue.transaction_id}",
            )
            + _selected_scope_iva_evidence_diagnostics(
                aggregation.issues,
                resolver_id=self.resolver_id,
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
                        terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
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
                        terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                    ),
                )
                + _iva_prorrata_apportionment_provenance(
                    context.revision,
                    aggregation_period,
                    aggregation.prorrata_apportionment,
                )
            ),
        )


def _present_unroutable_iva_categories(
    context: CalculationSourceContext, observations: Iterable[IvaLedgerObservation]
) -> tuple[IvaCategory, ...]:
    if context.modelo != Modelo("303").value:
        return ()
    present_categories = {observation.category for observation in observations}
    return tuple(
        category
        for category in structurally_unroutable_iva_base_categories(context.revision)
        if category in present_categories
    )


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
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
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
        if isinstance(binding.provider, LedgerIvaProvider) and binding.provider.fact == LedgerIvaFact.IVA_AMOUNT_SUM
    }
    return tuple(
        casilla
        for casilla in revision.casillas
        if "deducible" in casilla.section
        and any(binding_id in ledger_iva_amount_bindings for binding_id in bound_casilla_binding_ids(casilla))
    )
