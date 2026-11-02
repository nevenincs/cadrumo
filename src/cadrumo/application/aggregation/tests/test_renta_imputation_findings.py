"""Part payments, filed elections, unpaid and late withholding, and capital subsidies under RIRPF art. 7.

Worked invoice: 1.000,00 base + 210,00 IVA - 150,00 retencion leaves 1.060,00 to be paid.
A receipt of 530,00 settles half: 500,00 of base and 75,00 of retencion. Under accrual the
other 500,00 still accrues; under cash it waits for its own receipt (art. 7.2).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import (
    CasillaObservation,
    CasillaObservationValueKind,
    RegistryModeloObservation,
)
from ....domain.calculations.registry.concepto_ingreso import resolve_concepto_ingreso_catalogue
from ....domain.invoices.models import Invoice
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.tests.filing_record_test_support import build_modelo_filing_record_for_test
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.profile_export_binding import resolve_profile_export_values
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationFilingHistory,
    imputation_filing_history,
)
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    _InMemoryInvoiceCatalogueRepository,
    resolve_m100,
)
from .renta_income_aggregation_support import catalogue_read_ports
from .test_renta_imputation_criterion import (
    _ACCOUNTING,
    _BASE,
    _CASH,
    _CREDIT_0599,
    _CRITERION,
    _DEVENGO,
    _EARLIER,
    _INCOME_0171,
    _LATER,
    _REGIME,
    _ZERO,
    _declared,
    _expense_row,
    _in_year,
    _issued,
    _profile,
    _receipt,
    _received,
    _unresolved_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_COBROS = ActivityImputationCriterion.COBROS_Y_PAGOS
_ACCRUAL = ActivityImputationCriterion.DEVENGO


def _paying(on: date, amount: str, invoice_id: str | None = None) -> Transaction:
    return _receipt(on, invoice_id=invoice_id, amount=Decimal(amount))


def _part_paid(accrued: date, *payments: tuple[date, str]) -> tuple[tuple[Transaction, ...], Invoice]:
    invoice = _issued(accrued, linked=tuple(_paying(on, amount).transaction_id for on, amount in payments))
    return tuple(_paying(on, amount, invoice.invoice_id) for on, amount in payments), invoice


def _resolve(
    operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
    *,
    rows: tuple[Transaction, ...] = (),
    invoices: tuple[Invoice, ...] = (),
    year: int,
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
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=published_snapshot("100", filing_year=year, period="0A").revision,
            profile=_profile(operation, facts),
        ),
    )


def _messages(resolution: CalculationSourceResolution, source_ref: str) -> list[str]:
    return [item.message for item in resolution.diagnostics if item.source_ref == source_ref]


@pytest.mark.parametrize(
    ("payments", "expected"),
    [
        (((date(_LATER, 2, 1), "530.00"),), Decimal("1000.00")),
        (((date(_LATER, 2, 1), "530.00"), (date(_LATER, 3, 1), "530.00")), Decimal("1000.00")),
        # 100,00 / 1.060,00 of 1.000,00 is 94,34; the rest is 905,66, and they still meet at the base.
        (((date(_LATER, 2, 1), "100.00"),), Decimal("1000.00")),
    ],
)
def test_a_part_paid_invoice_counts_wholly_in_its_accrual_year(
    operation: PinnedAuthorityOperation, payments: tuple[tuple[date, str], ...], expected: Decimal
) -> None:
    rows, invoice = _part_paid(date(_LATER, 1, 15), *payments)
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=rows, invoices=(invoice,), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == expected
    assert _INCOME_0171 not in _unresolved_bindings(resolution)


def test_a_part_paid_invoice_collected_next_year_stays_wholly_in_the_accrual_year(
    operation: PinnedAuthorityOperation,
) -> None:
    rows, invoice = _part_paid(date(_EARLIER, 12, 15), (date(_LATER, 1, 10), "530.00"))
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO))
    earlier = _resolve(operation, facts, rows=rows, invoices=(invoice,), year=_EARLIER)
    later = _resolve(operation, facts, rows=rows, invoices=(invoice,), year=_LATER)
    assert earlier.binding_values[_INCOME_0171] == _BASE
    assert later.binding_values[_INCOME_0171] == _ZERO


def test_part_collections_count_as_collected_under_cash(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _part_paid(
        date(_EARLIER, 12, 1), (date(_EARLIER, 12, 20), "530.00"), (date(_LATER, 1, 10), "530.00")
    )
    facts = _declared((_EARLIER, _CASH), (_LATER, _CASH))
    earlier = _resolve(operation, facts, rows=rows, invoices=(invoice,), year=_EARLIER)
    later = _resolve(operation, facts, rows=rows, invoices=(invoice,), year=_LATER)
    assert earlier.binding_values[_INCOME_0171] == Decimal("500.00")
    assert later.binding_values[_INCOME_0171] == Decimal("500.00")


def test_a_shared_retencion_stays_out_of_the_credit_and_is_reported(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _part_paid(date(_LATER, 1, 15), (date(_LATER, 2, 1), "530.00"))
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=rows, invoices=(invoice,), year=_LATER)
    assert resolution.binding_values[_CREDIT_0599] == _ZERO
    assert "75.00 EUR" in _messages(resolution, "part_payment_allocated")[0]
    assert "75.00 EUR" in _messages(resolution, "accrued_withholding_unpaid")[0]


def test_receipts_above_the_invoice_cannot_be_placed(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _part_paid(date(_LATER, 1, 15), (date(_LATER, 2, 1), "800.00"), (date(_LATER, 3, 1), "800.00"))
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=rows, invoices=(invoice,), year=_LATER)
    assert _INCOME_0171 in _unresolved_bindings(resolution)


def test_withholding_on_an_unpaid_invoice_is_reported_with_count_and_amount(
    operation: PinnedAuthorityOperation,
) -> None:
    invoices = (_issued(date(_LATER, 3, 1), number="F-1"), _issued(date(_LATER, 4, 1), number="F-2"))
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), invoices=invoices, year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == Decimal("2000.00")
    assert resolution.binding_values[_CREDIT_0599] == _ZERO
    assert _messages(resolution, "accrued_withholding_unpaid")[0].startswith("2 accrued invoice(s) state 300.00 EUR")


def test_a_paid_invoice_reports_no_unpaid_withholding(operation: PinnedAuthorityOperation) -> None:
    rows, invoice = _part_paid(date(_LATER, 1, 15), (date(_LATER, 2, 1), "530.00"), (date(_LATER, 3, 1), "530.00"))
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=rows, invoices=(invoice,), year=_LATER)
    assert _messages(resolution, "accrued_withholding_unpaid") == []


def test_payment_after_the_accrual_year_was_filed_names_the_rectification(
    operation: PinnedAuthorityOperation,
) -> None:
    invoice = _issued(date(_EARLIER, 12, 15), linked=(_receipt(date(_LATER, 7, 10)).transaction_id,))
    row = _receipt(date(_LATER, 7, 10), invoice_id=invoice.invoice_id)
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO))
    filings = ImputationFilingHistory(filed_on={_EARLIER: date(_LATER, 6, 30)})
    source_ref = f"invoice:{invoice.invoice_id}"
    earlier = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER, filings=filings)
    later = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_LATER, filings=filings)
    assert f"rectificativa of {_EARLIER}" in _messages(earlier, source_ref)[0]
    assert "150.00 EUR" in _messages(earlier, source_ref)[0]
    assert _messages(later, source_ref)
    assert later.binding_values[_CREDIT_0599] == _ZERO
    assert _CREDIT_0599 not in _unresolved_bindings(later)


def test_payment_before_filing_needs_no_rectification(operation: PinnedAuthorityOperation) -> None:
    invoice = _issued(date(_EARLIER, 12, 15), linked=(_receipt(date(_LATER, 1, 10)).transaction_id,))
    row = _receipt(date(_LATER, 1, 10), invoice_id=invoice.invoice_id)
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO))
    filings = ImputationFilingHistory(filed_on={_EARLIER: date(_LATER, 6, 30)})
    resolution = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER, filings=filings)
    assert _messages(resolution, f"invoice:{invoice.invoice_id}") == []
    assert resolution.binding_values[_CREDIT_0599] == Decimal("150.00")


def test_a_filed_cash_election_blocks_returning_to_accrual_inside_three_years(
    operation: PinnedAuthorityOperation,
) -> None:
    invoice = _issued(date(_LATER, 3, 1))
    filings = ImputationFilingHistory(stated={_LATER - 1: _COBROS})
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), invoices=(invoice,), year=_LATER, filings=filings)
    blocked = [item for item in resolution.diagnostics if item.binding_id == _INCOME_0171]
    assert any(item.reason == "unresolved_binding" and f"return of {_LATER - 1}" in item.message for item in blocked)


def test_a_filed_return_contradicting_its_own_year_blocks(operation: PinnedAuthorityOperation) -> None:
    invoice = _issued(date(_LATER, 3, 1))
    filings = ImputationFilingHistory(stated={_LATER: _COBROS})
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), invoices=(invoice,), year=_LATER, filings=filings)
    assert _INCOME_0171 in _unresolved_bindings(resolution)


def test_counting_a_filed_election_lets_the_fourth_year_return() -> None:
    """A first cash year N binds N, N+1 and N+2; N+3 may return to accrual."""
    first = 2020
    filings = ImputationFilingHistory(stated={first: _COBROS, first + 1: _COBROS, first + 2: _COBROS})
    for year, expected in ((first + 2, None), (first + 3, _ACCRUAL)):
        criteria = ImputationCriteria(facts=_declared((year, _DEVENGO)), filings=filings)
        if year == first + 2:
            assert criteria.filed_conflict(year) is not None
        assert criteria.usable(year) is expected


def test_losing_the_election_to_commercial_accounting_is_no_conflict() -> None:
    year = 2024
    facts = (*_declared((year, _DEVENGO)), _in_year(_ACCOUNTING, True, year))
    criteria = ImputationCriteria(facts=facts, filings=ImputationFilingHistory(stated={year - 1: _COBROS}))
    assert criteria.usable(year) is _ACCRUAL


def test_a_filed_statement_never_fills_an_undeclared_year() -> None:
    criteria = ImputationCriteria(filings=ImputationFilingHistory(stated={2024: _ACCRUAL}))
    assert criteria.declared(2024) is None
    assert criteria.usable(2024) is None


def test_an_undated_regime_opens_cash_as_setup_writes_it() -> None:
    year = 2024
    facts = (
        _in_year(_CRITERION, _CASH, year),
        _in_year(_ACCOUNTING, False, year),
        UserProfileFact(path=_REGIME, value="directa_simplificada"),
    )
    assert ImputationCriteria(facts=facts).usable(year) is _COBROS


def _flag_observation(year: int, casilla: str, value: str) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="100",
        filing_year=year,
        period="0A",
        observations=(
            CasillaObservation(
                casilla_id=casilla,
                value_kind=CasillaObservationValueKind.TEXT,
                value=value,
                legal_refs=("rd-439-2007:art-7",),
                source_refs=("aeat-renta-2022-manual-parte1",),
            ),
        ),
    )


def test_the_filing_history_reads_the_marked_box_and_the_record_date() -> None:
    year = 2025
    filed = build_modelo_filing_record_for_test(modelo="100").model_copy(
        update={
            "filing_year": year - 1,
            "period": Period.from_year_and_code(year - 1, "0A"),
            "filed_at": datetime(year, 6, 1, tzinfo=UTC),
        }
    )
    observed = {
        (year - 1): _flag_observation(year - 1, "1443", "X"),
        (year - 2): _flag_observation(year - 2, "0169", ""),
    }
    history = imputation_filing_history(
        bucket_id=filed.bucket_id,
        year=year,
        annual_form=filed.modelo,
        annual_period_code="0A",
        load_observation=lambda _modelo, period: observed.get(period.filing_year),
        filing_records=ModeloRecordCatalogue(records={filed.filing_record_id: filed}),
    )
    assert history.stated == {year - 1: _COBROS, year - 2: _ACCRUAL}
    assert history.filed_on == {year - 1: date(year, 6, 1)}


@pytest.mark.parametrize("edition", [2022, 2023, 2024, 2025])
def test_the_election_boxes_keep_their_roles_in_each_edition(edition: int) -> None:
    roles = {
        str(casilla.id): casilla.semantic_role
        for casilla in published_snapshot("100", filing_year=edition, period="0A").revision.casillas
        if str(casilla.id) in {"0169", "1443", "1487"}
    }
    assert roles == {
        "0169": "irpf_ed_cobros_pagos_flag",
        "1443": "irpf_eo_cobros_pagos_flag",
        "1487": "irpf_eo_agr_cobros_pagos_flag",
    }


@pytest.mark.parametrize("criterion", [_DEVENGO, _CASH])
def test_a_capital_subsidy_stays_unresolved_under_either_criterion(
    operation: PinnedAuthorityOperation, criterion: str
) -> None:
    catalogue = resolve_concepto_ingreso_catalogue(effective_date=date(_LATER, 1, 1), authority=operation)
    row = _paying(date(_LATER, 2, 1), "1000.00").model_copy(
        update={"concepto_ingreso": catalogue.require("subvencion_capital")}
    )
    resolution = _resolve(operation, _declared((_LATER, criterion)), rows=(row,), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _ZERO
    blocked = [item.message for item in resolution.diagnostics if item.binding_id == _INCOME_0171]
    assert any("capital_subsidy_schedule_unknown" in message for message in blocked)


def test_a_part_paid_received_invoice_under_accrual_names_the_uncovered_rest(
    operation: PinnedAuthorityOperation,
) -> None:
    amount, base = Decimal("48.40"), Decimal("40.00")
    unlinked = _expense_row(date(_LATER, 4, 2), evidence_id=None, amount=amount, base=base)
    invoice = _received(date(_LATER, 4, 1), linked=(unlinked.transaction_id,))
    row = _expense_row(date(_LATER, 4, 2), evidence_id=invoice.invoice_id, amount=amount, base=base)
    invoices = _InMemoryInvoiceCatalogueRepository()
    invoices.save(build_invoice_catalogue((invoice,)))
    profile = _profile(operation, _declared((_LATER, _DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, year=_LATER, invoices=invoices)
    assert any(
        item.reason == "unresolved_binding" and "accrues 100.00" in item.message for item in resolution.diagnostics
    )


_CASILLA_0169_BINDING = "renta-profile-activity-cash-criterion-0169"


def _elected(operation: PinnedAuthorityOperation, facts: tuple[UserProfileFact, ...], year: int) -> object:
    revision = published_snapshot("100", filing_year=year, period="0A").revision
    exported = resolve_profile_export_values(
        tuple(binding for binding in revision.bindings if binding.id == _CASILLA_0169_BINDING),
        bucket_id=BUCKET_ID,
        filing_year=year,
        operation=operation,
        profile_record=_profile(operation, facts).record,
    )
    return exported.get("E1ITEMP")


@pytest.mark.parametrize("edition", [2022, 2023, 2024, 2025])
@pytest.mark.parametrize(("criterion", "marked"), [(_CASH, True), (_DEVENGO, False)])
def test_casilla_0169_states_the_year_criterion_in_each_edition(
    operation: PinnedAuthorityOperation, edition: int, criterion: str, marked: bool
) -> None:
    regime = UserProfileFact(path=_REGIME, value="directa_simplificada")
    facts = (_in_year(_CRITERION, criterion, edition), regime)
    assert _elected(operation, facts, edition) is marked
    assert _elected(operation, facts, edition + 1 if edition < 2025 else edition - 1) is None
    revision = published_snapshot("100", filing_year=edition, period="0A").revision
    binding = next(item for item in revision.bindings if str(item.id) == _CASILLA_0169_BINDING)
    assert "rd-439-2007:art-7" in binding.legal_refs


def test_casilla_0169_stays_absent_when_undeclared_or_outside_direct_estimation(
    operation: PinnedAuthorityOperation,
) -> None:
    year = 2025
    assert _elected(operation, (UserProfileFact(path=_REGIME, value="directa_normal"),), year) is None
    objetiva = (UserProfileFact(path=_REGIME, value="objetiva"), _in_year(_CRITERION, _CASH, year))
    assert _elected(operation, objetiva, year) is None
