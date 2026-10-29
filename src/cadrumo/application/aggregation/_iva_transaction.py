"""Canonical IVA transaction classification and observation projection.

This module owns the per-transaction IVA pipeline. Repository aggregation remains
in :mod:`.iva_ledger`; this module owns the transaction-level admission,
classification, and observation sinks consumed by that orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.i18n.render import tr as render_tr
from ...core.period import Period
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_cash_accounting_vocabulary import resolve_iva_cash_accounting_catalogue
from ...domain.calculations.registry.iva_category_catalogue import (
    require_iva_category,
    resolve_iva_category_catalogue,
)
from ...domain.calculations.registry.iva_legal_vocabulary import resolve_iva_exemption_article_catalogue
from ...domain.calculations.registry.iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.prorrata_exclusions import resolve_art104_tres_exclusion_catalogue
from ...domain.calculations.registry.prorrata_vocabulary import resolve_input_classification_catalogue
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.iva.components import (
    category_components,
    registry_category_projection,
    registry_component_catalogue,
    registry_component_presence_token,
    registry_kind_applicability_token,
)
from ...domain.iva.deduction_facts import (
    admits_iva_deduction_classification,
)
from ...domain.iva.flow import (
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
)
from ...domain.iva.lookup import rate_table_covers_any_positive_tier
from ...domain.iva.schema import (
    InvoiceKind,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
    IvaRateKind,
    is_iva_cash_accounting_none,
    spanish_eu_member_state,
)
from ...domain.transactions.cash_accounting_validation import validate_cash_accounting_axis
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from .currency_predicates import is_non_eur_without_conversion
from .invoice_kind import invoice_kind_for_direction
from .iva_ledger import IvaLedgerAggregationIssue, IvaLedgerAggregationIssueReason, ProrrataLedgerReference
from .iva_ledger_classification import (
    business_proportionality_for,
    has_converted_non_eur_amount,
    iva_category_deductible_proportion,
    iva_rate_kind_for,
    missing_tax_fact_detail,
    missing_tax_fact_reason,
    validate_iva_ledger_counterparty_category,
)
from .iva_transaction_projection import (
    cash_accounting_observations,
    inadmissible_deduction_issue,
    iva_observation,
    resolve_iva_prorrata_attachment,
)


def _resolve_iva_registry_declarations(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[object, ...]:
    """Resolve the selected IVA model surfaces and governed fact catalogues."""
    modelo_303 = operation.modelo_directory("303")
    modelo_390 = operation.modelo_directory("390")
    fact_ids = (
        "iva-invoice-classification-catalogue",
        "iva-category-component-catalogue",
        "iva-deduction-applicability-catalogue",
        "iva-regime-legend-catalogue",
        "iva-supply-nature-citation-catalogue",
    )
    facts = tuple(
        operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
        for fact_id in fact_ids
    )
    if not all(isinstance(fact, ResolvedMappingFact) for fact in facts):
        raise TypeError("IVA applicability and catalogue declarations must resolve as mapping facts")
    return (modelo_303, modelo_390, *facts)


@dataclass(frozen=True, slots=True)
class _IvaTransactionOutcome:
    """Per-transaction outcome carrying the typed sinks the orchestrator drains.

    A transaction either fails a pre-observation gate (``gate_issue``
    populated, nothing else) or it survives all pre-gates and produces
    an ``observation``. The observation path may additionally emit a
    ``prorrata_reference`` AND/OR a ``prorrata_issue`` — they are
    independent sinks: an invalid prorrata-reference attaches to the
    issue list, a valid one attaches to the prorrata-references list,
    and either way the observation itself is recorded.
    """

    gate_issue: IvaLedgerAggregationIssue | None = None
    observations: tuple[IvaLedgerObservation, ...] = ()
    prorrata_reference: ProrrataLedgerReference | None = None
    prorrata_issue: IvaLedgerAggregationIssue | None = None


@dataclass(frozen=True, slots=True)
class _IvaTransactionContext:
    transaction_id: str
    operation_date: date
    cash_treatment: IvaCashAccountingTreatment
    invoice_kind: InvoiceKind
    proportionality: Decimal


@dataclass(frozen=True, slots=True)
class _IvaTransactionAmounts:
    rate_kind: IvaRateKind
    base_amount: Decimal
    iva_amount: Decimal
    recargo_amount: Decimal


@dataclass(frozen=True, slots=True)
class _IvaTransactionClassification:
    category: IvaCategory
    flow_direction: IvaFlowDirection


@dataclass(frozen=True, slots=True)
class _IvaTransactionAdmission:
    """A row that cleared every pre-observation gate, with what it resolved to."""

    context: _IvaTransactionContext
    amounts: _IvaTransactionAmounts
    classification: _IvaTransactionClassification


def _period_admission_issue(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation_date: date,
    cash_treatment: IvaCashAccountingTreatment,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Preserve the filing-window refusal before any source-ownership diagnosis."""
    transaction_id = transaction.transaction_id
    if is_iva_cash_accounting_none(cash_treatment, authority=operation) and not resolved_period.contains(
        operation_date
    ):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"transaction date {operation_date.isoformat()} is outside {resolved_period}",
        )
    return None


