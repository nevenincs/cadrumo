"""Settlement and diagnostic measurements for the Renta activity-income ledger projection.

This sibling owns what the income projection reports about invoices and receipts
rather than the observations themselves: the accrued income an issued invoice
leaves unpaid, receipts that overpay their invoice, and the advisories a resolver
attaches about withholding that is unpaid, shared out, paid late or resting on an
untrusted invoice. The row typing is owned by :mod:`~.renta_income_models`;
:class:`TransactionCatalogue`, the profile's transaction catalogue;
:class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from ...core.aggregation import LedgerWithholdingDerivation
from ...core.casilla_id import CasillaId
from ...core.money.rounding import round_to_cents
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.invoices.service import INVOICE_MATCH_TOLERANCE
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..invoices.source_observations import is_rectificativa, rectified_invoices
from . import renta_income_evidence
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationUnresolved,
    accrual_entry_date,
    invoice_accrual_date,
    linked_accrual_date,
    received_invoice_reference,
)
from .renta_income_models import (
    AccruedUnpaidIncome,
    RectificativaCorrection,
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
    """Return what the issued invoices accruing in the window leave unsettled by their active receipts.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if criteria.usable(window_end.year) is not ActivityImputationCriterion.DEVENGO:
        return ()
    active = {
        transaction.transaction_id: transaction
        for transaction in transactions.values()
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
    }
    found: list[AccruedUnpaidIncome] = []
    for invoice in invoices.values():
        if is_rectificativa(invoice) or not _accrues_in_window(
            invoice, bucket_id=bucket_id, window_start=window_start, window_end=window_end, criteria=criteria
        ):
            continue
        remainder = _unsettled_remainder(invoice, active, target_casilla_id=target_casilla_id)
        if remainder is not None:
            found.append(remainder)
    return tuple(found)


def invoice_enters_window(
    invoice: Invoice,
    *,
    kind: InvoiceKind,
    bucket_id: str,
    window_start: date,
    window_end: date,
    criteria: ImputationCriteria,
) -> bool:
    """Return whether this bucket's invoice of ``kind`` accrues inside the window or is carried into it."""
    accrual = invoice_accrual_date(invoice)
    if invoice.kind is not kind or invoice.bucket_id != bucket_id or accrual is None:
        return False
    entry = accrual_entry_date(accrual, criteria, through_year=window_end.year)
    return entry is not None and window_start <= entry <= window_end


def _accrues_in_window(
    invoice: Invoice, *, bucket_id: str, window_start: date, window_end: date, criteria: ImputationCriteria
) -> bool:
    """Return whether this bucket's issued invoice, with a EUR value, enters the window."""
    return invoice.base_total_eur is not None and invoice_enters_window(
        invoice,
        kind=InvoiceKind.ISSUED,
        bucket_id=bucket_id,
        window_start=window_start,
        window_end=window_end,
        criteria=criteria,
    )


def _payment_shares(invoice: Invoice, receipts: Sequence[Transaction]) -> list[Decimal] | None:
    """Return each settling receipt's share of the invoice, or ``None`` when one cannot be stated."""
    payments = [row for row in receipts if renta_income_evidence.row_settles_invoice(invoice, row)]
    shares = [renta_income_evidence.part_payment_share(invoice, receipt) for receipt in payments]
    settled = [share for share in shares if share is not None]
    return settled if len(settled) == len(shares) else None


def _unsettled_remainder(
    invoice: Invoice, active: Mapping[str, Transaction], *, target_casilla_id: CasillaId
) -> AccruedUnpaidIncome | None:
    """Return the base and retencion the invoice's receipts leave unpaid, or ``None`` when nothing remains."""
    receipts = [active[row] for row in invoice.linked_transaction_ids if row in active]
    if renta_income_evidence.invoice_settled_in_parts(invoice, receipts):
        return None
    settled = _payment_shares(invoice, receipts)
    base_total = invoice.base_total_eur
    if settled is None or base_total is None:
        return None
    retencion = invoice.retention_amount_eur or Decimal("0")
    base_left = base_total - _settled_by_shares(base_total, settled)
    retencion_left = retencion - _settled_by_shares(retencion, settled)
    if base_left <= 0:
        return None
    return AccruedUnpaidIncome(
        invoice_id=invoice.invoice_id,
        target_casilla_id=target_casilla_id,
        base=base_left,
        withholding_unpaid=max(retencion_left, Decimal("0")),
    )


