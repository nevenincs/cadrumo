"""A ``decimal`` export slot carries implicit decimals, never a decimal point.

The fixed-width writer dispatched on ``data_type`` for money, integer and
boolean and fell through to ``str(value)`` for everything else, so a decimal
casilla wrote a literal ``.`` into its slot: a unit count rendered
``'1234.56'`` instead of its implicit-decimal form. Where the dotted string
exceeded the slot the export refused loudly; the dangerous case is the slot
wide enough to swallow the dot silently, behind a valid digest.

The contract under test is modelo-agnostic -- a ``decimal`` slot renders at its
own declared scale and never emits a separator, and the registry refuses a
decimal field that omits that scale -- so it is exercised against a modelo that
still ships export layouts. Modelo 303 régimen simplificado (página DP30302) is
used because its decimal slots span several different scales, which is what
makes the per-field scale visible rather than assumed.

Grounding, and the reason these expectations are not tautological: every
expected string below is transcribed from the bundled 2025 Diseño de Registro
for Modelo 303 (``aeat-dr-303-2025``), not computed from the writer. The diseño
sizes each slot as "N enteros y M decimales" summing to the FULL length, which
is precisely what leaves no byte for a separator:

* ``modelo_303`` página DP30302 campo 8, posición 32, longitud 6 --
  "Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales -
  Actividad 1 - Índice de cuota", contenido "1 entero y 5 decimales".
* ``modelo_303`` página DP30302 campo 10, posición 55, longitud 5 --
  "... Actividad 1 - 1T/2T/3T - Porcentaje ingreso a cuenta", contenido
  "3 enteros y 2 decimales".
* ``modelo_303`` página DP30302 campo 24, posición 214, longitud 10 --
  "Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 -
  Módulo 1 - Nº Unidades", contenido "8 enteros y 2 decimales".
* ``modelo_303`` página DP30302 campo 40, posición 437, longitud 3 --
  "... Actividad 1 - 1T/2T/3T - Indice corrector activ. de temporada [Z]",
  contenido "1 entero y 2 decimales".

The scale therefore cannot be inferred from the slot width -- this page pairs
width 6 with 5 decimals and width 5 with only 2 -- which is why the registry
declares it per field and the writer refuses a decimal field that omits it.

Real-behaviour: the shipped export field definitions loaded through the real
registry authority, rendered by the real writer and read back by the real
parser. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.fixed_width_codec import parse_fixed_width_export_field
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ..export import _format_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_FILING_YEAR = 2025
_PERIOD = "4T"

#: Régimen simplificado slots, addressed by the diseño geometry quoted above.
_INDICE_DE_CUOTA = "m303-2025.dp30302.f008"  # longitud 6, "1 entero y 5 decimales"
_PORCENTAJE_INGRESO_A_CUENTA = "m303-2025.dp30302.f010"  # longitud 5, "3 enteros y 2 decimales"
_NUMERO_UNIDADES = "m303-2025.dp30302.f024"  # longitud 10, "8 enteros y 2 decimales"
_INDICE_CORRECTOR_TEMPORADA = "m303-2025.dp30302.f040"  # longitud 3, "1 entero y 2 decimales"


@cache
def _shipped_export_fields() -> dict[str, ExportFieldDefinition]:
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    assert snapshot.revision.export_layouts, (
        f"modelo {_MODELO} revision {snapshot.revision.id} ships no export layout, "
        "so it cannot ground an export-slot rendering contract"
    )
    fields: dict[str, ExportFieldDefinition] = {}
    for layout in snapshot.revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                fields[field.id] = field
    return fields


def _field(field_id: str) -> ExportFieldDefinition:
    fields = _shipped_export_fields()
    assert field_id in fields, f"{field_id} is no longer a shipped Modelo {_MODELO} export field"
    return fields[field_id]


@pytest.mark.parametrize(
    ("field_id", "expected_length", "expected_decimals"),
    [
        (_INDICE_DE_CUOTA, 6, 5),
        (_PORCENTAJE_INGRESO_A_CUENTA, 5, 2),
        (_NUMERO_UNIDADES, 10, 2),
        (_INDICE_CORRECTOR_TEMPORADA, 3, 2),
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


def test_width_10_unit_count_slot_carries_no_decimal_point() -> None:
    """Campo 24, "8 enteros y 2 decimales" in a 10-byte slot.

    Reds against the ``str(value)`` fallthrough, which wrote a dot inside the
    slot and only 6 digits of the 10 the diseño specifies.
    """
    field = _field(_NUMERO_UNIDADES)

    rendered = _format_field(field, Decimal("1234.56"))

    assert rendered == "0000123456"
    assert len(rendered) == 10
    assert "." not in rendered
    assert rendered.isdigit()


def test_width_10_slot_scales_a_fractional_unit_count() -> None:
    """A half-unit módulo is 8 integer digits plus 2 decimal digits, not ``'12.5'``."""
    field = _field(_NUMERO_UNIDADES)

    rendered = _format_field(field, Decimal("12.5"))

    assert rendered == "0000001250"
    assert "." not in rendered


def test_width_5_percentage_slot_renders_at_its_declared_scale() -> None:
    """Campo 10, "3 enteros y 2 decimales": 2 % is written ``'00200'``, not ``'00002'``."""
    field = _field(_PORCENTAJE_INGRESO_A_CUENTA)

    rendered = _format_field(field, Decimal("2"))

    assert rendered == "00200"
    assert len(rendered) == 5
    assert "." not in rendered


def test_width_6_index_slot_uses_its_own_five_decimal_scale() -> None:
    """ "1 entero y 5 decimales": the scale is the field's, not money's fixed two.

    This is the case that proves the scale is per-field. The índice de cuota is
    a 6-byte slot holding one integer digit and five decimals, so rendering it
    at money's fixed two decimals writes ``'000100'`` -- a value AEAT reads
    back as 0,00100 instead of 1,00000.
    """
    field = _field(_INDICE_DE_CUOTA)

    rendered = _format_field(field, Decimal("1"))

    assert rendered == "100000"
    assert rendered != "000100", "rendered at money's two decimals instead of the field's five"
    assert len(rendered) == 6


def test_two_slots_of_different_width_and_scale_disagree_on_the_same_value() -> None:
    """The same value renders differently per slot, so scale cannot come from width.

    Width 6 carries 5 decimals while width 5 carries 2. If the writer derived
    the scale from the slot width -- or applied one fixed scale everywhere --
    these two renderings could not both be right.
    """
    indice = _format_field(_field(_INDICE_DE_CUOTA), Decimal("1"))
    porcentaje = _format_field(_field(_PORCENTAJE_INGRESO_A_CUENTA), Decimal("1"))

    assert indice == "100000"
    assert porcentaje == "00100"


@pytest.mark.parametrize(
    ("field_id", "value"),
    [
        (_NUMERO_UNIDADES, Decimal("1234.56")),
        (_PORCENTAJE_INGRESO_A_CUENTA, Decimal("2")),
        (_INDICE_DE_CUOTA, Decimal("0.16")),
        (_INDICE_CORRECTOR_TEMPORADA, Decimal("1.15")),
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
        field for field in _shipped_export_fields().values() if field.data_type == "decimal" and field.kind != "filler"
    ]

    assert decimal_fields, f"modelo {_MODELO} no longer ships decimal export fields"
    for field in decimal_fields:
        assert field.decimals is not None, f"{field.id} declares no decimals"
        assert field.length is not None
        assert field.decimals < field.length, f"{field.id} leaves no integer digits"


def test_registry_refuses_a_decimal_field_that_omits_its_scale() -> None:
    """The refusal is at registry build, so an unscaled slot can never be written.

    Constructed rather than derived from a shipped field: the invariant belongs
    to :class:`ExportFieldDefinition` itself, so it must hold for ANY decimal
    field and must not depend on some modelo happening to ship one.
    """
    payload: dict[str, object] = {
        "id": "unscaled-decimal-slot",
        "offset": 1,
        "length": 6,
        "kind": "casilla",
        "casilla_id": "01",
        "data_type": "decimal",
        "required": False,
        "padding": "left_zero",
        "justification": "right",
        "signed": False,
        "legal_refs": ("ley-37-1992:art-122",),
        "source_refs": ("aeat-dr-303-2025",),
    }

    # Declaring the scale is what makes the slot valid ...
    scaled = ExportFieldDefinition.model_validate({**payload, "decimals": 2})
    assert scaled.decimals == 2

    # ... and omitting it is refused. The validator raises
    # RegistryValidationError; pydantic surfaces it wrapped.
    with pytest.raises(ValidationError, match="must declare decimals"):
        ExportFieldDefinition.model_validate(payload)
