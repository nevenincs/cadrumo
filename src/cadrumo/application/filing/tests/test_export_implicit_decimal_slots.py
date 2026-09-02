"""A ``decimal`` export slot carries implicit decimals, never a decimal point.

The fixed-width writer dispatched on ``data_type`` for money, integer and
boolean and fell through to ``str(value)`` for everything else, so a decimal
casilla wrote a literal ``.`` into its slot: casilla 00041 rendered
``'000001234.56'``. Where the dotted string exceeded the slot the export refused
loudly, but Modelo 200 has 51 decimal slots wide enough to swallow the dot
silently, behind a valid digest.

Grounding, and the reason these expectations are not tautological: every
expected string below is transcribed from the bundled 2025 Diseño de Registro
for the modelo under test, not computed from the writer. The diseño sizes each
slot as "N enteros y M decimales" summing to the FULL length, which is what
leaves no byte for a separator:

* ``modelo_200`` página DP200001B campo 20, posición 162, longitud 9 --
  "Personal asalariado (cifra media del ejercicio) Personal fijo [00041]",
  contenido "7enteros 2 decimales".
* ``modelo_200`` página DP200014B, longitud 4, Nota 1 -- "En caso de tipo de
  gravamen único se rellenarán los dos primeros dígitos con el tipo, y los dos
  últimos con 00. Ej: 25% se rellenará como 2500." AEAT prints the expected
  output for this one, so the width-4 expectation is quoted, not derived.
* ``modelo_200`` página DP200015B, longitud 7 -- "Tipo de gravamen 2025
  [00103]", contenido "3 enteros y 4 decimales". This is the case that proves
  the scale is per-field: rendering it at money's fixed two decimals writes
  ``'0002500'`` where AEAT expects ``'0250000'``.

The scale therefore cannot be inferred from the slot width -- Modelo 200 pairs
width 9 with 2 decimals and width 7 with 4 -- which is why the registry declares
it per field and the writer refuses a decimal field that omits it.

Real-behaviour: the shipped export field definitions loaded through the real
registry authority, rendered by the real writer and read back by the real
parser. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.fixed_width_codec import parse_fixed_width_export_field
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ..export import _format_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _modelo_200_export_fields() -> dict[str, ExportFieldDefinition]:
    snapshot = bundled_authority().snapshot(Modelo.M200, filing_year=2025, period="0A")
    fields: dict[str, ExportFieldDefinition] = {}
    for layout in snapshot.revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                fields[field.id] = field
    return fields


def _field(field_id: str) -> ExportFieldDefinition:
    fields = _modelo_200_export_fields()
    assert field_id in fields, f"{field_id} is no longer a shipped Modelo 200 export field"
    return fields[field_id]


@pytest.mark.parametrize(
    ("field_id", "expected_length", "expected_decimals"),
    [
        ("modelo-200-page-001b-casilla-00041", 9, 2),
        ("modelo-200-page-001b-casilla-00042", 9, 2),
        ("modelo-200-page-015b-casilla-00105", 4, 2),
        ("modelo-200-page-015b-casilla-00103", 7, 4),
    ],
)
def test_shipped_slot_geometry_matches_the_diseno(
    field_id: str,
    expected_length: int,
    expected_decimals: int,
) -> None:
    """The shipped layout still declares the geometry the expectations below assume.

    Without this anchor a renumbering or a width change would leave the
    rendering assertions passing against a slot they no longer describe.
    """
    field = _field(field_id)
    assert field.data_type == "decimal"
    assert field.length == expected_length
    assert field.decimals == expected_decimals


def test_width_9_headcount_slot_carries_no_decimal_point() -> None:
    """Casilla 00041, "7enteros 2 decimales" in a 9-byte slot.

    Reds against the ``str(value)`` fallthrough, which wrote ``'000001234.56'``:
    a dot inside the slot, and only 8 digits of the 9 the diseño specifies.
    """
    field = _field("modelo-200-page-001b-casilla-00041")

    rendered = _format_field(field, Decimal("1234.56"))

    assert rendered == "000123456"
    assert len(rendered) == 9
    assert "." not in rendered
    assert rendered.isdigit()


def test_width_9_slot_scales_a_fractional_headcount() -> None:
    """A half-count is 7 integer digits plus 2 decimal digits, not ``'12.5'``."""
    field = _field("modelo-200-page-001b-casilla-00041")

    rendered = _format_field(field, Decimal("12.5"))

    assert rendered == "000001250"
    assert "." not in rendered


def test_width_4_rate_slot_matches_the_aeat_worked_example() -> None:
    """AEAT's own Nota 1: "25% se rellenará como 2500".

    Reds against the fallthrough, which wrote ``'0025'`` -- a value AEAT reads
    back as 0,25 %.
    """
    field = _field("modelo-200-page-015b-casilla-00105")

    rendered = _format_field(field, Decimal("25"))

    assert rendered == "2500"
    assert len(rendered) == 4
    assert "." not in rendered


def test_width_7_rate_slot_uses_its_own_four_decimal_scale() -> None:
    """ "3 enteros y 4 decimales": the scale is the field's, not money's fixed two."""
    field = _field("modelo-200-page-015b-casilla-00103")

    rendered = _format_field(field, Decimal("25"))

    assert rendered == "0250000"
    assert rendered != "0002500", "rendered at money's two decimals instead of the field's four"
    assert len(rendered) == 7


@pytest.mark.parametrize(
    ("field_id", "value"),
    [
        ("modelo-200-page-001b-casilla-00041", Decimal("1234.56")),
        ("modelo-200-page-015b-casilla-00105", Decimal("25")),
        ("modelo-200-page-015b-casilla-00103", Decimal("25")),
    ],
)
def test_implicit_decimal_slots_survive_a_write_read_cycle(field_id: str, value: Decimal) -> None:
    """The parser restores the point by shifting at the declared scale."""
    field = _field(field_id)

    rendered = _format_field(field, value)

    assert parse_fixed_width_export_field(field, rendered) == value


def test_every_shipped_decimal_slot_declares_its_scale() -> None:
    """A decimal slot with no declared scale cannot be rendered at all."""
    decimal_fields = [
        field
        for field in _modelo_200_export_fields().values()
        if field.data_type == "decimal" and field.kind != "filler"
    ]

    assert decimal_fields, "Modelo 200 no longer ships decimal export fields"
    for field in decimal_fields:
        assert field.decimals is not None, f"{field.id} declares no decimals"
        assert field.length is not None
        assert field.decimals < field.length, f"{field.id} leaves no integer digits"


def test_registry_refuses_a_decimal_field_that_omits_its_scale() -> None:
    """The refusal is at registry build, so an unscaled slot can never be written."""
    template = _field("modelo-200-page-001b-casilla-00041")
    payload = template.model_dump()
    payload.pop("decimals")

    # The validator raises RegistryValidationError; pydantic surfaces it wrapped.
    with pytest.raises(ValidationError, match="must declare decimals"):
        ExportFieldDefinition.model_validate(payload)