def _substrate_admission_issue(transaction: Transaction) -> IvaLedgerAggregationIssue | None:
    """Read tax substrate only after the row's business/flow ownership is known."""
    transaction_id = transaction.transaction_id
    if is_non_eur_without_conversion(transaction):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for IVA aggregation",
        )
    if has_converted_non_eur_amount(transaction):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE,
            detail=(
                f"transaction currency {transaction.raw.currency!r} has a converted gross value_in_eur "
                "but taxable_base/iva_amount remain native-currency facts; IVA aggregation requires "
                "explicit EUR tax substrate"
            ),
        )
    return None


def _unaccepted_registry_value_issue(
    transaction_id: str,
    *,
    field: str,
    value: str,
    effective_date: date,
) -> IvaLedgerAggregationIssue:
    return IvaLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
        detail=render_tr(
            "aggregation.iva_ledger.errors.unaccepted_registry_value",
            field=field,
            value=value,
            effective_date=effective_date.isoformat(),
        ),
    )


def _unaccepted_cash_accounting_treatment_issue(
    transaction: Transaction,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Refuse a treatment the pinned vocabulary does not declare.

    Read on the date every other treatment comparison in this pipeline reads
    it, so a treatment this check admits is one those comparisons can answer.
    """
    effective_date = today_madrid()
    catalogue = resolve_iva_cash_accounting_catalogue(effective_date=effective_date, authority=operation)
    try:
        catalogue.require(transaction.cash_accounting_treatment)
    except RegistryValidationError:
        return _unaccepted_registry_value_issue(
            transaction.transaction_id,
            field="cash_accounting_treatment",
            value=str(transaction.cash_accounting_treatment),
            effective_date=effective_date,
        )
    return None


def _cash_accounting_evidence_issue(
    transaction: Transaction,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Re-check the criterio-de-caja coupling the settlement split depends on.

    The split reads the operation date, the payment evidence and the substrate
    that caps them. The write path's own rule judges them here, scoped to this
    operation's pinned facts, so admission and use cannot disagree.
    """
    try:
        with validating_governed_facts(operation):
            validate_cash_accounting_axis(
                treatment=transaction.cash_accounting_treatment,
                operation_date=transaction.operation_date,
                payment_evidence=transaction.cash_accounting_payment_evidence,
                taxable_base=transaction.taxable_base,
                iva_amount=transaction.iva_amount,
                recargo_amount=transaction.recargo_amount,
                direction=transaction.direction,
            )
    except TransactionValidationError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            reason=IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EVIDENCE_INCOHERENT,
            detail=render_tr(
                "aggregation.iva_ledger.errors.cash_accounting_evidence_incoherent",
                refusal=str(exc),
            ),
        )
    return None


