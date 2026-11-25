"""DR369 general notes 6-7 distinguish absent numeric slots from declared zero."""

from decimal import Decimal

import pytest

from ..errors import RegistryValidationError
from ..fixed_width_codec import render_fixed_width_export_field
from ..fixed_width_parser import parse_fixed_width_export_field
from ..schema_exports import ExportFieldDefinition
from .authored_editions import filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _correction_amount() -> ExportFieldDefinition:
    snapshot = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period="EXT-1T", revision_id="esquema-exterior"
    )
    [record] = [
        record for record in snapshot.revision.export_layouts[0].records if record.id == "modelo-369-exterior-t36902"
    ]
    [amount, *_] = [field for field in record.fields if field.data_type == "money"]
    assert not amount.required
    assert amount.length == 17
    assert amount.absent_fill == "spaces"
    return amount


def test_absent_m369_correction_amount_round_trips_as_spaces():
    field = _correction_amount()
    assert render_fixed_width_export_field(field, None) == " " * 17
    assert parse_fixed_width_export_field(field, " " * 17) is None
    assert render_fixed_width_export_field(field, parse_fixed_width_export_field(field, " " * 17)) == " " * 17


@pytest.mark.parametrize(("amount", "wire"), [(Decimal("0"), "0" * 17), (Decimal("12.34"), "0" * 13 + "1234")])
def test_populated_m369_correction_amount_preserves_zero_and_numeric_padding(amount: Decimal, wire: str):
    field = _correction_amount()
    assert render_fixed_width_export_field(field, amount) == wire
    assert parse_fixed_width_export_field(field, wire) == amount


@pytest.mark.parametrize(
    ("amount", "wire"),
    [
        (Decimal("-15.37"), "-0000000000001537"),
        (Decimal("-0.01"), "-0000000000000001"),
        (Decimal("-99999999999999.99"), "-" + "9" * 16),
    ],
)
def test_a_negative_m369_correction_writes_the_minus_in_place_of_the_leading_digit(amount: Decimal, wire: str):
    """DR369 note 4 prints -15,37 as -0000000000001537."""
    field = _correction_amount()
    assert render_fixed_width_export_field(field, amount) == wire
    assert parse_fixed_width_export_field(field, wire) == amount


def test_a_positive_m369_correction_may_fill_the_slot_a_negative_could_not():
    field = _correction_amount()
    assert render_fixed_width_export_field(field, Decimal("999999999999999.99")) == "9" * 17
    with pytest.raises(RegistryValidationError):
        render_fixed_width_export_field(field, Decimal("-999999999999999.99"))


@pytest.mark.parametrize("wire", ["N0000000000001537", "0000000000000-153", "--000000000001537"])
def test_any_other_mark_in_an_m369_correction_refuses(wire: str):
    with pytest.raises(RegistryValidationError):
        parse_fixed_width_export_field(_correction_amount(), wire)


def test_m369_blank_rule_does_not_supply_missing_required_amount():
    field = _correction_amount().model_copy(update={"required": True})
    with pytest.raises(RegistryValidationError, match="required export field"):
        render_fixed_width_export_field(field, None)
    with pytest.raises(RegistryValidationError):
        parse_fixed_width_export_field(field, " " * 17)


def test_a_numeric_slot_declaring_no_absent_fill_keeps_its_zero_padding():
    field = _correction_amount().model_copy(update={"absent_fill": None})
    assert render_fixed_width_export_field(field, None) == "0" * 17
