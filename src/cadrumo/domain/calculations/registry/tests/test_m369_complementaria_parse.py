"""DR369 marker parsing preserves the exact blank-or-C source grammar."""

import pytest

from ..errors import RegistryValidationError
from ..export_parse import parse_field_value
from ..fixed_width_codec import render_fixed_width_export_field
from .authored_editions import filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _marker_fields():
    snapshot = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period="EXT-1T", revision_id="esquema-exterior"
    )
    fields = [
        field
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.computed_key == "continuation_page_marker"
    ]
    assert len(fields) == 3
    assert all(field.required and field.data_type == "text" and field.length == 1 for field in fields)
    return fields


@pytest.mark.parametrize("wire", [" ", "C"])
def test_m369_complementaria_readback_preserves_the_exact_marker(wire: str):
    for field in _marker_fields():
        parsed = parse_field_value(field, wire)
        assert parsed == wire
        assert render_fixed_width_export_field(field, parsed) == wire


@pytest.mark.parametrize("wire", ["X", "S", "0", "1", "c", "", "  ", "\t"])
def test_m369_complementaria_readback_refuses_tokens_outside_the_official_wire_grammar(wire: str):
    for field in _marker_fields():
        with pytest.raises(RegistryValidationError, match="exactly its presence marker or one ASCII space"):
            parse_field_value(field, wire)
