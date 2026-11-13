"""IVA ledger binding source resolution.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import normalise_supported_language, output_language
from ...core.period import Period
from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_flow_catalogue import resolve_iva_flow_direction_catalogue
from ...domain.calculations.registry.ledger_binding_resolution import UnroutedLedgerQuantity
from ...domain.calculations.registry.ledger_binding_selector_support import LedgerIvaFact
from ...domain.calculations.registry.ledger_iva_bindings import (
    IVA_INDEPENDENT_QUANTITY_FACTS,
    IvaLedgerObservation,
    LedgerIvaProvider,
    declarable_ledger_iva_observations,
    ledger_iva_quantity,
    structurally_unroutable_iva_base_categories,
    unrouted_ledger_iva_quantities,
    unsupported_ledger_iva_observations,
)
from ...domain.calculations.registry.prorrata_volume_catalogue import resolve_prorrata_volume_catalogue
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.iva.flow import IvaFlowDirection
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError, InvoiceCatalogueReadPorts
from .invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
)
from .invoice_iva_source import (
    cash_accounting_enrolled,
    invoice_iva_finding_diagnostics,
    period_invoice_iva_findings,
)
from .iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    IvaLedgerRowDateSource,
    IvaLedgerSettlementApportionment,
    aggregate_iva_ledger_observations_from_repositories,
)
from .iva_ledger_apportionment import resolve_iva_ledger_binding_values
from .modelo_bindings import aggregation_period_for_modelo
from .modelo_bindings_invoice_iva import (
    ScreenedInvoiceIva,
    category_counterparty_mismatch_diagnostics,
    invoice_screen_of,
    out_of_window_summary_diagnostics,
    recargo_rate_mismatch_diagnostics,
    reverse_charge_underivable_diagnostics,
)
from .modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    source_context_operation,
    source_diagnostics_for,
    source_issue_diagnostics,
    source_provenance_for,
    storage_degradation_resolution,
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
        IvaLedgerAggregationIssueReason.CUOTA_DISAGREES_WITH_RATE,
        IvaLedgerAggregationIssueReason.RECARGO_DEPARTS_FROM_PUBLISHED_RATE,
        IvaLedgerAggregationIssueReason.RECARGO_RATE_UNMODELLED,
        IvaLedgerAggregationIssueReason.RECARGO_TOBACCO_RUNG_UNSUPPORTED,
        IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY,
        IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
        IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT,
        IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT,
    }
)

# Reasons whose marker also carries the issue's own sentence. Their detail names
# a registry field and token, never a taxpayer figure, and without it the marker
# could not say which stored value to correct.
_DATED_ROW_SAMPLE_LIMIT = 3
# Hex characters of a ledger id named in a message; the ledger commands accept any prefix of it.
_SAMPLED_LEDGER_ID_PREFIX_LENGTH = 12

_IVA_SELECTED_SCOPE_DETAILED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT,
        IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT,
    }
)


# Reasons whose detail carries the row's own figures, worded in the filer's language. The figures reach the
# operator in the live diagnostic only: the persisted issue replaces the message by a fixed marker.
_IVA_SELECTED_SCOPE_FIGURE_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.CUOTA_DISAGREES_WITH_RATE,
        IvaLedgerAggregationIssueReason.RECARGO_DEPARTS_FROM_PUBLISHED_RATE,
        IvaLedgerAggregationIssueReason.RECARGO_RATE_UNMODELLED,
        IvaLedgerAggregationIssueReason.RECARGO_TOBACCO_RUNG_UNSUPPORTED,
    }
)


def _selected_scope_iva_evidence_language(issue: IvaLedgerAggregationIssue) -> OutputLanguage | None:
    """The language the message is worded in, for a reason whose message is the filer's own sentence."""
    if issue.reason not in _IVA_SELECTED_SCOPE_FIGURE_REASONS:
        return None
    return OutputLanguage(normalise_supported_language(output_language()) or OutputLanguage.EN.value)


