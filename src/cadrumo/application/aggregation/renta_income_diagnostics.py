"""Settlement and diagnostic measurements for the Renta activity-income ledger projection.

This sibling owns what the income projection reports about invoices and receipts
rather than the observations themselves: the accrued income an issued invoice
leaves unpaid, receipts that overpay their invoice, and the advisories a resolver
attaches about withholding that is unpaid, shared out, paid late or resting on an
untrusted invoice. The row typing is owned by :mod:`~.renta_income_models`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from ...core.aggregation import LedgerWithholdingDerivation
from ...core.casilla_id import CasillaId
from ...core.money.rounding import round_to_cents
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from . import renta_income_evidence
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationUnresolved,
    invoice_accrual_date,
    linked_accrual_date,
)
from .renta_income_models import (
    AccruedUnpaidIncome,
    RentaIncomeLedgerAggregationIssue,
    RentaIncomeLedgerAggregationIssueReason,
    RentaIncomeObservation,
)
from .source_mesh import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic


def accrued_unpaid_income(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    window_start: date,
    window_end: date,
    target_casilla_id: CasillaId,
    criteria: ImputationCriteria,
) -> tuple[AccruedUnpaidIncome, ...]:
    """Return what the issued invoices accruing in the window leave unsettled by their active receipts."""
    if criteria.usable(window_end.year) is not ActivityImputationCriterion.DEVENGO:
        return ()
    active = {
        transaction.transaction_id: transaction
        for transaction in transactions.values()
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
    }
    found: list[AccruedUnpaidIncome] = []
    for invoice in invoices.values():
        if not _accrues_in_window(invoice, bucket_id=bucket_id, window_start=window_start, window_end=window_end):
            continue
        remainder = _unsettled_remainder(invoice, active, target_casilla_id=target_casilla_id)
        if remainder is not None:
            found.append(remainder)
    return tuple(found)


def _accrues_in_window(invoice: Invoice, *, bucket_id: str, window_start: date, window_end: date) -> bool:
    """Return whether this bucket's EUR issued invoice accrues inside the window."""
    accrual = invoice_accrual_date(invoice)
    return not (
        invoice.kind is not InvoiceKind.ISSUED
        or invoice.bucket_id != bucket_id
        or invoice.currency != "EUR"
        or accrual is None
        or not window_start <= accrual <= window_end
    )


def _unsettled_remainder(
    invoice: Invoice, active: Mapping[str, Transaction], *, target_casilla_id: CasillaId
) -> AccruedUnpaidIncome | None:
    """Return the base and retencion the invoice's receipts leave unpaid, or ``None`` when nothing remains."""
    receipts = [active[row] for row in invoice.linked_transaction_ids if row in active]
    shares = [renta_income_evidence.part_payment_share(invoice, receipt) for receipt in receipts]
    if None in shares:
        return None
    retencion = invoice.retention_amount or Decimal("0")
    settled = [share for share in shares if share is not None]
    base_left = invoice.base_total - _settled_by_shares(invoice.base_total, settled)
    retencion_left = retencion - _settled_by_shares(retencion, settled)
    if base_left > 0:
        return AccruedUnpaidIncome(
            invoice_id=invoice.invoice_id,
            target_casilla_id=target_casilla_id,
            base=base_left,
            withholding_unpaid=max(retencion_left, Decimal("0")),
        )
    return None


def _settled_by_shares(amount: Decimal, shares: Sequence[Decimal]) -> Decimal:
    """Return the part of ``amount`` the receipts' shares have settled, each rounded to cents."""
    return sum((round_to_cents(amount * share) for share in shares), Decimal("0"))


def overpaid_invoice_issues(
    transactions: TransactionCatalogue, invoices: InvoiceCatalogue, *, bucket_id: str
) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
    """Refuse to place receipts that together exceed what their invoice leaves to be paid."""
    collected: dict[str, list[Transaction]] = {}
    for transaction in transactions.values():
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE and transaction.invoice_id is not None:
            collected.setdefault(transaction.invoice_id, []).append(transaction)
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    for invoice_id, receipts in collected.items():
        invoice = invoices.get(invoice_id)
        if invoice is None or invoice.kind is not InvoiceKind.ISSUED or invoice.bucket_id != bucket_id:
            continue
        if _receipts_within_invoice(invoice, receipts):
            continue
        issues.extend(_overpaid_receipt_issues(invoice, receipts))
    return tuple(issues)


def _receipts_within_invoice(invoice: Invoice, receipts: Sequence[Transaction]) -> bool:
    """Return whether the receipts are too few to compare or together stay within the invoice's net cash."""
    comparison = renta_income_evidence.settlement_comparison(invoice, receipts)
    return len(receipts) < 2 or comparison is None or comparison.cash <= comparison.owed


def _overpaid_receipt_issues(
    invoice: Invoice, receipts: Sequence[Transaction]
) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
    """Name each receipt of an overpaid invoice as an unresolved imputation."""
    return tuple(
        RentaIncomeLedgerAggregationIssue(
            transaction_id=row.transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED,
            detail=f"{ImputationUnresolved.OVERPAID_INVOICE.value}: receipts exceed invoice {invoice.invoice_number}",
        )
        for row in receipts
    )


