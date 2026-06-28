"""Modelo 721 registry grounding regressions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .._corpus_catalogue import verify_source_file
from .._legal import verify_legal_catalogue
from .._loader import load_registry_tree
from .._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _modelo_721() -> tuple[ModeloDefinition, ModeloRevision, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(modelo for modelo in modelos if modelo.id == "721")
    return modelo, modelo.revisions["2023-y-siguientes"], catalogues


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
        return
    if isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from _strings(item)


def test_modelo_721_articles_are_content_deadline_and_annex_amendment() -> None:
    _, _, catalogues = _modelo_721()
    art_3 = catalogues.legal["orden-hfp-886-2023:art-3"]
    art_4 = catalogues.legal["orden-hfp-886-2023:art-4"]
    amendment = catalogues.legal["orden-hac-1504-2024:art-9"]
    first_application = catalogues.legal["orden-hac-1504-2024:df-unica"]

    assert art_3.article == "3"
    assert art_3.required_text == (
        "información contenida en el anexo",
        "artículo 42 quater",
        "monedas virtuales situadas en el extranjero",
    )
    assert "1 de enero" not in art_3.required_text
    assert "31 de marzo" not in art_3.required_text
    assert art_4.article == "4"
    assert "1 de enero" in art_4.required_text
    assert "31 de marzo" in art_4.required_text
    assert "Se sustituye el anexo" in amendment.required_text
    assert "ejercicio 2024" in first_application.required_text
    verify_legal_catalogue(
        {
            art_3.id: art_3,
            art_4.id: art_4,
            amendment.id: amendment,
            first_application.id: first_application,
        },
        source_root=bundled_path(),
    )


def test_modelo_721_revision_uses_boe_layout_sources_and_applicability_chain() -> None:
    modelo, revision, catalogues = _modelo_721()

    assert revision.orden_aplicabilidad == (
        "orden-hfp-886-2023:art-1",
        "orden-hac-1504-2024:art-9",
        "orden-hac-1504-2024:df-unica",
    )
    assert {
        "boe-modelo-721-2023-layout",
        "boe-modelo-721-2024-layout",
        "aeat-modelo-721-procedure",
        "boe-modelo-721-2023-form",
    } <= set(revision.source_refs)

    all_modelo_strings = set(_strings(modelo.model_dump(mode="json")))
    assert "aeat-dr-721" not in all_modelo_strings

    workbook_refs = {reference.id: reference for reference in revision.workbook_parity_refs}
    assert workbook_refs["modelo-721-dr-2023"].workbook_source == "boe-modelo-721-2023-layout"
    assert workbook_refs["modelo-721-dr-2024"].workbook_source == "boe-modelo-721-2024-layout"

    for source_id in ("boe-modelo-721-2023-layout", "boe-modelo-721-2024-layout"):
        source = catalogues.sources[source_id]
        assert source.authority == "boe"
        assert source.evidence_tier == "layout_authority"
        assert source.kind == "form_spec"
        assert source.corpus_path.endswith(".pdf")
        verify_source_file(PROJECT_ROOT, source)


def test_modelo_721_deadline_windows_cite_article_4_not_content_article_3() -> None:
    _, revision, _ = _modelo_721()

    assert len(revision.deadline_windows) == 3
    for window in revision.deadline_windows:
        assert "orden-hfp-886-2023:art-4" in window.legal_refs
        assert "orden-hfp-886-2023:art-3" not in window.legal_refs
        if window.filing_year >= 2024:
            assert "orden-hac-1504-2024:df-unica" in window.legal_refs


def test_modelo_721_casillas_are_grounded_in_original_and_amended_boe_layouts() -> None:
    _, revision, _ = _modelo_721()

    assert revision.casillas
    for casilla in revision.casillas:
        assert "boe-modelo-721-2023-layout" in casilla.source_refs
        assert "boe-modelo-721-2024-layout" in casilla.source_refs
        assert "aeat-dr-721" not in casilla.source_refs
