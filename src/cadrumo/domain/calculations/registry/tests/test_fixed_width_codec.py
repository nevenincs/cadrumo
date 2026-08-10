"""Focused contract tests for canonical fixed-width coercion and shape."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.decimal import coerce_fixed_width_decimal
from .. import (
    ExportEncoding,
    ExportFieldDefinition,
    ExportJustification,
    ExportPadding,
    ExportRecordDefinition,
    RegistryValidationError,
    parse_fixed_width_export_field,
    render_fixed_width_export_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(**overrides: object) -> ExportFieldDefinition:
    payload: dict[str, object] = {
        "id": "fixed-width-field",
        "offset": 1,
        "length": 5,
        "kind": "casilla",
        "casilla_id": "01",
        "data_type": "integer",
        "required": False,
        "padding": "left_zero",
        "justification": "right",
        "signed": False,
        "legal_refs": ("ley-27-2014:art-40",),
        "source_refs": ("aeat-dr-200-2025",),
    }
    payload.update(overrides)
    return ExportFieldDefinition.model_validate(payload)


@pytest.mark.parametrize("value", (" 1", "1 ", "+1", "1e2", "NaN", "Infinity", True, 1.0))
def test_fixed_width_decimal_coercion_refuses_noncanonical_or_lossy_values(value: object) -> None:
    with pytest.raises(ValueError):
        coerce_fixed_width_decimal(value)


def test_fixed_width_decimal_coercion_accepts_exact_finite_values() -> None:
    assert coerce_fixed_width_decimal(7) == Decimal(7)
    assert coerce_fixed_width_decimal(Decimal("7.50")) == Decimal("7.50")
    assert coerce_fixed_width_decimal("7.50") == Decimal("7.50")


def test_integer_refuses_fractional_decimal_without_truncation() -> None:
    with pytest.raises(RegistryValidationError, match="fractional"):
        render_fixed_width_export_field(_field(), Decimal("7.5"))


@pytest.mark.parametrize(
    ("padding", "justification"),
    (
        ("left_zero", "left"),
        ("left_space", "left"),
        ("right_space", "right"),
        ("none", "left"),
    ),
)
def test_schema_refuses_contradictory_padding_and_justification(padding: str, justification: str) -> None:
    with pytest.raises(ValidationError, match="requires"):
        _field(padding=padding, justification=justification)


def test_padding_and_justification_are_hydrated_as_the_public_closed_axes() -> None:
    field = _field()

    assert field.padding is ExportPadding.LEFT_ZERO
    assert field.justification is ExportJustification.RIGHT


def test_record_encoding_is_the_public_closed_axis_and_refuses_unknown_codecs() -> None:
    record = ExportRecordDefinition(
        id="encoding-proof",
        record_type="1",
        order=0,
        encoding="latin-1",
        line_ending="none",
        fields=(_field(),),
    )
    assert record.encoding is ExportEncoding.LATIN_1

    with pytest.raises(ValidationError, match="encoding"):
        ExportRecordDefinition(
            id="invalid-encoding",
            record_type="1",
            order=0,
            encoding="utf-8",
            line_ending="none",
            fields=(_field(),),
        )


def test_parser_rejects_noncanonical_left_zero_and_accepts_declared_left_space() -> None:
    left_zero = _field()
    left_space = _field(padding="left_space", justification="right")

    with pytest.raises(RegistryValidationError, match="ASCII digits"):
        parse_fixed_width_export_field(left_zero, "   12")
    assert parse_fixed_width_export_field(left_space, "   12") == Decimal(12)
    with pytest.raises(RegistryValidationError, match="noncanonical"):
        parse_fixed_width_export_field(left_space, "00012")


def test_parser_refuses_negative_zero_inline_sign() -> None:
    field = _field(length=5, data_type="money", signed=True)

    with pytest.raises(RegistryValidationError, match="noncanonical"):
        parse_fixed_width_export_field(field, "N0000")


@pytest.mark.parametrize("raw", ("S", "1", "Y"))
def test_ordinary_boolean_wire_refuses_noncanonical_tokens(raw: str) -> None:
    field = _field(length=1, data_type="boolean", padding="right_space", justification="left")

    with pytest.raises(RegistryValidationError, match="canonical X or blank"):
        parse_fixed_width_export_field(field, raw)


@pytest.mark.parametrize(
    "overrides",
    (
        {"signed": True, "length": 1, "data_type": "money"},
        {"signed": True, "data_type": "integer"},
        {"signed": True, "data_type": "decimal", "decimals": 2},
        {"signed": True, "data_type": "money", "padding": "left_space"},
    ),
)
def test_schema_refuses_inconsistent_inline_sign_shapes(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="signed"):
        _field(**overrides)


def test_ordinary_boolean_semantics_are_x_or_blank_not_numeric_checkbox_policy() -> None:
    field = _field(length=1, data_type="boolean", padding="right_space", justification="left")

    assert render_fixed_width_export_field(field, True) == "X"
    assert render_fixed_width_export_field(field, "true") == "X"
    assert render_fixed_width_export_field(field, False) == " "
    assert render_fixed_width_export_field(field, "false") == " "


@pytest.mark.parametrize("invalid", (["X"], {"selected": True}))
def test_boolean_refuses_unhashable_invalid_values_through_the_typed_boundary(invalid: object) -> None:
    field = _field(length=1, data_type="boolean", padding="right_space", justification="left")

    with pytest.raises(RegistryValidationError):
        render_fixed_width_export_field(field, invalid)


@pytest.mark.parametrize("invalid", ([1], {"value": 1}))
def test_numeric_refuses_unhashable_invalid_values_through_the_typed_boundary(invalid: object) -> None:
    with pytest.raises(RegistryValidationError):
        render_fixed_width_export_field(_field(), invalid)
