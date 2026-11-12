"""Classification of one ledger transaction into a Renta income observation or the issue that keeps it out.

This module uses :class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal

from ...core.aggregation import LedgerIncomeGrounding
from ...core.casilla_id import CasillaId
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction
from ...domain.transactions.savings_link import has_savings_link
from ..invoices.source_observations import is_rectificativa
from . import renta_income_evidence, shared_issue_reasons
from .business_proportion import business_proportion
from .currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from .renta_business_eligibility import is_supplier_refund
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationUnresolved,
    accrual_entry_date,
    impute_ledger_row,
    linked_accrual_date,
)
from .renta_income_models import (
    RentaIncomeLedgerAggregationIssue,
    RentaIncomeLedgerAggregationIssueReason,
    RentaIncomeObservation,
)

_CAPITAL_SUBSIDY_CONCEPT = "subvencion_capital"


def classify_income_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None,
    bucket_id: str,
    cumulative_start: date,
    cumulative_end: date,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeObservation | RentaIncomeLedgerAggregationIssue | None:
    """Filter one ledger transaction against the selected income pipeline.

    Returns a :class:`RentaIncomeObservation` for an eligible receipt, a
    :class:`RentaIncomeLedgerAggregationIssue` for an INCOMING row that fails a
    gate, or ``None`` for an OUTGOING row this income pipeline does not own —
    deductible OUTGOING expenses are aggregated by the
    companion ``ledger_renta_gastos_pago_fraccionado_aggregation`` pipeline
    (:mod:`~.renta_gasto_ledger`), so the income pass skips them silently
    rather than emitting a misleading "expense dropped" advisory.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if _income_transaction_is_out_of_scope(transaction):
        return None
    gate_issue = _income_gate_issue(
        transaction,
        employment_category_matcher=employment_category_matcher,
    )
    if gate_issue is not None:
        return gate_issue
    proportion_or_issue = _income_business_proportion_or_issue(
        transaction,
        activity_category_matcher=activity_category_matcher,
    )
    if isinstance(proportion_or_issue, RentaIncomeLedgerAggregationIssue):
        return proportion_or_issue
    proportion = proportion_or_issue
    # Use the EUR projection after rejecting unconverted non-EUR rows above, so a
    # converted foreign-currency receipt contributes its EUR equivalent while a
    # domestic row retains its raw amount (mirrors the expense pipeline's
    # ``effective_eur_amount`` usage in ``renta_ledger.py``).
    gross_amount = effective_eur_amount(transaction) * proportion

    filing_date_or_issue = (
        _income_filing_date_or_issue(
            transaction,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
        )
        if criteria is None
        else _imputed_income_date_or_issue(
            transaction,
            invoices=invoices,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
            criteria=criteria,
        )
    )
    if filing_date_or_issue is None or isinstance(filing_date_or_issue, RentaIncomeLedgerAggregationIssue):
        return filing_date_or_issue
    filing_date = filing_date_or_issue

    return _income_observation(
        transaction,
        invoices=invoices,
        bucket_id=bucket_id,
        proportion=proportion,
        gross_amount=gross_amount,
        filing_date=filing_date,
        target_casilla_id=target_casilla_id,
        receipts_by_invoice=receipts_by_invoice,
    )


def _income_transaction_is_out_of_scope(transaction: Transaction) -> bool:
    """Return whether the income pass must silently skip this transaction."""
    # Operator reviewed and deliberately excluded this row from filing (a final
    # disposition): omit it before the actividad-económica category override can
    # re-admit it. OUTGOING rows belong to the gasto pipeline and are skipped
    # rather than reported as income exclusions. So do a supplier's refunds, which
    # take the expense back there rather than coming in as income here. A row
    # linked to a savings position is capital-mobiliario income, read only by the
    # position resolver, so it never counts as activity income too.
    return (
        transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED
        or has_savings_link(posicion_ref=transaction.posicion_ref)
        or transaction.direction is not TransactionDirection.INCOMING
        or is_supplier_refund(transaction)
    )