def _unaccepted_row_value_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    effective_category: IvaCategory,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Refuse a declared registry value this operation's authority does not accept.

    Each value is judged against the pinned authority on the date its write
    admission judged it, so a value admitted under the same authority is never
    refused here. The identification state is judged only where it is used: the
    intra-community gate reads it for a declared intra-community supply alone.
    """
    exemption_issue = _unaccepted_exemption_article_issue(
        transaction,
        transaction_id=transaction_id,
        effective_category=effective_category,
        operation=operation,
    )
    if exemption_issue is not None:
        return exemption_issue
    ledger_date = transaction.raw.value_date or transaction.raw.booked_date
    input_classification = transaction.input_classification
    if input_classification is not None:
        input_catalogue = resolve_input_classification_catalogue(effective_date=ledger_date, authority=operation)
        try:
            input_catalogue.require(input_classification)
        except RegistryValidationError:
            return _unaccepted_registry_value_issue(
                transaction_id,
                field="input_classification",
                value=str(input_classification),
                effective_date=ledger_date,
            )
    exclusion_issue = _unaccepted_art_104_tres_exclusion_issue(
        transaction,
        transaction_id=transaction_id,
        operation=operation,
    )
    if exclusion_issue is not None:
        return exclusion_issue
    identification_state = transaction.counterparty_identification_state
    if identification_state is not None and transaction.iva_category == require_iva_category(
        "intra_community_supply",
        authority=operation,
    ):
        member_states = resolve_eu_member_state_catalogue(effective_date=ledger_date, authority=operation)
        try:
            member_states.require(identification_state)
        except RegistryValidationError:
            return _unaccepted_registry_value_issue(
                transaction_id,
                field="counterparty_identification_state",
                value=str(identification_state),
                effective_date=ledger_date,
            )
    return None


def _unaccepted_exemption_article_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    effective_category: IvaCategory,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    exemption_article = transaction.exemption_article
    if exemption_article is None:
        return None
    effective_date = today_madrid()
    catalogue = resolve_iva_exemption_article_catalogue(effective_date=effective_date, authority=operation)
    try:
        catalogue.require(exemption_article)
    except RegistryValidationError:
        return _unaccepted_registry_value_issue(
            transaction_id,
            field="exemption_article",
            value=str(exemption_article),
            effective_date=effective_date,
        )
    if effective_category != require_iva_category("domestic_exempt", authority=operation):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
            detail=render_tr(
                "aggregation.iva_ledger.errors.exemption_article_outside_domestic_exempt",
                value=str(exemption_article),
                category=effective_category.value,
            ),
        )
    return None


def _unaccepted_art_104_tres_exclusion_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    exclusion = transaction.art_104_tres_exclusion
    if exclusion is None:
        return None
    effective_date = today_madrid()
    catalogue = resolve_art104_tres_exclusion_catalogue(effective_date=effective_date, authority=operation)
    try:
        declared = catalogue.require(exclusion)
    except RegistryValidationError:
        return _unaccepted_registry_value_issue(
            transaction_id,
            field="art_104_tres_exclusion",
            value=str(exclusion),
            effective_date=effective_date,
        )
    if declared not in catalogue.operator_declared:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.UNACCEPTED_REGISTRY_VALUE,
            detail=render_tr(
                "aggregation.iva_ledger.errors.art_104_tres_exclusion_not_operator_declared",
                value=str(declared),
            ),
        )
    return None


def _resolve_iva_transaction_context(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionContext | _IvaTransactionOutcome:
    transaction_id = transaction.transaction_id
    ledger_date = transaction.raw.value_date or transaction.raw.booked_date
    operation_date = transaction.operation_date or ledger_date
    cash_treatment = transaction.cash_accounting_treatment
    # The filing window depends on the treatment, so an undeclared one cannot
    # be placed in or out of the period. Its refusal is held until the
    # candidate filters below have had their say: a personal row or one with no
    # IVA flow does not feed this calculation, whatever its treatment says.
    unaccepted_treatment = _unaccepted_cash_accounting_treatment_issue(transaction, operation=operation)
    if unaccepted_treatment is None:
        period_issue = _period_admission_issue(
            transaction,
            resolved_period=resolved_period,
            operation_date=operation_date,
            cash_treatment=cash_treatment,
            operation=operation,
        )
        if period_issue is not None:
            return _IvaTransactionOutcome(gate_issue=period_issue)
    ownership = _resolve_iva_transaction_ownership(
        transaction,
        operation_date=operation_date,
        resolved_period=resolved_period,
        operation=operation,
    )
    if isinstance(ownership, _IvaTransactionOutcome):
        return ownership
    invoice_kind, proportionality = ownership
    # Establish the source's business/flow ownership before diagnosing missing
    # tax substrate. A personal foreign-currency row is not held-back IVA.
    substrate_issue = _substrate_admission_issue(transaction)
    if substrate_issue is not None:
        return _IvaTransactionOutcome(gate_issue=substrate_issue)
    if unaccepted_treatment is not None:
        return _IvaTransactionOutcome(gate_issue=unaccepted_treatment)
    incoherent_cash_accounting = _cash_accounting_evidence_issue(transaction, operation=operation)
    if incoherent_cash_accounting is not None:
        return _IvaTransactionOutcome(gate_issue=incoherent_cash_accounting)
    return _IvaTransactionContext(
        transaction_id=transaction_id,
        operation_date=operation_date,
        cash_treatment=cash_treatment,
        invoice_kind=invoice_kind,
        proportionality=proportionality,
    )


def _resolve_iva_transaction_ownership(
    transaction: Transaction,
    *,
    operation_date: date,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> tuple[InvoiceKind, Decimal] | _IvaTransactionOutcome:
    transaction_id = transaction.transaction_id
    invoice_kind = invoice_kind_for_direction(transaction.direction)
    if invoice_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                detail=f"transaction direction {transaction.direction.value!r} is not an IVA settlement flow",
            ),
        )
    proportionality = business_proportionality_for(transaction)
    if proportionality is None:
        reason = (
            IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        business_classification = transaction.business_classification.value
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=reason,
                detail=f"business classification {business_classification!r} cannot feed IVA aggregation",
            ),
        )
    if invoice_kind is InvoiceKind.RECEIVED:
        category_proportion = iva_category_deductible_proportion(
            transaction,
            proportionality,
            operation_date=operation_date,
            year=resolved_period.filing_year,
            operation=operation,
        )
        if category_proportion is None:
            return _IvaTransactionOutcome(
                gate_issue=IvaLedgerAggregationIssue(
                    transaction_id=transaction_id,
                    reason=IvaLedgerAggregationIssueReason.NON_DEDUCTIBLE_MIXED_USE,
                    detail=(
                        f"category {transaction.category_id!r} grants no IVA deduction for simultaneous "
                        "business and private use"
                    ),
                ),
            )
        proportionality = category_proportion
    return invoice_kind, proportionality


def _resolve_iva_transaction_amounts(
    transaction: Transaction,
    *,
    operation_date: date,
    proportionality: Decimal,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionAmounts | _IvaTransactionOutcome:
    return _resolved_iva_transaction_amounts(
        transaction,
        operation_date=operation_date,
        proportionality=proportionality,
        operation=operation,
    )


def _resolved_iva_transaction_amounts(
    transaction: Transaction,
    *,
    operation_date: date,
    proportionality: Decimal,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionAmounts | _IvaTransactionOutcome:
    """Validate measured tax facts, then scale them for the business share."""
    transaction_id = transaction.transaction_id
    missing_reason = missing_tax_fact_reason(transaction)
    if missing_reason is not None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=missing_reason,
                detail=missing_tax_fact_detail(missing_reason),
            ),
        )
    taxable_base = transaction.taxable_base
    iva_amount = transaction.iva_amount
    iva_rate = transaction.iva_rate
    if taxable_base is None or iva_amount is None or iva_rate is None:
        msg = (
            f"transaction {transaction_id} cleared the IVA missing-fact screen while base, cuota or "
            "tipo is still unmeasured; the screen and the required tax facts disagree"
        )
        raise ValueError(msg)
    if iva_rate == Decimal("0") and iva_amount != Decimal("0"):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW,
                detail=(
                    f"row declares iva_rate 0 with iva_amount {iva_amount}; a zero tipo "
                    "admits only a zero cuota, so one of the two facts is wrong"
                ),
            ),
        )
    rate_kind = _canonical_iva_rate_kind(
        transaction,
        iva_rate=iva_rate,
        operation_date=operation_date,
        operation=operation,
    )
    if isinstance(rate_kind, _IvaTransactionOutcome):
        return rate_kind
    # Only the cuota follows the business share. The Modelo 303 instructions
    # declare the deductible bases "sin prorratear" (IVA Deducible), and for
    # bienes de inversion state that the base goes unreduced even where the
    # deduction percentage for partial affectation (LIVA art. 95.Tres) applies.
    return _IvaTransactionAmounts(
        rate_kind=rate_kind,
        base_amount=taxable_base,
        iva_amount=iva_amount * proportionality,
        recargo_amount=(transaction.recargo_amount or Decimal("0")) * proportionality,
    )


def _canonical_iva_rate_kind(
    transaction: Transaction,
    *,
    iva_rate: Decimal,
    operation_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaRateKind | _IvaTransactionOutcome:
    """Resolve a declared rate against the legal table available on its date."""
    rate_kind = iva_rate_kind_for(iva_rate, on_date=operation_date, operation=operation)
    if rate_kind is None:
        member_state = spanish_eu_member_state(effective_date=operation_date, authority=operation)
        if rate_table_covers_any_positive_tier(member_state, operation_date, operation=operation):
            return _IvaTransactionOutcome(
                gate_issue=IvaLedgerAggregationIssue(
                    transaction_id=transaction.transaction_id,
                    reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
                    detail=(
                        f"IVA rate {iva_rate} is not a canonical substrate IVA rate for {operation_date.isoformat()}"
                    ),
                ),
            )
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction.transaction_id,
                reason=IvaLedgerAggregationIssueReason.IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE,
                detail=(
                    f"no IVA rate is on record for {operation_date.isoformat()}: the rate table "
                    "reaches no tier bearing a positive rate on that date, so a transaction dated "
                    f"there cannot be classified whatever rate it carries. The rate {iva_rate} is "
                    "not what needs correcting -- the filing year is outside the supported window"
                ),
            ),
        )
    return rate_kind


def _declared_category_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    explicit_category: IvaCategory,
    invoice_kind: InvoiceKind,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Return why an OPERATOR-DECLARED category contradicts the row, or ``None``.

    Every screen here is scoped to the declared category deliberately. The
    derived branch reads its category off the rate, so it cannot contradict the
    rate; a screen written across both would be vacuous on half its population
    while reading as though it covered it.
    """
    effective_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
    if explicit_category in registry_category_projection(
        "m303_base_out_of_scope",
        effective_date=effective_date,
        authority=operation,
    ):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY,
            detail=(
                f"iva_category {explicit_category.value!r} does not produce a declarable ledger IVA "
                "observation; the registry places its base outside the Modelo 303 ledger scope"
            ),
        )
    counterparty_issue = validate_iva_ledger_counterparty_category(transaction, operation=operation)
    if counterparty_issue is not None:
        return counterparty_issue
    catalogue = registry_component_catalogue(effective_date=effective_date, authority=operation)
    components = category_components(explicit_category, invoice_kind, component_catalogue=catalogue)
    does_not_arise = registry_kind_applicability_token(
        "does_not_arise",
        effective_date=effective_date,
        authority=operation,
    )
    if components.applicability == does_not_arise:
        # The row's own note names the category that IS this side's
        # counterpart, so the refusal can say what the operator probably meant.
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE,
            detail=(
                f"row declares iva_category {explicit_category.value!r} on a "
                f"{invoice_kind.value!r} invoice, a combination that describes no operation. "
                f"{components.retencion_note}"
            ),
        )
    zero_by_law = registry_component_presence_token("zero_by_law", effective_date=effective_date, authority=operation)
    if components.cuota == zero_by_law and transaction.iva_rate != Decimal("0"):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY,
            detail=(
                f"row declares iva_category {explicit_category.value!r} on a "
                f"{invoice_kind.value!r} invoice, whose cuota is zero by law, with "
                f"iva_rate {transaction.iva_rate}; a category that admits no cuota admits "
                "no tipo either, so one of the two facts is wrong"
            ),
        )
    return None


