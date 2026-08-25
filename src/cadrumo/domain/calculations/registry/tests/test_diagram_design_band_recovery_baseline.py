"""Regression coverage for the physical geometry reader's pre-2003 diagrams.

The 2000/2002 AEAT designs are byte rulers with floating captions, rather than
tabular field rows.  Their printed horizontal field rules are not represented
uniformly in the PDFs: some are rectangles, others are closed curves, and adjacent
segments in one physical rule band may have slightly different vertical bounds.
The canonical geometry reader must normalize those document facts before it assigns
any byte offsets.  This module pins the recovered official spans, not a
modelo-specific parser exception.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_180_DIAGRAM = ("modelo_180", "02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf")
_MODELO_349_DIAGRAM = ("modelo_349", "03-349-orden-hac-360-2002-28-kb-pdf.pdf")


def _extraction(folder: str, name: str):
    return extract_record_design(bundled_path("corpus", "aeat_official", "disenos_registro", folder, "files", name))


def test_pre_2003_diagrams_now_read_as_complete_official_record_designs() -> None:
    """The parser may not return partial chart sheets as filing-ready layouts."""
    for folder, name in (_MODELO_180_DIAGRAM, _MODELO_349_DIAGRAM):
        extraction = _extraction(folder, name)
        assert extraction.is_complete, f"{name} left a physical byte-ruler span unread: {extraction.skipped}"
        assert not extraction.skipped


def test_modelo_180_recovers_the_shared_trailing_geometry_without_inventing_labels() -> None:
    """Its misaligned final ruler segments cover 176--260 on both record types."""
    extraction = _extraction(*_MODELO_180_DIAGRAM)
    sheets = {sheet.name: sheet for sheet in extraction.sheets}

    assert {sheet.total_positions for sheet in sheets.values()} == {260}
    assert set(sheets) == {
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Perceptor",
    }

    declarante = sheets["Tipo 1 - Registro De Declarante"]
    assert [(field.offset, field.length) for field in declarante.fields[-3:]] == [
        (176, 62),
        (238, 13),
        (251, 10),
    ]
    perceptor = sheets["Tipo 2 - Registro De Perceptor"]
    assert [(field.offset, field.length) for field in perceptor.fields[-2:]] == [(114, 137), (251, 10)]
    assert all(field.type_code == "No consta en gráfico" for sheet in sheets.values() for field in sheet.fields)


def test_modelo_349_recovers_curve_encoded_leading_and_trailing_rule_segments() -> None:
    """All four 250-byte records retain the official curve-derived spans."""
    extraction = _extraction(*_MODELO_349_DIAGRAM)
    sheets = {sheet.name: sheet for sheet in extraction.sheets}

    assert {sheet.total_positions for sheet in sheets.values()} == {250}
    assert set(sheets) == {
        "Tipo 0 - Registro De Presentador",
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Operador Intracomunitario",
        "Tipo 2 - Registro De Rectificaciones",
    }
    assert [(field.offset, field.length) for field in sheets["Tipo 0 - Registro De Presentador"].fields[3:6]] == [
        (9, 9),
        (18, 40),
        (58, 2),
    ]
    expected_tails = {
        "Tipo 2 - Registro De Operador Intracomunitario": [(147, 32), (179, 72)],
        "Tipo 2 - Registro De Rectificaciones": [(177, 2), (179, 72)],
    }
    for sheet_name, expected_tail in expected_tails.items():
        fields = sheets[sheet_name].fields
        assert [(field.offset, field.length) for field in fields[3:5]] == [(9, 9), (18, 58)]
        assert [(field.offset, field.length) for field in fields[-2:]] == expected_tail


def test_modelo_180_recovered_reserved_band_still_carries_its_caption_in_the_document() -> None:
    """The official source names the recovered reserved band.

    ``SELLO ELECTRÓNICO (RESERVADO)`` sits immediately above the 196-260 ruler on the
    Tipo 1 record. The geometric reader can retain that factual caption; a re-bundled
    source that drops it must make this proof fail rather than preserve a remembered
    label.
    """
    from .._record_design import _extract_pdf_text_lines

    folder, name = _MODELO_180_DIAGRAM
    path = bundled_path("corpus", "aeat_official", "disenos_registro", folder, "files", name)
    lines = [line.strip() for line in _extract_pdf_text_lines(path.read_bytes(), source_label=name)]

    assert any("SELLO ELECTR" in line for line in lines), (
        "the caption naming the recovered 196-260 band is gone from the document"
    )
    assert any(line.startswith("196 197 198") for line in lines), (
        "the 196-260 ruler is gone, so the band this baseline describes no longer exists"
    )