def selected_scope_iva_evidence_message(issue: IvaLedgerAggregationIssue) -> str:
    """Explain a failed selected-scope IVA evidence issue, keeping its own figure detail."""
    if issue.reason in _IVA_SELECTED_SCOPE_FIGURE_REASONS:
        return issue.detail
    marker = f"selected-scope IVA evidence failure: {issue.reason.value}"
    # A row dated by its bank movement carries the sentence too: without it the
    # marker blames the rate when the missing fact may be the operation date.
    movement_dated = issue.operation_date_source not in (None, IvaLedgerRowDateSource.OPERATION_DATE)
    if issue.reason in _IVA_SELECTED_SCOPE_DETAILED_REASONS or movement_dated:
        return f"{marker}: {issue.detail}"
    return marker


def selected_scope_iva_evidence_diagnostics(
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
            message=selected_scope_iva_evidence_message(issue),
            message_language=_selected_scope_iva_evidence_language(issue),
        )
        for issue in issues
        if issue.reason in _IVA_SELECTED_SCOPE_EVIDENCE_FAILURE_REASONS
    )


def _ledger_row_sample(ledger_ids: Sequence[str]) -> str:
    """Name a few rows by the id prefix the ledger commands accept."""
    ordered = sorted(ledger_ids)
    sample = ", ".join(ledger_id[:_SAMPLED_LEDGER_ID_PREFIX_LENGTH] for ledger_id in ordered[:_DATED_ROW_SAMPLE_LIMIT])
    elided = len(ordered) - _DATED_ROW_SAMPLE_LIMIT
    return f"{sample} and {elided} more" if elided > 0 else sample


