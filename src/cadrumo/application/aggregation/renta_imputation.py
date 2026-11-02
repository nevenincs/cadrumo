"""Which window an activity's invoice accrues in, and what a zero in a ledger box rests on.

Activity income and expense follow accrual (LIRPF art. 14.1.b) unless the
taxpayer elected cash (RIRPF art. 7.2). A box that sums bank rows can read zero
while an invoice accrued inside its window was collected outside it, so a zero
is proven only when neither a row nor an accruing invoice exists.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingValueOutcome
from ...core.parsing.utils import parse_bool
from ...core.period import Period
from ...domain.calculations.registry.cash_election_minimum_years import cash_election_minimum_years
from ...domain.calculations.registry.errors import GovernedFactNotApplicableError
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
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.bindings import RegistryModeloObservation
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.filing_record import ModeloRecordCatalogue


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
    invoices: Iterable[Invoice],
    *,
    kind: InvoiceKind,
    bucket_id: str,
    start: date,
    end: date,
    criteria: ImputationCriteria,
) -> tuple[Invoice, ...]:
    """Return the bucket's invoices of ``kind`` accruing in the window, or carried into it by a change of criterion.

    An unknown accrual is read at its issue date.
    """

    def reaches_window(invoice: Invoice) -> bool:
        accrual = invoice_accrual_date(invoice) or invoice.issued_at
        entry = accrual_entry_date(accrual, criteria, through_year=end.year)
        return start <= accrual <= end or (entry is not None and start <= entry <= end)

    return tuple(
        invoice
        for invoice in invoices
        if invoice.kind is kind and invoice.bucket_id == bucket_id and reaches_window(invoice)
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

    OVERPAID_INVOICE = "overpaid_invoice"
    """The receipts linked to one invoice exceed what it leaves to be paid, so no share of it is known."""

    ACCRUAL_CONFLICT = "accrual_conflict"
    """The accrual date stated on the row disagrees with the one its invoice documents."""

    CAPITAL_SUBSIDY_SCHEDULE_UNKNOWN = "capital_subsidy_schedule_unknown"
    """A capital subsidy follows its asset's amortization under either criterion, and no schedule links one."""

    EUR_VALUE_UNKNOWN = "eur_value_unknown"
    """A foreign invoice accrues with no rate stamped on it, so what it adds to the box is not known."""

    RECTIFICATIVA_ACROSS_YEARS = "rectificativa_across_years"
    """A correction accrues outside the year of its invoice, and no source says which year it reduces."""

    RECTIFICATIVA_TARGET_UNKNOWN = "rectificativa_target_unknown"
    """The invoice a correction names is not recorded, so the year it corrects is not known."""

    RECTIFICATIVA_ABOVE_INVOICE = "rectificativa_above_invoice"
    """Corrections exceed the base they correct, so they state a result or a replacement rather than a reduction."""

    RECTIFICATIVA_RETENCION_STATED = "rectificativa_retencion_stated"
    """A correction states a retencion, and what that does to the credit already taken is not settled."""

    RECTIFICATIVA_WITH_RECEIPT = "rectificativa_with_receipt"
    """Money came in on a correction, which contradicts reading it as a reduction of accrued income."""


_CRITERION_PATH: Final[str] = "irpf.activity_income_imputation_criterion"
_COMMERCIAL_ACCOUNTING_PATH: Final[str] = "irpf.codigo_comercio_accounting"
_ESTIMATION_REGIME_PATH: Final[str] = "irpf.estimation_regime"


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
class ImputationFilingHistory:
    """What the taxpayer's annual returns state: the criterion captured from each, and when each was filed."""

    stated: Mapping[int, ActivityImputationCriterion] = field(default_factory=dict[int, ActivityImputationCriterion])
    filed_on: Mapping[int, date] = field(default_factory=dict[int, date])


