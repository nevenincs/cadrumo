"""The filing renderer projects declared scheme-period parts without fake draft objects."""

from __future__ import annotations

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..record_field_renderer import _scheme_period_value, format_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period_fields(revision: str, period: str) -> dict[str, ExportFieldDefinition]:
    snapshot = published_snapshot("369", filing_year=2026, period=period, revision_id=revision)
    [layout] = snapshot.revision.export_layouts
    return {
        field.scheme_period_part: field
        for record in layout.records
        for field in record.fields
        if field.scheme_period_part is not None
    }


@pytest.mark.parametrize(("quarter", "ordinal"), [("1T", "01"), ("2T", "02"), ("3T", "03"), ("4T", "04")])
def test_each_exterior_quarter_renders_the_three_official_detail_rows(quarter: str, ordinal: str) -> None:
    fields = _period_fields("esquema-exterior", f"EXT-{quarter}")
    period = Period.from_year_and_code(2026, f"EXT-{quarter}")

    rendered = {part: format_field(field, _scheme_period_value(field, period)) for part, field in fields.items()}

    assert rendered == {"filing_year": "2026", "period_type": "T", "quarter_ordinal": ordinal}


def test_a_declared_row_outside_a_scheme_period_reads_its_bound_value() -> None:
    [field, *_] = _period_fields("esquema-exterior", "EXT-1T").values()
    assert _scheme_period_value(field, Period.from_year_and_code(2026, "1T")) is None
