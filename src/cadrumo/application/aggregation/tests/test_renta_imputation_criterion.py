"""The dated imputation criterion places activity income and expense in one ejercicio.

LIRPF art. 14.1.b imputes on accrual; RIRPF art. 7.2 opens a cash election kept
three years; art. 7.4 forbids a change of criterion from computing a row twice or
never. Every case runs the production resolver against the published revision.

Worked income figures: 1.000,00 base + 210,00 IVA - 150,00 retencion = 1.060,00 banked.
Worked expense figures: 100,00 base + 21,00 IVA = 121,00 paid, 100,00 deductible.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ....domain.calculations.registry.invoice_legal_classification import advance_payment_received_role
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.work_profile import ModeloWorkProfile
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..renta_imputation import ImputationCriteria, ImputationUnresolved, impute_row
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    _InMemoryInvoiceCatalogueRepository,
    m130_box,
    resolve_m100,
    resolve_m130,
)
from .ledger_transaction_support import ledger_raw_transaction
from .renta_income_aggregation_support import catalogue_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_LATER = newest_authored_edition("100")
_EARLIER = _LATER - 1
_BASE = Decimal("1000.00")
_IVA = Decimal("210.00")
_RETENCION = Decimal("150.00")
_BANKED = Decimal("1060.00")
_ZERO = Decimal("0")
_INCOME_0171 = "renta-ledger-income-0171"
_CREDIT_0599 = "renta-ledger-actividad-retenciones-0599"
_INCOME_M130_01 = "modelo-130-actividad-economica-ingresos-cumulative"
_CRITERION = "irpf.activity_income_imputation_criterion"
_ACCOUNTING = "irpf.codigo_comercio_accounting"
_REGIME = "irpf.estimation_regime"
_DEVENGO = "devengo"
_CASH = "cobros_y_pagos"


def _in_year(path: str, value: object, year: int) -> UserProfileFact:
    return UserProfileFact.model_validate(
        {"path": path, "value": value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
    )


def _declared(*by_year: tuple[int, str]) -> tuple[UserProfileFact, ...]:
    """State one criterion per year, with the regime and accounting a cash election requires."""
    facts: list[UserProfileFact] = []
    for year, criterion in by_year:
        facts.append(_in_year(_CRITERION, criterion, year))
        if criterion == _CASH:
            facts.append(_in_year(_REGIME, "directa_simplificada", year))
            facts.append(_in_year(_ACCOUNTING, False, year))
    return tuple(facts)


def _profile(operation: PinnedAuthorityOperation, facts: tuple[UserProfileFact, ...]) -> ModeloWorkProfile:
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *facts),
            context=leased_profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _receipt(on: date, *, invoice_id: str | None = None, amount: Decimal = _BANKED) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"cobro-{on.isoformat()}",
                booked_date=on,
                value_date=on,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SL",
                description="cobro factura",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(_LATER, 2, 1, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_LATER, 2, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "invoice_id": invoice_id,
        },
    )


def _issued(
    accrued: date,
    *,
    linked: tuple[str, ...] = (),
    number: str = "F-1",
    advance_received_on: date | None = None,
) -> Invoice:
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=_IVA,
    )
    advance: dict[str, object] = (
        {}
        if advance_received_on is None
        else {"operation_date": advance_received_on, "operation_date_role": advance_payment_received_role()}
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": accrued,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "bucket_id": BUCKET_ID,
            "base_total": _BASE,
            "iva_total": _IVA,
            "grand_total": _BASE + _IVA,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID if linked else PaymentStatus.PENDING,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": _RETENCION,
            "linked_transaction_ids": linked,
            **advance,
        },
    )


def _paid_invoice(
    accrued: date, collected: date, *, advance_received_on: date | None = None
) -> tuple[Transaction, Invoice]:
    """Return one receipt and the issued invoice it collects, each naming the other."""
    unlinked = _receipt(collected)
    invoice = _issued(accrued, linked=(unlinked.transaction_id,), advance_received_on=advance_received_on)
    return _receipt(collected, invoice_id=invoice.invoice_id), invoice


def _resolve(
    operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
    *,
    rows: tuple[Transaction, ...] = (),
    invoices: tuple[Invoice, ...] = (),
    year: int,
    modelo: str = "100",
    period: str = "0A",
) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(rows)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=build_invoice_catalogue(invoices), transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo=modelo,
            filing_year=year,
            period=Period.from_year_and_code(year, period),
            revision=published_snapshot(modelo, filing_year=year, period=period).revision,
            profile=_profile(operation, facts),
        ),
    )


def _unresolved_bindings(resolution: CalculationSourceResolution) -> set[str]:
    return {str(item.binding_id) for item in resolution.diagnostics if item.reason == "unresolved_binding"}


_BOTH_YEARS = (date(_EARLIER, 12, 20), date(_LATER, 1, 10))


@pytest.mark.parametrize(
    ("criterion", "earlier", "later"),
    [(_DEVENGO, _BASE, _ZERO), (_CASH, _ZERO, _BASE)],
)
def test_a_boundary_invoice_lands_once_in_the_year_its_criterion_names(
    operation: PinnedAuthorityOperation, criterion: str, earlier: Decimal, later: Decimal
) -> None:
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    facts = _declared((_EARLIER, criterion), (_LATER, criterion))
    in_earlier = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER)
    in_later = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_LATER)
    assert in_earlier.binding_values[_INCOME_0171] == earlier
    assert in_later.binding_values[_INCOME_0171] == later
    assert not _unresolved_bindings(in_earlier) | _unresolved_bindings(in_later)


def test_the_withholding_of_a_boundary_invoice_follows_its_income(operation: PinnedAuthorityOperation) -> None:
    """The 150,00 retained travels with the 1.000,00 into the accrual year, and only there."""
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO))
    earlier = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER)
    later = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_LATER)
    assert earlier.binding_values[_CREDIT_0599] == _RETENCION
    assert later.binding_values[_CREDIT_0599] == _ZERO


def test_an_unset_criterion_picks_no_year_and_keeps_the_box_withheld(operation: PinnedAuthorityOperation) -> None:
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    for year in (_EARLIER, _LATER):
        resolution = _resolve(operation, (), rows=(row,), invoices=(invoice,), year=year)
        assert resolution.binding_values[_INCOME_0171] == _ZERO
        assert _INCOME_0171 in _unresolved_bindings(resolution)


def test_a_year_with_no_activity_needs_no_criterion(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(operation, (), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _ZERO
    assert not _unresolved_bindings(resolution)


def test_a_ledger_row_with_no_invoice_under_accrual_stays_unresolved(operation: PinnedAuthorityOperation) -> None:
    """The bank date is not a stand-in for an accrual nothing documents."""
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=(_receipt(date(_LATER, 3, 1)),), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _ZERO
    assert _INCOME_0171 in _unresolved_bindings(resolution)


def test_a_ledger_row_with_no_invoice_under_cash_lands_on_its_bank_date(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(operation, _declared((_LATER, _CASH)), rows=(_receipt(date(_LATER, 3, 1)),), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] > _ZERO
    assert not _unresolved_bindings(resolution)


def test_an_unpaid_invoice_accrues_as_income_without_withholding(operation: PinnedAuthorityOperation) -> None:
    """Under accrual the base counts with no receipt; the 150,00 is not deductible before payment."""
    invoice = _issued(date(_LATER, 3, 1))
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), invoices=(invoice,), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _BASE
    assert resolution.binding_values[_CREDIT_0599] == _ZERO
    assert f"invoice:{invoice.invoice_id}" in {item.source_ref for item in resolution.provenance}


def test_an_unpaid_invoice_is_no_income_under_cash(operation: PinnedAuthorityOperation) -> None:
    invoice = _issued(date(_LATER, 3, 1))
    resolution = _resolve(operation, _declared((_LATER, _CASH)), invoices=(invoice,), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _ZERO


def test_an_advance_receipt_has_no_accrual_to_stand_on(operation: PinnedAuthorityOperation) -> None:
    """An advance's date is when the money arrived, so accrual stays unresolved rather than taking it."""
    received = date(_LATER, 2, 1)
    row, invoice = _paid_invoice(received, received, advance_received_on=received)
    resolution = _resolve(operation, _declared((_LATER, _DEVENGO)), rows=(row,), invoices=(invoice,), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == _ZERO
    assert _INCOME_0171 in _unresolved_bindings(resolution)


@pytest.mark.parametrize(
    ("period", "criterion", "expected"),
    [
        ("1T", _DEVENGO, _BASE),
        ("2T", _DEVENGO, _BASE),
        ("3T", _DEVENGO, _BASE),
        ("1T", _CASH, _ZERO),
        ("2T", _CASH, _BASE),
        ("3T", _CASH, _BASE),
    ],
)
def test_m130_quarters_accumulate_the_row_once_from_the_quarter_its_criterion_names(
    operation: PinnedAuthorityOperation, period: str, criterion: str, expected: Decimal
) -> None:
    """Accrued 15 March, collected 5 April: the cumulative box holds 1.000,00 from then on, never 2.000,00."""
    row, invoice = _paid_invoice(date(_LATER, 3, 15), date(_LATER, 4, 5))
    resolution = _resolve(
        operation,
        _declared((_LATER, criterion)),
        rows=(row,),
        invoices=(invoice,),
        year=_LATER,
        modelo="130",
        period=period,
    )
    assert resolution.binding_values[_INCOME_M130_01] == expected


def test_a_quarter_excludes_a_receipt_that_accrued_the_year_before(operation: PinnedAuthorityOperation) -> None:
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    resolution = _resolve(
        operation,
        _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO)),
        rows=(row,),
        invoices=(invoice,),
        year=_LATER,
        modelo="130",
        period="1T",
    )
    assert resolution.binding_values[_INCOME_M130_01] == _ZERO


