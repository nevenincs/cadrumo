"""The limits an entry form is served, held against the writers that own them."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Final, get_args

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from ....core.decimal.grammar import european_thousands_reading_is_ambiguous
from ....core.percentage import Percentage, fraction_of_percentage
from ....core.unit_proportion import UnitProportion
from ....domain.buckets.event import BucketEvent
from ....domain.invoices import figures
from ..allocate_operation import LedgerAllocateRequest
from ..classify_requests import LedgerClassifyPatch
from ..counterparty_operation import LedgerCounterpartyRequest
from ..entry_limits import LedgerEntryDecimalRule, TextLimitName, ledger_entry_limits
from ..evidence_add_operation import LedgerEvidenceAddRequest
from ..evidence_mutation_operation import LedgerEvidenceUpdatePatch
from ..invoice_evidence_confirm_operation import LedgerEvidenceConfirmRequest
from ..ledger_add_contracts import LedgerAddRequest
from ..own_account_operation import LedgerOwnAccountRequest
from ..split_operation import LedgerSplitChildRequest, LedgerSplitRequest
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
    assert units["retention_rate"] == "points"
    # What the confirmation takes in those points, and the fraction a stored invoice holds for them.
    assert "retention_points" in LedgerEvidenceConfirmRequest.model_fields
    assert fraction_of_percentage(Decimal("15")) == Decimal("0.15")
    assert figures.retention_findings(fraction_of_percentage(Decimal("1")), Decimal("10"), Decimal("1000")) == ()
    assert figures.retention_findings(Decimal("1"), Decimal("1000"), Decimal("1000")) == ()
    assert [
        finding.code
        for finding in figures.retention_findings(
            fraction_of_percentage(Decimal("1")), Decimal("1000"), Decimal("1000")
        )
    ] == [figures.FigureFindingCode.RETENTION_AMOUNT_MISMATCH]
    assert LedgerEvidenceUpdatePatch(iva_rate="100").iva_rate == "100"
    with pytest.raises(ValidationError):
        LedgerEvidenceUpdatePatch(iva_rate="100.5")


def test_the_recorded_limits_are_what_the_backend_answers() -> None:
    recorded = json.loads(_RECORDING.read_text(encoding="utf-8"))
    assert recorded["limits"] == ledger_entry_limits().model_dump(mode="json")


def _text(length: int) -> str:
    return "x" * length


def _parts(count: int) -> tuple[LedgerSplitChildRequest, ...]:
    return tuple(LedgerSplitChildRequest(amount="1", description=f"part {at}") for at in range(count))


#: Each served text limit, with every request field whose own bound it states and what fills it.
_OWNERS: Final[dict[str, list[tuple[type[BaseModel], str, Callable[[int], object]]]]] = {
    "split_parts": [(LedgerSplitRequest, "children", _parts)],
    "split_part_description": [(LedgerSplitChildRequest, "description", _text)],
    "entry_text": [
        (LedgerUpdatePatch, "description", _text),
        (LedgerUpdatePatch, "counterparty", _text),
        (LedgerUpdatePatch, "notes", _text),
        (LedgerAddRequest, "description", _text),
    ],
    "group_label": [(LedgerUpdatePatch, "group_label", _text)],
    "classify_token": [(LedgerClassifyPatch, "category_id", _text), (LedgerClassifyPatch, "iva_category", _text)],
    "usage_ratio_id": [(LedgerAllocateRequest, "usage_ratio_id", _text)],
    "event_payload_value": [(BucketEvent, "payload", lambda n: {"reason": _text(n)})],
    "evidence_label": [
        (LedgerEvidenceUpdatePatch, "supplier", _text),
        (LedgerEvidenceUpdatePatch, "invoice_number", _text),
        (LedgerEvidenceAddRequest, "supplier", _text),
    ],
    "evidence_note": [(LedgerEvidenceUpdatePatch, "notes", _text), (LedgerEvidenceAddRequest, "notes", _text)],
    "own_account_iban": [(LedgerOwnAccountRequest, "iban", _text)],
    "own_account_swift_bic": [(LedgerOwnAccountRequest, "swift_bic", _text)],
    "counterparty_tax_id": [(LedgerCounterpartyRequest, "tax_identifier", _text)],
    "counterparty_note": [(LedgerCounterpartyRequest, "note", _text)],
}


def _takes(model: type[BaseModel], field: str, value: object) -> bool:
    adapter = TypeAdapter(model.model_fields[field].rebuild_annotation())
    try:
        adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def test_every_served_text_limit_is_one_a_writer_owns() -> None:
    served = {limit.name for limit in ledger_entry_limits().text_limits}
    assert served == set(_OWNERS) == set(get_args(TextLimitName.__value__))
    assert len(ledger_entry_limits().text_limits) == len(served)


@pytest.mark.parametrize("name", sorted(_OWNERS))
def test_the_writers_take_exactly_what_the_text_limit_served_says(name: str) -> None:
    served = next(limit.max for limit in ledger_entry_limits().text_limits if limit.name == name)
    for model, field, fill in _OWNERS[name]:
        assert _takes(model, field, fill(served)), f"{model.__name__}.{field} refuses the served {served}"
        assert not _takes(model, field, fill(served + 1)), f"{model.__name__}.{field} takes more than {served}"
