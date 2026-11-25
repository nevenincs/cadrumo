"""A change of criterion leaves every invoice computed in exactly one year (RIRPF art. 7.4).

Worked income: 1.000,00 base + 210,00 IVA - 150,00 retencion = 1.060,00 to bank. Each case
adds the years and checks the total against 1.000,00, the figure that art. 7.4 protects.
Worked expense: 100,00 base + 21,00 IVA = 121,00 paid. The years run relative to the newest
authored edition, since the rule is not about any year in particular.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.tests.register_support import MemoryRepository
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..renta_imputation import ImputationFilingHistory
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryInvoiceCatalogueRepository,
    InMemoryTransactionCatalogueRepository,
    resolve_m100,
)
from .renta_income_aggregation_support import catalogue_read_ports
from .test_renta_imputation_criterion import (
    ACCOUNTING,
    BASE,
    CASH,
    CREDIT_0599,
    DEVENGO,
    INCOME_0171,
    INCOME_M130_01,
    LATER,
    RETENCION,
    ZERO,
    declared,
    expense_row,
    in_year,
    issued,
    received,
    renta_imputation_criterion_profile,
    renta_imputation_criterion_receipt,
    unresolved_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_Y = LATER - 2
_Y1 = LATER - 1
_Y2 = LATER
_YEARS = (_Y, _Y1, _Y2)


def _cash_then_accrual() -> tuple[UserProfileFact, ...]:
    """Cash in the first year, then accrual because Codigo de Comercio accounting ended the election (art. 7.2.2)."""
    return (
        *declared((_Y, CASH), (_Y1, DEVENGO), (_Y2, DEVENGO)),
        in_year(ACCOUNTING, True, _Y1),
        in_year(ACCOUNTING, True, _Y2),
    )


def _accrual_then_cash() -> tuple[UserProfileFact, ...]:
    return declared((_Y, DEVENGO), (_Y1, CASH), (_Y2, CASH))


def _resolve(
    operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
    *,
    year: int,
    rows: tuple[Transaction, ...] = (),
    invoices: tuple[Invoice, ...] = (),
    modelo: str = "100",
    period: str = "0A",
    filings: ImputationFilingHistory | None = None,
) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(rows)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=build_invoice_catalogue(invoices), transactions=transactions),
        imputation_filings=(lambda _context: filings) if filings is not None else None,
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo=modelo,
            filing_year=year,
            period=Period.from_year_and_code(year, period),
            revision=published_snapshot(modelo, filing_year=year, period=period).revision,
            profile=renta_imputation_criterion_profile(operation, facts),
        ),
    )


def _income_by_year(
    operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
    *,
    rows: tuple[Transaction, ...] = (),
    invoices: tuple[Invoice, ...] = (),
) -> dict[int, Decimal]:
    return {
        year: _resolve(operation, facts, year=year, rows=rows, invoices=invoices).binding_values[INCOME_0171]
        for year in _YEARS
    }


def _collected(accrued: date, *payments: tuple[date, str]) -> tuple[tuple[Transaction, ...], Invoice]:
    invoice = issued(
        accrued,
        linked=tuple(
            renta_imputation_criterion_receipt(on, amount=Decimal(amount)).transaction_id for on, amount in payments
        ),
    )
    rows = tuple(
        renta_imputation_criterion_receipt(on, invoice_id=invoice.invoice_id, amount=Decimal(amount))
        for on, amount in payments
    )
    return rows, invoice


def test_collected_two_years_after_accruing_lands_in_the_first_accrual_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """The finding itself: accrued in Y under cash, collected in Y+2 under accrual, so Y+1 owns it."""
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 2, 1), "1060.00"))
    assert _income_by_year(operation, _cash_then_accrual(), rows=rows, invoices=(invoice,)) == {
        _Y: ZERO,
        _Y1: BASE,
        _Y2: ZERO,
    }


def test_the_row_enters_the_first_instalment_of_the_accrual_year(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 2, 1), "1060.00"))
    resolution = _resolve(
        operation, _cash_then_accrual(), year=_Y1, rows=rows, invoices=(invoice,), modelo="130", period="1T"
    )
    assert resolution.binding_values[INCOME_M130_01] == BASE


def test_uncollected_income_of_a_cash_year_enters_the_first_accrual_year(operation: PinnedAuthorityOperation) -> None:
    """Art. 7.4 reaches the invoice nobody has paid yet: no later accrual year would ever compute it."""
    invoice = issued(date(_Y, 11, 1))
    assert _income_by_year(operation, _cash_then_accrual(), invoices=(invoice,)) == {
        _Y: ZERO,
        _Y1: BASE,
        _Y2: ZERO,
    }


def test_the_uncollected_rest_of_a_part_paid_invoice_enters_the_first_accrual_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """530,00 of 1.060,00 collected under cash is 500,00 there; the other 500,00 waits for Y+1."""
    rows, invoice = _collected(date(_Y, 10, 1), (date(_Y, 12, 1), "530.00"))
    assert _income_by_year(operation, _cash_then_accrual(), rows=rows, invoices=(invoice,)) == {
        _Y: Decimal("500.00"),
        _Y1: Decimal("500.00"),
        _Y2: ZERO,
    }


def test_a_part_collected_on_each_side_of_the_change_still_adds_up_once(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _collected(date(_Y, 10, 1), (date(_Y, 12, 1), "530.00"), (date(_Y2, 3, 1), "530.00"))
    assert _income_by_year(operation, _cash_then_accrual(), rows=rows, invoices=(invoice,)) == {
        _Y: Decimal("500.00"),
        _Y1: Decimal("500.00"),
        _Y2: ZERO,
    }


def test_wholly_collected_under_cash_stays_there(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _collected(date(_Y, 10, 1), (date(_Y, 12, 1), "1060.00"))
    assert _income_by_year(operation, _cash_then_accrual(), rows=rows, invoices=(invoice,)) == {
        _Y: BASE,
        _Y1: ZERO,
        _Y2: ZERO,
    }


def test_the_withholding_travels_with_the_carried_income(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 2, 1), "1060.00"))
    resolution = _resolve(operation, _cash_then_accrual(), year=_Y1, rows=rows, invoices=(invoice,))
    assert resolution.binding_values[CREDIT_0599] == RETENCION


def test_collection_after_the_carried_year_was_filed_names_that_year_for_rectification(
    operation: PinnedAuthorityOperation,
) -> None:
    """The retencion follows its income into Y+1, so paying it after that return was filed rectifies Y+1."""
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 7, 10), "1060.00"))
    filings = ImputationFilingHistory(filed_on={_Y1: date(_Y2, 6, 30)})
    resolution = _resolve(operation, _cash_then_accrual(), year=_Y1, rows=rows, invoices=(invoice,), filings=filings)
    messages = [item.message for item in resolution.diagnostics if item.source_ref == f"invoice:{invoice.invoice_id}"]
    assert f"rectificativa of {_Y1}" in messages[0]


def test_an_undeclared_collection_year_blocks_the_carried_year_rather_than_losing_the_row(
    operation: PinnedAuthorityOperation,
) -> None:
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 2, 1), "1060.00"))
    facts = (*declared((_Y, CASH), (_Y1, DEVENGO)), in_year(ACCOUNTING, True, _Y1))
    resolution = _resolve(operation, facts, year=_Y1, rows=rows, invoices=(invoice,))
    assert INCOME_0171 in unresolved_bindings(resolution)


def test_a_cash_year_with_nothing_after_it_keeps_the_invoice_waiting(operation: PinnedAuthorityOperation) -> None:
    invoice = issued(date(_Y, 11, 1))
    facts = declared((_Y, CASH), (_Y1, CASH), (_Y2, CASH))
    assert _income_by_year(operation, facts, invoices=(invoice,)) == {_Y: ZERO, _Y1: ZERO, _Y2: ZERO}


def test_leaving_accrual_for_cash_computes_an_unpaid_invoice_once(operation: PinnedAuthorityOperation) -> None:
    invoice = issued(date(_Y, 11, 1))
    assert _income_by_year(operation, _accrual_then_cash(), invoices=(invoice,)) == {
        _Y: BASE,
        _Y1: ZERO,
        _Y2: ZERO,
    }


def test_leaving_accrual_for_cash_does_not_count_a_later_collection_again(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _collected(date(_Y, 11, 1), (date(_Y2, 2, 1), "1060.00"))
    assert _income_by_year(operation, _accrual_then_cash(), rows=rows, invoices=(invoice,)) == {
        _Y: BASE,
        _Y1: ZERO,
        _Y2: ZERO,
    }


def test_an_advance_collected_under_accrual_for_a_cash_year_refuses_in_the_collection_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """Collected under accrual before accruing, and accruing under cash: neither rule reaches it, so it says so."""
    rows, invoice = _collected(date(_Y1, 2, 1), (date(_Y, 12, 1), "1060.00"))
    resolution = _resolve(operation, _accrual_then_cash(), year=_Y, rows=rows, invoices=(invoice,))
    assert INCOME_0171 in unresolved_bindings(resolution)
    assert any("uncomputed_across_change" in item.message for item in resolution.diagnostics)


def _expense_by_year(
    operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
    *,
    accrued: date,
    paid: date,
) -> dict[int, Decimal]:
    invoice = received(accrued, linked=(expense_row(paid, evidence_id=None).transaction_id,))
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice,)))
    row = expense_row(paid, evidence_id=invoice.invoice_id)
    profile = renta_imputation_criterion_profile(operation, facts)
    history = ActivityAssetHistory()
    return {
        year: sum(
            resolve_m100(history, rows=(row,), profile=profile, year=year, invoices=repository).binding_values.values(),
            ZERO,
        )
        for year in _YEARS
    }


def test_an_expense_across_the_change_lands_in_the_first_accrual_year(operation: PinnedAuthorityOperation) -> None:
    assert _expense_by_year(operation, _cash_then_accrual(), accrued=date(_Y, 11, 1), paid=date(_Y2, 2, 1)) == {
        _Y: ZERO,
        _Y1: Decimal("100.00"),
        _Y2: ZERO,
    }


def test_an_expense_leaving_accrual_for_cash_is_not_deducted_twice(operation: PinnedAuthorityOperation) -> None:
    assert _expense_by_year(operation, _accrual_then_cash(), accrued=date(_Y, 11, 1), paid=date(_Y2, 2, 1)) == {
        _Y: Decimal("100.00"),
        _Y1: ZERO,
        _Y2: ZERO,
    }


def test_an_unpaid_received_invoice_of_a_cash_year_withholds_the_first_accrual_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """It is computed there, but only a ledger row carries the category that picks its box, so the box waits."""
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((received(date(_Y, 11, 1), linked=()),)))
    profile = renta_imputation_criterion_profile(operation, _cash_then_accrual())
    resolution = resolve_m100(ActivityAssetHistory(), profile=profile, year=_Y1, invoices=repository)
    assert any(
        item.reason == "unresolved_binding" and "accrual_unclassified" in item.message
        for item in resolution.diagnostics
    )
