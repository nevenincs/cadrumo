"""Modelo 131 registry behaviour for objective-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from .....core.corpus_text import normalise_corpus_text
from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ..ids import LegalRefId
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import build_snapshot
from ..temporal import select_revision
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
    "workflow",
}
_EXTRACTION_PROFILE_TARGET_LEGAL_REFS: frozenset[LegalRefId] = frozenset(
    [
        "rd-439-2007:art-110",
        "rd-439-2007:art-95",
    ]
)
_ORDEN_EHA_672_ART_1: LegalRefId = "orden-eha-672-2007:art-1"
_ORDEN_EHA_672_ART_3: LegalRefId = "orden-eha-672-2007:art-3"
_M131_REVISION_ORDER_REFS: dict[str, LegalRefId] = {
    "2024": "orden-hfp-1359-2023:art-4",
    "2025": "orden-hac-1347-2024:art-4",
    "2026": "orden-hac-1425-2025:art-4",
}
_M131_LAYOUT_SOURCE = "boe-modelo-131-2007-form"
_M131_PROCEDURE_SOURCE = "aeat-modelo-131-procedure"
_M131_INSTRUCTIONS_SOURCE = "aeat-modelo-131-instructions"


def _collect_legal_refs(value: object) -> set[LegalRefId]:
    if isinstance(value, dict):
        collected = set()
        refs = value.get("legal_refs")
        if isinstance(refs, (list, tuple)):
            collected.update(ref for ref in refs if isinstance(ref, str))
        for child in value.values():
            collected.update(_collect_legal_refs(child))
        return collected
    if isinstance(value, (list, tuple)):
        collected = set()
        for child in value:
            collected.update(_collect_legal_refs(child))
        return collected
    return set()


def _source_window_covers(source: Any, revision: Any) -> bool:
    """Report whether ``source``'s applicability window overlaps ``revision``'s life."""
    if source.applies_to is not None and source.applies_to < revision.valid_from:
        return False
    return not (
        source.applies_from is not None and revision.valid_to is not None and source.applies_from > revision.valid_to
    )


def _refs_by_id(items: tuple[Any, ...]) -> dict[str, tuple[LegalRefId, ...]]:
    return {str(item.id): tuple(item.legal_refs) for item in items}


@pytest.fixture(scope="module")
def modelo_131_registry():
    return _committed_modelo("131")


def test_modelo_131_supported_year_2022_deadline_census_dates_sources_and_ownership(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    modelo, catalogues = modelo_131_registry
    revision = modelo.revisions["2019-2023"]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}
    expected_2022 = {
        "1T": (date(2022, 4, 1), date(2022, 4, 20), date(2022, 4, 15), "aeat-calendario-contribuyente-2022"),
        "2T": (date(2022, 7, 1), date(2022, 7, 20), date(2022, 7, 15), "aeat-calendario-contribuyente-2022"),
        "3T": (date(2022, 10, 1), date(2022, 10, 20), date(2022, 10, 15), "aeat-calendario-contribuyente-2022"),
        "4T": (date(2023, 1, 1), date(2023, 1, 30), date(2023, 1, 25), "aeat-calendario-contribuyente-2023"),
    }

    assert len(revision.deadline_windows) == len(windows) == 8
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}
    assert {period for year, period in windows if year == 2022} == set(expected_2022)
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for source_ref in {"aeat-calendario-contribuyente-2022", "aeat-calendario-contribuyente-2023"}:
        source = catalogues.sources[source_ref]
        assert (source.authority, source.evidence_tier) == ("aeat", "official_source_guidance")
        assert source_ref in revision.source_refs
        assert source_ref in revision.constructs[0].source_refs
        assert (bundled_path() / source.corpus_path).is_file()

    projected = bundled_authority().deadline_windows(2022, modelos=("131",))
    assert len(projected) == 4
    assert {window.period.registry_token for _, _, window in projected} == set(expected_2022)

    for period, (opens_on, closes_on, payment_cutoff_on, calendar_ref) in expected_2022.items():
        window = windows[(2022, period)]
        assert select_revision(modelo, filing_year=2022, period=period) is revision
        assert window.id == f"modelo-131-2022-{period.lower()}"
        assert window.filing_year == window.period.filing_year == 2022
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (
            opens_on,
            closes_on,
            payment_cutoff_on,
        )
        assert set(window.source_refs) == {"aeat-modelo-131-instructions", calendar_ref}


def test_modelo_131_guidance_and_layout_sources_are_separated(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    modelo, catalogues = modelo_131_registry
    procedure = catalogues.sources[_M131_PROCEDURE_SOURCE]
    instructions = catalogues.sources[_M131_INSTRUCTIONS_SOURCE]
    layout = catalogues.sources[_M131_LAYOUT_SOURCE]

    assert _M131_PROCEDURE_SOURCE in modelo.source_refs
    assert _M131_INSTRUCTIONS_SOURCE in modelo.source_refs
    assert _M131_LAYOUT_SOURCE in modelo.source_refs
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert instructions.evidence_tier == "official_source_guidance"
    assert instructions.authority == "aeat"
    assert instructions.kind == "instructions"
    assert (bundled_path() / instructions.corpus_path).is_file()
    assert layout.evidence_tier == "layout_authority"
    assert layout.authority == "boe"
    assert layout.kind == "form_spec"

    for revision in modelo.revisions.values():
        assert _M131_LAYOUT_SOURCE in revision.source_refs
        assert _M131_INSTRUCTIONS_SOURCE in revision.source_refs
        # The sede procedure ficha is required only of the revisions it actually
        # governs. The bundled page states "Ejercicio 2026" and nothing earlier,
        # so its applies_from is 2026-01-01, and a 2024 or 2025 revision citing
        # it would claim grounding from a page that documents a later campaign --
        # which `_check_revision_scoped_source_windows` refuses at snapshot build.
        # Requiring it unconditionally made this test demand the refusal.
        if _source_window_covers(procedure, revision):
            assert _M131_PROCEDURE_SOURCE in revision.source_refs
        else:
            assert _M131_PROCEDURE_SOURCE not in revision.source_refs
        for parameter in revision.parameters:
            for citation in parameter.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
        for formula in revision.formulas:
            for citation in formula.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
        for binding in revision.bindings:
            for citation in binding.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"


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
    assert {_ORDEN_EHA_672_ART_1, _ORDEN_EHA_672_ART_3}.issubset(construct_refs_2024["renta-2024-dependent-modelos"])

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
