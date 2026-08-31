"""Focused contract tests for canonical fixed-width coercion and shape."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.decimal.fixed_width import coerce_fixed_width_decimal
from .....core.directory_scan import scan_directory
from ..errors import RegistryValidationError
from ..export_value_policy import ExportValuePolicy, ParsedExportPolicyWireValue
from ..fixed_width_codec import (
    ExportEncoding,
    ExportJustification,
    ExportPadding,
    FixedWidthRecordRenderError,
    parse_fixed_width_export_field,
    render_fixed_width_export_field,
    render_fixed_width_export_record_body,
)
from ..schema_exports import ExportFieldDefinition, ExportRecordDefinition

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
        (
            {
                "length": 8,
                "data_type": "date",
                "padding": "none",
                "justification": "none",
                "date_format": "ddmmaaaa",
                "value_policy": ExportValuePolicy.DDMMYYYY,
            },
            "29022024",
            "29022024",
            "29022024",
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
                "length": 8,
                "data_type": "date",
                "padding": "none",
                "justification": "none",
                "date_format": "ddmmaaaa",
                "value_policy": ExportValuePolicy.DDMMYYYY,
            },
            "29022023",
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
        {"length": 8, "data_type": "integer", "value_policy": ExportValuePolicy.DDMMYYYY},
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


@pytest.mark.parametrize("absent", (None, ""))
@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({"data_type": "integer"}, "00000"),
        ({"data_type": "decimal", "decimals": 2}, "00000"),
        ({"data_type": "money"}, "00000"),
    ),
)
def test_optional_numeric_slot_absent_renders_its_declared_blank_fill(
    overrides: dict[str, object],
    expected: str,
    absent: object,
) -> None:
    """An optional numeric casilla the taxpayer lacks occupies its slot as zeros.

    Grounded in the AEAT record designs bundled under
    ``_data/corpus/aeat_official/disenos_registro``: "los campos numéricos que no
    tengan contenido se rellenarán a ceros". The expected wire is the declared
    ``left_zero`` padding across the declared width, not a value invented here.
    """
    field = _field(required=False, **overrides)

    assert render_fixed_width_export_field(field, absent) == expected


@pytest.mark.parametrize("absent", (None, ""))
def test_optional_text_slot_absent_renders_its_declared_blank_fill(absent: object) -> None:
    """Optional identifier text still occupies its official fixed-width slot.

    The identifier policy validates an actual activity identifier. It does not
    invent one where the source authority has none, so an optional absent value
    renders as the schema's two blank bytes rather than reaching that policy.
    """
    field = _field(
        data_type="text",
        length=2,
        padding="none",
        justification="none",
        required=False,
        value_policy=ExportValuePolicy.IDENTIFIER_DIGITS,
    )

    assert render_fixed_width_export_field(field, absent) == "  "


@pytest.mark.parametrize("absent", (None, ""))
@pytest.mark.parametrize(
    "overrides",
    (
        {"data_type": "integer"},
        {"data_type": "decimal", "decimals": 2},
        {"data_type": "money"},
        {"data_type": "money", "signed": True},
    ),
)
def test_required_numeric_slot_absent_still_refuses(overrides: dict[str, object], absent: object) -> None:
    """A required numeric casilla has no blank representation and must refuse.

    This is the anti-weakening half of the optional-slot contract above: were an
    omitted mandatory figure to render as zeros, a filing would silently
    under-declare behind a valid digest. Modelo 180's declarante retenciones
    total and Modelo 145's perceptor birth year are declared ``required = true``
    precisely so this path refuses.
    """
    field = _field(required=True, **overrides)

    with pytest.raises(RegistryValidationError, match="has no value to render"):
        render_fixed_width_export_field(field, absent)


@pytest.mark.parametrize("absent", (None, ""))
def test_required_text_slot_absent_still_refuses(absent: object) -> None:
    """Blank padding remains an optional-slot representation, never a default."""
    field = _field(
        data_type="text",
        length=2,
        padding="none",
        justification="none",
        required=True,
        value_policy=ExportValuePolicy.IDENTIFIER_DIGITS,
    )

    with pytest.raises(RegistryValidationError, match="has no value to render"):
        render_fixed_width_export_field(field, absent)


def test_absent_optional_signed_numeric_keeps_its_sign_marker_slot() -> None:
    """A signed field's leading marker byte is never consumed by the zero fill."""
    field = _field(data_type="money", signed=True, required=False, length=17)

    rendered = render_fixed_width_export_field(field, None)

    assert rendered == " " + "0" * 16
    assert parse_fixed_width_export_field(field, rendered) == Decimal(0)


def test_absent_optional_numeric_slot_parses_back_as_its_declared_zero() -> None:
    """The blank fill is canonical wire, so the codec round-trips it."""
    field = _field(data_type="integer", required=False)

    rendered = render_fixed_width_export_field(field, None)

    assert parse_fixed_width_export_field(field, rendered) == Decimal(0)


def _absence_record(*, required: bool) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id="absent-optional-numeric-record",
        record_type="1",
        order=0,
        encoding="iso-8859-1",
        line_ending="none",
        fields=(
            _field(id="present-year", offset=1, length=4, casilla_id="01", required=True),
            _field(id="absent-year", offset=5, length=4, casilla_id="02", required=required),
        ),
    )


def test_record_renders_when_an_optional_numeric_casilla_is_absent() -> None:
    """One unfilled optional numeric slot must not refuse the whole record.

    The refusal is raised per record, so before this contract held, a taxpayer
    with no descendants could not export a Modelo 145 communication at all.
    """
    body = render_fixed_width_export_record_body(
        _absence_record(required=False),
        field_values={"01": "2010"},
    )

    assert body == b"20100000"


def test_record_refuses_when_a_required_numeric_casilla_is_absent() -> None:
    """The same absent slot on a required field still refuses the record.

    The refusal carries its registered identity and machine facts, never an
    authored sentence. Asserting the key and the context alone would stay green
    against re-introduced English, because message resolution prefers the key
    while ``str(exc)`` prefers a positional argument and would still carry the
    prose into tracebacks and logs; pinning ``str(exc)`` to the key is what
    makes a re-introduced sentence at any of these raise sites fail.
    """
    from .....core.errors.error_codes import get_registered_error_code, resolve_error_message

    with pytest.raises(FixedWidthRecordRenderError) as excinfo:
        render_fixed_width_export_record_body(
            _absence_record(required=True),
            field_values={"01": "2010"},
        )

    error = excinfo.value
    assert error.field_id == "absent-year"
    assert error.reason == "fixed_width_value"
    assert error.context is not None
    assert error.context["export_field_id"] == "absent-year"
    assert error.translated_message == "errors.fail.fixed_width_record_render"
    assert get_registered_error_code(error).code == "FAIL_FIXED_WIDTH_RECORD_RENDER"
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message


def test_allowed_values_enforcement_has_one_canonical_codec_owner() -> None:
    production_root = Path("src/cadrumo")
    owners = tuple(
        path
        for path in scan_directory(production_root, pattern="*.py", recursive=True, prune_directories=("tests",))
        if "def _require_allowed_value" in path.read_text(encoding="utf-8")
    )

    assert owners == (production_root / "domain/calculations/registry/fixed_width_codec.py",)
