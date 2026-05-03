"""Cover the Anexo D ledger-derived input overlay helper.

Exercises
:func:`aeat.domain.formulas._rulesets.modelo_100.anexo_d_ledgers.derive_anexo_d_normal_inputs`
to confirm caller-supplied direct aggregates are preserved when no
ledger context is provided and that
:class:`aeat.domain.profile.inventory.InventoryLedger` overrides win
when supplied. Asset amortization is registry-gated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....profile.assets import AmortizationLedger, AssetClass, AssetRecord
from ....profile.errors import AssetRecordError
from ....profile.inventory import InventoryLedger, ValuationMethod
from .anexo_d_ledgers import derive_anexo_d_normal_inputs

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_direct_aggregates_remain_unchanged_without_ledgers() -> None:
    provided = {"0155": Decimal("99.00"), "0173": Decimal("88.00")}

    assert derive_anexo_d_normal_inputs(provided, year=2025, actividad_id="retail") == provided


def test_inventory_ledgers_win() -> None:
    provided = {"0155": Decimal("99.00"), "0173": Decimal("88.00")}
    inventories = (
        InventoryLedger(
            actividad_id="retail",
            year=2025,
            valuation_method=ValuationMethod.FIFO,
            opening_stock=Decimal("1000.00"),
            closing_stock=Decimal("1250.00"),
        ),
    )

    resolved = derive_anexo_d_normal_inputs(
        provided,
        year=2025,
        actividad_id="retail",
        inventory_ledgers=inventories,
    )

    assert resolved["0155"] == Decimal("250.00")
    assert resolved["0173"] == Decimal("88.00")


def test_asset_amortization_requires_registry_snapshot() -> None:
    provided = {"0155": Decimal("99.00"), "0173": Decimal("88.00")}
    assets = (
        AssetRecord(
            identifier="pc",
            description="pc",
            asset_class=AssetClass.ELECTRONICA_INFORMATICA,
            acquisition_date=date(2025, 1, 1),
            cost_basis=Decimal("1000.00"),
            actividad_id="retail",
        ),
    )

    with pytest.raises(AssetRecordError, match="validated registry snapshot"):
        derive_anexo_d_normal_inputs(
            provided,
            year=2025,
            actividad_id="retail",
            assets=assets,
            amortization_ledger=AmortizationLedger(),
        )
