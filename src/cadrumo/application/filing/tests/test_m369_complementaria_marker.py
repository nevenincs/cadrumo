"""DR369's mandatory Complementaria byte marks an extra page, never an amended return.

The file description defines it: blank on the single page, ``C`` on a further page
of the same type when a return holds more than 28 elements. Orden HAC/610/2021 art.
7.5 forbids amending a filed return, so no amendment fact may reach this byte.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..record_field_renderer import format_field

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

_SCHEMES = (("esquema-exterior", "EXT-1T"), ("esquema-union", "1T"), ("esquema-importacion", "01"))


def _fields() -> list[ExportFieldDefinition]:
    fields: list[ExportFieldDefinition] = []
    for revision_id, period in _SCHEMES:
        snapshot = published_snapshot(
            "369", filing_year=filing_year_envelope().horizon, period=period, revision_id=revision_id
        )
        fields.extend(
            field
            for layout in snapshot.revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.computed_key == "continuation_page_marker"
        )
    assert len(fields) == 12
    assert all(field.required and field.data_type == "text" and field.length == 1 for field in fields)
    assert all(field.producer_key is None and field.presence_marker == "C" for field in fields)
    return fields


def test_every_m369_page_indicator_is_fed_by_the_page_and_writes_c_or_blank() -> None:
    for field in _fields():
        assert format_field(field, " ") == " "
        assert format_field(field, "C") == "C"