def _receipts_settle_unrated(invoice: Invoice, transactions: TransactionCatalogue) -> bool:
    """Return whether the invoice's active receipts exist and settle it."""
    receipts = [
        row
        for row in (transactions.get(row_id) for row_id in invoice.linked_transaction_ids)
        if row is not None and row.lifecycle_state is TransactionLifecycleState.ACTIVE
    ]
    comparison = renta_income_evidence.settlement_comparison(invoice, receipts)
    return bool(receipts) and comparison is not None and comparison.settled


def accrued_without_eur_value(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    window_start: date,
    window_end: date,
    criteria: ImputationCriteria,
) -> tuple[str, ...]:
    """Name the unrated foreign invoices accruing in the window that their active receipts do not settle.

    Their accrued income has no EUR figure, and a box left silent would read as complete.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if criteria.usable(window_end.year) is not ActivityImputationCriterion.DEVENGO:
        return ()
    found: list[str] = []
    for invoice in invoices.values():
        if invoice.grand_total_eur is not None or is_rectificativa(invoice):
            continue
        if not invoice_enters_window(
            invoice,
            kind=InvoiceKind.ISSUED,
            bucket_id=bucket_id,
            window_start=window_start,
            window_end=window_end,
            criteria=criteria,
        ):
            continue
        if not _receipts_settle_unrated(invoice, transactions):
            found.append(invoice.invoice_number)
    return tuple(found)


class RectificativaReading(NamedTuple):
    """The corrections one window nets, and those it refuses to place."""

    corrections: tuple[RectificativaCorrection, ...] = ()
    refused: tuple[str, ...] = ()


class ReceivedRectificativaReading(NamedTuple):
    """What the received corrections of a window take off each invoice they name."""

    fractions: Mapping[str, Decimal]
    """The share of each corrected invoice the window's corrections remove, keyed by its id."""
    netted: tuple[Invoice, ...] = ()
    refused: tuple[str, ...] = ()


class _ReadCorrections(NamedTuple):
    """The window's admitted corrections per invoice they reduce, and why others were refused."""

    by_target: tuple[tuple[Invoice, tuple[Invoice, ...]], ...] = ()
    refused: tuple[str, ...] = ()


