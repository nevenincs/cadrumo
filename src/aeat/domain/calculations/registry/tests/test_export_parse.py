"""Focused unit tests for the pure helpers in _export_parse.

`_export_parse` is the XML-dictionary / BOE-record export parser. The
public `parse_export_payload` surface is covered indirectly by the
per-modelo registry round-trip tests (Modelo 100, 349, committed
registry), but the small pure helpers underneath had no direct
unit-test coverage. A regression in (for example) the comma-decimal
normalisation or the data_type dispatch would silently corrupt every
parsed export payload.

Tests here are structural / algorithmic — they fix the contract of
each helper, not any AEAT calculation result.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._errors import RegistryValidationError
from .._export_parse import (
    _local_name,
    _parse_boolean,
    _parse_decimal,
    _parse_dictionary_casilla_id,
    _parse_xml_decimal,
    _parse_xml_dictionary_value,
)
from .._schema import ExportFieldDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# _parse_dictionary_casilla_id
# ---------------------------------------------------------------------------


def test_parse_dictionary_casilla_id_returns_digit_string_unchanged() -> None:
    assert _parse_dictionary_casilla_id("01") == "01"
    assert _parse_dictionary_casilla_id("1234") == "1234"


def test_parse_dictionary_casilla_id_strips_surrounding_whitespace() -> None:
    assert _parse_dictionary_casilla_id("  01  ") == "01"


def test_parse_dictionary_casilla_id_returns_none_for_empty_input() -> None:
    assert _parse_dictionary_casilla_id("") is None


def test_parse_dictionary_casilla_id_returns_none_for_whitespace_only() -> None:
    assert _parse_dictionary_casilla_id("   ") is None


def test_parse_dictionary_casilla_id_returns_none_for_asterisk_prefixed() -> None:
    """AEAT dictionaries use `*` to mark non-casilla rows (notes, separators)."""
    assert _parse_dictionary_casilla_id("*not-a-casilla") is None
    assert _parse_dictionary_casilla_id("*01") is None


def test_parse_dictionary_casilla_id_returns_none_for_non_digit_text() -> None:
    assert _parse_dictionary_casilla_id("abc") is None
    assert _parse_dictionary_casilla_id("01a") is None
    assert _parse_dictionary_casilla_id("01.5") is None


# ---------------------------------------------------------------------------
# _local_name
# ---------------------------------------------------------------------------


def test_local_name_strips_xml_namespace_prefix() -> None:
    assert _local_name("{http://example.com/ns}casilla") == "casilla"


def test_local_name_returns_bare_tag_unchanged() -> None:
    assert _local_name("casilla") == "casilla"


def test_local_name_handles_empty_namespace_braces() -> None:
    assert _local_name("{}casilla") == "casilla"


# ---------------------------------------------------------------------------
# _parse_xml_decimal
# ---------------------------------------------------------------------------


def test_parse_xml_decimal_empty_returns_zero() -> None:
    assert _parse_xml_decimal("") == Decimal("0")


def test_parse_xml_decimal_whitespace_only_returns_zero() -> None:
    assert _parse_xml_decimal("   ") == Decimal("0")


def test_parse_xml_decimal_comma_decimal_separator_normalises_to_dot() -> None:
    """Spanish locale uses `,` as the decimal separator; AEAT exports
    follow that convention."""
    assert _parse_xml_decimal("123,45") == Decimal("123.45")


def test_parse_xml_decimal_dot_decimal_separator_works_unchanged() -> None:
    assert _parse_xml_decimal("123.45") == Decimal("123.45")


def test_parse_xml_decimal_integer_string_works() -> None:
    assert _parse_xml_decimal("12345") == Decimal("12345")


def test_parse_xml_decimal_strips_surrounding_whitespace() -> None:
    assert _parse_xml_decimal("  123,45  ") == Decimal("123.45")


def test_parse_xml_decimal_malformed_raises_registry_validation_error() -> None:
    with pytest.raises(RegistryValidationError, match="invalid decimal"):
        _parse_xml_decimal("not-a-number")


# ---------------------------------------------------------------------------
# _parse_boolean
# ---------------------------------------------------------------------------


def test_parse_boolean_returns_none_for_empty_input() -> None:
    assert _parse_boolean("") is None
    assert _parse_boolean("   ") is None


@pytest.mark.parametrize("truthy", ["X", "1", "S", "SI", "TRUE", "x", "true", "  X  "])
def test_parse_boolean_accepts_canonical_truthy_tokens(truthy: str) -> None:
    """AEAT dictionaries use 'X' or 'S/SI' to mark a checked flag."""
    assert _parse_boolean(truthy) is True


@pytest.mark.parametrize("falsy", ["0", "N", "NO", "FALSE", "no", "false"])
def test_parse_boolean_accepts_canonical_falsy_tokens(falsy: str) -> None:
    assert _parse_boolean(falsy) is False


def test_parse_boolean_raises_on_unrecognised_token() -> None:
    with pytest.raises(RegistryValidationError, match="boolean export field"):
        _parse_boolean("maybe")


def test_parse_boolean_delegates_to_core_parse_bool() -> None:
    """The wrapper must call _core_parse_bool; tokens that overlap with the
    core truthy set ("1", "true") must still resolve through the wrapper."""
    # "1" is in both the registry and core truthy sets — must be True.
    assert _parse_boolean("1") is True
    # "no" is in core falsy set and registry falsy set — must be False.
    assert _parse_boolean("no") is False


# ---------------------------------------------------------------------------
# _parse_xml_dictionary_value
# ---------------------------------------------------------------------------


def test_parse_xml_dictionary_value_dispatches_n_codes_to_decimal() -> None:
    """AEAT XML dictionaries encode numeric fields with data_type starting
    with 'N' (e.g. 'N15.2') or 'P' (percentage)."""
    assert _parse_xml_dictionary_value("N15.2", "123,45") == Decimal("123.45")


def test_parse_xml_dictionary_value_dispatches_p_codes_to_decimal() -> None:
    assert _parse_xml_dictionary_value("P5.2", "0,21") == Decimal("0.21")


def test_parse_xml_dictionary_value_dispatches_l_codes_to_boolean() -> None:
    assert _parse_xml_dictionary_value("L1", "X") is True
    assert _parse_xml_dictionary_value("L1", "0") is False


def test_parse_xml_dictionary_value_passes_unknown_codes_through_as_raw_string() -> None:
    """Anything that does not start with N/P/L is treated as alphanumeric
    and returned as-is so the caller can apply its own normalisation."""
    assert _parse_xml_dictionary_value("A60", "ESPAÑA") == "ESPAÑA"
    assert _parse_xml_dictionary_value("D8", "20250101") == "20250101"


def test_parse_xml_dictionary_value_data_type_dispatch_is_case_insensitive() -> None:
    """The dispatcher uppercases the data_type before prefix matching,
    so lowercase codes still route to the right branch."""
    assert _parse_xml_dictionary_value("n15.2", "100") == Decimal("100")
    assert _parse_xml_dictionary_value("l1", "X") is True


# ---------------------------------------------------------------------------
# _parse_decimal argument-order regression
# ---------------------------------------------------------------------------


def _decimal_field(field_id: str = "casilla.0501") -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": None,
            "length": None,
            "kind": "literal",
            "literal": "0",
            "data_type": "decimal",
            "required": False,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


def test_parse_decimal_raw_first_yields_correct_value() -> None:
    """_parse_decimal(raw, field) parses a comma-decimal BOE string correctly.

    Verifies that raw is treated as the numeric string and field is used only
    for error context.  The canonical argument order is (raw, field).
    """
    field = _decimal_field()
    assert _parse_decimal("3005,06", field) == Decimal("3005.06")


def test_parse_decimal_invalid_raw_includes_field_id_in_error() -> None:
    """_parse_decimal raises RegistryValidationError with the field id in the message.

    Proves that field is passed as the ExportFieldDefinition (not as raw),
    so the error message correctly names the field id rather than trying to
    parse the field object as a decimal string.
    """
    field = _decimal_field("casilla.0501")
    with pytest.raises(RegistryValidationError, match=r"casilla\.0501"):
        _parse_decimal("invalid", field)
