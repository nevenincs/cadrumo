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
from typing import Any

import pytest
from pydantic import ValidationError

from .....core import BindingSourceKind
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path
from .._binding_selector_utils import (
    BindingFixedExportSelector,
    BindingRowExportSelector,
    binding_export_selector,
)
from .._export import (
    _export_fields_overlap,
    _justification_for_binding_data_type,
    _padding_for_binding_data_type,
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


def _binding(
    selector: dict[str, Any],
    *,
    source: BindingSourceKind = BindingSourceKind.MANUAL_INPUT,
    aggregation: BindingAggregation | None = None,
) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "binding-under-test",
            "source": source,
            "selector": selector,
            "aggregation": aggregation,
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
# binding_export_selector
# ---------------------------------------------------------------------------


def test_binding_export_selector_accepts_fixed_field_shape() -> None:
    binding = _binding(
        {
            "record": "DPA",
            "field": "ingresos-integros",
            "offset": 42,
            "length": 10,
            "data_type": "money",
        },
    )

    selector = binding_export_selector(binding)

    assert isinstance(selector, BindingFixedExportSelector)
    assert selector.record == "DPA"
    assert selector.field == "ingresos-integros"
    assert selector.offset == 42
    assert selector.length == 10
    assert selector.data_type == "money"


def test_binding_export_selector_accepts_row_field_shape() -> None:
    binding = _binding(
        {
            "record": "perceptor",
            "row_field": "retencion_practicada",
            "fact": "row_field",
            "grouping": "per_perceptor",
        },
        source=BindingSourceKind.WITHHOLDING,
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    selector = binding_export_selector(binding)

    assert isinstance(selector, BindingRowExportSelector)
    assert selector.record == "perceptor"
    assert selector.row_field == "retencion_practicada"


def test_binding_export_selector_ignores_non_export_row_fact_without_record() -> None:
    binding = _binding(
        {
            "row_field": "retencion_practicada",
            "fact": "row_field",
            "grouping": "per_perceptor",
        },
        source=BindingSourceKind.WITHHOLDING,
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    assert binding_export_selector(binding) is None


def test_binding_export_selector_ignores_value_data_type_without_record() -> None:
    binding = _binding({"casilla_id": "0168", "data_type": "boolean", "true_value": "N", "false_value": "S"})

    assert binding_export_selector(binding) is None


def test_binding_export_selector_rejects_partial_fixed_field_shape() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": 42, "data_type": "money"})


def test_binding_export_selector_rejects_ambiguous_fixed_and_row_shape() -> None:
    with pytest.raises(ValidationError):
        _binding(
            {
                "record": "DPA",
                "row_field": "importe",
                "offset": 42,
                "length": 10,
                "data_type": "money",
            },
        )


def test_binding_export_selector_rejects_unknown_data_type() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": 42, "length": 10, "data_type": "weird"})


def test_binding_export_selector_rejects_non_integer_offset() -> None:
    with pytest.raises(ValidationError):
        _binding({"record": "DPA", "offset": ("1", "2"), "length": 10, "data_type": "money"})


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
