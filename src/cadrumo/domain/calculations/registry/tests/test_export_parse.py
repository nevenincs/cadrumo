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

from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding, parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema import ExportFieldDefinition
from cadrumo.domain.calculations.registry.export_parse import xml_dictionary_entries
from ..errors import RegistryValidationError
from ..export_parse import (
    _local_name,
    _parse_dictionary_casilla_id,
    _parse_xml_boolean,
    _parse_xml_decimal,
    _parse_xml_dictionary_value,
)
from ._modelo_100_registry_support import _loaded_registry, _source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# _parse_dictionary_casilla_id
# ---------------------------------------------------------------------------


def test_parse_dictionary_casilla_id_accepts_published_numeric_identities() -> None:
    cases = {
        "01": "01",
        "1234": "1234",
        "  01  ": "01",
    }

    for raw, expected in cases.items():
        assert _parse_dictionary_casilla_id(raw) == expected, raw


def test_parse_dictionary_casilla_id_accepts_grounded_letter_identities_only_when_enabled() -> None:
    for raw, expected in {"A": "A", "  M  ": "M"}.items():
        assert _parse_dictionary_casilla_id(raw) is None
        assert _parse_dictionary_casilla_id(raw, allow_letter_id=True) == expected


def test_parse_dictionary_casilla_id_rejects_non_casilla_rows() -> None:
    """AEAT dictionaries use `*` to mark non-casilla rows (notes, separators)."""
    cases = ("", "   ", "*not-a-casilla", "*01", "###", "a", "AA", "abc", "01a", "01.5")

    for raw in cases:
        assert _parse_dictionary_casilla_id(raw) is None, raw


def test_parse_dictionary_casilla_id_letter_grammar_stays_one_uppercase_letter() -> None:
    """Enabling the annex form widens the grammar by exactly one uppercase letter."""
    cases = ("", "   ", "*A", "###", "a", "m", "AA", "A1", "1A", "abc", "01a", "01.5")

    for raw in cases:
        assert _parse_dictionary_casilla_id(raw, allow_letter_id=True) is None, raw


@pytest.mark.parametrize(
    ("filing_year", "field_id", "expected_casilla_id"),
    (
        (2024, "VHADQ", "A"),
        (2025, "MDIC", "I"),
    ),
)
def test_m100_dictionary_preserves_published_letter_casilla_identities(
    filing_year: int,
    field_id: str,
    expected_casilla_id: str,
) -> None:
    modelos_by_id, catalogues = _loaded_registry()
    layout = modelos_by_id["100"].revisions[str(filing_year)].export_layouts[0]

    entries = xml_dictionary_entries(
        layout,
        source_root=_source_root(),
        sources=catalogues.sources,
    )
    entry = next(item for item in entries if item.field_id == field_id)

    assert entry.casilla_id == expected_casilla_id


@pytest.mark.parametrize("filing_year", (2024, 2025))
def test_m100_dictionary_preserves_published_numeric_casilla_identities(filing_year: int) -> None:
    """Widening the grammar for annex boxes leaves the numeric rows spelled exactly as published."""
    modelos_by_id, catalogues = _loaded_registry()
    layout = modelos_by_id["100"].revisions[str(filing_year)].export_layouts[0]

    entries = xml_dictionary_entries(
        layout,
        source_root=_source_root(),
        sources=catalogues.sources,
    )
    entry = next(item for item in entries if item.field_id == "TITA")

    assert entry.casilla_id == "0001"


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


def test_payload_with_auxiliary_header_prefix_skips_the_header_before_records() -> None:
    """A declared page-zero header opens the payload ahead of the records.

    The parser holds no filing-instance facts (year, period, product identity),
    so the skip is exact extent rather than content re-derivation: the records
    that follow must still match their own literals, and a payload shorter than
    the declared prefix cannot satisfy them.
    """
    from ..export_parse import parse_export_payload
    from ..schema import (
        AuxiliaryEnvelopeHeaderDefinition,
        ExportLayoutDefinition,
        ExportRecordDefinition,
        FilingEnvelopePrefixFieldDeclaration,
        FilingEnvelopePrefixRole,
    )

    roles = tuple(
        role for role in FilingEnvelopePrefixRole if role is not FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
    )
    declaration = AuxiliaryEnvelopeHeaderDefinition(
        source_ref="aeat-dr-232-2018",
        source_sha256="a" * 64,
        record_identity="DR23200",
        prefix_fields=tuple(FilingEnvelopePrefixFieldDeclaration(role=role, length=1) for role in roles),
        prefix_extent=13,
        product_identity_requirement="aeat-product-software-identity-v1",
    )
    record = ExportRecordDefinition.model_validate(
        {
            "id": "record-m232-test",
            "record_type": "test",
            "order": 0,
            "encoding": ExportEncoding.LATIN_1,
            "line_ending": "crlf",
            "fields": (
                {
                    "id": "m232-test.f001",
                    "offset": 1,
                    "length": 1,
                    "kind": "literal",
                    "literal": "T",
                    "data_type": "text",
                    "required": False,
                    "padding": "right_space",
                    "justification": "left",
                    "signed": False,
                    "legal_refs": ("ley-27-2014:art-18",),
                    "source_refs": ("aeat-dr-232-2018",),
                },
            ),
        },
    )
    layout = ExportLayoutDefinition.model_validate(
        {
            "id": "generated-modelo-232-test-fichero",
            "format": "fixed_width",
            "source_refs": ("aeat-dr-232-2018",),
            "legal_refs": ("ley-27-2014:art-18",),
            "records": (record,),
            "auxiliary_envelope_header": declaration,
        },
    )
    payload = b"H" * 13 + b"T" + b"\r\n"

    parsed = parse_export_payload(layout, payload)
    assert parsed.casillas == ()
    assert len(parsed.fields) == 1
    assert parsed.fields[0].field_id == "m232-test.f001"