def _effective_iva_category_for(
    transaction: Transaction,
    *,
    rate_kind: IvaRateKind,
    operation: PinnedAuthorityOperation,
) -> IvaCategory:
    """Return the dated IVA category a ledger row settles under.

    A declared category is resolved against the catalogue effective on the row's
    own date, so the caller holds the effective member rather than the persisted
    token; an undeclared one is read off the tier its rate resolved to, which is
    the registry's own category for that tier.
    """
    effective_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
    explicit_category = transaction.iva_category
    if explicit_category is not None:
        return resolve_iva_category_catalogue(
            effective_date=effective_date,
            authority=operation,
        ).require(explicit_category)
    catalogue = resolve_iva_rate_kind_catalogue(effective_date=effective_date, authority=operation)
    definition = next((item for item in catalogue.definitions if item.token == rate_kind), None)
    if definition is None:
        raise ValueError(f"IVA rate kind {rate_kind!s} is not declared by the pinned rate catalogue")
    return IvaCategory(definition.category)


def _resolve_iva_transaction_classification(
    transaction: Transaction,
    *,
    transaction_id: str,
    invoice_kind: InvoiceKind,
    amounts: _IvaTransactionAmounts,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionClassification | _IvaTransactionOutcome:
    rate_kind = amounts.rate_kind
    effective_category = _effective_iva_category_for(transaction, rate_kind=rate_kind, operation=operation)
    unaccepted_value = _unaccepted_row_value_issue(
        transaction,
        transaction_id=transaction_id,
        effective_category=effective_category,
        operation=operation,
    )
    if unaccepted_value is not None:
        return _IvaTransactionOutcome(gate_issue=unaccepted_value)
    declared_issue = _declared_transaction_category_issue(
        transaction,
        transaction_id=transaction_id,
        effective_category=effective_category,
        invoice_kind=invoice_kind,
        operation=operation,
    )
    if declared_issue is not None:
        return _IvaTransactionOutcome(gate_issue=declared_issue)
    effective_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
    cash_accounting_issue = _cash_accounting_category_issue(
        transaction,
        transaction_id=transaction_id,
        effective_category=effective_category,
        effective_date=effective_date,
        operation=operation,
    )
    if cash_accounting_issue is not None:
        return _IvaTransactionOutcome(gate_issue=cash_accounting_issue)
    flow_direction = derive_flow_for_classification(category=effective_category, invoice_direction=invoice_kind)
    # Input IVA is deductible only on an exact fact kind with immutable
    # provenance; refusing here reports the row instead of failing the run.
    missing_deduction_issue = _missing_deduction_classification_issue(
        transaction,
        transaction_id=transaction_id,
        category=effective_category,
        flow_direction=flow_direction,
    )
    if missing_deduction_issue is not None:
        return _IvaTransactionOutcome(gate_issue=missing_deduction_issue)
    inadmissible_deduction = inadmissible_deduction_issue(
        transaction,
        transaction_id=transaction_id,
        category=effective_category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=amounts.base_amount,
        iva_amount=amounts.iva_amount,
    )
    if inadmissible_deduction is not None:
        return _IvaTransactionOutcome(gate_issue=inadmissible_deduction)
    return _IvaTransactionClassification(category=effective_category, flow_direction=flow_direction)


def _declared_transaction_category_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    effective_category: IvaCategory,
    invoice_kind: InvoiceKind,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    if transaction.iva_category is None:
        return None
    return _declared_category_issue(
        transaction,
        transaction_id=transaction_id,
        explicit_category=effective_category,
        invoice_kind=invoice_kind,
        operation=operation,
    )


def _cash_accounting_category_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    effective_category: IvaCategory,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    if is_iva_cash_accounting_none(transaction.cash_accounting_treatment, authority=operation):
        return None
    excluded = registry_category_projection(
        "cash_accounting_excluded",
        effective_date=effective_date,
        authority=operation,
    )
    if effective_category not in excluded:
        return None
    return IvaLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EXCLUDED_CATEGORY,
        detail=(
            f"iva_category {effective_category.value!r} is excluded from the cash-accounting regime "
            "under Ley 37/1992 art. 163 duodecies"
        ),
    )