@dataclass(frozen=True, slots=True)
class ImputationCriteria:
    """The dated election as the profile declares it, read one ejercicio at a time.

    Absence and conflict both read as ``None``. Nothing here supplies accrual as
    a default: a cash election made in an earlier return is invisible to a fresh
    profile and binds for three years, so an unstated year is unknown.

    ``filings`` is what the taxpayer's own returns say about those years. A filed
    statement never fills an undeclared year: it can only contradict one.
    """

    facts: tuple[UserProfileFact, ...] = ()
    filings: ImputationFilingHistory = field(default_factory=lambda: ImputationFilingHistory())

    def declared(self, year: int) -> ActivityImputationCriterion | None:
        """Return the single criterion stated for ``year``, or ``None`` when absent or contradictory."""
        values = _dated_values(self.facts, _CRITERION_PATH, year)
        if len(values) != 1:
            return None
        return ActivityImputationCriterion(str(next(iter(values))))

    def _regime_declared(self, year: int) -> bool:
        """Whether a regime is stated for ``year``; setup writes the regime in force undated, which answers it."""
        dated = _dated_values(self.facts, _ESTIMATION_REGIME_PATH, year)
        if dated:
            return len(dated) == 1
        return any(fact.path == _ESTIMATION_REGIME_PATH and fact.valid_from is None for fact in self.facts)

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
        if self.filed_conflict(year) is not None:
            return False
        if declared is ActivityImputationCriterion.COBROS_Y_PAGOS:
            return self._regime_declared(year) and self._commercial_accounting(year) is False
        if declared is ActivityImputationCriterion.DEVENGO and self._commercial_accounting(year) is not True:
            first_cash_year = self._first_binding_cash_year(year)
            return first_cash_year is None or year - first_cash_year >= cash_election_minimum_years(filing_year=year)
        return True

    def _in_force(self, year: int) -> ActivityImputationCriterion | None:
        """Return the criterion a year ran under: its filed return's when captured, else the declared one."""
        return self.filings.stated.get(year) or self.declared(year)

    def _first_binding_cash_year(self, year: int) -> int | None:
        """Return the first year of the cash run reaching into the two years before ``year``, if any."""
        cash = ActivityImputationCriterion.COBROS_Y_PAGOS
        try:
            minimum_years = cash_election_minimum_years(filing_year=year)
        except GovernedFactNotApplicableError:
            return None
        for back in range(1, minimum_years):
            first = year - back
            if self._in_force(first) is cash:
                while self._in_force(first - 1) is cash:
                    first -= 1
                return first
        return None

    def filed_conflict(self, year: int) -> str | None:
        """Name the filed return that contradicts ``year``'s declaration, or the election it still binds.

        RIRPF art. 7.2.1 makes the statement in the return the election itself, so a
        profile disagreeing with that return is wrong about one of them and picks no year.
        """
        declared = self.declared(year)
        if declared is None:
            return None
        stated = self.filings.stated.get(year)
        if stated is not None and stated is not declared:
            return f"the filed return of {year} states {stated.value} but the profile declares {declared.value}"
        return self._binding_cash_conflict(year, declared)

    def _binding_cash_conflict(self, year: int, declared: ActivityImputationCriterion) -> str | None:
        """Name the filed cash return whose three-year election still binds a declared accrual ``year``."""
        if declared is not ActivityImputationCriterion.DEVENGO or self._commercial_accounting(year) is True:
            return None
        first_cash_year = self._first_binding_cash_year(year)
        if first_cash_year is None:
            return None
        minimum_years = cash_election_minimum_years(filing_year=year)
        if year - first_cash_year >= minimum_years:
            return None
        filed = sorted(
            on_file
            for on_file, criterion in self.filings.stated.items()
            if criterion is ActivityImputationCriterion.COBROS_Y_PAGOS and first_cash_year <= on_file < year
        )
        if not filed:
            return None
        return (
            f"the filed return of {filed[0]} states cobros_y_pagos, which binds through "
            f"{first_cash_year + minimum_years - 1} (RIRPF art. 7.2.1), but the profile declares "
            f"{declared.value} for {year}"
        )

    def usable(self, year: int) -> ActivityImputationCriterion | None:
        """Return ``year``'s criterion when it is declared and admissible."""
        return self.declared(year) if self.election_open(year) else None


def declared_imputation_criteria(
    record: UserProfileRecord | None, filings: ImputationFilingHistory | None = None
) -> ImputationCriteria:
    """Read the dated imputation facts of the bucket's profile; no record states no year."""
    return ImputationCriteria(
        facts=() if record is None else tuple(record.facts),
        filings=filings if filings is not None else ImputationFilingHistory(),
    )


_CASH_ELECTION_ROLES: Final[frozenset[str]] = frozenset(
    {"irpf_ed_cobros_pagos_flag", "irpf_eo_cobros_pagos_flag", "irpf_eo_agr_cobros_pagos_flag"}
)
"""The semantic roles of the cash-election boxes: estimacion directa, objetiva and its agricultural block.

A box is named by its role in the revision that edition declares, never by its number."""

