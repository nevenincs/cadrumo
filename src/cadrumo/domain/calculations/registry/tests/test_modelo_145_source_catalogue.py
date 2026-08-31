"""Modelo 145 source and legal catalogue verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.resources._boundary import bundled_path
from ..corpus_catalogue import verify_source_file
from ..legal import verify_legal_catalogue
from ..record_design import extract_record_design_pdf
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_IDS = {
    "rd-439-2007:art-88",
    "resolucion-dgt-2011-01-03-modelo-145:aprobacion",
    "resolucion-dgt-2013-12-17-modelo-145:amendment",
    "resolucion-dgt-2014-12-18-modelo-145:amendment",
}

_SOURCE_IDS = {
    "aeat-modelo-145-procedure",
    "aeat-modelo-145-obligaciones-retenedor",
    "aeat-modelo-145-form",
    "aeat-dr-145-v20",
    "boe-modelo-145-2011-approval",
    "boe-modelo-145-2013-amendment",
    "boe-modelo-145-2014-amendment",
}


def _catalogues():
    _, catalogues = _committed_registry_tree()
    return catalogues


def test_modelo_145_legal_authority_is_reviewed_and_corpus_backed() -> None:
    catalogues = _catalogues()
    legal = {legal_id: catalogues.legal[legal_id] for legal_id in _LEGAL_IDS}

    verify_legal_catalogue(legal, source_root=bundled_path())

    assert {entry.document_id for entry in legal.values()} == {
        "BOE-A-2007-6820",
        "BOE-A-2011-208",
        "BOE-A-2014-59",
        "BOE-A-2014-13679",
    }
    assert all(entry.evidence_tier == "legal_authority" for entry in legal.values())

    art_88 = legal["rd-439-2007:art-88"]
    assert art_88.article == "88"
    assert "deberán comunicar al pagador la situación personal y familiar" in art_88.required_text
    assert "El contenido de las comunicaciones se ajustará al modelo que se apruebe por Resolución" in (
        art_88.required_text
    )


def test_modelo_145_source_authority_files_match_catalogue_fingerprints() -> None:
    catalogues = _catalogues()
    sources = {source_id: catalogues.sources[source_id] for source_id in _SOURCE_IDS}

    for source in sources.values():
        verify_source_file(bundled_path(), source)

    assert sources["aeat-modelo-145-procedure"].evidence_tier == "official_source_guidance"
    assert sources["aeat-modelo-145-obligaciones-retenedor"].evidence_tier == "official_source_guidance"
    assert sources["aeat-modelo-145-form"].kind == "form_spec"
    assert sources["aeat-dr-145-v20"].evidence_tier == "layout_authority"
    assert sources["boe-modelo-145-2011-approval"].evidence_tier == "layout_authority"
    assert sources["boe-modelo-145-2013-amendment"].evidence_tier == "layout_authority"
    assert sources["boe-modelo-145-2014-amendment"].evidence_tier == "layout_authority"


def test_modelo_145_form_cites_rd_439_art_88_regulatory_anchor() -> None:
    catalogues = _catalogues()
    form_source = catalogues.sources["aeat-modelo-145-form"]
    form_extract = bundled_path() / f"{form_source.corpus_path}.extracted.json"
    payload = json.loads(form_extract.read_text(encoding="utf-8"))
    form_text = "\n".join(unit["text"] for unit in payload["units"])

    assert "rd-439-2007:art-88" in catalogues.legal
    assert "Comunicación de datos al pagador (artículo 88 del Reglamento del IRPF)" in form_text
    assert "a los efectos previstos en el artículo 88 del Reglamento del IRPF" in form_text


def test_modelo_145_aeat_sources_pin_non_filing_scope() -> None:
    catalogues = _catalogues()
    procedure = bundled_path() / catalogues.sources["aeat-modelo-145-procedure"].corpus_path
    obligations = bundled_path() / catalogues.sources["aeat-modelo-145-obligaciones-retenedor"].corpus_path

    procedure_text = procedure.read_text(encoding="utf-8", errors="replace")
    obligations_text = obligations.read_text(encoding="utf-8", errors="replace")

    assert "No requiere presentación ante la Administración Tributaria" in procedure_text
    assert "Ante el pagador" in procedure_text
    assert "no requiere presentación ni tramitación por parte de la persona física" in procedure_text
    assert "no permiten la realización de trámites por vía electrónica" in obligations_text
    assert "ante el pagador de las retribuciones" in obligations_text


def test_modelo_145_record_design_source_matches_manifest() -> None:
    catalogues = _catalogues()
    source = catalogues.sources["aeat-dr-145-v20"]
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_145", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored_path = Path(source.corpus_path).relative_to("corpus/aeat_official/disenos_registro/modelo_145").as_posix()
    artefact = next(item for item in manifest["artefacts"] if item["stored_path"] == stored_path)

    assert artefact["url"] == source.source_url
    assert artefact["bytes"] == source.bytes
    assert artefact["sha256"] == source.sha256
    assert manifest["modelo"] == "145"
    assert manifest["artefact_count"] == 1
    assert artefact["modelo"] == "145"
    assert artefact["stored_path"] == "files/dr145v20.pdf"


def test_modelo_145_record_design_extracts_official_model_marker() -> None:
    catalogues = _catalogues()
    source = catalogues.sources["aeat-dr-145-v20"]
    sheets = extract_record_design_pdf(bundled_path() / source.corpus_path).accept_partial()

    assert len(sheets) == 1
    sheet = sheets[0]
    assert sheet.total_positions == 610
    first_field = sheet.fields[0]
    assert first_field.offset == 1
    assert first_field.length == 9
    assert "<T145010>" in first_field.description