def _missing_deduction_classification_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    category: IvaCategory,
    flow_direction: IvaFlowDirection,
) -> IvaLedgerAggregationIssue | None:
    # Input IVA is deductible only on an exact fact kind with immutable
    # provenance; refusing here reports the row instead of failing the run.
    # Asked of fact 0085 rather than of the flow alone. Every RECEIVED row
    # settles as ``soportado``, while LIVA art. 92.Uno grants a deduction only
    # of a cuota that was devengada and repercutida. Exempt, not-subject, or
    # recargo-cost rows therefore have no deduction identity to supply. A 0 %
    # sujeta row remains in the domestic family and still requires its identity.
    if not (
        is_deducible_flow(flow_direction)
        and admits_iva_deduction_classification(category=category, flow_direction=flow_direction)
        and (transaction.deduction_fact_kind is None or transaction.deduction_provenance is None)
    ):
        return None
    return IvaLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
        detail="IVA deduction facts require an exact kind and immutable evidence provenance before calculation",
    )


def classify_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionOutcome:
    """Filter + classify one ledger transaction against the IVA aggregation pipeline.

    Returns an :class:`_IvaTransactionOutcome` carrying the typed
    sinks the orchestrator drains. Each pre-observation gate projects
    to ``gate_issue`` with a typed
    :class:`IvaLedgerAggregationIssueReason`. The observation-eligible
    path constructs the observation and (when present) the prorrata
    reference; an invalid prorrata reference is reported as a
    ``prorrata_issue`` alongside the observation.
    """
    admission = _admit_iva_transaction(transaction, resolved_period=resolved_period, operation=operation)
    if isinstance(admission, _IvaTransactionOutcome):
        return admission
    return _project_iva_transaction(
        transaction,
        resolved_period=resolved_period,
        context=admission.context,
        amounts=admission.amounts,
        classification=admission.classification,
        operation=operation,
    )