def test_leaving_cash_for_accrual_computes_a_straddling_row_in_the_first_accrual_year(
    operation: PinnedAuthorityOperation,
) -> None:
    """Art. 7.4: accrued under cash, collected under accrual, so neither rule alone reaches it."""
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    facts = (*_declared((_EARLIER, _CASH), (_LATER, _DEVENGO)), _in_year(_ACCOUNTING, True, _LATER))
    earlier = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER)
    later = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_LATER)
    assert earlier.binding_values[_INCOME_0171] == _ZERO
    assert later.binding_values[_INCOME_0171] == _BASE


def test_leaving_accrual_for_cash_does_not_compute_the_row_again(operation: PinnedAuthorityOperation) -> None:
    """Art. 7.4: accrued under accrual and already computed, so the later cash year adds nothing."""
    row, invoice = _paid_invoice(*_BOTH_YEARS)
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _CASH))
    earlier = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_EARLIER)
    later = _resolve(operation, facts, rows=(row,), invoices=(invoice,), year=_LATER)
    assert earlier.binding_values[_INCOME_0171] == _BASE
    assert later.binding_values[_INCOME_0171] == _ZERO


def test_returning_to_accrual_inside_the_three_year_minimum_is_not_usable() -> None:
    cash_then_accrual = ImputationCriteria(facts=_declared((_EARLIER, _CASH), (_LATER, _DEVENGO)))
    assert cash_then_accrual.usable(_LATER) is None
    assert (
        impute_row(date(_LATER, 2, 1), date(_LATER, 1, 1), cash_then_accrual) is ImputationUnresolved.ELECTION_NOT_OPEN
    )