def _rows_of(invoice: Invoice, transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    """Return the active rows that link ``invoice`` on the side its kind reads."""

    def linked_id(row: Transaction) -> str | None:
        return row.invoice_id if invoice.kind is InvoiceKind.ISSUED else received_invoice_reference(row)

    return tuple(
        row
        for row in transactions.values()
        if row.lifecycle_state is TransactionLifecycleState.ACTIVE and linked_id(row) == invoice.invoice_id
    )


def _cash_refund_refusals(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    kind: InvoiceKind,
    bucket_id: str,
    window_start: date,
    window_end: date,
) -> tuple[str, ...]:
    """Refuse each correction with money returned in the window: under cash no source says what it nets against.

    RIRPF art. 7.2 and the AEAT manual place cobros and pagos by their date and stop there.
    """
    refused: list[str] = []
    for invoice in invoices.values():
        if invoice.kind is not kind or invoice.bucket_id != bucket_id or not is_rectificativa(invoice):
            continue
        if any(
            not renta_income_evidence.row_settles_invoice(invoice, row)
            and window_start <= (row.raw.value_date or row.raw.booked_date) <= window_end
            for row in _rows_of(invoice, transactions)
        ):
            unresolved = ImputationUnresolved.RECTIFICATIVA_REFUND_UNDER_CASH.value
            refused.append(f"{unresolved}: rectificativa {invoice.invoice_number}")
    return tuple(refused)


def _correction_refusal(
    invoice: Invoice, candidates: Sequence[Invoice], *, window_end: date
) -> ImputationUnresolved | None:
    """Return why the correction cannot be placed on the invoice it names, or ``None``."""
    if len(candidates) > 1:
        return ImputationUnresolved.RECTIFICATIVA_TARGET_AMBIGUOUS
    return _rectificativa_refusal(invoice, candidates[0] if candidates else None, window_end=window_end)


def _admit_corrections(
    corrected: Mapping[str, Sequence[Invoice]], targets: Mapping[str, Invoice], refused: list[str]
) -> list[tuple[Invoice, tuple[Invoice, ...]]]:
    """Admit the corrections that stay within their invoice's base, appending the others to ``refused``."""
    admitted: list[tuple[Invoice, tuple[Invoice, ...]]] = []
    for target_id, rows in corrected.items():
        total = sum((row.base_total_eur or Decimal("0") for row in rows), Decimal("0"))
        base = targets[target_id].base_total_eur
        if base is None or total > base:
            unresolved = ImputationUnresolved.RECTIFICATIVA_ABOVE_INVOICE.value
            refused.extend(f"{unresolved}: rectificativa {row.invoice_number}" for row in rows)
            continue
        admitted.append((targets[target_id], tuple(rows)))
    return admitted


def _read_corrections(
    invoices: InvoiceCatalogue,
    *,
    kind: InvoiceKind,
    bucket_id: str,
    window_start: date,
    window_end: date,
    criteria: ImputationCriteria,
) -> _ReadCorrections:
    """Read which corrections of ``kind`` accruing in the window reduce an invoice of the same year.

    A correction accruing in the year of its invoice nets against that year: LIRPF art.
    14.1.b and LIS art. 11.1 impute by accrual and the AEAT manual subtracts returns and
    discounts from the income of the year (Manual Renta, ch. 7, "Partidas negativas").
    Nothing in those sources says which year a later correction reduces, so that case
    refuses, as does anything else that leaves the correction's effect unknown.
    """
    corrected: dict[str, list[Invoice]] = {}
    targets: dict[str, Invoice] = {}
    refused: list[str] = []
    for invoice in invoices.values():
        if not is_rectificativa(invoice) or not invoice_enters_window(
            invoice, kind=kind, bucket_id=bucket_id, window_start=window_start, window_end=window_end, criteria=criteria
        ):
            continue
        candidates = rectified_invoices(invoice, invoices)
        target = candidates[0] if candidates else None
        refusal = _correction_refusal(invoice, candidates, window_end=window_end)
        if refusal is not None:
            refused.append(f"{refusal.value}: rectificativa {invoice.invoice_number}")
        elif target is not None and _accrues_by(target, window_end):
            targets[target.invoice_id] = target
            corrected.setdefault(target.invoice_id, []).append(invoice)
    admitted = _admit_corrections(corrected, targets, refused)
    return _ReadCorrections(tuple(admitted), tuple(refused))


def rectificativa_reading(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    window_start: date,
    window_end: date,
    target_casilla_id: CasillaId,
    criteria: ImputationCriteria,
) -> RectificativaReading:
    """Read what the issued rectificativas of the window do to its income under the year's criterion.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.
    """
    usable = criteria.usable(window_end.year)
    if usable is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return RectificativaReading(
            refused=_cash_refund_refusals(
                invoices,
                transactions,
                kind=InvoiceKind.ISSUED,
                bucket_id=bucket_id,
                window_start=window_start,
                window_end=window_end,
            ),
        )
    if usable is not ActivityImputationCriterion.DEVENGO:
        return RectificativaReading()
    read = _read_corrections(
        invoices,
        kind=InvoiceKind.ISSUED,
        bucket_id=bucket_id,
        window_start=window_start,
        window_end=window_end,
        criteria=criteria,
    )
    corrections = tuple(
        RectificativaCorrection(
            invoice_id=row.invoice_id,
            invoice_number=row.invoice_number,
            target_casilla_id=target_casilla_id,
            reduction=row.base_total_eur,
        )
        for _, rows in read.by_target
        for row in rows
        if row.base_total_eur is not None and row.base_total_eur != Decimal("0")
    )
    return RectificativaReading(corrections, read.refused)


def _net_received_corrections(
    read: _ReadCorrections, transactions: TransactionCatalogue
) -> ReceivedRectificativaReading:
    """State each admitted correction as the share it removes, refusing those with a receipt of their own."""
    fractions: dict[str, Decimal] = {}
    refused = list(read.refused)
    netted: list[Invoice] = []
    unresolved = ImputationUnresolved.RECTIFICATIVA_WITH_RECEIPT.value
    for target, rows in read.by_target:
        base = target.base_total_eur
        if base is None or base == Decimal("0"):
            continue
        fractions[target.invoice_id] = sum((row.base_total_eur or Decimal("0") for row in rows), Decimal("0")) / base
        netted.extend(rows)
        refused.extend(
            f"{unresolved}: rectificativa {row.invoice_number}"
            for row in rows
            if any(renta_income_evidence.row_settles_invoice(row, link) for link in _rows_of(row, transactions))
        )
    return ReceivedRectificativaReading(fractions, tuple(netted), tuple(refused))


def received_rectificativa_reading(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    window_start: date,
    window_end: date,
    criteria: ImputationCriteria,
) -> ReceivedRectificativaReading:
    """Read what the received rectificativas of the window do to its expense under the year's criterion.

    Only a ledger row carries the category and business share that decide a box, so a correction
    is stated as the share it removes from the invoice it names, applied to that invoice's rows.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.
    """
    usable = criteria.usable(window_end.year)
    if usable is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return ReceivedRectificativaReading(
            fractions={},
            refused=_cash_refund_refusals(
                invoices,
                transactions,
                kind=InvoiceKind.RECEIVED,
                bucket_id=bucket_id,
                window_start=window_start,
                window_end=window_end,
            ),
        )
    if usable is not ActivityImputationCriterion.DEVENGO:
        return ReceivedRectificativaReading({})
    read = _read_corrections(
        invoices,
        kind=InvoiceKind.RECEIVED,
        bucket_id=bucket_id,
        window_start=window_start,
        window_end=window_end,
        criteria=criteria,
    )
    return _net_received_corrections(read, transactions)


def _within_window_year(rectificativa: Invoice, target: Invoice, *, window_end: date) -> bool:
    """Return whether the correction and its invoice both accrue in the window's year."""
    corrected_on = invoice_accrual_date(rectificativa)
    target_on = invoice_accrual_date(target)
    return (
        corrected_on is not None
        and target_on is not None
        and corrected_on.year == target_on.year
        and corrected_on.year == window_end.year
    )


def _rectificativa_refusal(
    rectificativa: Invoice, target: Invoice | None, *, window_end: date
) -> ImputationUnresolved | None:
    """Return why the correction's effect on the window cannot be stated, or ``None`` when it can."""
    if rectificativa.base_total_eur is None:
        return ImputationUnresolved.EUR_VALUE_UNKNOWN
    if target is None:
        return ImputationUnresolved.RECTIFICATIVA_TARGET_UNKNOWN
    if not _within_window_year(rectificativa, target, window_end=window_end):
        return ImputationUnresolved.RECTIFICATIVA_ACROSS_YEARS
    if rectificativa.retention_amount is not None and rectificativa.retention_amount != Decimal("0"):
        return ImputationUnresolved.RECTIFICATIVA_RETENCION_STATED
    if rectificativa.kind is InvoiceKind.ISSUED and target.retention_amount not in (None, Decimal("0")):
        return ImputationUnresolved.RECTIFICATIVA_OF_RETENCION
    return None


def _accrues_by(invoice: Invoice, window_end: date) -> bool:
    """Return whether the invoice has accrued by the window's end, so a correction has something to reduce."""
    accrual = invoice_accrual_date(invoice)
    return accrual is not None and accrual <= window_end


def received_rectificativa_netting_diagnostics(
    netted: Sequence[Invoice], *, source_kind: str, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name the received corrections netted as reductions, for the reason the issued ones are named."""
    if not netted:
        return ()
    listed = ", ".join(f"{row.invoice_number} ({row.base_total_eur} EUR)" for row in netted)
    return (
        CalculationSourceDiagnostic(
            reason="unsettled_legal_reading",
            source_kind=source_kind,
            resolver_id=resolver_id,
            source_ref="renta-rectificativa:netted",
            message=f"Activity expense nets these rectificativas as reductions of the year's expense: {listed}"[
                :DIAGNOSTIC_MESSAGE_MAX_LENGTH
            ],
            remedy=(
                "Check each listed rectificativa: one stating the amounts after the correction, or raising the "
                "price, nets the wrong way and needs its base corrected."
            ),
        ),
    )


def rectificativa_netting_diagnostics(
    corrections: Sequence[RectificativaCorrection], *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name the corrections netted as reductions, a reading the record itself cannot confirm.

    RD 1619/2012 art. 15.5 lets a rectificativa state the correction or the amounts as they
    stand after it, and the invoice records neither which it did nor whether the price rose.
    """
    if not corrections:
        return ()
    netted = ", ".join(f"{row.invoice_number} ({row.reduction} EUR)" for row in corrections)
    return (
        CalculationSourceDiagnostic(
            reason="unsettled_legal_reading",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            source_ref="renta-rectificativa:netted",
            message=f"Activity income nets these rectificativas as reductions of the year's income: {netted}"[
                :DIAGNOSTIC_MESSAGE_MAX_LENGTH
            ],
            remedy=(
                "Check each listed rectificativa: one stating the amounts after the correction, or raising the "
                "price, nets the wrong way and needs its base corrected."
            ),
        ),
    )


def _settled_by_shares(amount: Decimal, shares: Sequence[Decimal]) -> Decimal:
    """Return the part of ``amount`` the receipts' shares have settled, each rounded to cents."""
    return sum((round_to_cents(amount * share) for share in shares), Decimal("0"))


def overpaid_invoice_issues(
    transactions: TransactionCatalogue, invoices: InvoiceCatalogue, *, bucket_id: str
) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
    """Refuse to place receipts that together exceed what their invoice leaves to be paid.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
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
    """Return whether the receipts cannot be compared or stay within the invoice's net cash, past the tolerance."""
    comparison = renta_income_evidence.settlement_comparison(invoice, receipts)
    return comparison is None or comparison.cash - comparison.owed <= INVOICE_MATCH_TOLERANCE


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


def paid_after_cut_off_diagnostics(
    observations: Sequence[RentaIncomeObservation], *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report the retencion imputed to a pago fraccionado's window whose receipt is dated after it."""
    held = [row for row in observations if row.withheld_derivation is LedgerWithholdingDerivation.PAID_AFTER_CUT_OFF]
    if not held:
        return ()
    total = sum((row.withheld_amount for row in held), Decimal("0"))
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=(
                f"{len(held)} receipt(s) paid after the end of this window carry {total} EUR of retencion on "
                "income imputed to it. It is deducted only once paid (RIRPF art. 110.3.a; TEAC 00/03187/2011), "
                "so this pago fraccionado leaves it out; the annual return credits it."
            ),
            source_ref="withholding_paid_after_cut_off",
        ),
    )


def rental_activity_component_diagnostics(
    observations: Sequence[RentaIncomeObservation], *, resolver_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report the retencion of rental activity rows, which the activity credit leaves to the rental credit."""
    rental = [
        row for row in observations if row.withheld_derivation is LedgerWithholdingDerivation.RENTAL_ACTIVITY_COMPONENT
    ]
    if not rental:
        return ()
    total = sum((row.withheld_amount for row in rental), Decimal("0"))
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=(
                f"{len(rental)} receipt(s) of an arrendador de inmuebles activity (tipo de actividad A01) carry "
                f"{total} EUR of retencion. The annual return credits urban-rental withholding apart from the "
                "activity credit, so it is left out of that credit; record it with the payer certificates of "
                "the rental activity, whose credit carries it."
            ),
            source_ref="withholding_rental_activity_component",
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

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    findings: list[CalculationSourceDiagnostic] = []
    for transaction in transactions.values():
        invoice = _retention_bearing_invoice(transaction, invoices, bucket_id=bucket_id)
        if invoice is None:
            continue
        finding = _late_retention_finding(transaction, invoice, year=year, criteria=criteria, resolver_id=resolver_id)
        if finding is not None:
            findings.append(finding)
    return tuple(findings)


def _retention_bearing_invoice(
    transaction: Transaction, invoices: InvoiceCatalogue, *, bucket_id: str
) -> Invoice | None:
    """Return the bucket's invoice that an active receipt settles, when it states a retencion."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE or transaction.invoice_id is None:
        return None
    invoice = invoices.get(transaction.invoice_id)
    if (
        invoice is None
        or invoice.bucket_id != bucket_id
        or not renta_income_evidence.row_settles_invoice(invoice, transaction)
    ):
        return None
    if invoice.retention_amount in (None, 0):
        return None
    return invoice


def _late_retention_finding(
    transaction: Transaction,
    invoice: Invoice,
    *,
    year: int,
    criteria: ImputationCriteria,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    """Report the retencion this receipt paid after the return of its accrual year was filed."""
    accrual = linked_accrual_date(invoice, kind=InvoiceKind.ISSUED)
    cash = transaction.raw.value_date or transaction.raw.booked_date
    entry = None if accrual is None else accrual_entry_date(accrual, criteria, through_year=cash.year)
    if entry is None:
        return None
    filed_on = criteria.filings.filed_on.get(entry.year)
    if filed_on is None or cash <= filed_on or year not in {entry.year, cash.year}:
        return None
    share = renta_income_evidence.part_payment_share(invoice, transaction)
    stated_eur = invoice.retention_amount_eur
    if stated_eur is None:
        what = f"a retencion of {invoice.retention_amount} {invoice.currency}, with no EUR value,"
    else:
        what = f"{stated_eur if share is None else round_to_cents(stated_eur * share)} EUR of retencion"
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="ledger_renta_income_aggregation",
        resolver_id=resolver_id,
        source_ref=f"invoice:{invoice.invoice_id}",
        message=(
            f"Invoice {invoice.invoice_number}: {what} was paid on {cash}, after the "
            f"return of {entry.year} was filed on {filed_on}. Claim it by an autoliquidacion rectificativa "
            f"of {entry.year} (TEAC 00/03187/2011; LGT art. 120.3); it is never credited in {cash.year}."
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