def _iva_row_date_diagnostics(
    aggregation: IvaLedgerAggregation,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Say when a row's period rests on the bank date, or on a date after the money.

    Neither refuses. A movement date is right for an operation settled the day it
    occurs and for a collected pago anticipado, so only the operator can tell. The
    one-sided invoice screen cannot catch this: it reports invoice figures above
    ledger figures, so the quarter that receives a late-collected sale passes.
    """
    found: list[CalculationSourceDiagnostic] = []
    if aggregation.movement_dated_ledger_ids:
        found.append(
            CalculationSourceDiagnostic(
                reason="iva_row_placed_on_movement_date",
                source_kind="ledger_iva_aggregation",
                resolver_id=resolver_id,
                message=(
                    f"{len(aggregation.movement_dated_ledger_ids)} ledger row(s) were placed in this period on their "
                    f"bank movement date because no operation date is recorded: "
                    f"{_ledger_row_sample(aggregation.movement_dated_ledger_ids)}. LIVA art. 75 fixes the devengo by "
                    "the operation, not the collection, so a sale near a period end can belong to the previous one"
                ),
                remedy=(
                    "Record the operation date on each row. For a pago anticipado, art. 75.Dos dates the amount "
                    "received at its collection, so record the collection date"
                ),
                asserted_legal_refs=("ley-37-1992:art-75",),
            )
        )
    if aggregation.operation_after_movement_ledger_ids:
        found.append(
            CalculationSourceDiagnostic(
                reason="iva_operation_date_after_movement",
                source_kind="ledger_iva_aggregation",
                resolver_id=resolver_id,
                message=(
                    f"{len(aggregation.operation_after_movement_ledger_ids)} ledger row(s) record an operation date "
                    f"later than their bank movement: "
                    f"{_ledger_row_sample(aggregation.operation_after_movement_ledger_ids)}. If that money was a pago "
                    "anticipado, LIVA art. 75.Dos dates the amount received at its collection, except for art. 25 "
                    "supplies"
                ),
                remedy="If the row is a pago anticipado, record the collection date as its operation date",
                asserted_legal_refs=("ley-37-1992:art-75",),
            )
        )
    return tuple(found)


_UNROUTED_IVA_QUANTITY_SENTENCES: Final[Mapping[str, CalculationNoteSentence]] = MappingProxyType(
    {
        "base_amount_sum": CalculationNoteSentence.UNROUTED_IVA_BASE,
        "iva_amount_sum": CalculationNoteSentence.UNROUTED_IVA_CUOTA,
        "recargo_amount_sum": CalculationNoteSentence.UNROUTED_IVA_RECARGO,
    }
)
"""The sentence that names one row's undrawn IVA quantity, by the fact the screen found undrawn."""

if frozenset(_UNROUTED_IVA_QUANTITY_SENTENCES) != IVA_INDEPENDENT_QUANTITY_FACTS:
    raise ValueError("every screened IVA quantity is worded by exactly one calculation note sentence")


@dataclass(frozen=True, slots=True)
class _UnroutedIvaQuantityRow:
    """One row's amount of one IVA quantity that no binding drawing that quantity reaches."""

    fact: str
    observation: IvaLedgerObservation
    amount: Decimal


@dataclass(frozen=True, slots=True)
class _ProrrataOnlyExemptOutput:
    """The taxpayer's exempt output whose base the periodic return has no box for: it only drives the prorrata.

    An operation exempt without the right to deduct (LIVA art. 20) enters the
    prorrata denominator (art. 104.Dos), and the Modelo 303 declares its base in
    no box; the annual summary carries it in the volume of operations. Such a row
    is accounted for, not lost, so its base is no unrouted quantity. A row is
    taken as one only when the registry's prorrata output-volume vocabulary
    names its category as sin derecho, no base binding of the revision could
    ever reach that category, and the taxpayer performs the operation.
    """

    categories: frozenset[IvaCategory]
    output_flows: frozenset[IvaFlowDirection]

    def accounts_for(self, observation: IvaLedgerObservation) -> bool:
        return observation.category in self.categories and observation.flow_direction in self.output_flows


def _prorrata_only_exempt_output(
    context: CalculationSourceContext,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> _ProrrataOnlyExemptOutput | None:
    """The exempt output the periodic return leaves to the prorrata, or ``None`` on any other modelo."""
    if context.modelo != form_for_role("iva.periodic"):
        return None
    sin_derecho = resolve_prorrata_volume_catalogue(effective_date=period.end_date, authority=operation).sin_derecho
    categories = sin_derecho & frozenset(structurally_unroutable_iva_base_categories(context.revision))
    if not categories:
        return None
    flows = resolve_iva_flow_direction_catalogue(effective_date=period.end_date, authority=operation)
    return _ProrrataOnlyExemptOutput(
        categories=categories,
        output_flows=frozenset({flows.issued_token, flows.supplier_reverse_charge_token}),
    )


def _without_prorrata_only_exempt_bases(
    quantities: Iterable[UnroutedLedgerQuantity[IvaLedgerObservation]],
    exempt_output: _ProrrataOnlyExemptOutput | None,
) -> tuple[UnroutedLedgerQuantity[IvaLedgerObservation], ...]:
    """Drop the base of each row the prorrata accounts for; every other undrawn quantity stays."""
    if exempt_output is None:
        return tuple(quantities)
    kept: list[UnroutedLedgerQuantity[IvaLedgerObservation]] = []
    for quantity in quantities:
        rows = (
            quantity.observations
            if quantity.fact != "base_amount_sum"
            else tuple(row for row in quantity.observations if not exempt_output.accounts_for(row))
        )
        if rows:
            kept.append(
                UnroutedLedgerQuantity(
                    fact=quantity.fact,
                    total=sum((ledger_iva_quantity(quantity.fact, row) for row in rows), Decimal("0")),
                    observations=rows,
                )
            )
    return tuple(kept)


def _unrouted_iva_quantity_rows(
    quantities: Iterable[UnroutedLedgerQuantity[IvaLedgerObservation]],
) -> tuple[_UnroutedIvaQuantityRow, ...]:
    """Split each undrawn quantity into the rows that carry it, each with its own amount.

    The screen detects per fact and per selector, so a fact can be drawn for some
    categories and undrawn for others. A note per row names the record, its date
    and the amount left out, which is what the filer needs to correct its
    classification; a total over several rows names none of them.
    """
    return tuple(
        _UnroutedIvaQuantityRow(
            fact=quantity.fact,
            observation=observation,
            amount=ledger_iva_quantity(quantity.fact, observation),
        )
        for quantity in quantities
        for observation in quantity.observations
    )


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
        settlement: IvaLedgerSettlementApportionment | None = None,
    ) -> None:
        """Bind repositories used to resolve IVA ledger sources.

        ``settlement`` carries the year's definitive prorrata percentages for
        the annual settlement liquidation once they are derivable. A
        sectorized apportionment takes it only when it settles every declared
        sector.
        """
        self._settlement = settlement
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
                    invoice_reader=self._invoice_catalogue_read_ports.invoice_reader,
                    prorrata_register_repository=self._prorrata_register_repository,
                    investment_asset_register=self._investment_asset_register,
                    investment_asset_profile_id=self._investment_asset_profile_id,
                    operation=operation,
                )
            except (InvoiceCatalogueReadPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
                return storage_degradation_resolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    source_kinds=self.owned_sources,
                    error=exc,
                )
            aggregation = _with_settlement_apportionment(aggregation, self._settlement)
            transaction_ids = {
                observation.ledger_id
                for observation in aggregation.observations
                if not _is_invoice_observation(observation)
            }
            transaction_ids.update(reference.transaction_id for reference in aggregation.prorrata_references)
            binding_values = resolve_iva_ledger_binding_values(
                context.revision,
                aggregation.observations,
                prorrata_apportionment=aggregation.prorrata_apportionment,
                operation=operation,
            )
            exempt_output = _prorrata_only_exempt_output(context, aggregation_period, operation)
        return self._assemble_resolution(
            context,
            aggregation_period,
            aggregation,
            binding_values,
            transaction_ids,
            invoice_screen_of(aggregation),
            exempt_output,
        )

    def _assemble_resolution(
        self,
        context: CalculationSourceContext,
        aggregation_period: Period,
        aggregation: IvaLedgerAggregation,
        binding_values: Mapping[BindingId, Decimal],
        transaction_ids: set[str],
        invoice_screen: ScreenedInvoiceIva,
        exempt_output: _ProrrataOnlyExemptOutput | None,
    ) -> CalculationSourceResolution:
        # Report declarable observations that no binding consumes.
        unconsumed = unsupported_ledger_iva_observations(context.revision, aggregation.observations)
        # A consumed row can still carry an unrouted quantity, except a base the prorrata accounts for.
        unrouted_quantities = _without_prorrata_only_exempt_bases(
            unrouted_ledger_iva_quantities(context.revision, aggregation.observations), exempt_output
        )
        # Check taxpayer-relevant categories that cannot route a base.
        unroutable_categories = _present_unroutable_iva_categories(context, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(sorted(transaction_ids)),
            diagnostics=self._screening_diagnostics(context, aggregation_period, aggregation, invoice_screen)
            + self._unrouted_diagnostics(context, unconsumed, unrouted_quantities, unroutable_categories),
            provenance=self._ledger_provenance(context, aggregation_period, aggregation)
            + _prorrata_only_exempt_output_provenance(context.revision, aggregation_period, aggregation, exempt_output),
        )

    def _screening_diagnostics(
        self,
        context: CalculationSourceContext,
        aggregation_period: Period,
        aggregation: IvaLedgerAggregation,
        invoice_screen: ScreenedInvoiceIva,
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        """Report the window, invoice-screen, cash-accounting and ledger-issue findings."""
        return (
            out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + devengo_proxy_attribution_diagnostics(
                invoice_screen.compared,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + _iva_row_date_diagnostics(aggregation, resolver_id=self.resolver_id)
            + reverse_charge_underivable_diagnostics(
                invoice_screen.reverse_charge_underivable,
                resolver_id=self.resolver_id,
            )
            + category_counterparty_mismatch_diagnostics(
                invoice_screen.category_counterparty_mismatches,
                resolver_id=self.resolver_id,
            )
            + recargo_rate_mismatch_diagnostics(
                invoice_screen.recargo_rate_divergences,
                resolver_id=self.resolver_id,
            )
            + invoice_iva_finding_diagnostics(
                period_invoice_iva_findings(
                    aggregation.invoice_findings,
                    invoice_ids=aggregation.invoice_ids,
                    cash_accounting_enrolled=cash_accounting_enrolled(
                        context.profile.record if context.profile is not None else None,
                        as_of=aggregation_period.end_date,
                    ),
                ),
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
            + selected_scope_iva_evidence_diagnostics(
                aggregation.issues,
                resolver_id=self.resolver_id,
            )
        )

    def _unrouted_diagnostics(
        self,
        context: CalculationSourceContext,
        unconsumed: Sequence[IvaLedgerObservation],
        unrouted_quantities: Sequence[UnroutedLedgerQuantity[IvaLedgerObservation]],
        unroutable_categories: Sequence[IvaCategory],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        """Report the amounts and categories that no binding consumes."""
        return (
            source_diagnostics_for(
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
            + source_diagnostics_for(
                _unrouted_iva_quantity_rows(unrouted_quantities),
                reason="unrouted_declarable_quantity",
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
                source_ref=lambda row: _observation_source_ref(row.observation),
                message=lambda row: (
                    f"IVA row {row.observation.ledger_id!r} carries {row.amount} EUR of {row.fact!r} in "
                    f"category {row.observation.category.value!r}, which no ledger_iva_aggregation binding "
                    f"on revision {context.revision.id!r} draws for that category; that amount is not "
                    "declared on this calculation"
                ),
                fact=lambda row: CalculationNoteFact.of(
                    _UNROUTED_IVA_QUANTITY_SENTENCES[row.fact],
                    rows=(row.observation.ledger_id,),
                    row_date=row.observation.transaction_date.isoformat(),
                    row_amount=row.amount,
                ),
            )
            + source_diagnostics_for(
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
            )
        )

    def _ledger_provenance(
        self,
        context: CalculationSourceContext,
        aggregation_period: Period,
        aggregation: IvaLedgerAggregation,
    ) -> tuple[CalculationSourceProvenance, ...]:
        """Name each record, prorrata reference and apportionment the resolution rests on.

        An invoice yields one observation per line, yet it is one record, so it
        is named once however many rates its lines bear.
        """
        return (
            source_provenance_for(
                _observations_by_record(aggregation.observations),
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                    contributor_source_kind="ledger_iva_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=_observation_source_ref(observation),
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                ),
            )
            + source_provenance_for(
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
        )


def _observations_by_record(observations: Iterable[IvaLedgerObservation]) -> tuple[IvaLedgerObservation, ...]:
    """The first observation of each record, in observation order."""
    first: dict[str, IvaLedgerObservation] = {}
    for observation in observations:
        first.setdefault(_observation_source_ref(observation), observation)
    return tuple(first.values())


def _is_invoice_observation(observation: IvaLedgerObservation) -> bool:
    return observation.ledger_id.startswith("invoice:")


def _observation_source_ref(observation: IvaLedgerObservation) -> str:
    """Name the record an observation came from: its invoice, or the movement that carries its own facts."""
    if _is_invoice_observation(observation):
        return "invoice:" + observation.ledger_id.split(":", 2)[1]
    return f"transaction:{observation.ledger_id}"


def _present_unroutable_iva_categories(
    context: CalculationSourceContext, observations: Iterable[IvaLedgerObservation]
) -> tuple[IvaCategory, ...]:
    if context.modelo != form_for_role("iva.periodic"):
        return ()
    present_categories = {observation.category for observation in declarable_ledger_iva_observations(observations)}
    return tuple(
        category
        for category in structurally_unroutable_iva_base_categories(context.revision)
        if category in present_categories
    )


def _with_settlement_apportionment(
    aggregation: IvaLedgerAggregation,
    settlement: IvaLedgerSettlementApportionment | None,
) -> IvaLedgerAggregation:
    """Attach the settlement percentages when they cover the apportionment's declared sectors.

    A sectorized apportionment is settled only when the settlement names
    exactly its declared sectors; otherwise the settlement liquidation keeps
    its provisional percentages and the regularisation box reports the
    unsettled sector.
    """
    apportionment = aggregation.prorrata_apportionment
    if settlement is None or apportionment is None:
        return aggregation
    declared = {sector.sector_id for sector in apportionment.sector_apportionments}
    if {item.sector_id for item in settlement.sector_percentages} != declared:
        return aggregation
    return aggregation.model_copy(
        update={"prorrata_apportionment": apportionment.model_copy(update={"settlement": settlement})}
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
            source_ref=iva_prorrata_apportionment_source_ref(period, apportionment),
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
            legal_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.legal_refs)),
            source_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.source_refs)),
        ),
    )