def _income_gate_issue(
    transaction: Transaction,
    *,
    employment_category_matcher: Callable[[Transaction], bool],
) -> RentaIncomeLedgerAggregationIssue | None:
    """Return the first currency or IRPF-category issue for an income row."""
    transaction_id = transaction.transaction_id
    if is_non_eur_without_conversion(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta income",
        )

    # Nómina entries (irpf_category="trabajo") belong to rendimientos del
    # trabajo and must not feed an activity-income target.
    if employment_category_matcher(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME,
            detail=(
                f"irpf_category {transaction.irpf_category!r} belongs to rendimientos del trabajo, "
                "not actividad económica; excluded from activity income"
            ),
        )
    return None


def _income_business_proportion_or_issue(
    transaction: Transaction,
    *,
    activity_category_matcher: Callable[[Transaction], bool],
) -> Decimal | RentaIncomeLedgerAggregationIssue:
    """Return the business share or the precise classification issue."""
    proportion = _income_business_proportion(
        transaction,
        activity_category_matcher=activity_category_matcher,
    )
    if proportion is not None:
        return proportion
    reason = RentaIncomeLedgerAggregationIssueReason(
        shared_issue_reasons.business_state_issue_reason(transaction.business_classification)
    )
    return RentaIncomeLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=reason,
        detail=f"business classification {transaction.business_classification.value!r} cannot feed Renta income",
    )


def _income_filing_date_or_issue(
    transaction: Transaction,
    *,
    cumulative_start: date,
    cumulative_end: date,
) -> date | RentaIncomeLedgerAggregationIssue:
    """Return the transaction filing date or its cumulative-window issue."""
    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if cumulative_start <= filing_date <= cumulative_end:
        return filing_date
    return RentaIncomeLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        detail=f"filing date {filing_date} is outside the cumulative income window",
    )


def _receipt_unresolved(
    transaction: Transaction, invoice: Invoice | None, accrual: date | None, criteria: ImputationCriteria
) -> ImputationUnresolved | None:
    """Return the reading a receipt cannot have under the dated election, or ``None`` when it has one."""
    # A capital subsidy follows its asset's amortization under either criterion, and no
    # ledger row carries a schedule: AEAT Manual Renta, ch. 6, citing STS 398/2022.
    if str(transaction.concepto_ingreso) == _CAPITAL_SUBSIDY_CONCEPT:
        return ImputationUnresolved.CAPITAL_SUBSIDY_SCHEDULE_UNKNOWN
    if invoice is None or accrual is None or criteria.usable(accrual.year) is not ActivityImputationCriterion.DEVENGO:
        return None
    # Under accrual a correction reduces the year's income, so money coming in on one has no reading.
    if is_rectificativa(invoice):
        return ImputationUnresolved.RECTIFICATIVA_WITH_RECEIPT
    # A shared receipt of an invoice whose figures cannot be shared out, or a lone receipt
    # above the invoice, stands for nothing known: cash past the invoice is not its income.
    if (
        len(invoice.linked_transaction_ids) != 1 or renta_income_evidence.receipt_overpays_invoice(invoice, transaction)
    ) and renta_income_evidence.part_payment_share(invoice, transaction) is None:
        return ImputationUnresolved.ACCRUAL_UNKNOWN
    return None


def _imputed_income_date_or_issue(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    cumulative_start: date,
    cumulative_end: date,
    criteria: ImputationCriteria,
) -> date | RentaIncomeLedgerAggregationIssue | None:
    """Place one receipt by the dated election; a row this window has no claim on returns ``None``."""
    cash = transaction.raw.value_date or transaction.raw.booked_date
    invoice = None if transaction.invoice_id is None else invoices.get(transaction.invoice_id)
    accrual = linked_accrual_date(invoice, kind=InvoiceKind.ISSUED)
    # A row the window has to account for, so a refusal must not read as nothing to place.
    entry = None if accrual is None else accrual_entry_date(accrual, criteria, through_year=cumulative_end.year)
    in_window = any(
        on is not None and cumulative_start <= on <= cumulative_end
        for on in (cash, accrual, transaction.accrual_date, entry)
    )
    imputed = _receipt_unresolved(transaction, invoice, accrual, criteria) or impute_ledger_row(
        transaction, invoice, kind=InvoiceKind.ISSUED, criteria=criteria
    )
    if isinstance(imputed, ImputationUnresolved):
        if not in_window:
            return None
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED,
            detail=f"{imputed.value}: receipt of {cash} cannot be placed in an ejercicio",
        )
    return imputed if cumulative_start <= imputed <= cumulative_end else None


