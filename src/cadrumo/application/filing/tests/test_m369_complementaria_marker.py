"""DR369's mandatory Complementaria byte admits C or an ordinary-return blank."""

from __future__ import annotations

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.filing.errors import FilingExportValidationError

from ..record_field_renderer import _header_field_value, format_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _fields():
    snapshot = published_snapshot("369", filing_year=2026, period="EXT-1T", revision_id="esquema-exterior")
    fields = [
        field
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.producer_key is FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA
    ]
    assert len(fields) == 3
    assert all(field.required and field.data_type == "text" and field.length == 1 for field in fields)
    return fields


@pytest.mark.parametrize(("value", "expected"), [(None, " "), (False, " "), (True, "C")])
def test_m369_mandatory_complementaria_slot_renders_ordinary_and_amended_returns(value: bool | None, expected: str):
    for field in _fields():
        rendered = _header_field_value(
            field, {FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: value}, modelo=Modelo("369")
        )
        assert format_field(field, rendered) == expected


@pytest.mark.parametrize("value", [1, "C", "X", "false"])
def test_m369_complementaria_refuses_untyped_amendment_values(value: object):
    for field in _fields():
        with pytest.raises(FilingExportValidationError, match="typed amendment boolean"):
            _header_field_value(field, {FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: value}, modelo=Modelo("369"))


def test_m369_marker_rendering_preserves_other_modelos_required_and_presence_rules():
    [field, *_] = _fields()
    with pytest.raises(FilingExportValidationError, match="is required"):
        _header_field_value(field, {FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: None})
    assert _header_field_value(field, {FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: True}) == "X"


def test_m369_complementaria_refuses_a_missing_producer_fact():
    for field in _fields():
        with pytest.raises(FilingExportValidationError, match="amendment producer fact"):
            _header_field_value(field, {}, modelo=Modelo("369"))
