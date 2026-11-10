"""Classification of one ledger transaction into a Renta expense observation or the issue that keeps it out.

This module uses :class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, overload

from ...core.decimal.constants import ZERO
from ...core.period import Period
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.categories.profile import CategoryProfile
from ...domain.categories.spending_category import SpendingCategory
from ...domain.contribuyente.ccaa import CCAA
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.iva.schema import InvoiceKind
from ...domain.renta.ledger_expenses import (
    RentaDeductibilityContext,
    RentaDeductibilityResult,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
    select_deductibility_profile,
)
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from . import shared_issue_reasons
from .currency_predicates import (
    effective_eur_amount,
    is_non_eur_without_conversion,
)
from .renta_business_eligibility import (
    exclusive_business_use,
    relies_on_activity_marker,
    renta_expense_business_proportion,
    row_scaling_proportion,
)

if TYPE_CHECKING:
    pass
from .renta_imputation import ImputationCriteria, ImputationUnresolved, impute_ledger_row, received_invoice_reference
from .renta_ledger_evidence import (
    iva_amount_for,
    purchase_invoice_evidence_payload,
    recargo_amount_for,
    taxable_base_for,
)
from .renta_ledger_models import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
)

_LEDGER_CATALOGUE_ID = "ledger"


@dataclass(frozen=True, slots=True)
class CategoryRuleRefusal:
    """Why a ledger category cannot be evaluated; ``reason`` is a shared issue-reason string."""

    reason: str
    detail: str


def resolve_category_rule(
    category_id: str | None,
    *,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    profile_year: int,
) -> tuple[SpendingCategory, CategoryProfile] | CategoryRuleRefusal:
    """Resolve a ledger category and the profile selected for the taxpayer's residence.

    The one owner of whether a row's category can answer for its expense, for the
    annual declaration and the pago fraccionado alike. RIRPF art. 110.1.a) computes
    the payment on the rendimiento neto, with no deduction rule of its own, so a
    row the annual declaration cannot evaluate is not evaluable for the payment.

    Returns:
        The category with its selected profile, or the refusal naming why the
        row, the taxonomy, the year's profiles or the residence comunidad cannot
        supply one.
    """
    if category_id is None or not category_id.strip():
        return CategoryRuleRefusal(
            shared_issue_reasons.MISSING_CATEGORY,
            "business expense has no spending category; assign it so its deduction rule can run",
        )
    try:
        category = normalize_spending_category(category_id)
    except RegistryValidationError:
        return CategoryRuleRefusal(
            shared_issue_reasons.UNKNOWN_CATEGORY,
            f"ledger category {category_id!r} is not in the spending taxonomy",
        )
    profile = profiles.get(category)
    if profile is None:
        return CategoryRuleRefusal(
            shared_issue_reasons.MISSING_CATEGORY_PROFILE,
            f"category {category.value!r} has no profile for {profile_year}",
        )
    category_region_overrides = {
        ccaa: overrides[category] for ccaa, overrides in region_overrides.items() if category in overrides
    }
    selected_profile = select_deductibility_profile(
        state_profile=profile,
        region_override_profiles=category_region_overrides,
        context=context,
    )
    if selected_profile is None:
        return CategoryRuleRefusal(
            shared_issue_reasons.REGION_UNDECLARED_FOR_OVERRIDE,
            (
                f"category {category.value!r} carries a territorial-regime deductibility override for "
                f"{profile_year} but the residence comunidad autonoma is undeclared"
            ),
        )
    return category, selected_profile


def classify_renta_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    resolved_period: Period,
    resolved_profile_year: int,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    activity_key: str,
    criteria: ImputationCriteria | None = None,
    definitive_prorrata_pending: bool = False,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Filter + classify one ledger transaction against the Renta-expense pipeline.

    Returns either a typed :class:`RentaDeductibleExpenseObservation`
    (the transaction survives every gate and is eligible) or a typed
    :class:`RentaLedgerAggregationIssue` (any gate rejects it). The
    twelve original early-return branches each project to a typed
    issue with their dedicated reason code; the eligible path returns
    the constructed observation.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    direction = renta_direction_for(transaction.direction, transaction.purchase_invoice_evidence_id)
    if direction is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
            f"transaction direction {transaction.direction.value!r} is not a Renta expense flow",
        )
    if is_non_eur_without_conversion(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            f"transaction currency {transaction.raw.currency!r} is not supported for Renta expenses",
        )
    # Use the EUR projection after rejecting unconverted non-EUR rows, so converted
    # rows contribute their EUR equivalent while EUR rows retain their raw amount.
    eur_amount = effective_eur_amount(transaction)
    proportion = _renta_business_proportion_or_issue(transaction)
    if isinstance(proportion, RentaLedgerAggregationIssue):
        return proportion
    category_profile = _renta_category_profile_or_issue(
        transaction,
        profiles=profiles,
        region_overrides=region_overrides,
        context=context,
        profile_year=resolved_profile_year,
    )
    if isinstance(category_profile, RentaLedgerAggregationIssue):
        return category_profile
    category, profile = category_profile
    proportion = row_scaling_proportion(transaction, proportion, profile.proportionality)
    fact = _renta_expense_fact_or_issue(
        transaction,
        invoices=invoices,
        bucket_id=bucket_id,
        direction=direction,
        category=category,
        activity_key=activity_key,
        eur_amount=eur_amount,
        proportion=proportion,
    )
    if isinstance(fact, RentaLedgerAggregationIssue):
        return fact
    return _renta_observation_or_issue(
        transaction,
        fact=fact,
        profile=profile,
        context=context,
        period=resolved_period,
        imputed=None
        if criteria is None
        else impute_ledger_row(
            transaction,
            None if fact.invoice_id is None else invoices.get(fact.invoice_id),
            kind=InvoiceKind.RECEIVED,
            criteria=criteria,
        ),
        definitive_prorrata_pending=definitive_prorrata_pending,
    )


def _renta_business_proportion_or_issue(
    transaction: Transaction,
) -> Decimal | RentaLedgerAggregationIssue:
    """Return the annual filing business proportion or its precise refusal."""
    # Annual filing deliberately refuses the actividad marker that quarterly M130
    # accepts, through the shared predicate rather than a second policy copy.
    proportion = renta_expense_business_proportion(transaction, accept_activity_marker=False)
    if proportion is not None:
        return proportion
    if relies_on_activity_marker(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW,
            "actividad-marked expense needs business-classification review before the annual declaration",
        )
    reason = RentaLedgerAggregationIssueReason(
        shared_issue_reasons.business_state_issue_reason(transaction.business_classification)
    )
    return _renta_transaction_issue(
        transaction,
        reason,
        f"business classification {transaction.business_classification.value!r} cannot feed Renta expenses",
    )


def _renta_category_profile_or_issue(
    transaction: Transaction,
    *,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    profile_year: int,
) -> tuple[SpendingCategory, CategoryProfile] | RentaLedgerAggregationIssue:
    """Resolve the first-slice category and the profile selected for residence."""
    resolved = resolve_category_rule(
        transaction.category_id,
        profiles=profiles,
        region_overrides=region_overrides,
        context=context,
        profile_year=profile_year,
    )
    if isinstance(resolved, CategoryRuleRefusal):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason(resolved.reason),
            resolved.detail,
        )
    return resolved


def _renta_expense_fact_or_issue(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    direction: RentaExpenseDirection,
    category: SpendingCategory,
    activity_key: str,
    eur_amount: Decimal,
    proportion: Decimal,
) -> RentaDeductibleExpenseFact | RentaLedgerAggregationIssue:
    """Enrich a transaction with invoice evidence and construct its expense fact."""
    evidence_payload = purchase_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction=transaction,
    )
    if isinstance(evidence_payload, RentaLedgerAggregationIssue):
        return evidence_payload
    try:
        return RentaDeductibleExpenseFact(
            transaction_id=transaction.transaction_id,
            invoice_id=received_invoice_reference(transaction),
            catalogue_id=_LEDGER_CATALOGUE_ID,
            operation_date=transaction.raw.value_date or transaction.raw.booked_date,
            invoice_issue_date=evidence_payload.invoice_issue_date,
            posting_date=transaction.raw.booked_date,
            gross_amount=business_fact_amount(eur_amount, proportion),
            taxable_base=business_fact_amount(taxable_base_for(transaction, evidence_payload), proportion),
            iva_amount=business_fact_amount(iva_amount_for(transaction, evidence_payload), proportion),
            recargo_amount=business_fact_amount(recargo_amount_for(transaction, evidence_payload), proportion),
            direction=direction,
            category=category,
            activity_key=activity_key,
            exclusive_business_use=exclusive_business_use(transaction),
        )
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def _unplaced_payment_issue(
    transaction: Transaction, *, fact: RentaDeductibleExpenseFact, period: Period, unresolved: ImputationUnresolved
) -> RentaLedgerAggregationIssue:
    """Return the issue for a payment whose ejercicio the imputation could not decide."""
    if not (period.contains(fact.operation_date) or period.contains(fact.filing_date)):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            f"payment of {fact.operation_date.isoformat()} is outside {period}",
        )
    return _renta_transaction_issue(
        transaction,
        RentaLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED,
        f"{unresolved.value}: payment of {fact.operation_date.isoformat()} cannot be placed in an ejercicio",
    )


def _renta_observation_or_issue(
    transaction: Transaction,
    *,
    fact: RentaDeductibleExpenseFact,
    profile: CategoryProfile,
    context: RentaDeductibilityContext,
    period: Period,
    imputed: date | ImputationUnresolved | None = None,
    definitive_prorrata_pending: bool = False,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Apply filing-period and deductibility gates to one validated fact."""
    if isinstance(imputed, ImputationUnresolved):
        return _unplaced_payment_issue(transaction, fact=fact, period=period, unresolved=imputed)
    anchor = fact.filing_date if imputed is None else imputed
    if not period.contains(anchor):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            f"filing date {anchor.isoformat()} is outside {period}",
        )
    if definitive_prorrata_pending and fact.taxable_base is not None and (fact.iva_amount or Decimal(0)) != 0:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.DEFINITIVE_PRORRATA_PENDING,
            f"the definitive IVA prorrata of {period.filing_year} is not registered, "
            "so the part of this row's IVA that joins the expense is not known",
        )
    result = evaluate_renta_deductibility(fact, profile, context)
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason(refusal_issue_reason(result)),
            result.reason,
        )
    try:
        return build_renta_deductible_expense_observation(fact, result, tax_year=period.filing_year, imputed_on=imputed)
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def refusal_issue_reason(result: RentaDeductibilityResult) -> str:
    """Return the shared issue reason a refused deductibility result reports.

    A refusal that asks the operator for one specific fact keeps its own
    reason; every other refusal is the generic ineligible-deductibility reason.
    """
    if result.refusal is not None:
        return result.refusal.value
    return shared_issue_reasons.INELIGIBLE_DEDUCTIBILITY


