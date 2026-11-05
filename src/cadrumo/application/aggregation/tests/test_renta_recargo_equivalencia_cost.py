"""A retailer in the recargo de equivalencia deducts the IVA and recargo she bears as cost.

LIVA art. 154.Dos gives the retailer no right to deduct the IVA or the recargo a supplier charges her,
so both join the acquisition cost for the IRPF (LIRPF art. 28, with the IS rules on non-deductible IVA). The
regime comes from the profile, so the same purchase under the general regime keeps only its base.

Worked figures: a purchase of 6.800,00 base, 1.428,00 IVA at 21 % and 353,60 recargo at 5,2 % costs
8.581,60 to the retailer; a purchase of 1.000,00 plus 210,00 IVA costs 1.210,00 to her and 1.000,00 to a
general-regime taxpayer, who recovers the IVA.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.models import Transaction
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from .ledger_source_mesh_support import _m130_binding_id, _revision, cash_criterion_profile, resolve_m130
from .renta_ledger_support import ledger_expense_transaction
from .test_renta_gasto_linked_invoice import _YEAR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_CATEGORY = SpendingCategory.from_registry("suministros_cliente_directos")


def _purchase(*, base: str, iva: str, recargo: str | None = None) -> Transaction:
    gross = Decimal(base) + Decimal(iva) + Decimal(recargo or "0")
    return ledger_expense_transaction(
        "compra",
        amount=gross,
        category=_CATEGORY,
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
        taxable_base=Decimal(base),
        iva_amount=Decimal(iva),
        recargo_amount=None if recargo is None else Decimal(recargo),
    )


def _expense_box(regime: str, row: Transaction) -> Decimal:
    profile = cash_criterion_profile(_YEAR, extra_facts=(UserProfileFact(path="iva.regime", value=regime),))
    resolution = resolve_m130(ActivityAssetHistory(), "1T", rows=(row,), profile=profile)
    return resolution.binding_values[_m130_binding_id(_revision("130", "2019-y-siguientes"))]


def test_the_retailer_deducts_the_base_the_iva_and_the_recargo_as_cost() -> None:
    row = _purchase(base="6800.00", iva="1428.00", recargo="353.60")

    assert _expense_box("RECARGO_EQUIVALENCIA", row) == Decimal("8581.60")


def test_the_retailer_bears_the_iva_of_an_ordinary_purchase_as_cost() -> None:
    assert _expense_box("RECARGO_EQUIVALENCIA", _purchase(base="1000.00", iva="210.00")) == Decimal("1210.00")


def test_a_general_regime_taxpayer_keeps_only_the_base() -> None:
    assert _expense_box("GENERAL", _purchase(base="1000.00", iva="210.00")) == Decimal("1000.00")