def _prorrata_only_exempt_output_provenance(
    revision: ModeloRevision,
    period: Period,
    aggregation: IvaLedgerAggregation,
    exempt_output: _ProrrataOnlyExemptOutput | None,
) -> tuple[CalculationSourceProvenance, ...]:
    """Record that the period holds exempt output left to the prorrata while no apportionment applied.

    Such output means the taxpayer performs operations without the right to
    deduct, so the prorrata applies (LIVA art. 102.Uno); deducting with no
    apportionment is then a full deduction the verify gate refuses.
    """
    if exempt_output is None or aggregation.prorrata_apportionment is not None:
        return ()
    rows = {
        _observation_source_ref(observation)
        for observation in aggregation.observations
        if exempt_output.accounts_for(observation)
    }
    if not rows:
        return ()
    casillas = _iva_deducible_cuota_casillas(revision)
    return (
        CalculationSourceProvenance(
            resolver_id=LedgerIvaAggregationSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            contributor_source_kind="ledger_iva_aggregation",
            contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=prorrata_only_exempt_output_source_ref(period, len(rows)),
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
            legal_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.legal_refs)),
            source_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.source_refs)),
        ),
    )


_PRORRATA_ONLY_EXEMPT_OUTPUT_SOURCE_REF_PREFIX = "prorrata-only-exempt-output"


