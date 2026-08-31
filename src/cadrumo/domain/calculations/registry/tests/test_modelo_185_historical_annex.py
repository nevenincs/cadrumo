"""Hash-pinned primary Annex-I evidence for Modelo 185's historical span."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.hashing import hash_file
from .....core.resources._boundary import bundled_path
from ..record_design import extract_record_design
from ..record_design_pdf_visual import _extract_pdf_text_lines
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "boe-modelo-185-2003-annex-i"


def test_modelo_185_historical_annex_is_hash_pinned_and_exposes_both_record_types() -> None:
    """The original BOE annex distinguishes both 120-position record types.

    This is acquisition evidence only. The canonical record-design parser
    cannot yet separate the historical Type-2 page into its own exact record,
    so this primary source must not be promoted to a coordinate authority.
    """
    modelo, catalogues = _committed_modelo("185")
    revision = modelo.revisions["2003-2025"]
    source = catalogues.sources[_SOURCE_REF]
    path = bundled_path() / source.corpus_path

    assert _SOURCE_REF in revision.source_refs
    assert source.evidence_tier == "layout_authority"
    assert source.authority == "boe"
    assert source.kind == "form_spec"
    assert source.record_design_epoch is None
    assert (source.published_at, source.applies_from, source.applies_to) == (
        date(2003, 1, 30),
        date(2003, 1, 31),
        date(2025, 12, 31),
    )
    assert source.source_url == "https://www.boe.es/boe/dias/2003/01/30/pdfs/A03911-03920.pdf"
    assert hash_file(path) == (source.sha256, source.bytes)

    lines = _extract_pdf_text_lines(path.read_bytes(), source_label=source.id)
    type_1 = "Tipo 1: Registro del declarante: Datos identificativos."
    type_2 = "Tipo 2: Registro del declarado."
    type_1_index = next(index for index, line in enumerate(lines) if type_1 in line)
    type_2_index = next(index for index, line in enumerate(lines) if type_2 in line)

    assert type_1_index < type_2_index
    assert sum("Registros de: 120 posiciones." in line for line in lines) >= 2

    parsed = extract_record_design(path)
    assert tuple(sheet.name for sheet in parsed.sheets) == ("Tipo 1 - Registro De Declarante",)
    assert any(type_2 in line for line in lines)
