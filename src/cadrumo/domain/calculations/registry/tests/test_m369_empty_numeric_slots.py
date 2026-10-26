"""DR369 general notes 6-7 distinguish absent numeric slots from declared zero."""

from decimal import Decimal

import pytest

from ..errors import RegistryValidationError
from ..fixed_width_codec import render_fixed_width_export_field
from ..fixed_width_parser import parse_fixed_width_export_field
from ..schema_exports import ExportFieldDefinition
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _correction_amount() -> ExportFieldDefinition:
    snapshot = published_snapshot("369", filing_year=2026, period="EXT-1T", revision_id="esquema-exterior")
    [record] = [
        record for record in snapshot.revision.export_layouts[0].records if record.id == "modelo-369-exterior-t36902"
    ]
    [amount, *_] = [field for field in record.fields if field.data_type == "decimal" and field.decimals == 2]
    assert not amount.required
    assert amount.length == 17
    assert "aeat-dr-369-2021" in amount.source_refs
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


def test_m369_blank_rule_does_not_supply_missing_required_amount():
    field = _correction_amount().model_copy(update={"required": True})
    with pytest.raises(RegistryValidationError, match="required export field"):
        render_fixed_width_export_field(field, None)
    with pytest.raises(RegistryValidationError):
        parse_fixed_width_export_field(field, " " * 17)


def test_m369_blank_rule_requires_its_canonical_source_reference():
    field = _correction_amount().model_copy(update={"source_refs": ("aeat-dr-200-2025",)})
    assert render_fixed_width_export_field(field, None) == "0" * 17
