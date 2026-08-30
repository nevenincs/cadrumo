"""Modelo 131 casilla 05: the agrarian volumen de ingresos, and what it leaves out.

Two filters make this aggregation different from the Modelo 130 one, and both are
legal rather than incidental. Every test here is about a row that must NOT arrive,
because the failure mode of an aggregation is silence: a dropped row leaves a
smaller number, and a smaller number looks exactly like a correct one.

The two filters default in OPPOSITE directions, which is the part worth pinning.
An undeclared activity contributes nothing, because silence cannot mean "agrarian"
without mis-routing a non-agrarian filer's income into an agrarian box. An
undeclared concept contributes everything, because silence about a receipt's nature
almost always means ordinary income, and reading it as exceptional would drop real
income out of the declared volume.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core import ConceptoIngreso, TipoActividad
from ....core.period import Period
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from .._renta_income_ledger import aggregate_renta_m131_agrario_income_ledger
from ._renta_income_aggregation_support import _raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "9f86d081-884c-4d65-9a2f-eaa0c55ad015"  # was 'test'
_Q1 = Period.from_year_and_code(2025, "1T")
_IN_WINDOW = date(2025, 2, 14)


def _agrarian_row(
    provider_id: str,
    *,
    amount: Decimal = Decimal("1000.00"),
    tipo_actividad: TipoActividad | None = TipoActividad.B01_AGRICOLA,
    concepto_ingreso: ConceptoIngreso | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=_IN_WINDOW,
                value_date=_IN_WINDOW,
                amount=amount,
                currency="EUR",
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
            "concepto_ingreso": concepto_ingreso,
        },
    )


def _total(*transactions: Transaction) -> Decimal:
    catalogue = TransactionCatalogue.model_validate(
        {"transactions": {t.transaction_id: t for t in transactions}},
    )
    aggregation = aggregate_renta_m131_agrario_income_ledger(catalogue, bucket_id=_BUCKET, period=_Q1)
    return sum((o.gross_amount for o in aggregation.observations), start=Decimal("0"))


def test_an_agricola_receipt_reaches_casilla_05() -> None:
    """The positive control. Without it every exclusion below could pass vacuously."""
    assert _total(_agrarian_row("agri-1")) == Decimal("1000.00")


def test_every_code_in_the_registry_selector_contributes() -> None:
    """All four art. 110.1.c) codes, not a sample.

    ``B03 Forestal`` is the one that matters most here: it is absent from the art.
    95 agrícola/ganadera selector, so an implementation that reused that selector
    would pass a test written only against ``B01``.
    """
    for code in (
        TipoActividad.A02_GANADERIA_INDEPENDIENTE,
        TipoActividad.B01_AGRICOLA,
        TipoActividad.B02_GANADERA,
        TipoActividad.B03_FORESTAL,
    ):
        assert _total(_agrarian_row(f"row-{code.value}", tipo_actividad=code)) == Decimal("1000.00"), code


def test_a_non_agrarian_activity_stays_out_of_the_agrarian_box() -> None:
    """A professional receipt belongs to the estimación-objetiva side, not here."""
    assert _total(_agrarian_row("prof-1", tipo_actividad=TipoActividad.A05_PROFESIONALES)) == Decimal("0")


def test_an_undeclared_activity_contributes_nothing() -> None:
    """Silence about activity is not agrarian, and the asymmetry with concept is deliberate.

    Reading an unmarked row as agrarian would move a non-agrarian filer's income
    into casilla 05 while the same row is already claimed by the objetiva side of
    the return. Under-filling a box the operator can complete by hand is
    recoverable; mis-routing income between two boxes of one return is not.
    """
    assert _total(_agrarian_row("unknown-1", tipo_actividad=None)) == Decimal("0")


def test_a_capital_subsidy_is_excluded_but_a_current_one_is_not() -> None:
    """The distinction art. 110.1.c) draws INSIDE subsidies.

    The pair is asserted together rather than in two tests, because the failure
    this guards against is treating them as one thing: any rule keyed on the word
    "subvención" gets exactly one of them wrong.
    """
    corriente = _agrarian_row("sub-corr", concepto_ingreso=ConceptoIngreso.SUBVENCION_CORRIENTE)
    capital = _agrarian_row("sub-cap", concepto_ingreso=ConceptoIngreso.SUBVENCION_CAPITAL)

    assert _total(corriente) == Decimal("1000.00")
    assert _total(capital) == Decimal("0")


def test_an_indemnity_is_excluded() -> None:
    """The other half of the art. 110.1.c) exclusion."""
    assert _total(_agrarian_row("indem", concepto_ingreso=ConceptoIngreso.INDEMNIZACION)) == Decimal("0")


def test_an_undeclared_concept_is_included() -> None:
    """Silence about concept means ordinary income, the opposite default to activity.

    The two defaults point in opposite directions on purpose, and each points away
    from the worse error for its own axis.
    """
    assert _total(_agrarian_row("plain", concepto_ingreso=None)) == Decimal("1000.00")


def test_a_mixed_catalogue_sums_only_the_qualifying_rows() -> None:
    """The filters compose rather than merely working one at a time.

    Five rows, three of which must not arrive. Asserting the total rather than the
    count is what makes a partially-applied filter visible: dropping the activity
    check alone still yields three observations, but the wrong sum.
    """
    total = _total(
        _agrarian_row("keep-agri", amount=Decimal("500.00")),
        _agrarian_row("keep-forest", amount=Decimal("300.00"), tipo_actividad=TipoActividad.B03_FORESTAL),
        _agrarian_row("drop-prof", amount=Decimal("900.00"), tipo_actividad=TipoActividad.A05_PROFESIONALES),
        _agrarian_row("drop-unknown", amount=Decimal("700.00"), tipo_actividad=None),
        _agrarian_row(
            "drop-capital",
            amount=Decimal("400.00"),
            concepto_ingreso=ConceptoIngreso.SUBVENCION_CAPITAL,
        ),
    )

    assert total == Decimal("800.00")
