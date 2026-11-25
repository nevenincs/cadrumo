"""A PDF record design that names its line terminator by word reads as the CRLF constant."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..record_design import extract_record_design_pdf
from ..record_design_pdf_rows import parse_pdf_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_840 = Path("corpus/aeat_official/disenos_registro/modelo_840/files/01-840-orden-hac-2572-2003-99-kb-pdf.pdf")


def test_modelo_840_terminator_rows_carry_the_crlf_constant_and_two_bytes() -> None:
    """Every page of the Modelo 840 design ends with `Salto de linea. Constante CRLF.`"""
    extraction = extract_record_design_pdf(bundled_path() / _DESIGN_840)

    terminators = [
        field
        for sheet in extraction.sheets
        for field in sheet.fields
        if (field.description or "").startswith("Salto de l")
    ]

    assert len(terminators) == len(extraction.sheets) == 3
    assert {(field.length, field.content) for field in terminators} == {(2, "Constante CRLF")}


def test_modelo_840_closing_tags_keep_their_printed_tag() -> None:
    """The end-tag rows are untouched by the terminator reading."""
    extraction = extract_record_design_pdf(bundled_path() / _DESIGN_840)

    closing = [
        field.content
        for sheet in extraction.sheets
        for field in sheet.fields
        if (field.description or "").startswith("Identificador de fin de registro")
    ]

    assert closing == ['"</T840010>"', '"</T840020>"', '"</T840030>"']


def test_a_row_with_neither_a_constant_nor_a_length_is_not_a_field() -> None:
    """A described row without a printed length or a terminator caption stays refused."""
    assert parse_pdf_row("106 1131 An Descripcion sin longitud ni constante", 117) is None