def _income_observation(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    proportion: Decimal,
    gross_amount: Decimal,
    filing_date: date,
    target_casilla_id: CasillaId,
    receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None = None,
) -> RentaIncomeObservation:
    """Enrich an eligible income row with invoice evidence and withholding."""
    transaction_id = transaction.transaction_id

    # taxable_base carries the IVA-exclusive base imponible when set; it
    # feeds the taxable_base_sum fact path for the rendimiento-neto binding.
    evidence, evidence_refusal = renta_income_evidence.sales_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction=transaction,
        receipts_by_invoice=receipts_by_invoice,
    )

    # The linked invoice's own base takes precedence over the transaction's tax
    # substrate, with the transaction field as fallback -- the same ordering the
    # expense pipeline uses. A grounded row therefore also stops reporting
    # CASH_FALLBACK below, correctly: the substrate now genuinely exists.
    # The transaction fallback goes through the EUR-equivalent accessor:
    # ``transaction.taxable_base`` is denominated in the row's native
    # currency (see ``domain.transactions.tests.test_gross_invariant``), so a
    # converted foreign-currency row needs the same fx_rate projection the
    # gross amount above already received.
    declared_base = (
        evidence.taxable_base if evidence.taxable_base is not None else effective_eur_taxable_base(transaction)
    )
    # Scaled by the SAME proportion the gross above carries, never a second
    # decision: the two figures describe one receipt, so a rule that divided one
    # and not the other would declare a fraction of the income while the
    # retención derived from the undivided base stayed whole.
    taxable_base_amount: Decimal | None = None if declared_base is None else declared_base * proportion

    withheld = renta_income_evidence.income_withheld_amount(transaction, evidence=evidence)

    return RentaIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=target_casilla_id,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        withheld_amount=withheld.amount,
        withheld_derivation=withheld.derivation,
        sales_invoice_refusal=evidence_refusal,
        filing_date=filing_date,
        source_jurisdiction=transaction.source_jurisdiction,
        grounding=(
            LedgerIncomeGrounding.SUBSTRATE_DECLARED
            if taxable_base_amount is not None
            else LedgerIncomeGrounding.CASH_FALLBACK
        ),
    )


def _income_business_proportion(
    transaction: Transaction,
    *,
    activity_category_matcher: Callable[[Transaction], bool],
) -> Decimal | None:
    """Return the share of one income row that is activity income, or ``None``.

    The single proportion decision for the row: every money figure the
    observation carries is scaled by this one value, so the gross and the
    taxable base cannot disagree about how much of the receipt is the
    activity's.

    When ``irpf_category`` is explicitly set to ``"actividad_economica"`` the
    transaction is already classified as a professional-activity receipt and
    ``business_classification`` is treated as ``BUSINESS`` by definition (the
    category tag is the authoritative signal). This avoids the common case
    where a transaction is tagged with ``irpf_category=actividad_economica``
    before the broader ``business_classification`` sweep has run.

    That short-circuit is also the legally correct answer to a MIXED
    classification on an activity receipt, not merely a convenience. Partial
    affectation is a property of ASSETS: LIRPF art. 29.2 (Ley 35/2006,
    BOE-A-2006-20764) limits it to "elementos patrimoniales que sirvan sólo
    parcialmente al objeto de la actividad económica", and it reaches the
    rendimiento neto through the deductibility of the gastos those assets
    generate (art. 28.1). Nothing in art. 27-30 divides an INGRESO by a usage
    percentage -- a client's payment for professional services is wholly an
    ingreso íntegro of the activity however the taxpayer's own desk, car or
    flat happens to be split. The retención the payer withholds on it agrees:
    RIRPF art. 95.1 (RD 439/2007) fixes the rate "sobre los ingresos íntegros
    satisfechos", a fact about the payment, carrying no affectation term at
    all. So an activity-tagged row is undivided on every figure, and because
    ``income_withheld_amount`` derives a retención for activity rows only,
    every row that carries one is a row this returns ``1`` for.
    """
    if activity_category_matcher(transaction):
        # The selected activity-category matcher is the authoritative eligibility gate.
        return Decimal("1")
    return business_proportion(transaction.business_classification, transaction.business_pct)
