"""Modelo 131 registry behaviour for objective-estimation instalment filings."""

from __future__ import annotations

from typing import Any

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, build_snapshot
from .._text import normalise_corpus_text
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_COMMON_SURFACES = {
    "approval",
    "calculation",
    "export",
    "extractor",
    "filing",
    "portal",
    "reconciliation",
    "review",
    "verification",
    "workflow",
}
_EXTRACTION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    [
        "rd-439-2007:art-110",
        "rd-439-2007:art-95",
    ]
)
_ORDEN_EHA_672_ART_1 = "orden-eha-672-2007:art-1"
_ORDEN_EHA_672_ART_3 = "orden-eha-672-2007:art-3"
_M131_REVISION_ORDER_REFS = {
    "2024": "orden-hfp-1359-2023:art-4",
    "2025": "orden-hac-1347-2024:art-4",
    "2026": "orden-hac-1425-2025:art-4",
}


def _collect_legal_refs(value: object) -> set[str]:
    if isinstance(value, dict):
        collected = set()
        refs = value.get("legal_refs")
        if isinstance(refs, (list, tuple)):
            collected.update(str(ref) for ref in refs)
        for child in value.values():
            collected.update(_collect_legal_refs(child))
        return collected
    if isinstance(value, (list, tuple)):
        collected = set()
        for child in value:
            collected.update(_collect_legal_refs(child))
        return collected
    return set()


def _refs_by_id(items: tuple[Any, ...]) -> dict[str, tuple[str, ...]]:
    return {
        str(item.id): tuple(str(ref) for ref in item.legal_refs)
        for item in items
    }


@pytest.fixture(scope="module")
def modelo_131_registry():
    return _committed_modelo("131")


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (2023, _COMMON_SURFACES),
        (2024, _COMMON_SURFACES),
        (2025, _COMMON_SURFACES),
        (2026, _COMMON_SURFACES | {"deadline"}),
    ],
)
def test_modelo_131_validated_snapshot_owns_workflow_surfaces(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    modelo, catalogues = modelo_131_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= required_surfaces
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_131_extraction_profile_legal_refs_match_target_casillas(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    modelo, _ = modelo_131_registry
    for revision in modelo.revisions.values():
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        assert revision.extraction_profiles, revision.id
        for profile in revision.extraction_profiles:
            target_refs = frozenset(
                legal_ref
                for target in profile.target_casillas
                for legal_ref in casillas_by_id[target.casilla_id].legal_refs
            )
            assert target_refs == _EXTRACTION_PROFILE_TARGET_LEGAL_REFS
            assert frozenset(profile.legal_refs) == _EXTRACTION_PROFILE_TARGET_LEGAL_REFS


def test_orden_eha_672_catalogue_splits_modelo_130_and_131_articles(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    _, catalogues = modelo_131_registry
    art_1 = catalogues.legal[_ORDEN_EHA_672_ART_1]
    art_3 = catalogues.legal[_ORDEN_EHA_672_ART_3]

    assert art_1.article == "1"
    assert art_1.corpus_ref.endswith("#a1")
    assert "Aprobación del modelo 130" in art_1.required_text
    assert "Actividades económicas en estimación directa" in art_1.required_text
    assert "código 130" in art_1.required_text
    assert "131" not in " ".join(art_1.required_text)

    assert art_3.article == "3"
    assert art_3.corpus_ref.endswith("#a3")
    assert "Aprobación del modelo 131" in art_3.required_text
    assert "Actividades económicas en estimación objetiva" in art_3.required_text
    assert "código 131" in art_3.required_text

    for reference in (art_1, art_3):
        corpus_path = bundled_path() / reference.corpus_ref.split("#", 1)[0]
        corpus_text = normalise_corpus_text(corpus_path.read_text(encoding="utf-8"))
        for required_text in reference.required_text:
            assert normalise_corpus_text(required_text) in corpus_text


def test_modelo_131_registry_uses_approval_article_3_not_modelo_130_article_1(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    modelo, _ = modelo_131_registry
    legal_refs = _collect_legal_refs(modelo.model_dump())

    assert _ORDEN_EHA_672_ART_3 in legal_refs
    assert _ORDEN_EHA_672_ART_1 not in legal_refs


def test_modelo_131_current_workbook_parity_refs_carry_revision_order(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    modelo, _ = modelo_131_registry

    for revision_id, order_ref in _M131_REVISION_ORDER_REFS.items():
        revision = modelo.revisions[revision_id]
        assert revision.workbook_parity_refs, revision_id
        for parity_ref in revision.workbook_parity_refs:
            assert order_ref in parity_ref.legal_refs, (
                f"{parity_ref.id} must cite {order_ref} so DR parity is grounded "
                f"in the Modelo 131 order for revision {revision_id}"
            )


def test_modelo_100_cross_modelo_131_refs_use_approval_article_3() -> None:
    modelo_100, _ = _committed_modelo("100")

    revision_2024 = modelo_100.revisions["2024"]
    binding_refs_2024 = _refs_by_id(revision_2024.bindings)
    relation_refs_2024 = _refs_by_id(revision_2024.relations)
    dependency_refs_2024 = _refs_by_id(revision_2024.dependency_classifications)
    formula_refs_2024 = _refs_by_id(revision_2024.formulas)
    construct_refs_2024 = _refs_by_id(revision_2024.constructs)

    for refs in (
        binding_refs_2024["renta-2024-modelo-131-pagos-fraccionados"],
        relation_refs_2024["renta-2024-rel-131-pagos-fraccionados"],
        dependency_refs_2024["renta-2024-dep-131"],
    ):
        assert _ORDEN_EHA_672_ART_3 in refs
        assert _ORDEN_EHA_672_ART_1 not in refs
    assert {_ORDEN_EHA_672_ART_1, _ORDEN_EHA_672_ART_3}.issubset(
        formula_refs_2024["renta-2024-pagos-fraccionados-ingresados"]
    )
    assert {_ORDEN_EHA_672_ART_1, _ORDEN_EHA_672_ART_3}.issubset(
        construct_refs_2024["renta-2024-dependent-modelos"]
    )

    revision_2025 = modelo_100.revisions["2025"]
    binding_refs_2025 = _refs_by_id(revision_2025.bindings)
    relation_refs_2025 = _refs_by_id(revision_2025.relations)
    dependency_refs_2025 = _refs_by_id(revision_2025.dependency_classifications)
    construct_refs_2025 = _refs_by_id(revision_2025.constructs)

    for refs in (
        binding_refs_2025["renta-2025-modelo-131-pagos-fraccionados"],
        relation_refs_2025["renta-2025-rel-131-pagos-fraccionados"],
        dependency_refs_2025["renta-2025-dep-131"],
    ):
        assert _ORDEN_EHA_672_ART_3 in refs
        assert _ORDEN_EHA_672_ART_1 not in refs
    for construct_id in (
        "renta-dependent-modelos",
        "renta-payments-retentions",
        "renta-economic-activities",
    ):
        assert {_ORDEN_EHA_672_ART_1, _ORDEN_EHA_672_ART_3}.issubset(construct_refs_2025[construct_id])