def _renta_transaction_issue(
    transaction: Transaction,
    reason: RentaLedgerAggregationIssueReason,
    detail: str,
) -> RentaLedgerAggregationIssue:
    return RentaLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        category_id=transaction.category_id,
        reason=reason,
        detail=detail,
    )


def renta_direction_for(
    direction: TransactionDirection,
    purchase_invoice_evidence_id: str | None,
) -> RentaExpenseDirection | None:
    """Map a ledger direction, with its purchase invoice evidence, to the Renta expense direction."""
    if direction is TransactionDirection.OUTGOING:
        return RentaExpenseDirection.OUTGOING_EXPENSE
    if direction is TransactionDirection.INCOMING and purchase_invoice_evidence_id is not None:
        return RentaExpenseDirection.REFUND
    return None


@overload
def business_fact_amount(amount: None, proportion: Decimal) -> None: ...
@overload
def business_fact_amount(amount: Decimal, proportion: Decimal) -> Decimal: ...
def business_fact_amount(amount: Decimal | None, proportion: Decimal) -> Decimal | None:
    """Scale a ledger magnitude by the business proportion, keeping an absent amount absent."""
    if amount is None:
        return None
    if amount < ZERO:
        raise ValueError("ledger amount must be a non-negative magnitude")
    return amount * proportion
