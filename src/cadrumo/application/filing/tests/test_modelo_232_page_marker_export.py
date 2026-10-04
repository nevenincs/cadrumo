"""Modelo 232's page indicator renders blank on an ordinary filing and refuses what it cannot carry.

DR232 (``aeat-dr-232-2018``) prints campo 5 of both pages, DR23201 and DR23202, at
posición 12, longitud 1, tipo A, ``Indicador de página complementaria``, validación
``Obligatorio``, contenido ``C o blanco``. The position is always written and blank is
one of its two values, so an ordinary page's indicator is a single space and a
complementaria's is ``C``. The published layout once declared the slot required with no
blank, which refused every ordinary export at this byte.

Real-behaviour: the shipped export fields loaded from the published authority, the real
``complementaria_page_marker`` producer over a real producer snapshot, and the real
fixed-width writer. The expected bytes are transcribed from the diseño, never read from
the layout under test. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.filing.errors import FilingExportValidationError
from ..record_field_renderer import complementaria_page_marker, format_field
from .export_support import _approved_registry_draft, _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "232"
_FILING_YEAR = 2025
_PERIOD = "0A"

#: DR232 campo 5 on each page: posición 12, longitud 1.
_PAGE_MARKERS = ("m232-2018.dr23201.f005", "m232-2018.dr23202.f005")
_DR232_POSITION = 12
_DR232_LENGTH = 1


@cache
def _shipped_export_fields() -> dict[str, ExportFieldDefinition]:
    snapshot = published_snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    return {
        field.id: field
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for field in record.fields
    }


def _field(field_id: str) -> ExportFieldDefinition:
    fields = _shipped_export_fields()
    assert field_id in fields, f"{field_id} is no longer a shipped Modelo {_MODELO} export field"
    return fields[field_id]


@pytest.mark.parametrize("field_id", _PAGE_MARKERS)
def test_the_page_marker_sits_at_its_dr232_position_and_admits_blank(field_id: str) -> None:
    field = _field(field_id)

    assert (field.offset, field.length) == (_DR232_POSITION, _DR232_LENGTH)
    assert field.computed_key == "complementaria_page_marker"
    assert field.required is False


@pytest.mark.parametrize("field_id", _PAGE_MARKERS)
def test_an_ordinary_page_renders_its_marker_blank(field_id: str) -> None:
    marker = complementaria_page_marker(_approved_registry_draft(), _typed_producer_snapshot())

    assert marker is None
    assert format_field(_field(field_id), marker) == " "


@pytest.mark.parametrize("field_id", _PAGE_MARKERS)
def test_a_complementaria_page_renders_its_marker_c(field_id: str) -> None:
    marker = complementaria_page_marker(_approved_registry_draft(), _typed_producer_snapshot(complementaria=True))

    assert marker == "C"
    assert format_field(_field(field_id), marker) == "C"


@pytest.mark.parametrize("field_id", _PAGE_MARKERS)
@pytest.mark.parametrize("illegal", ["CC", 1])
def test_a_value_the_one_byte_marker_cannot_carry_is_refused(field_id: str, illegal: object) -> None:
    with pytest.raises(FilingExportValidationError, match=field_id):
        format_field(_field(field_id), illegal)