def test_a_cash_election_three_years_old_may_end() -> None:
    criteria = ImputationCriteria(
        facts=_declared((_LATER - 3, _CASH), (_LATER - 2, _CASH), (_LATER - 1, _CASH), (_LATER, _DEVENGO))
    )
    assert criteria.usable(_LATER) is not None


def test_cash_without_a_declared_accounting_state_is_not_usable() -> None:
    criteria = ImputationCriteria(facts=(_in_year(_CRITERION, _CASH, _LATER),))
    assert criteria.usable(_LATER) is None


def test_contradictory_criteria_in_one_year_read_as_undeclared() -> None:
    criteria = ImputationCriteria(facts=(_in_year(_CRITERION, _CASH, _LATER), _in_year(_CRITERION, _DEVENGO, _LATER)))
    assert criteria.declared(_LATER) is None


def _expense_row(
    on: date,
    *,
    evidence_id: str | None,
    amount: Decimal = Decimal("121.00"),
    base: Decimal = Decimal("100.00"),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(f"gasto-{on.isoformat()}", booked_date=on, amount=amount),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": evidence_id,
            "taxable_base": base,
            "category_id": SpendingCategory.from_registry("asesoria_fiscal").value,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _received(accrued: date, *, linked: tuple[str, ...]) -> Invoice:
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "R-1",
            "issued_at": accrued,
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID if linked else PaymentStatus.PENDING,
            "linked_transaction_ids": linked,
        },
    )


def _expense_ledger(accrued: date, paid: date) -> tuple[Transaction, _InMemoryInvoiceCatalogueRepository]:
    unlinked = _expense_row(paid, evidence_id=None)
    invoice = _received(accrued, linked=(unlinked.transaction_id,))
    repository = _InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice,)))
    return _expense_row(paid, evidence_id=invoice.invoice_id), repository


@pytest.mark.parametrize(
    ("criterion", "first_year", "second_year"),
    [(_DEVENGO, Decimal("100.00"), _ZERO), (_CASH, _ZERO, Decimal("100.00"))],
)
def test_m100_expense_lands_once_in_the_year_its_criterion_names(
    operation: PinnedAuthorityOperation, criterion: str, first_year: Decimal, second_year: Decimal
) -> None:
    row, invoices = _expense_ledger(date(_EARLIER, 4, 1), date(_LATER, 1, 10))
    profile = _profile(operation, _declared((_EARLIER, criterion), (_LATER, criterion)))
    history = ActivityAssetHistory()
    first = resolve_m100(history, rows=(row,), profile=profile, year=_EARLIER, invoices=invoices)
    second = resolve_m100(history, rows=(row,), profile=profile, year=_LATER, invoices=invoices)
    assert sum(first.binding_values.values(), _ZERO) == first_year
    assert sum(second.binding_values.values(), _ZERO) == second_year


