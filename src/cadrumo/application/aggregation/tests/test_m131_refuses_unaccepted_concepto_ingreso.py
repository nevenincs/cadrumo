"""Modelo 131 casilla 05 refuses an income concept the pinned vocabulary does not declare.

The art. 110.1.c) narrowing used to ask only whether a concept was in the
exclusion set, so a stored concept that a later authority retired was in neither
set and counted as ordinary income. The row is now refused with its field, value
and identity named, while an admitted concept lands exactly where it did.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.concepto_ingreso import ConceptoIngreso
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ..errors import UnacceptedLedgerRegistryValueError
from ..modelo_bindings import _activity_category_matcher, _employment_category_matcher
from ..renta_income_ledger import aggregate_renta_m131_agrario_income_ledger
from .renta_income_aggregation_support import raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "9f86d081-884c-4d65-9a2f-eaa0c55ad015"
_QUARTER = Period.from_year_and_code(2026, "2T")
_IN_WINDOW = date(2026, 5, 14)
_RETIRED = ConceptoIngreso.from_registry("retired_concept")


def _receipt(provider_id: str, *, tipo_actividad: TipoActividad, concepto_ingreso: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": raw_transaction(
                provider_id,
                booked_date=_IN_WINDOW,
                value_date=_IN_WINDOW,
                amount=Decimal("1000.00"),
                currency="EUR",
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 7, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
            "concepto_ingreso": ConceptoIngreso.from_registry(concepto_ingreso),
        },
    )


def _stale(row: Transaction, concepto_ingreso: ConceptoIngreso) -> Transaction:
    """Hand the row back carrying a concept no admission re-checked, as a stale stored row arrives."""
    values = {name: getattr(row, name) for name in Transaction.model_fields} | {"concepto_ingreso": concepto_ingreso}
    return Transaction.model_construct(_fields_set=row.model_fields_set | {"concepto_ingreso"}, **values)


def _casilla_05(row: Transaction) -> Decimal:
    catalogue = TransactionCatalogue.model_construct(transactions={row.transaction_id: row})
    with bundled_indexed_authority().operation() as operation:
        aggregation = aggregate_renta_m131_agrario_income_ledger(
            catalogue,
            bucket_id=_BUCKET,
            period=_QUARTER,
            modelo=Modelo("131").value,
            target_casilla_id=validated_casilla_id("05"),
            agrarian_activity_codes=frozenset(
                TipoActividad(code)
                for code in tipo_actividad_code_set(
                    "modelo-131:selector-m036-volumen-ingresos-agrario",
                    effective_date=_QUARTER.end_date,
                    authority=operation,
                )
            ),
            activity_category_matcher=_activity_category_matcher(operation),
            employment_category_matcher=_employment_category_matcher(operation),
            operation=operation,
        )
    return sum((observation.gross_amount for observation in aggregation.observations), start=Decimal("0"))


def test_an_undeclared_concept_on_an_agrarian_receipt_is_refused_with_the_row_named() -> None:
    admitted = _receipt("agrarian-ordinario", tipo_actividad=TipoActividad.B01_AGRICOLA, concepto_ingreso="ordinario")
    assert _casilla_05(admitted) == Decimal("1000.00")

    stale = _stale(admitted, _RETIRED)
    with pytest.raises(UnacceptedLedgerRegistryValueError) as refusal:
        _casilla_05(stale)

    assert refusal.value.context == {
        "field": "concepto_ingreso",
        "value": "retired_concept",
        "transaction_id": stale.transaction_id,
        "effective_date": _QUARTER.end_date.isoformat(),
    }


def test_an_admitted_excluded_concept_still_stays_out_of_casilla_05() -> None:
    capital = _receipt(
        "agrarian-capital",
        tipo_actividad=TipoActividad.B01_AGRICOLA,
        concepto_ingreso="subvencion_capital",
    )

    assert _casilla_05(capital) == Decimal("0")


def test_an_undeclared_concept_on_a_row_the_narrowing_never_reads_is_not_refused() -> None:
    """A professional receipt is outside the agrarian activity set, so its concept is never consulted."""
    professional = _stale(
        _receipt("professional", tipo_actividad=TipoActividad.A05_PROFESIONALES, concepto_ingreso="ordinario"),
        _RETIRED,
    )

    assert _casilla_05(professional) == Decimal("0")
