"""Which window an activity's invoice accrues in, and what a zero in a ledger box rests on.

Activity income and expense follow accrual (LIRPF art. 14.1.b) unless the
taxpayer elected cash (RIRPF art. 7.2). A box that sums bank rows can read zero
while an invoice accrued inside its window was collected outside it, so a zero
is proven only when neither a row nor an accruing invoice exists.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingValueOutcome
from ...domain.calculations.registry.invoice_legal_classification import advance_payment_received_role
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .source_mesh import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic
from .source_resolution_operations import unresolved_binding_diagnostics

if TYPE_CHECKING:
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision


def invoice_accrual_date(invoice: Invoice) -> date | None:
    """Return the date ``invoice`` accrues on, or ``None`` when its document does not state one.

    RD 1619/2012 art. 6.1.i records an operation date only when it differs from
    expedition, so an invoice stating none documents an operation on its issue
    date. An advance-payment date is when money arrived, not when the income
    accrued, so it answers nothing here.
    """
    if invoice.operation_date is None:
        return invoice.issued_at
    if invoice.operation_date_role == advance_payment_received_role():
        return None
    return invoice.operation_date


def accruing_invoices(
    invoices: Iterable[Invoice], *, kind: InvoiceKind, bucket_id: str, start: date, end: date
) -> tuple[Invoice, ...]:
    """Return the bucket's invoices of ``kind`` that accrue in the window, an unknown accrual read at its issue date."""
    return tuple(
        invoice
        for invoice in invoices
        if invoice.kind is kind
        and invoice.bucket_id == bucket_id
        and start <= (invoice_accrual_date(invoice) or invoice.issued_at) <= end
    )


def ledger_sum_outcome(value: Decimal, *, rows_present: bool, accruing_invoice_present: bool) -> BindingValueOutcome:
    """State what one ledger-summed activity box rests on: a proven zero needs no row and no accruing invoice."""
    if value != 0 or rows_present or accruing_invoice_present:
        return BindingValueOutcome.FROM_BEARING_ROWS
    return BindingValueOutcome.PROVEN_ZERO


class ActivityImputationCriterion(StrEnum):
    """The two criteria RIRPF art. 7 admits for activity income and expense."""

    DEVENGO = "devengo"
    COBROS_Y_PAGOS = "cobros_y_pagos"


class ImputationUnresolved(StrEnum):
    """Why one row cannot be placed in an ejercicio."""

    CRITERION_UNDECLARED = "criterion_undeclared"
    """A year the row touches has no usable declared criterion."""

    ACCRUAL_UNKNOWN = "accrual_unknown"
    """Under accrual, the row has no document stating when it accrued."""

    ELECTION_NOT_OPEN = "election_not_open"
    """The declared criterion conflicts with RIRPF art. 7.2's eligibility or three-year minimum."""

    UNCOMPUTED_ACROSS_CHANGE = "uncomputed_across_change"
    """A change of criterion would leave the row computed in no year, which art. 7.4 forbids."""


_CRITERION_PATH: Final[str] = "irpf.activity_income_imputation_criterion"
_COMMERCIAL_ACCOUNTING_PATH: Final[str] = "irpf.codigo_comercio_accounting"
_ESTIMATION_REGIME_PATH: Final[str] = "irpf.estimation_regime"
_MINIMUM_ELECTION_YEARS: Final[int] = 3


def _dated_values(facts: Iterable[UserProfileFact], path: str, year: int) -> set[object]:
    """Return the values of ``path`` in force during ``year``; an undated fact states no year."""
    first, last = date(year, 1, 1), date(year, 12, 31)
    return {
        fact.value
        for fact in facts
        if fact.path == path
        and fact.valid_from is not None
        and fact.valid_from <= last
        and (fact.valid_to is None or fact.valid_to >= first)
    }


