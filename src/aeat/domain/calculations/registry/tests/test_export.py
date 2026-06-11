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

from decimal import Decimal
from typing import Any

import pytest

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
