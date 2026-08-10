"""Focused contract tests for canonical fixed-width coercion and shape."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.decimal import coerce_fixed_width_decimal
from .. import (
    ExportEncoding,
    ExportFieldDefinition,
    ExportJustification,
    ExportPadding,
    ExportRecordDefinition,
    ExportValuePolicy,
    ParsedExportPolicyWireValue,
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


def test_allowed_integer_domain_is_enforced_symmetrically_after_wire_normalization() -> None:
    field = _field(
        length=2,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=("3", "1"),
    )

    assert field.allowed_values == ("1", "3")
    assert render_fixed_width_export_field(field, 1) == "01"
    assert parse_fixed_width_export_field(field, "03") == Decimal(3)
    with pytest.raises(RegistryValidationError, match="outside allowed_values"):
        render_fixed_width_export_field(field, "2")
    with pytest.raises(RegistryValidationError, match="outside allowed_values"):
        parse_fixed_width_export_field(field, "02")


def test_schema_refuses_allowed_values_without_the_enumerated_policy() -> None:
    with pytest.raises(ValidationError, match="requires value_policy"):
        _field(
            length=1,
            allowed_values=("1",),
            value_policy="selected-1-unselected-0",
        )
    with pytest.raises(ValidationError, match="requires value_policy"):
        _field(length=1, allowed_values=("1",))


@pytest.mark.parametrize(
    ("overrides", "value", "wire", "parsed"),
    (
        (
            {"length": 1, "value_policy": ExportValuePolicy.SELECTED_1_UNSELECTED_0},
            True,
            "1",
            Decimal(1),
        ),
        (
            {"length": 2, "value_policy": ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS},
            2026,
            "26",
            ParsedExportPolicyWireValue(
                policy=ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
                raw="26",
            ),
        ),
        ({"length": 2, "value_policy": ExportValuePolicy.UNSIGNED_INTEGER}, 7, "07", Decimal(7)),
        (
            {"length": 5, "data_type": "decimal", "decimals": 2, "value_policy": ExportValuePolicy.IMPLIED_DECIMAL},
            Decimal("12.34"),
            "01234",
            Decimal("12.34"),
        ),
        (
            {
                "length": 1,
                "value_policy": ExportValuePolicy.ENUMERATED_DIGITS,
                "allowed_values": ("1", "3"),
            },
            3,
            "3",
            Decimal(3),
        ),
        (
            {
                "length": 4,
                "data_type": "text",
                "padding": "none",
                "justification": "none",
                "value_policy": ExportValuePolicy.DIGIT_STRING,
            },
            "0123",
            "0123",
            "0123",
        ),
        (
            {
                "length": 13,
                "data_type": "text",
                "padding": "none",
                "justification": "none",
                "value_policy": ExportValuePolicy.IDENTIFIER_DIGITS,
            },
            "0012345678901",
            "0012345678901",
            "0012345678901",
        ),
        ({"length": 4, "value_policy": ExportValuePolicy.FOUR_DIGIT_YEAR}, 2026, "2026", Decimal(2026)),
        ({"length": 2, "value_policy": ExportValuePolicy.TWO_DIGIT_MONTH}, 8, "08", Decimal(8)),
        ({"length": 2, "value_policy": ExportValuePolicy.TWO_DIGIT_DAY}, "9", "09", Decimal(9)),
        (
            {
                "length": 8,
                "data_type": "date",
                "padding": "none",
                "justification": "none",
                "date_format": "aaaammdd",
                "value_policy": ExportValuePolicy.YYYYMMDD,
            },
            "20240229",
            "20240229",
            "20240229",
        ),
    ),
)
def test_complete_reviewed_policy_set_renders_and_parses_exact_wire_bytes(
    overrides: dict[str, object],
    value: object,
    wire: str,
    parsed: object,
) -> None:
    field = _field(**overrides)

    assert render_fixed_width_export_field(field, value) == wire
    actual = parse_fixed_width_export_field(field, wire)
    assert actual == parsed
    assert render_fixed_width_export_field(field, actual) == wire


def test_enumeration_is_the_only_policy_that_can_combine_with_allowed_values() -> None:
    field = _field(
        length=1,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=("1", "3"),
    )
    assert render_fixed_width_export_field(field, 1) == "1"
    with pytest.raises(RegistryValidationError, match="outside allowed_values"):
        render_fixed_width_export_field(field, 2)

    with pytest.raises(ValidationError, match="requires value_policy"):
        _field(
            length=4,
            value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
            allowed_values=("2026",),
        )


@pytest.mark.parametrize(
    ("overrides", "raw"),
    (
        ({"length": 2, "value_policy": ExportValuePolicy.TWO_DIGIT_MONTH}, "13"),
        ({"length": 2, "value_policy": ExportValuePolicy.TWO_DIGIT_DAY}, "00"),
        ({"length": 4, "value_policy": ExportValuePolicy.FOUR_DIGIT_YEAR}, "0999"),
        (
            {
                "length": 8,
                "data_type": "date",
                "padding": "none",
                "justification": "none",
                "date_format": "aaaammdd",
                "value_policy": ExportValuePolicy.YYYYMMDD,
            },
            "20230229",
        ),
        (
            {
                "length": 4,
                "data_type": "text",
                "padding": "none",
                "justification": "none",
                "value_policy": ExportValuePolicy.DIGIT_STRING,
            },
            "12 3",
        ),
    ),
)
def test_policy_wire_mutations_are_refused_before_generic_parsing(
    overrides: dict[str, object],
    raw: str,
) -> None:
    with pytest.raises(RegistryValidationError):
        parse_fixed_width_export_field(_field(**overrides), raw)


@pytest.mark.parametrize(
    "overrides",
    (
        {"length": 2, "data_type": "text", "value_policy": ExportValuePolicy.UNSIGNED_INTEGER},
        {"length": 5, "data_type": "integer", "value_policy": ExportValuePolicy.IMPLIED_DECIMAL},
        {"length": 8, "data_type": "integer", "value_policy": ExportValuePolicy.YYYYMMDD},
        {"length": 4, "value_policy": ExportValuePolicy.DIGIT_STRING},
        {"length": 13, "value_policy": ExportValuePolicy.IDENTIFIER_DIGITS},
        {"length": 3, "value_policy": ExportValuePolicy.FOUR_DIGIT_YEAR},
        {"length": 1, "value_policy": ExportValuePolicy.TWO_DIGIT_MONTH},
        {"length": 3, "value_policy": ExportValuePolicy.TWO_DIGIT_DAY},
        {"length": 1, "value_policy": ExportValuePolicy.ENUMERATED_DIGITS},
    ),
)
def test_schema_refuses_each_policy_on_an_inconsistent_shape(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _field(**overrides)


@pytest.mark.parametrize(
    "allowed_values",
    ((), ("1", "1"), ("",), ("01",), ("+1",), ("１",), ("123456",)),
)
def test_schema_refuses_empty_duplicate_noncanonical_or_out_of_width_allowed_domains(
    allowed_values: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError, match="allowed_values"):
        _field(value_policy=ExportValuePolicy.ENUMERATED_DIGITS, allowed_values=allowed_values)


@pytest.mark.parametrize(
    "overrides",
    (
        {"data_type": "text"},
        {"data_type": "decimal", "decimals": 2},
        {"data_type": "money"},
        {"signed": True, "data_type": "money"},
        {"padding": "left_space"},
        {"kind": "literal", "literal": "1"},
    ),
)
def test_schema_refuses_allowed_domains_on_incompatible_field_shapes(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _field(
            value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
            allowed_values=("1", "3"),
            **overrides,
        )


def test_allowed_values_enforcement_has_one_canonical_codec_owner() -> None:
    production_root = Path("src/cadrumo")
    owners = tuple(
        path
        for path in production_root.rglob("*.py")
        if "tests" not in path.parts
        if "def _require_allowed_value" in path.read_text(encoding="utf-8")
    )

    assert owners == (production_root / "domain/calculations/registry/_fixed_width_codec.py",)