def prorrata_only_exempt_output_source_ref(period: Period, row_count: int) -> str:
    """Return the reference a calculation records when it left exempt output to a prorrata it did not apply.

    :func:`recorded_prorrata_only_exempt_output` reads the row count back.
    """
    return f"{_PRORRATA_ONLY_EXEMPT_OUTPUT_SOURCE_REF_PREFIX}:{period.filing_year}:rows:{row_count}"


def recorded_prorrata_only_exempt_output(source_refs: Iterable[str]) -> int | None:
    """Read back how many records of exempt output a calculation left to an unapplied prorrata, or ``None``."""
    for source_ref in source_refs:
        match source_ref.split(":"):
            case [prefix, _filing_year, "rows", row_count] if prefix == _PRORRATA_ONLY_EXEMPT_OUTPUT_SOURCE_REF_PREFIX:
                return int(row_count)
            case _:
                continue
    return None


_PRORRATA_APPORTIONMENT_SOURCE_REF_PREFIX = "prorrata-apportionment"


@dataclass(frozen=True, slots=True)
class RecordedProrrataApportionment:
    """The provisional prorrata a saved calculation recorded that it applied."""

    filing_year: int
    regime: str
    percentage: Decimal
    provenance: str


def recorded_prorrata_apportionment(source_refs: Iterable[str]) -> RecordedProrrataApportionment | None:
    """Read back the apportionment a calculation recorded, or ``None`` when it applied none.

    The reference is the one this module writes for the deducible casillas,
    so its leading fields are fixed: year, regime, percentage and provenance.
    """
    for source_ref in source_refs:
        match source_ref.split(":"):
            case [prefix, filing_year, regime, "percentage", percentage, "provenance", provenance, *_] if (
                prefix == _PRORRATA_APPORTIONMENT_SOURCE_REF_PREFIX
            ):
                return RecordedProrrataApportionment(
                    filing_year=int(filing_year),
                    regime=regime,
                    percentage=Decimal(percentage),
                    provenance=provenance,
                )
            case _:
                continue
    return None


def iva_prorrata_apportionment_source_ref(
    period: Period,
    apportionment: IvaLedgerProrrataApportionment,
) -> str:
    """Return the reference a calculation records for the apportionment it deducted under.

    :func:`recorded_prorrata_apportionment` reads its leading fields back.
    """
    source_ref = (
        f"{_PRORRATA_APPORTIONMENT_SOURCE_REF_PREFIX}:{period.filing_year}:{apportionment.regime.value}:"
        f"percentage:{apportionment.percentage}:provenance:{apportionment.provenance.value}"
    )
    if apportionment.source_observation_ref is not None:
        source_ref = f"{source_ref}:source-observation:{apportionment.source_observation_ref}"
    if apportionment.settlement is not None:
        source_ref = (
            f"{source_ref}:settlement:{apportionment.settlement.period.registry_token}:"
            f"definitive:{apportionment.settlement.percentage}"
        )
        for sector in apportionment.settlement.sector_percentages:
            source_ref = f"{source_ref}:sector:{sector.sector_id}:definitive:{sector.percentage}"
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