@dataclass(frozen=True, slots=True)
class ImputationCriteria:
    """The dated election as the profile declares it, read one ejercicio at a time.

    Absence and conflict both read as ``None``. Nothing here supplies accrual as
    a default: a cash election made in an earlier return is invisible to a fresh
    profile and binds for three years, so an unstated year is unknown.
    """

    facts: tuple[UserProfileFact, ...] = ()

    def declared(self, year: int) -> ActivityImputationCriterion | None:
        """Return the single criterion stated for ``year``, or ``None`` when absent or contradictory."""
        values = _dated_values(self.facts, _CRITERION_PATH, year)
        if len(values) != 1:
            return None
        return ActivityImputationCriterion(str(next(iter(values))))

    def _commercial_accounting(self, year: int) -> bool | None:
        values = _dated_values(self.facts, _COMMERCIAL_ACCOUNTING_PATH, year)
        only = next(iter(values)) if len(values) == 1 else None
        return only if isinstance(only, bool) else None

    def election_open(self, year: int) -> bool:
        """Whether ``year``'s declared criterion is admissible under RIRPF art. 7.2.

        Cash needs a declared regime and a declared absence of Codigo de Comercio
        accounting (art. 7.2.3). Returning to accrual inside the three-year
        minimum (art. 7.2.1) conflicts unless the election lost effect (art. 7.2.2).
        """
        declared = self.declared(year)
        if declared is ActivityImputationCriterion.COBROS_Y_PAGOS:
            return (
                len(_dated_values(self.facts, _ESTIMATION_REGIME_PATH, year)) == 1
                and self._commercial_accounting(year) is False
            )
        if declared is ActivityImputationCriterion.DEVENGO and self._commercial_accounting(year) is not True:
            first_cash_year = year
            while self.declared(first_cash_year - 1) is ActivityImputationCriterion.COBROS_Y_PAGOS:
                first_cash_year -= 1
            return first_cash_year == year or year - first_cash_year >= _MINIMUM_ELECTION_YEARS
        return True

    def usable(self, year: int) -> ActivityImputationCriterion | None:
        """Return ``year``'s criterion when it is declared and admissible."""
        return self.declared(year) if self.election_open(year) else None


def declared_imputation_criteria(record: UserProfileRecord | None) -> ImputationCriteria:
    """Read the dated imputation facts of the bucket's profile; no record states no year."""
    return ImputationCriteria(facts=() if record is None else tuple(record.facts))


def _quarter(on: date) -> int:
    return (on.month - 1) // 3


def impute_row(cash: date, accrual: date | None, criteria: ImputationCriteria) -> date | ImputationUnresolved:
    """Return the one date a banked row is computed on, or why no date can be given.

    One row answers with one date, so a row can land in one ejercicio at most,
    across a change of criterion too (RIRPF art. 7.4). A row accrued under cash
    and collected under accrual enters the first accrual year on its first day:
    DGT V2024-16 and V4636-16 place it in the change year, and the first-quarter
    placement for Modelo 130 is the conservative reading no norm addresses.
    """
    at_cash = criteria.usable(cash.year)
    if not criteria.election_open(cash.year):
        return ImputationUnresolved.ELECTION_NOT_OPEN
    if accrual is None:
        if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
            return cash
        if at_cash is ActivityImputationCriterion.DEVENGO:
            return ImputationUnresolved.ACCRUAL_UNKNOWN
        return ImputationUnresolved.CRITERION_UNDECLARED
    if accrual.year == cash.year:
        if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
            return cash
        if at_cash is ActivityImputationCriterion.DEVENGO:
            return accrual
        return cash if _quarter(cash) == _quarter(accrual) else ImputationUnresolved.CRITERION_UNDECLARED
    at_accrual = criteria.usable(accrual.year)
    if at_cash is None or at_accrual is None:
        return ImputationUnresolved.CRITERION_UNDECLARED
    if accrual < cash:
        if at_accrual is ActivityImputationCriterion.DEVENGO:
            return accrual
        if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
            return cash
        for year in range(accrual.year + 1, cash.year + 1):
            between = criteria.usable(year)
            if between is None:
                return ImputationUnresolved.CRITERION_UNDECLARED
            if between is ActivityImputationCriterion.DEVENGO:
                return date(year, 1, 1)
        return ImputationUnresolved.UNCOMPUTED_ACROSS_CHANGE
    if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return cash
    if at_accrual is ActivityImputationCriterion.DEVENGO:
        return accrual
    return ImputationUnresolved.UNCOMPUTED_ACROSS_CHANGE