_RECORD_DESIGN_FLAG_MARK: Final[str] = "X"
"""The mark a record design prints in a checked box; any other affirmative is a yes/no word."""


def _marked(value: Decimal | str) -> bool:
    if isinstance(value, Decimal):
        return value != 0
    token = value.strip()
    return token.upper() == _RECORD_DESIGN_FLAG_MARK or parse_bool(token) is True


def imputation_filing_history(
    *,
    bucket_id: str,
    year: int,
    annual_form: str,
    annual_period_code: str,
    load_observation: Callable[[str, Period], RegistryModeloObservation | None],
    filing_records: ModeloRecordCatalogue,
    authority: PinnedAuthorityOperation,
) -> ImputationFilingHistory:
    """Read what the annual returns reaching ``year`` state about the criterion and when each was filed.

    A captured box that is marked states the election. An unmarked box states accrual
    only where the capture carries it: a capture without the box says nothing either way.
    The boxes are the ones the pinned authority's revision for each past year gives the
    cash-election roles.
    """
    supported_years = authority.supported_filing_years().years
    stated: dict[int, ActivityImputationCriterion] = {}
    filed_on: dict[int, date] = {}
    lookback_years = cash_election_minimum_years(filing_year=year, authority=authority)
    for past in range(year - lookback_years, year + 1):
        period = Period.from_year_and_code(past, annual_period_code)
        record = filing_records.current_for(bucket_id=bucket_id, modelo=annual_form, filing_year=past, period=period)
        if record is not None:
            filed_on[past] = record.filed_at.date()
        observation = load_observation(annual_form, period)
        if observation is not None and past in supported_years:
            criterion = _criterion_stated_by(observation, annual_form, past, annual_period_code, authority)
            if criterion is not None:
                stated[past] = criterion
    return ImputationFilingHistory(stated=stated, filed_on=filed_on)


def _criterion_stated_by(
    observation: RegistryModeloObservation,
    annual_form: str,
    past: int,
    annual_period_code: str,
    authority: PinnedAuthorityOperation,
) -> ActivityImputationCriterion | None:
    """Return the criterion a captured return states through its cash-election boxes, or ``None`` when it has none."""
    revision = authority.revision_for_context(annual_form, filing_year=past, period=annual_period_code)
    boxes = {str(box.id) for box in revision.casillas if str(box.semantic_role) in _CASH_ELECTION_ROLES}
    flags = tuple(row.value for row in observation.observations if str(row.casilla_id) in boxes)
    if not flags:
        return None
    if any(_marked(flag) for flag in flags):
        return ActivityImputationCriterion.COBROS_Y_PAGOS
    return ActivityImputationCriterion.DEVENGO


def accrual_entry_date(accrual: date, criteria: ImputationCriteria, *, through_year: int) -> date | None:
    """Return when income accrued on ``accrual`` enters computation under accrual, looking up to ``through_year``.

    Under accrual that is the accrual date. Accrued under cash and still uncollected when
    accrual begins, RIRPF art. 7.4 forbids leaving it uncomputed, so it enters the first
    accrual year on its first day: :func:`impute_row` places a banked row the same way. A
    year that states no usable criterion, or a cash run reaching ``through_year``, gives
    ``None``.
    """
    at_accrual = criteria.usable(accrual.year)
    if at_accrual is ActivityImputationCriterion.DEVENGO:
        return accrual
    if at_accrual is None:
        return None
    for year in range(accrual.year + 1, through_year + 1):
        between = criteria.usable(year)
        if between is None:
            return None
        if between is ActivityImputationCriterion.DEVENGO:
            return date(year, 1, 1)
    return None


def _quarter(on: date) -> int:
    return (on.month - 1) // 3


def _impute_without_accrual(cash: date, at_cash: ActivityImputationCriterion | None) -> date | ImputationUnresolved:
    if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return cash
    if at_cash is ActivityImputationCriterion.DEVENGO:
        return ImputationUnresolved.ACCRUAL_UNKNOWN
    return ImputationUnresolved.CRITERION_UNDECLARED


def _impute_within_year(
    cash: date, accrual: date, at_cash: ActivityImputationCriterion | None
) -> date | ImputationUnresolved:
    if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return cash
    if at_cash is ActivityImputationCriterion.DEVENGO:
        return accrual
    return cash if _quarter(cash) == _quarter(accrual) else ImputationUnresolved.CRITERION_UNDECLARED


