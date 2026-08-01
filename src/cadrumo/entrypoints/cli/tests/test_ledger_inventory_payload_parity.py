"""Inventory transport rows must refuse what the canonical inventory models refuse.

The inventory CLI envelope is built by dumping a canonical
:class:`~domain.contribuyente.inventory.InventoryLedger` to JSON and
re-validating the mapping (``_ledger_inventory_cli.py``: ``payload =
ledger.model_dump(mode="json")`` then ``model_validate(payload)``). That dump
renders every ``Decimal`` as a string, every ``StrEnum`` as its bare value, and
the movement date as an ISO string, so the transport rows declared them as
plain ``str``/``int`` and inherited none of the canonical bounds: a blank SKU,
a zero quantity, a bogus valuation method, an IVA rate of 101, a deductible
ratio of 2, and year 1800 all crossed the envelope.

Typing the rows directly from the canonical enums and ``Decimal``/``date``
fields is NOT available here: the strict ``OutputSchema`` base refuses a bare
``'fifo'`` string for an enum-typed field and an ISO string for a ``date``
field, so it would refuse every real payload the CLI produces. The rows
therefore stay strings and carry the canonical bound on the text.

:meth:`TestCanonicalBridge.test_real_dump_bridge_round_trips` is the load-bearing
test: it drives the exact construction the CLI performs, so a regression that
re-breaks the bridge fails here rather than at an operator's terminal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.contribuyente.inventory import (
    InventoryLedger,
    MovementKind,
    MovementRecord,
    StockLayer,
    ValuationMethod,
)
from .._ledger_business_payloads import (
    InventoryCreateResult,
    InventoryLedgerPayload,
    InventoryMovementPayload,
    InventoryStockLayerPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _canonical_ledger() -> InventoryLedger:
    """Return a populated ledger of the shape the inventory service returns."""
    return InventoryLedger(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        opening_layers=(
            StockLayer(
                sku="widget",
                quantity=Decimal("10"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening-1",
            ),
        ),
        period_movements=(
            MovementRecord(
                movement_id="mv-1",
                movement_date=date(2026, 3, 1),
                kind=MovementKind.PURCHASE,
                sku="widget",
                quantity=Decimal("5"),
                unit_cost=Decimal("12.00"),
                taxable_base=Decimal("60.00"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("12.60"),
                deductible_iva_ratio=Decimal("1.00"),
            ),
        ),
    )


def _layer(**overrides: object) -> InventoryStockLayerPayload:
    fields: dict[str, object] = {
        "sku": "widget",
        "quantity": "10",
        "unit_cost": "10.00",
        "source_movement_id": "opening-1",
    }
    fields.update(overrides)
    return InventoryStockLayerPayload(**fields)  # type: ignore[arg-type]


def _movement(**overrides: object) -> InventoryMovementPayload:
    fields: dict[str, object] = {
        "movement_id": "mv-1",
        "movement_date": "2026-03-01",
        "kind": MovementKind.PURCHASE.value,
        "sku": "widget",
        "quantity": "5",
        "unit_cost": "12.00",
        "iva_rate": "21",
        "deductible_iva_ratio": "1.00",
        "schema_version": "1",
    }
    fields.update(overrides)
    return InventoryMovementPayload(**fields)  # type: ignore[arg-type]


def _ledger_row(**overrides: object) -> InventoryLedgerPayload:
    fields: dict[str, object] = {
        "actividad_id": "act-1",
        "year": 2026,
        "valuation_method": ValuationMethod.FIFO.value,
        "opening_stock": "100.00",
        "schema_version": "1",
    }
    fields.update(overrides)
    return InventoryLedgerPayload(**fields)  # type: ignore[arg-type]


class TestCanonicalBridge:
    """The production dump/validate bridge must keep working."""

    def test_real_dump_bridge_round_trips(self) -> None:
        """Drive the exact construction ``_ledger_inventory_cli`` performs."""
        payload = _canonical_ledger().model_dump(mode="json")
        payload["bucket_event_ids"] = ["evt-1"]

        result = InventoryCreateResult.model_validate(payload)

        assert result.valuation_method == ValuationMethod.FIFO.value
        assert result.period_movements[0].kind == MovementKind.PURCHASE.value
        assert result.period_movements[0].movement_date == "2026-03-01"
        assert result.opening_layers[0].sku == "widget"

    def test_bridge_output_is_wire_identical(self) -> None:
        """Validation must not reshape the JSON the operator receives."""
        payload = _canonical_ledger().model_dump(mode="json")
        payload["bucket_event_ids"] = []

        rendered = InventoryCreateResult.model_validate(payload).model_dump(mode="json")

        for key, value in payload.items():
            assert rendered[key] == value, f"transport reshaped {key!r}"


class TestStockLayerBounds:
    """Canonical ``StockLayer`` bounds, re-asserted on the wire strings."""

    def test_well_formed_layer_validates(self) -> None:
        assert _layer().quantity == "10"

    def test_blank_sku_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _layer(sku="")

    def test_zero_quantity_is_refused(self) -> None:
        """The canonical layer requires ``quantity > 0``."""
        with pytest.raises(ValidationError):
            _layer(quantity="0")

    def test_negative_unit_cost_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _layer(unit_cost="-1.00")

    def test_blank_source_movement_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _layer(source_movement_id="")


class TestMovementBounds:
    """Canonical ``MovementRecord`` bounds, re-asserted on the wire strings."""

    def test_well_formed_movement_validates(self) -> None:
        assert _movement().kind == MovementKind.PURCHASE.value

    def test_bogus_kind_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _movement(kind="bogus")

    @pytest.mark.parametrize("bad_date", ["not-a-date", "2026-13-45", "01/03/2026", ""])
    def test_malformed_movement_date_is_refused(self, bad_date: str) -> None:
        with pytest.raises(ValidationError):
            _movement(movement_date=bad_date)

    def test_zero_quantity_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _movement(quantity="0")

    def test_iva_rate_above_one_hundred_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _movement(iva_rate="101")

    def test_deductible_ratio_above_one_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _movement(deductible_iva_ratio="2")

    def test_blank_movement_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _movement(movement_id="")

    @pytest.mark.parametrize("bad", ["not-decimal", "NaN", "Infinity"])
    def test_non_decimal_amount_is_refused(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            _movement(unit_cost=bad)


class TestLedgerBounds:
    """Canonical ``InventoryLedger`` bounds, re-asserted on the wire strings."""

    def test_well_formed_ledger_validates(self) -> None:
        assert _ledger_row().year == 2026

    def test_bogus_valuation_method_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _ledger_row(valuation_method="bogus")

    def test_year_below_the_canonical_floor_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _ledger_row(year=1800)

    def test_negative_opening_stock_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _ledger_row(opening_stock="-1.00")

    def test_blank_actividad_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _ledger_row(actividad_id="")

    def test_unsupported_schema_version_is_refused(self) -> None:
        """The canonical ledger rejects any version but the current one."""
        with pytest.raises(ValidationError):
            _ledger_row(schema_version="-1")
