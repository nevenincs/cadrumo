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

from .....core import validated_casilla_id
from .. import ExportFieldDefinition, bundled_authority, parse_fixed_width_export_field
from .._errors import RegistryValidationError
from .._export_parse import (
    _local_name,
    _parse_dictionary_casilla_id,
    _parse_xml_boolean,
    _parse_xml_decimal,
    _parse_xml_dictionary_value,
    xml_dictionary_entries,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# _parse_dictionary_casilla_id
# ---------------------------------------------------------------------------


def test_parse_dictionary_casilla_id_preserves_the_exact_supported_grammar() -> None:
    cases = {
        "01": "01",
        "1234": "1234",
        "  01  ": "01",
        " A ": "A",
    }

    for raw, expected in cases.items():
        assert _parse_dictionary_casilla_id(raw) == expected, raw


def test_parse_dictionary_casilla_id_rejects_non_casilla_rows() -> None:
    """AEAT dictionaries use `*` to mark non-casilla rows (notes, separators)."""
    cases = ("", "   ", "*not-a-casilla", "*01", "###", "abc", "a", "AA", "01a", "01.5")

    for raw in cases:
        assert _parse_dictionary_casilla_id(raw) is None, raw


@pytest.mark.parametrize("filing_year", (2024, 2025))
def test_m100_bundled_dictionary_rows_preserve_numeric_and_annex_box_identities(filing_year: int) -> None:
    """Both source dictionaries carry numeric boxes and published one-letter annex boxes."""
    authority = bundled_authority()
    revision = authority.snapshot("100", filing_year=filing_year, period="0A").revision
    (layout,) = revision.export_layouts

    entries = xml_dictionary_entries(
        layout,
        source_root=authority.source_root,
        sources=authority.catalogues.sources,
    )

    tita = next(entry for entry in entries if entry.field_id == "TITA")
    vhadq = next(entry for entry in entries if entry.field_id == "VHADQ")
    assert tita.casilla_id == validated_casilla_id("0001", surface="M100 numeric dictionary row")
    assert vhadq.casilla_id == validated_casilla_id("A", surface="M100 annex dictionary row")


# ---------------------------------------------------------------------------
# _local_name
# ---------------------------------------------------------------------------


def test_local_name_returns_tag_name_without_namespace() -> None:
    cases = {
        "{http://example.com/ns}casilla": "casilla",
        "casilla": "casilla",
        "{}casilla": "casilla",
    }

    for tag, expected in cases.items():
        assert _local_name(tag) == expected, tag


# ---------------------------------------------------------------------------
# _parse_xml_decimal
# ---------------------------------------------------------------------------


def test_parse_xml_decimal_normalises_supported_numeric_forms() -> None:
    """Spanish locale uses `,` as the decimal separator; AEAT exports
    follow that convention."""
    cases = {
        "": Decimal("0"),
        "   ": Decimal("0"),
        "123,45": Decimal("123.45"),
        "123.45": Decimal("123.45"),
        "12345": Decimal("12345"),
        "  123,45  ": Decimal("123.45"),
    }

    for raw, expected in cases.items():
        assert _parse_xml_decimal(raw) == expected, raw


def test_parse_xml_decimal_malformed_raises_registry_validation_error() -> None:
    with pytest.raises(RegistryValidationError, match="invalid decimal"):
        _parse_xml_decimal("not-a-number")


# ---------------------------------------------------------------------------
# _parse_xml_boolean
# ---------------------------------------------------------------------------


def test_parse_xml_boolean_returns_none_for_empty_input() -> None:
    assert _parse_xml_boolean("LGC", "") is None
    assert _parse_xml_boolean("S_N", "   ") is None


def test_parse_xml_boolean_accepts_declared_dictionary_truthy_tokens() -> None:
    assert _parse_xml_boolean("LGC", "1") is True
    assert _parse_xml_boolean("S_N", "SI") is True
    assert _parse_xml_boolean("s_n", "  si  ") is True


def test_parse_xml_boolean_accepts_declared_dictionary_falsy_tokens() -> None:
    assert _parse_xml_boolean("LGC", "0") is False
    assert _parse_xml_boolean("S_N", "NO") is False
    assert _parse_xml_boolean("s_n", "  no  ") is False


@pytest.mark.parametrize(("data_type", "raw"), (("LGC", "X"), ("LGC", "SI"), ("S_N", "1"), ("S_N", "false")))
def test_parse_xml_boolean_raises_on_wrong_or_unrecognised_vocabulary(data_type: str, raw: str) -> None:
    with pytest.raises(RegistryValidationError, match="XML dictionary boolean field"):
        _parse_xml_boolean(data_type, raw)


# ---------------------------------------------------------------------------
# _parse_xml_dictionary_value
# ---------------------------------------------------------------------------


def test_parse_xml_dictionary_value_dispatches_by_declared_data_type() -> None:
    """Each row is read as the type the official dictionary declares for it.

    Every code here is one the bundled Modelo 100 dictionaries actually use, across
    the revisions that ship: ``N102``/``P102``/``P030`` for amounts and counts,
    ``LGC`` and ``S_N`` for the two boolean spellings, and ``X``/``FEC``/``AAA``/
    ``TIT`` for rows carried as text. Asserting against invented codes would leave
    the dispatch free to be wrong about every real one.
    """
    cases: tuple[tuple[str, str, Decimal | str | bool], ...] = (
        ("N102", "123,45", Decimal("123.45")),
        ("P102", "12000.25", Decimal("12000.25")),
        ("P030", "365", Decimal("365")),
        # tipo_logico spells its two states 0 and 1; tipo_SINO_Exclusivo spells the
        # same two states NO and SI. Both rows carry a boolean.
        ("LGC", "1", True),
        ("LGC", "0", False),
        ("S_N", "SI", True),
        ("S_N", "NO", False),
        ("X", "ESPAÑA", "ESPAÑA"),
        ("FEC", "1/2/1980", "1/2/1980"),
        ("AAA", "2021", "2021"),
        ("TIT", "2", "2"),
        # The dictionary spells its codes uppercase; matching is case-insensitive
        # so a lowercased code is not silently read as text.
        ("n102", "100", Decimal("100")),
        ("lgc", "1", True),
        ("s_n", "SI", True),
    )

    for data_type, raw, expected in cases:
        assert _parse_xml_dictionary_value(data_type, raw) == expected, (data_type, raw)


# ---------------------------------------------------------------------------
# canonical fixed-width decimal parser
# ---------------------------------------------------------------------------


def _decimal_field(field_id: str = "casilla.0501") -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": 1,
            "length": 6,
            "kind": "casilla",
            "casilla_id": "0501",
            "data_type": "decimal",
            # A decimal slot carries digits only and declares the scale the
            # reader shifts by; a field omitting it cannot be rendered and is
            # refused at validation.
            "decimals": 2,
            "required": False,
            "padding": "left_zero",
            "justification": "right",
            "signed": False,
            "legal_refs": ("ley-37-1992:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )


def test_parse_fixed_width_decimal_yields_correct_value() -> None:
    """The public codec reads an implicit-decimal slot at the declared scale.

    Verifies that raw is treated as the numeric string and field is used only
    for error context.  The canonical argument order is (raw, field).

    The slot is DIGITS ONLY and the decimal point is restored by shifting, which
    is the fichero-BOE convention the writer emits: ``300506`` at ``decimals =
    2`` is 3.005,06 €. This case previously passed ``"3005,06"``, which the
    reader now refuses as non-digit data -- the punctuated form was the older
    contract, not a second accepted spelling, so asserting it would pin a
    behaviour the format does not have.
    """
    field = _decimal_field()
    assert parse_fixed_width_export_field(field, "300506") == Decimal("3005.06")


def test_parse_fixed_width_decimal_invalid_raw_includes_field_id_in_error() -> None:
    """The public codec includes the field id in invalid-input errors.

    Proves that field is passed as the ExportFieldDefinition (not as raw),
    so the error message correctly names the field id rather than trying to
    parse the field object as a decimal string.
    """
    field = _decimal_field("casilla.0501")
    with pytest.raises(RegistryValidationError, match=r"casilla\.0501"):
        parse_fixed_width_export_field(field, "invalid")
