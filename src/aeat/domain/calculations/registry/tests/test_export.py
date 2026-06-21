"""Focused unit tests for the pure helpers in _export.

`_export` resolves export layouts (fixed-width BOE-record fields) from
the registry. The public ``resolve_export_layout`` surface is covered
indirectly through the per-modelo registry tests (Modelo 100, 349,
record-design suite), but the small pure helpers underneath had no
direct unit-test coverage. A regression in (for example) interval-
overlap detection or numeric-padding dispatch would silently corrupt
every emitted export payload.

Tests here are structural / contract assertions on the helpers, not
calculation tautologies.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from typing import Any

import pytest

from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._export import (
    _binding_data_type,
    _export_fields_overlap,
    _justification_for_binding_data_type,
    _padding_for_binding_data_type,
    _selector_int,
)
from .._schema import DataBindingDefinition, ExportFieldDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


#: Minimum byte width of fixed-width header values that have a known length, so a
#: copy-paste of the header_key onto a too-short field cannot silently truncate /
#: overflow the emitted fichero. ``devengo_start_date`` is a ``ddmmaaaa`` date.
_MIN_HEADER_FIELD_WIDTH: dict[str, int] = {
    "devengo_start_date": 8,
    "fecha_inicio_periodo": 8,
    "fecha_fin_periodo": 8,
}


def _walk_header_fields(node: object) -> list[tuple[str, int, str]]:
    """Recursively collect (header_key, length, id) from any nested export-layout dict.

    Export-layout TOML nests differently across modelos (``export_layouts`` is a
    single table for some, an array of tables for others), so a recursive walk over
    dicts/lists is the robust way to reach every field record.
    """
    found: list[tuple[str, int, str]] = []
    if isinstance(node, dict):
        header_key = node.get("header_key")
        length = node.get("length")
        if isinstance(header_key, str) and isinstance(length, int):
            found.append((header_key, length, str(node.get("id", "?"))))
        for value in node.values():
            found.extend(_walk_header_fields(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk_header_fields(value))
    return found


def _walk_export_layout_fields() -> list[tuple[str, str, str, int]]:
    """Yield (file, field_id, header_key, length) for every export-layout header field."""
    registry_root = bundled_path("registry", "aeat")
    rows: list[tuple[str, str, str, int]] = []
    for toml_path in registry_root.glob("modelos/*/revisions/*/export*/*.toml"):
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        for header_key, length, field_id in _walk_header_fields(data):
            rows.append((toml_path.name, field_id, header_key, length))
    return rows


def test_no_fixed_width_header_field_is_too_short_for_its_value() -> None:
    """A header field must be wide enough for the fixed-width value it carries.

    Regression for the M202 export-blocking defect: several length-1
    "datos adicionales" indicator fields were copy-paste mis-keyed to
    ``header_key = "devengo_start_date"`` (an 8-char ``ddmmaaaa`` date), so
    ``encode`` raised "value exceeds length 1" and the IS pago fraccionado could
    not be exported at all. This scans every export-layout TOML and fails if any
    field carries a known fixed-width header value in a field too short to hold it.
    """
    offenders = [
        f"{file}:{field_id} header_key={header_key!r} length={length} < {_MIN_HEADER_FIELD_WIDTH[header_key]}"
        for file, field_id, header_key, length in _walk_export_layout_fields()
        if header_key in _MIN_HEADER_FIELD_WIDTH and length < _MIN_HEADER_FIELD_WIDTH[header_key]
    ]
    assert not offenders, "Fixed-width header value mapped to a too-short export field:\n  " + "\n  ".join(offenders)


def _field(
    *,
    field_id: str = "test.field",
    offset: int | None,
    length: int | None,
) -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": offset,
            "length": length,
            "kind": "literal",
            "literal": "x",
            "data_type": "text",
            "required": False,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


def _binding(selector: dict[str, Any]) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "binding-under-test",
            "source": "collectible_invoice",
            "selector": selector,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


# ---------------------------------------------------------------------------
# _export_fields_overlap
# ---------------------------------------------------------------------------


def test_export_fields_overlap_returns_false_when_left_offset_is_none() -> None:
    left = _field(field_id="a", offset=None, length=5)
    right = _field(field_id="b", offset=0, length=5)

    assert _export_fields_overlap(left, right) is False


def test_export_fields_overlap_returns_false_when_left_length_is_none() -> None:
    left = _field(field_id="a", offset=0, length=None)
    right = _field(field_id="b", offset=0, length=5)

    assert _export_fields_overlap(left, right) is False


def test_export_fields_overlap_returns_false_when_right_offset_is_none() -> None:
    left = _field(field_id="a", offset=0, length=5)
    right = _field(field_id="b", offset=None, length=5)

    assert _export_fields_overlap(left, right) is False


def test_export_fields_overlap_detects_partial_overlap() -> None:
    """Fields a[0..4] and b[3..7] share positions 3 and 4."""
    left = _field(field_id="a", offset=0, length=5)
    right = _field(field_id="b", offset=3, length=5)

    assert _export_fields_overlap(left, right) is True


def test_export_fields_overlap_detects_full_overlap_when_offsets_match() -> None:
    left = _field(field_id="a", offset=10, length=4)
    right = _field(field_id="b", offset=10, length=4)

    assert _export_fields_overlap(left, right) is True


def test_export_fields_overlap_returns_false_for_adjacent_fields() -> None:
    """a[0..4] ends at position 4; b[5..9] starts at 5 — no shared cell."""
    left = _field(field_id="a", offset=0, length=5)
    right = _field(field_id="b", offset=5, length=5)

    assert _export_fields_overlap(left, right) is False


def test_export_fields_overlap_returns_false_for_separated_fields() -> None:
    left = _field(field_id="a", offset=0, length=5)
    right = _field(field_id="b", offset=20, length=5)

    assert _export_fields_overlap(left, right) is False


# ---------------------------------------------------------------------------
# _selector_int
# ---------------------------------------------------------------------------


def test_selector_int_accepts_int_value() -> None:
    binding = _binding({"offset": 42})

    assert _selector_int(binding, "offset") == 42


def test_selector_int_coerces_decimal_value() -> None:
    binding = _binding({"offset": Decimal("17")})

    assert _selector_int(binding, "offset") == 17


def test_selector_int_raises_when_selector_value_is_tuple() -> None:
    binding = _binding({"offset": ("1", "2")})

    with pytest.raises(RegistryValidationError, match="must be numeric"):
        _selector_int(binding, "offset")


def test_selector_int_raises_when_selector_key_is_absent() -> None:
    binding = _binding({"offset": 5})

    with pytest.raises(RegistryValidationError, match="'length'"):
        _selector_int(binding, "length")


# ---------------------------------------------------------------------------
# _binding_data_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("data_type", ["text", "integer", "decimal", "money", "date", "boolean"])
def test_binding_data_type_accepts_each_allowed_type(data_type: str) -> None:
    binding = _binding({"data_type": data_type})

    assert _binding_data_type(binding, data_type) == data_type


def test_binding_data_type_raises_on_unknown_type_string() -> None:
    binding = _binding({"data_type": "weird"})

    with pytest.raises(RegistryValidationError, match="not exportable"):
        _binding_data_type(binding, "weird")


def test_binding_data_type_raises_when_value_is_not_a_string() -> None:
    binding = _binding({"data_type": "text"})

    with pytest.raises(RegistryValidationError, match="not exportable"):
        _binding_data_type(binding, 42)


# ---------------------------------------------------------------------------
# _padding_for_binding_data_type — numeric → left_zero, others → right_space
# ---------------------------------------------------------------------------


def test_padding_for_binding_data_type_returns_left_zero_for_money() -> None:
    """Numeric fixed-width export fields pad with leading zeros so the
    parser can recover the magnitude unambiguously."""
    assert _padding_for_binding_data_type("money") == "left_zero"


def test_padding_for_binding_data_type_returns_left_zero_for_integer() -> None:
    assert _padding_for_binding_data_type("integer") == "left_zero"


def test_padding_for_binding_data_type_returns_left_zero_for_decimal() -> None:
    assert _padding_for_binding_data_type("decimal") == "left_zero"


def test_padding_for_binding_data_type_returns_right_space_for_text() -> None:
    assert _padding_for_binding_data_type("text") == "right_space"


def test_padding_for_binding_data_type_returns_right_space_for_date() -> None:
    assert _padding_for_binding_data_type("date") == "right_space"


def test_padding_for_binding_data_type_returns_right_space_for_boolean() -> None:
    assert _padding_for_binding_data_type("boolean") == "right_space"


# ---------------------------------------------------------------------------
# _justification_for_binding_data_type — numeric → right, others → left
# ---------------------------------------------------------------------------


def test_justification_for_binding_data_type_returns_right_for_money() -> None:
    assert _justification_for_binding_data_type("money") == "right"


def test_justification_for_binding_data_type_returns_right_for_integer() -> None:
    assert _justification_for_binding_data_type("integer") == "right"


def test_justification_for_binding_data_type_returns_right_for_decimal() -> None:
    assert _justification_for_binding_data_type("decimal") == "right"


def test_justification_for_binding_data_type_returns_left_for_text() -> None:
    assert _justification_for_binding_data_type("text") == "left"


def test_justification_for_binding_data_type_returns_left_for_date() -> None:
    assert _justification_for_binding_data_type("date") == "left"


def test_justification_for_binding_data_type_returns_left_for_boolean() -> None:
    assert _justification_for_binding_data_type("boolean") == "left"
