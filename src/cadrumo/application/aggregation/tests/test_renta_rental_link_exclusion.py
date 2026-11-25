"""A ledger row linked to a lease or a property belongs to the rental resolver and to no activity aggregation.

Each linked row below would be admitted by the activity pipelines if it carried no link: it is a business
expense in a valid spending category. Its link alone keeps it out of the annual and quarterly activity
expenses and out of activity income, while the rental resolver counts it, so no amount is counted twice.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_selected_for
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..renta_gasto_ledger import aggregate_renta_gasto_ledger
from ..renta_inmueble_resolver import resolve_renta_inmueble_terms
from ..renta_inmueble_source import renta_inmueble_occurrences
from ..renta_ledger import aggregate_renta_ledger_expenses
from .renta_gasto_aggregation_support import gasto_transaction
from .renta_income_aggregation_support import renta_income_aggregation_period
from .renta_inmueble_support import inmueble, lease, ledger_row, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"
_GASTOS_CASILLA = validated_casilla_id("02")
_AMOUNT = Decimal("121.00")
_CATEGORY = "asesoria_fiscal"


def _year() -> int:
    return newest_authored_edition("100")


def _terms(year: int):
    with bundled_indexed_authority().operation() as operation:
        return resolve_renta_inmueble_terms(
            modelo="100",
            revision_id=revision_selected_for("100", year, "0A").id,
            devengo=date(year, 12, 31),
            operation=operation,
        )


def _linked_expense() -> Transaction:
    return ledger_row(
        "linked-fee",
        amount=_AMOUNT,
        direction=TransactionDirection.OUTGOING,
        booked=date(_year(), 3, 10),
        business_classification=BusinessClassification.BUSINESS,
        category_id=_CATEGORY,
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        inmueble_ref="0",
        gasto_capital_inmobiliario="comunidad",
    )


def _unlinked_expense() -> Transaction:
    return gasto_transaction(
        "unlinked-fee",
        value_date=date(_year(), 3, 10),
        amount=_AMOUNT,
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        category_id=_CATEGORY,
    )


def _annual(*rows: Transaction):
    return aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(rows),
        InvoiceCatalogue(),
        bucket_id=_BUCKET_ID,
        period=renta_income_aggregation_period(_year(), "0A"),
        profile_year=_year(),
    )


def _quarterly(*rows: Transaction):
    return aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions(rows),
        bucket_id=_BUCKET_ID,
        period=renta_income_aggregation_period(_year(), "1T"),
        modelo="130",
        target_casilla_id=_GASTOS_CASILLA,
        accept_activity_marker=True,
    )


def test_a_linked_expense_is_absent_from_the_annual_activity_expenses_and_an_unlinked_one_is_not() -> None:
    linked, unlinked = _linked_expense(), _unlinked_expense()

    result = _annual(linked, unlinked)

    assert {observation.transaction_id for observation in result.observations} == {unlinked.transaction_id}
    assert not result.issues


def test_a_linked_expense_is_absent_from_the_quarterly_activity_expenses_and_an_unlinked_one_is_not() -> None:
    linked, unlinked = _linked_expense(), _unlinked_expense()

    result = _quarterly(linked, unlinked)

    assert {observation.transaction_id for observation in result.observations} == {unlinked.transaction_id}
    assert not result.issues


def test_the_rental_resolver_counts_the_linked_expense() -> None:
    year = _year()
    built = renta_inmueble_occurrences(
        path_values=profile_facts((inmueble(ejercicio=year),), (lease(start=date(year - 1, 9, 1)),)),
        transactions=(_linked_expense(),),
        ejercicio=year,
        concepts=resolve_gasto_capital_inmobiliario_catalogue(effective_date=date(year, 12, 31)),
        terms=_terms(year),
    )

    (occurrence,) = built.occurrences
    assert occurrence.gasto("comunidad") is not None