def accrued_withholding_unpaid_diagnostics(
    accrued: Sequence[AccruedUnpaidIncome], *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report the withholding imputed to the window that stays undeductible until its income is paid."""
    unpaid = [row for row in accrued if row.withholding_unpaid > 0]
    if not unpaid:
        return ()
    total = sum((row.withholding_unpaid for row in unpaid), Decimal("0"))
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=(
                f"{len(unpaid)} accrued invoice(s) state {total} EUR of retencion on income not yet collected. "
                "It belongs to this ejercicio (RIRPF art. 79) but is not deductible until paid (art. 78.1; "
                "TEAC 00/03187/2011), so it is left out of the credit."
            ),
            source_ref="accrued_withholding_unpaid",
        ),
    )


def part_payment_diagnostics(
    observations: Sequence[RentaIncomeObservation], *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report the part payments whose base and retencion are a pro rata share, not a stated figure."""
    allocated = [
        row for row in observations if row.withheld_derivation is LedgerWithholdingDerivation.ALLOCATED_ON_PART_PAYMENT
    ]
    if not allocated:
        return ()
    total = sum((row.withheld_amount for row in allocated), Decimal("0"))
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=(
                f"{len(allocated)} part payment(s) carry {total} EUR of retencion shared pro rata from their "
                "invoices (RIRPF arts. 78.1 and 95.1). It stays out of the credit until the payer states it."
            ),
            source_ref="part_payment_allocated",
        ),
    )


def rectification_diagnostics(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    year: int,
    criteria: ImputationCriteria,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name each retencion paid after the return of its accrual year was filed.

    The withholding stays in the year its income accrued (RIRPF art. 79) and the right
    to deduct it arises on payment, so TEAC 00/03187/2011 recovers it by rectifying that
    year (LGT art. 120.3), never by crediting it in the year of payment.
    """
    findings: list[CalculationSourceDiagnostic] = []
    for transaction in transactions.values():
        bearing = _retention_bearing_invoice(transaction, invoices, bucket_id=bucket_id)
        if bearing is None:
            continue
        invoice, retention = bearing
        finding = _late_retention_finding(
            transaction, invoice, retention, year=year, criteria=criteria, resolver_id=resolver_id
        )
        if finding is not None:
            findings.append(finding)
    return tuple(findings)


def _retention_bearing_invoice(
    transaction: Transaction, invoices: InvoiceCatalogue, *, bucket_id: str
) -> tuple[Invoice, Decimal] | None:
    """Return the bucket's invoice that an active receipt settles, with the retencion it states."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE or transaction.invoice_id is None:
        return None
    invoice = invoices.get(transaction.invoice_id)
    if invoice is None or invoice.bucket_id != bucket_id:
        return None
    retention = invoice.retention_amount
    if retention in (None, 0):
        return None
    return invoice, retention


def _late_retention_finding(
    transaction: Transaction,
    invoice: Invoice,
    retention: Decimal,
    *,
    year: int,
    criteria: ImputationCriteria,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    """Report the retencion this receipt paid after the return of its accrual year was filed."""
    accrual = linked_accrual_date(invoice, kind=InvoiceKind.ISSUED)
    if accrual is None or criteria.usable(accrual.year) is not ActivityImputationCriterion.DEVENGO:
        return None
    cash = transaction.raw.value_date or transaction.raw.booked_date
    filed_on = criteria.filings.filed_on.get(accrual.year)
    if filed_on is None or cash <= filed_on or year not in {accrual.year, cash.year}:
        return None
    share = renta_income_evidence.part_payment_share(invoice, transaction)
    amount = retention if share is None else round_to_cents(retention * share)
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="ledger_renta_income_aggregation",
        resolver_id=resolver_id,
        source_ref=f"invoice:{invoice.invoice_id}",
        message=(
            f"Invoice {invoice.invoice_number}: {amount} EUR of retencion was paid on {cash}, after the "
            f"return of {accrual.year} was filed on {filed_on}. Claim it by an autoliquidacion rectificativa "
            f"of {accrual.year} (TEAC 00/03187/2011; LGT art. 120.3); it is never credited in {cash.year}."
        ),
    )


def unusable_sales_invoice_diagnostics(
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
    the message budget by :func:`fitted_diagnostic_id_list`, so a long list
    degrades to a count instead of raising out of the diagnostic and taking the
    calculation down with it.
    """
    by_reason: dict[renta_income_evidence.SalesInvoiceEvidenceRefusal, list[RentaIncomeObservation]] = {}
    for observation in observations:
        if observation.sales_invoice_refusal is not None:
            by_reason.setdefault(observation.sales_invoice_refusal, []).append(observation)
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
                + fitted_diagnostic_id_list(
                    sorted(row.transaction_id for row in rows),
                    budget=DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(preamble),
                ),
            ),
        )
    return tuple(diagnostics)


def fitted_diagnostic_id_list(identifiers: Sequence[str], *, budget: int) -> str:
    """Render ``identifiers`` into at most ``budget`` characters, stating omissions.

    Shows as many ids as fit alongside the "(and N more)" suffix that describes
    the ones it dropped -- the suffix is part of the budget, because a
    truncation notice that itself overflows would defeat the cap it exists to
    respect.

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
