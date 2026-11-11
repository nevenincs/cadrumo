"""The filing renderer projects declared scheme-period parts without fake draft objects."""

from __future__ import annotations

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.export_scheme_period import contradicts_scheme_period, scheme_period_value
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..record_field_renderer import format_field

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

    rendered = {part: format_field(field, scheme_period_value(field, period)) for part, field in fields.items()}

    assert rendered == {"filing_year": "2026", "period_type": "T", "quarter_ordinal": ordinal}


@pytest.mark.parametrize(("quarter", "ordinal"), [("1T", "01"), ("2T", "02"), ("3T", "03"), ("4T", "04")])
def test_each_union_quarter_prints_type_t_and_its_ordinal(quarter: str, ordinal: str) -> None:
    fields = _period_fields("esquema-union", quarter)
    period = Period.from_year_and_code(2026, quarter)
    rendered = {part: format_field(field, scheme_period_value(field, period)) for part, field in fields.items()}
    assert rendered == {"filing_year": "2026", "period_type": "T", "quarter_ordinal": ordinal}


@pytest.mark.parametrize(("month", "ordinal"), [("01", "01"), ("09", "09"), ("12", "12")])
def test_each_import_month_prints_type_m_and_its_ordinal(month: str, ordinal: str) -> None:
    fields = _period_fields("esquema-importacion", month)
    period = Period.from_year_and_code(2026, month)
    rendered = {part: format_field(field, scheme_period_value(field, period)) for part, field in fields.items()}
    assert rendered == {"filing_year": "2026", "period_type": "M", "month_ordinal": ordinal}


def test_a_row_of_another_cadence_answers_nothing_and_keeps_its_required_refusal() -> None:
    field = _period_fields("esquema-importacion", "01")["month_ordinal"]
    assert scheme_period_value(field, Period.from_year_and_code(2026, "1T")) is None


@pytest.mark.parametrize(
    ("entered", "contradicts"), [("3", False), ("03", False), ("3.00", False), ("4", True), (None, False), ("", False)]
)
def test_an_entered_period_is_compared_by_value_with_the_filed_one(entered: str | None, contradicts: bool) -> None:
    field = _period_fields("esquema-importacion", "03")["month_ordinal"]
    assert contradicts_scheme_period(field, Period.from_year_and_code(2026, "03"), entered) is contradicts


def test_an_entered_period_type_of_another_cadence_contradicts() -> None:
    field = _period_fields("esquema-union", "1T")["period_type"]
    assert contradicts_scheme_period(field, Period.from_year_and_code(2026, "1T"), "M") is True