def _impute_accrued_before_cash(
    cash: date,
    accrual: date,
    criteria: ImputationCriteria,
    at_cash: ActivityImputationCriterion,
    at_accrual: ActivityImputationCriterion,
) -> date | ImputationUnresolved:
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
        return _impute_without_accrual(cash, at_cash)
    if accrual.year == cash.year:
        return _impute_within_year(cash, accrual, at_cash)
    at_accrual = criteria.usable(accrual.year)
    if at_cash is None or at_accrual is None:
        return ImputationUnresolved.CRITERION_UNDECLARED
    if accrual < cash:
        return _impute_accrued_before_cash(cash, accrual, criteria, at_cash, at_accrual)
    if at_cash is ActivityImputationCriterion.COBROS_Y_PAGOS:
        return cash
    if at_accrual is ActivityImputationCriterion.DEVENGO:
        return accrual
    return ImputationUnresolved.UNCOMPUTED_ACROSS_CHANGE


def linked_accrual_date(invoice: Invoice | None, *, kind: InvoiceKind) -> date | None:
    """Return the accrual of the invoice a row links to, when it links to one of ``kind``."""
    return invoice_accrual_date(invoice) if invoice is not None and invoice.kind is kind else None


def row_accrual_date(
    row: Transaction, invoice: Invoice | None, *, kind: InvoiceKind
) -> date | ImputationUnresolved | None:
    """Return the date a row accrues on from its invoice or its stated date, ``None`` when neither gives one.

    The stated date is the operator's own statement for a row no document places,
    and it is never read from the row's IVA ``operation_date``: LIVA art. 75 moves
    the IVA at an advance while the income or expense accrues on delivery. When a
    linked invoice documents a different date neither is preferred, because the
    disagreement is the operator's to settle.
    """
    linked = linked_accrual_date(invoice, kind=kind)
    stated = row.accrual_date
    if stated is None:
        return linked
    if linked is None or linked == stated:
        return stated
    return ImputationUnresolved.ACCRUAL_CONFLICT


def impute_ledger_row(
    row: Transaction, invoice: Invoice | None, *, kind: InvoiceKind, criteria: ImputationCriteria
) -> date | ImputationUnresolved:
    """Place one ledger row by what it and its invoice state about its accrual."""
    accrual = row_accrual_date(row, invoice, kind=kind)
    if isinstance(accrual, ImputationUnresolved):
        return accrual
    return impute_row(row.raw.value_date or row.raw.booked_date, accrual, criteria)


def rows_touching_window(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    kind: InvoiceKind,
    invoice_id_of: Callable[[Transaction], str | None],
    start: date,
    end: date,
    criteria: ImputationCriteria,
) -> TransactionCatalogue:
    """Keep the rows banked in the window or linked to an invoice accruing in it or carried into it.

    A date stated on the row counts as its invoice's does. Only these can land in
    the window, so other years' rows raise no refusal here. Every receipt of a carried
    invoice stays, including one banked in an earlier cash year, because what it settled
    decides the rest the window computes.
    """

    def carried_in(accrual: date | None) -> bool:
        entry = None if accrual is None else accrual_entry_date(accrual, criteria, through_year=end.year)
        return entry is not None and start <= entry <= end

    def touches(row: Transaction) -> bool:
        cash = row.raw.value_date or row.raw.booked_date
        if start <= cash <= end:
            return True
        if row.accrual_date is not None and start <= row.accrual_date <= end:
            return True
        invoice_id = invoice_id_of(row)
        accrual = linked_accrual_date(None if invoice_id is None else invoices.get(invoice_id), kind=kind)
        return (accrual is not None and start <= accrual <= end) or carried_in(accrual) or carried_in(row.accrual_date)

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
    conflict = criteria.filed_conflict(year)
    message = (
        f"ejercicio {year} cannot be placed: {conflict}; correct the declared criterion or rectify that return"
        if undeclared and conflict is not None
        else f"ejercicio {year} has no usable income imputation criterion (irpf.activity_income_imputation_criterion, "
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
    "ImputationFilingHistory",
    "ImputationUnresolved",
    "accrual_entry_date",
    "accruing_invoices",
    "declared_imputation_criteria",
    "imputation_blocking_diagnostics",
    "imputation_filing_history",
    "impute_ledger_row",
    "impute_row",
    "invoice_accrual_date",
    "ledger_sum_outcome",
    "linked_accrual_date",
    "row_accrual_date",
    "rows_left_out_summary",
    "rows_touching_window",
]
