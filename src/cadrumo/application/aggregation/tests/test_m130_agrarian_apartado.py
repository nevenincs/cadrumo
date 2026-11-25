"""Modelo 130 keeps agrarian activity out of apartado I and declares it in apartado II.

The instructions: agrarian data "no se consignarán en este apartado [I], sino en el
apartado II". Worked by hand for one first quarter:

- consulting: income 10000, expenses 2000, so 01 = 10000, 02 = 2000, 03 = 8000, 04 = 1600;
- agrarian B01: sales 30000 (its expenses 20000 count nowhere on the form),
  so 08 = 30000 and 09 = 600 at the 2 per cent;
- 12 = 1600 + 600 = 2200.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.calculation_resolution import resolve_calculation_inputs
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..source_mesh import CalculationSourceContext
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
    resolve_m130,
)
from .renta_income_aggregation_support import catalogue_read_ports, raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_DECLARED = 2025
_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_VOLUME_BINDING = "modelo-130-volumen-ingresos-agrario"
_AGRARIAN_WITHHELD_BINDING = "modelo-130-retenciones-agrarias"


def _row(
    name: str,
    *,
    direction: TransactionDirection,
    amount: str,
    activity: TipoActividad | None,
    booked: date | None = None,
    category: str | None = None,
) -> Transaction:
    on = booked or date(_DECLARED, 2, 10)
    return Transaction.model_validate(
        {
            "raw": raw_transaction(name, booked_date=on, value_date=on, amount=Decimal(amount), currency="EUR"),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": category,
            "taxable_base": Decimal(amount),
            "iva_rate": None,
            "iva_amount": Decimal("0"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_DECLARED, 7, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": activity,
        },
    )


def _sale(name: str, amount: str, activity: TipoActividad | None, booked: date | None = None) -> Transaction:
    return _row(name, direction=TransactionDirection.INCOMING, amount=amount, activity=activity, booked=booked)


def _purchase(name: str, amount: str, activity: TipoActividad | None) -> Transaction:
    return _row(
        name,
        direction=TransactionDirection.OUTGOING,
        amount=amount,
        activity=activity,
        category="material_oficina",
    )


_CONSULTING = TipoActividad.A05_PROFESIONALES
_FARMING = TipoActividad.B01_AGRICOLA


def _mixed_quarter() -> tuple[Transaction, ...]:
    return (
        _sale("consulting-sale", "10000.00", _CONSULTING),
        _purchase("consulting-cost", "2000.00", _CONSULTING),
        _sale("farm-sale", "30000.00", _FARMING),
        _purchase("farm-cost", "20000.00", _FARMING),
    )


def _income(rows: tuple[Transaction, ...], period: str = "1T"):
    catalogue = TransactionCatalogue.from_transactions(rows)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(catalogue)
    return LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=catalogue),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=_DECLARED,
            period=Period.from_year_and_code(_DECLARED, period),
            revision=published_snapshot("130", filing_year=_DECLARED, period=period).revision,
            profile=cash_criterion_profile(_DECLARED),
        ),
    )


def _calculated(
    operation: PinnedAuthorityOperation,
    bindings: Mapping[str, Decimal],
    typed: Mapping[CasillaId, Decimal] | None = None,
) -> dict[str, Decimal]:
    snapshot = operation.snapshot("130", filing_year=_DECLARED, period="1T")
    resolved = {
        **bindings,
        "irpf.previous_year_economic_activity_net_income": Decimal("100000"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
    }
    inputs = resolve_calculation_inputs(
        revision=snapshot.revision,
        filing_year=_DECLARED,
        period=Period.from_year_and_code(_DECLARED, "1T"),
        backend_casilla_inputs=None,
        resolved_bindings=resolved,
        casilla_inputs=typed or {},
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs.casilla_inputs,
        date_context={"filing_period": date(_DECLARED, 4, 20)},
        binding_values=resolved,
        enum_binding_values={"modelo-130-estimacion-directa-modalidad": "directa_normal"},
    )
    return {
        **{str(key): value for key, value in inputs.casilla_inputs.items()},
        **{str(entry.target_casilla_id): entry.value for entry in result.entries},
    }


def test_a_mixed_quarter_splits_between_the_two_apartados(*, operation: PinnedAuthorityOperation) -> None:
    rows = _mixed_quarter()
    income = _income(rows)
    expenses = resolve_m130(ActivityAssetHistory(), "1T", rows=rows)

    boxes = _calculated(operation, {**income.binding_values, **expenses.binding_values})

    expected = {"01": "10000", "02": "2000", "03": "8000", "04": "1600", "08": "30000", "09": "600", "12": "2200"}
    assert {box: boxes[box] for box in expected} == {box: Decimal(value) for box, value in expected.items()}, boxes


def test_a_row_with_no_declared_activity_stays_in_apartado_i() -> None:
    """Silence cannot mean agrarian, the same default the Modelo 131 volume holds."""
    income = _income((_sale("undeclared", "500.00", None),))

    assert income.binding_values[_INCOME_BINDING] == Decimal("500.00")
    assert income.binding_values[_VOLUME_BINDING] == Decimal("0")


def test_box_08_takes_the_quarter_while_box_01_stays_cumulative() -> None:
    """Instructions: 08 is "el volumen de ingresos del trimestre"; 01 runs from the first day of the year."""
    rows = (
        _sale("q1-consulting", "1000.00", _CONSULTING, date(_DECLARED, 2, 1)),
        _sale("q2-consulting", "2000.00", _CONSULTING, date(_DECLARED, 5, 1)),
        _sale("q1-farm", "4000.00", _FARMING, date(_DECLARED, 2, 1)),
        _sale("q2-farm", "8000.00", _FARMING, date(_DECLARED, 5, 1)),
    )

    income = _income(rows, "2T")

    assert income.binding_values[_INCOME_BINDING] == Decimal("3000.00")
    assert income.binding_values[_VOLUME_BINDING] == Decimal("8000.00")
    assert income.diagnostics == () or all("unrouted" not in item.reason for item in income.diagnostics)


def test_a_farm_row_is_counted_once_as_income_and_never_as_an_expense() -> None:
    expenses = resolve_m130(ActivityAssetHistory(), "1T", rows=(_purchase("farm-only", "700.00", _FARMING),))

    assert sum(expenses.binding_values.values(), Decimal("0")) == Decimal("0")
    assert expenses.source_transaction_ids == ()


def test_a_typed_box_08_replaces_the_ledger_volume_rather_than_adding_to_it(
    *, operation: PinnedAuthorityOperation
) -> None:
    income = _income((_sale("farm", "30000.00", _FARMING),))

    boxes = _calculated(operation, income.binding_values, {validated_casilla_id("08"): Decimal("1000.00")})

    assert boxes["08"] == Decimal("1000.00"), boxes
    assert boxes["09"] == Decimal("20.00"), boxes
