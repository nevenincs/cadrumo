"""Modelo 721 registry grounding regressions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from .....core.resources import bundled_path
from .....tests import REPO_ROOT
from .._corpus_catalogue import verify_source_file
from .._legal import verify_legal_catalogue
from .._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_721() -> tuple[ModeloDefinition, ModeloRevision, RegistryCatalogues]:
    modelo, catalogues = _committed_modelo("721")
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
    } <= set(revision.source_refs)

    all_modelo_strings = set(_strings(modelo.model_dump(mode="json")))
    assert "aeat-dr-721" not in all_modelo_strings
    assert "boe-modelo-721-2023-form" not in all_modelo_strings
    assert "ley-11-2021:da-10" not in all_modelo_strings
    assert "boe-modelo-721-2023-form" not in catalogues.sources
    assert catalogues.sources["aeat-modelo-721-procedure"].evidence_tier == "official_source_guidance"

    workbook_refs = {reference.id: reference for reference in revision.workbook_parity_refs}
    assert workbook_refs["modelo-721-dr-2023"].workbook_source == "boe-modelo-721-2023-layout"
    assert workbook_refs["modelo-721-dr-2024"].workbook_source == "boe-modelo-721-2024-layout"

    for source_id in ("boe-modelo-721-2023-layout", "boe-modelo-721-2024-layout"):
        source = catalogues.sources[source_id]
        assert source.authority == "boe"
        assert source.evidence_tier == "layout_authority"
        assert source.kind == "form_spec"
        assert source.corpus_path.endswith(".pdf")
        verify_source_file(REPO_ROOT, source)


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


def test_modelo_721_threshold_continuity_has_registry_parameters_without_calculation_surface() -> None:
    modelo, revision, _ = _modelo_721()

    link_ids_by_surface = {link.surface: link.id for link in revision.application_links}
    expected_link_ids_by_surface = {
        "portal": "modelo-721-portal",
        "filing": "modelo-721-filing",
        "extractor": "modelo-721-extractor",
        "deadline": "modelo-721-deadline",
    }

    assert "calculation" not in link_ids_by_surface
    assert "modelo-721-calculation" not in revision.constructs[0].application_links
    assert expected_link_ids_by_surface.items() <= link_ids_by_surface.items()
    assert {parameter.id for parameter in revision.parameters} >= {
        "modelo-721-asset-declaration-threshold-eur",
        "modelo-721-redeclaration-increment-threshold-eur",
    }
    assert modelo.id == "721"


def test_modelo_721_redeclaration_is_not_authored_as_scalar_previous_filing_binding() -> None:
    """M721 token continuity is row-set advisory evidence, not scalar previous_filing.

    The previous_filing resolver folds a casilla-value mapping to one Decimal per
    binding. Modelo 721 repeats the same token casillas per custodian/token row, so
    a scalar binding would lose the row identity needed for the re-declaration
    baseline. Reintroducing this as registry previous_filing requires a row-set
    selector, not the retired source_output key.
    """
    _, revision, _ = _modelo_721()

    previous_filing_bindings = [binding.id for binding in revision.bindings if binding.source == "previous_filing"]
    all_binding_strings = set(_strings(tuple(binding.model_dump(mode="json") for binding in revision.bindings)))

    assert previous_filing_bindings == []
    assert "source_output" not in all_binding_strings