def iva_transaction_gate_issue(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Return the first pre-observation gate issue for one row, or ``None``.

    :func:`classify_iva_transaction` stopped before the projection step. A
    readiness consumer needs to know WHETHER a row will be excluded and why, not
    what it would have contributed, and the projection step is where the
    criterio-de-caja split and the prorrata attachment are computed -- work whose
    result a readiness report has nothing to say about.

    Running the same gates in the same order is the point: a readiness verdict
    derived independently would eventually disagree with the calculation's, and
    an operator cannot act on two answers.
    """
    admission = _admit_iva_transaction(transaction, resolved_period=resolved_period, operation=operation)
    if isinstance(admission, _IvaTransactionOutcome):
        return admission.gate_issue
    return None


def _admit_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionAdmission | _IvaTransactionOutcome:
    """Run every pre-observation gate, yielding the facts projection needs."""
    _resolve_iva_registry_declarations(effective_date=resolved_period.end_date, operation=operation)
    context = _resolve_iva_transaction_context(transaction, resolved_period=resolved_period, operation=operation)
    if isinstance(context, _IvaTransactionOutcome):
        return context
    amounts = _resolve_iva_transaction_amounts(
        transaction,
        operation_date=context.operation_date,
        proportionality=context.proportionality,
        operation=operation,
    )
    if isinstance(amounts, _IvaTransactionOutcome):
        return amounts
    classification = _resolve_iva_transaction_classification(
        transaction,
        transaction_id=context.transaction_id,
        invoice_kind=context.invoice_kind,
        amounts=amounts,
        operation=operation,
    )
    if isinstance(classification, _IvaTransactionOutcome):
        return classification
    return _IvaTransactionAdmission(context=context, amounts=amounts, classification=classification)


def _project_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
    context: _IvaTransactionContext,
    amounts: _IvaTransactionAmounts,
    classification: _IvaTransactionClassification,
    operation: PinnedAuthorityOperation,
) -> _IvaTransactionOutcome:
    prorrata_reference, prorrata_issue, linked_prorrata_id = resolve_iva_prorrata_attachment(
        transaction,
        flow_direction=classification.flow_direction,
        operation_date=context.operation_date,
        base_amount=amounts.base_amount,
        iva_amount=amounts.iva_amount,
    )
    if not is_iva_cash_accounting_none(context.cash_treatment, authority=operation):
        observations = cash_accounting_observations(
            transaction,
            resolved_period=resolved_period,
            operation_date=context.operation_date,
            category=classification.category,
            rate_kind=amounts.rate_kind,
            flow_direction=classification.flow_direction,
            proportionality=context.proportionality,
            full_base_amount=amounts.base_amount,
            full_iva_amount=amounts.iva_amount,
            linked_prorrata_id=linked_prorrata_id,
            deduction_fact_kind=transaction.deduction_fact_kind,
            deduction_provenance=transaction.deduction_provenance,
            operation=operation,
        )
        if isinstance(observations, IvaLedgerAggregationIssue):
            return _IvaTransactionOutcome(gate_issue=observations)
        if not observations:
            return _IvaTransactionOutcome(
                gate_issue=IvaLedgerAggregationIssue(
                    transaction_id=context.transaction_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(
                        "cash-accounting operation date, payment evidence dates, and fallback date "
                        f"are outside {resolved_period}"
                    ),
                ),
            )
        return _IvaTransactionOutcome(
            observations=observations,
            prorrata_reference=prorrata_reference,
            prorrata_issue=prorrata_issue,
        )
    observation = iva_observation(
        ledger_id=transaction.transaction_id,
        transaction_date=context.operation_date,
        category=classification.category,
        exemption_article=transaction.exemption_article,
        rate_kind=amounts.rate_kind,
        flow_direction=classification.flow_direction,
        base_amount=amounts.base_amount,
        iva_amount=amounts.iva_amount,
        recargo_amount=amounts.recargo_amount,
        prorrata_reference_id=linked_prorrata_id,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        input_classification=transaction.input_classification,
        prorrata_sector_id=transaction.prorrata_sector_id,
        # The rate the operator declared on the row, kept beside the tier it
        # resolved to. Read from the transaction rather than re-derived from
        # the tier: the tier-to-rate mapping is date-dependent, so re-deriving
        # would answer "what does this tier mean today" when the question is
        # "what was this line actually charged".
        applied_rate=transaction.iva_rate,
        deduction_fact_kind=transaction.deduction_fact_kind,
        deduction_provenance=transaction.deduction_provenance,
        investment_asset_id=transaction.investment_asset_id,
        rectifies_ledger_id=transaction.rectifies_ledger_id,
        operation=operation,
    )
    return _IvaTransactionOutcome(
        observations=(observation,),
        prorrata_reference=prorrata_reference,
        prorrata_issue=prorrata_issue,
    )
