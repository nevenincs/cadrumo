"""Focused tests for the public AEAT export parser surface.

The parser's internal XML and record helpers stay implementation details.
These tests exercise the public payload and dictionary entry APIs, while the
per-modelo registry round-trip tests provide the end-to-end coverage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import xml_dictionary_entries
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding, parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ._modelo_100_registry_support import _loaded_registry, _source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    source = catalogues.sources[str(layout.dictionary_source_ref)]

    entries = xml_dictionary_entries(
        layout,
        sources=catalogues.sources,
        source_payloads={
            str(source.id): (_source_root() / source.corpus_path).read_bytes() for source in catalogues.sources.values()
        },
    )
    entry = next(item for item in entries if item.field_id == field_id)

    assert source.applies_from == date(filing_year, 1, 1)
    assert source.supports_single_uppercase_letter_casilla_ids
    assert entry.casilla_id == expected_casilla_id


@pytest.mark.parametrize("filing_year", (2024, 2025))
def test_m100_dictionary_preserves_published_numeric_casilla_identities(filing_year: int) -> None:
    """Widening the grammar for annex boxes leaves the numeric rows spelled exactly as published."""
    modelos_by_id, catalogues = _loaded_registry()
    layout = modelos_by_id["100"].revisions[str(filing_year)].export_layouts[0]

    entries = xml_dictionary_entries(
        layout,
        sources=catalogues.sources,
        source_payloads={
            str(source.id): (_source_root() / source.corpus_path).read_bytes() for source in catalogues.sources.values()
        },
    )
    entry = next(item for item in entries if item.field_id == "TITA")

    assert entry.casilla_id == "0001"


def test_m100_letter_casilla_grammar_is_declared_by_the_bound_source() -> None:
    """The earliest capable source's own temporal row begins the extension."""
    modelos_by_id, catalogues = _loaded_registry()
    sources = tuple(
        catalogues.sources[
            str(modelos_by_id["100"].revisions[str(filing_year)].export_layouts[0].dictionary_source_ref)
        ]
        for filing_year in range(2020, 2026)
    )
    capable = tuple(source for source in sources if source.supports_single_uppercase_letter_casilla_ids)
    capable_starts = tuple(source.applies_from for source in capable)

    assert capable_starts and all(start is not None for start in capable_starts)
    assert min(start for start in capable_starts if start is not None) == date(2024, 1, 1)
    assert all(source.applies_from is not None for source in sources)
    assert all(source.dictionary_casilla_id_grammar == "numeric" for source in sources[:4])


def test_m100_letter_casilla_parsing_refuses_when_source_capability_is_removed() -> None:
    """The same published dictionary row becomes non-casilla without its capability."""
    modelos_by_id, catalogues = _loaded_registry()
    layout = modelos_by_id["100"].revisions["2024"].export_layouts[0]
    source = catalogues.sources[str(layout.dictionary_source_ref)]
    dictionary_path = _source_root() / source.corpus_path
    removed_capability = SourceReference.model_validate(
        {**source.model_dump(), "dictionary_casilla_id_grammar": "numeric"},
    )
    dictionary_payload = dictionary_path.read_bytes()
    admitted = xml_dictionary_entries(
        layout,
        sources={str(source.id): source},
        source_payloads={str(source.id): dictionary_payload},
    )
    refused = xml_dictionary_entries(
        layout,
        sources={str(removed_capability.id): removed_capability},
        source_payloads={str(removed_capability.id): dictionary_payload},
    )

    assert next(item for item in admitted if item.field_id == "VHADQ").casilla_id == "A"
    assert next(item for item in refused if item.field_id == "VHADQ").casilla_id is None


def test_extended_dictionary_grammar_refuses_a_non_dictionary_source() -> None:
    """Only a dictionary source may claim the annex grammar."""
    _, catalogues = _loaded_registry()
    source = catalogues.sources["aeat-dr-100-2024-dictionary"]
    malformed = source.model_dump()
    malformed["kind"] = "manual_pdf"

    with pytest.raises(ValidationError, match="dictionary_casilla_id_grammar"):
        SourceReference.model_validate(malformed)


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
    from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
    from cadrumo.domain.calculations.registry.schema_exports import (
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
            "encoding": ExportEncoding.ISO_8859_1,
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