@pytest.mark.parametrize(
    ("period", "criterion", "expected"),
    [
        ("1T", _DEVENGO, _ZERO),
        ("2T", _DEVENGO, Decimal("100.00")),
        ("3T", _DEVENGO, Decimal("100.00")),
        ("2T", _CASH, _ZERO),
        ("3T", _CASH, Decimal("100.00")),
    ],
)
def test_m130_expense_accumulates_once_from_the_quarter_its_criterion_names(
    operation: PinnedAuthorityOperation, period: str, criterion: str, expected: Decimal
) -> None:
    row, invoices = _expense_ledger(date(2025, 4, 1), date(2025, 7, 10))
    profile = _profile(operation, _declared((2025, criterion)))
    resolution = resolve_m130(ActivityAssetHistory(), period, rows=(row,), profile=profile, invoices=invoices)
    assert m130_box(resolution) == expected


def test_an_expense_row_with_no_invoice_under_accrual_stays_unresolved(operation: PinnedAuthorityOperation) -> None:
    row = _expense_row(date(2025, 4, 1), evidence_id=None)
    profile = _profile(operation, _declared((2025, _DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), "2T", rows=(row,), profile=profile)
    assert m130_box(resolution) == _ZERO
    assert "unresolved_binding" in {item.reason for item in resolution.diagnostics}


def test_an_unset_criterion_withholds_the_expense_box(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _expense_ledger(date(2025, 4, 1), date(2025, 4, 2))
    resolution = resolve_m130(
        ActivityAssetHistory(), "2T", rows=(row,), profile=_profile(operation, ()), invoices=invoices
    )
    assert "unresolved_binding" in {item.reason for item in resolution.diagnostics}


def test_an_unpaid_received_invoice_under_accrual_keeps_the_box_withheld(operation: PinnedAuthorityOperation) -> None:
    """It accrues, but only a ledger row carries the category that picks its box."""
    invoices = _InMemoryInvoiceCatalogueRepository()
    invoices.save(build_invoice_catalogue((_received(date(2025, 4, 1), linked=()),)))
    profile = _profile(operation, _declared((2025, _DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), "2T", profile=profile, invoices=invoices)
    assert "unresolved_binding" in {item.reason for item in resolution.diagnostics}


_CREDIT_M130_06 = "modelo-130-actividad-economica-retenciones-cumulative"
_FIRST_QUARTER_ACCRUAL = (date(2025, 3, 20), date(2025, 4, 10))


@pytest.mark.parametrize(
    ("criterion", "income", "credit"),
    [(_DEVENGO, _BASE, _RETENCION), (_CASH, _ZERO, _ZERO)],
)
def test_m130_first_quarter_income_and_credit_follow_the_criterion(
    operation: PinnedAuthorityOperation, criterion: str, income: Decimal, credit: Decimal
) -> None:
    """An invoice of 1.000,00 less 150,00 retained, accrued in March and collected in April."""
    row, invoice = _paid_invoice(*_FIRST_QUARTER_ACCRUAL)
    resolution = _resolve(
        operation,
        _declared((2025, criterion)),
        rows=(row,),
        invoices=(invoice,),
        year=2025,
        modelo="130",
        period="1T",
    )
    assert resolution.binding_values[_INCOME_M130_01] == income
    assert resolution.binding_values[_CREDIT_M130_06] == credit


@pytest.mark.parametrize(
    ("modelo", "period", "capped", "follow_the_criterion"),
    [
        ("100", "0A", "0599", ("0171",)),
        ("130", "1T", "06", ("01", "02")),
    ],
)
def test_only_the_retencion_credit_stays_capped_beside_the_boxes_the_criterion_places(
    operation: PinnedAuthorityOperation, modelo: str, period: str, capped: str, follow_the_criterion: tuple[str, ...]
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=2025, period=period)
    reached = {
        str(casilla_id)
        for entry in capped_binding_reach(
            snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
        ).values()
        for casilla_id in entry.casilla_ids
    }
    assert capped in reached
    assert not reached.intersection(follow_the_criterion)
    expense_sources = {
        "ledger_renta_gastos_estimacion_directa_aggregation",
        "ledger_renta_gastos_pago_fraccionado_aggregation",
    }
    expense_bindings = [binding for binding in snapshot.revision.bindings if str(binding.source) in expense_sources]
    assert expense_bindings
    assert all(binding.grade_cap is None for binding in expense_bindings)
