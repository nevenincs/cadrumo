"""The limits an entry form is served, held against the writers that own them."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core.decimal.grammar import european_thousands_reading_is_ambiguous
from ....core.percentage import Percentage
from ....core.unit_proportion import UnitProportion
from ....domain.invoices import figures
from ..entry_limits import LedgerEntryDecimalRule, ledger_entry_limits
from ..evidence_mutation_operation import LedgerEvidenceUpdatePatch
from ..update_contracts import LedgerUpdatePatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECORDING: Final = Path(__file__).resolve().parents[5] / (
    "native/desktop/frontend/src/dev/fixtures/ledgerEntryOptions.json"
)


def _rule(name: str) -> LedgerEntryDecimalRule:
    return next(rule for rule in ledger_entry_limits().decimal_rules if rule.rule == name)


def test_every_rule_says_its_decimals_and_whether_zero_is_a_value() -> None:
    assert {rule.rule: (rule.decimals, rule.zero) for rule in ledger_entry_limits().decimal_rules} == {
        "amount": (2, False),
        "tax_amount": (2, True),
        "quantity": (6, False),
        "unit_price": (6, True),
    }


@pytest.mark.parametrize(
    ("field", "text", "taken"),
    [
        ("amount", "12.34", True),
        ("amount", "12.345", False),
        ("amount", "-1", False),
        ("taxable_base", "0", True),
        ("taxable_base", "12.34", True),
        ("taxable_base", "12.3456", False),
        ("iva_amount", "0.01", True),
        ("iva_amount", "0.0101", False),
    ],
)
def test_the_correction_writer_holds_money_to_the_rule_served(field: str, text: str, taken: bool) -> None:
    assert _rule("amount").decimals == _rule("tax_amount").decimals == 2
    if taken:
        assert getattr(LedgerUpdatePatch(**{field: text}), field) == text
        return
    with pytest.raises(ValidationError):
        LedgerUpdatePatch(**{field: text})


def test_an_invoice_line_refuses_the_zero_the_rules_refuse() -> None:
    assert not _rule("quantity").zero
    assert _rule("unit_price").zero
    assert figures.quantity_finding(Decimal("0")) is not None
    assert figures.quantity_finding(Decimal("0.000001")) is None
    assert figures.line_amount_finding(Decimal("0"), field_name="unit_price") is None
    assert figures.line_amount_finding(Decimal("-0.01"), field_name="unit_price") is not None


def test_percentages_stop_where_their_owners_do() -> None:
    limits = ledger_entry_limits()
    assert limits.percent_points_max == "100"
    assert limits.percent_fraction_max == "1"
    points = TypeAdapter(Percentage)
    fraction = TypeAdapter(UnitProportion)
    assert points.validate_python(Decimal(limits.percent_points_max)) == Decimal("100")
    assert fraction.validate_python(Decimal(limits.percent_fraction_max)) == Decimal("1")
    with pytest.raises(ValidationError):
        points.validate_python(Decimal("100.0001"))
    with pytest.raises(ValidationError):
        fraction.validate_python(Decimal("1.0001"))


@pytest.mark.parametrize(
    ("text", "two_way"),
    [
        ("1.234", True),
        ("10.500", True),
        ("100.000", True),
        ("1.23", False),
        ("1.2345", False),
        ("0.333", False),
        ("1000.000", False),
        ("1234", False),
    ],
)
def test_the_two_way_shape_served_answers_as_the_owner_does(text: str, two_way: bool) -> None:
    served = re.fullmatch(ledger_entry_limits().two_way_decimal, text) is not None
    assert served == two_way
    assert served == european_thousands_reading_is_ambiguous(text)


def test_an_evidence_rate_is_on_the_points_scale_the_field_is_served_on() -> None:
    units = {item.field: item.unit for item in ledger_entry_limits().document_percent_fields}
    assert units["iva_rate"] == "points"
    assert LedgerEvidenceUpdatePatch(iva_rate="100").iva_rate == "100"
    with pytest.raises(ValidationError):
        LedgerEvidenceUpdatePatch(iva_rate="100.5")


def test_the_recorded_limits_are_what_the_backend_answers() -> None:
    recorded = json.loads(_RECORDING.read_text(encoding="utf-8"))
    assert recorded["limits"] == ledger_entry_limits().model_dump(mode="json")