def linked_accrual_date(invoice: Invoice | None, *, kind: InvoiceKind) -> date | None:
    """Return the accrual of the invoice a row links to, when it links to one of ``kind``."""
    return invoice_accrual_date(invoice) if invoice is not None and invoice.kind is kind else None


def rows_touching_window(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    kind: InvoiceKind,
    invoice_id_of: Callable[[Transaction], str | None],
    start: date,
    end: date,
) -> TransactionCatalogue:
    """Keep the rows banked in the window or linked to an invoice accruing in it.

    Only these can land in the window, so other years' rows raise no refusal here.
    """

    def touches(row: Transaction) -> bool:
        cash = row.raw.value_date or row.raw.booked_date
        if start <= cash <= end:
            return True
        invoice_id = invoice_id_of(row)
        accrual = linked_accrual_date(None if invoice_id is None else invoices.get(invoice_id), kind=kind)
        return accrual is not None and start <= accrual <= end

    return TransactionCatalogue.from_transactions(tuple(row for row in transactions.values() if touches(row)))


def rows_left_out_summary(
    transactions: TransactionCatalogue, kept: TransactionCatalogue
) -> OutOfWindowTransactionSummary | None:
    """Count the rows ``rows_touching_window`` left out, so the return still says some were."""
    left_out = tuple(
        row.raw.value_date or row.raw.booked_date
        for row in transactions.values()
        if kept.get(row.transaction_id) is None
    )
    if not left_out:
        return None
    return OutOfWindowTransactionSummary(
        count=len(left_out), min_filing_date=min(left_out), max_filing_date=max(left_out)
    )


def imputation_blocking_diagnostics(
    *,
    source_kind: str,
    resolver_id: str,
    revision: ModeloRevision,
    binding_ids: Iterable[BindingId],
    criteria: ImputationCriteria,
    year: int,
    activity_present: bool,
    unresolved_details: Sequence[str],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Withhold a year's activity boxes while its criterion is unknown or a row cannot be placed.

    An unset criterion picks no year, so any activity in the window keeps the
    boxes from check, export and recording; the calculation still shows them.
    A year with no activity has nothing to place and raises nothing.
    """
    undeclared = activity_present and criteria.usable(year) is None
    if not undeclared and not unresolved_details:
        return ()
    message = (
        f"ejercicio {year} has no usable income imputation criterion (irpf.activity_income_imputation_criterion, "
        "RIRPF art. 7); declare devengo or cobros_y_pagos dated for that year"
        if undeclared
        else f"{len(unresolved_details)} row(s) cannot be placed in an ejercicio under RIRPF art. 7: "
        + "; ".join(unresolved_details[:3])
    )
    return unresolved_binding_diagnostics(
        revision=revision,
        source_kind=source_kind,
        binding_ids=tuple(binding_ids),
        resolver_id=resolver_id,
        message=message[:DIAGNOSTIC_MESSAGE_MAX_LENGTH],
    )


__all__ = [
    "ActivityImputationCriterion",
    "ImputationCriteria",
    "ImputationUnresolved",
    "accruing_invoices",
    "declared_imputation_criteria",
    "imputation_blocking_diagnostics",
    "impute_row",
    "invoice_accrual_date",
    "ledger_sum_outcome",
    "linked_accrual_date",
    "rows_left_out_summary",
    "rows_touching_window",
]
