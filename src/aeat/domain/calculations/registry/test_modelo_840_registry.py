"""Tests for committed Modelo 840 registry foundation."""

from __future__ import annotations

import re
from functools import lru_cache

import pytest
from pdfminer.high_level import extract_text

from aeat.core.resources import bundled_path

from . import (
    RegistryValidator,
    build_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@lru_cache(maxsize=1)
def _load_modelo_840():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "840")
    return modelo, catalogues


_FORBIDDEN_REMOTE_ACTIONS = frozenset(
    [
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    ]
)


def test_committed_modelo_840_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_840()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2003-y-siguientes"}


@pytest.mark.parametrize(
    "filing_year",
    [2003, 2010, 2018, 2024, 2026],
)
def test_committed_modelo_840_resolves_revision_by_filing_year(filing_year: int) -> None:
    modelo, catalogues = _load_modelo_840()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )
    assert snapshot.revision.id == "2003-y-siguientes"


def test_committed_modelo_840_is_informative_only() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        assert revision.formulas == (), revision.id
        assert revision.relations == (), revision.id
        for casilla in revision.casillas:
            assert casilla.input_kind in {"informational", "manual"}, casilla.id


def test_committed_modelo_840_workbook_parity_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_840()
    for revision in modelo.revisions.values():
        ref = next(
            (r for r in revision.workbook_parity_refs if r.workbook_source == "aeat-dr-840"),
            None,
        )
        assert ref is not None, revision.id
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        source = catalogues.sources["aeat-dr-840"]
        assert source.evidence_tier == "layout_authority"
        artefact_path = bundled_path() / source.corpus_path
        assert artefact_path.is_file(), artefact_path


def test_committed_modelo_840_printed_form_source_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_840()
    source = catalogues.sources["aeat-modelo-840-printed-form"]

    assert source.authority == "aeat"
    assert source.kind == "manual_pdf"
    assert source.source_url == (
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G323/mod840e_es_es.pdf"
    )

    artefact_path = bundled_path() / source.corpus_path
    assert artefact_path.is_file(), artefact_path
    assert source.id in modelo.source_refs
    for revision in modelo.revisions.values():
        assert source.id in revision.source_refs


def test_committed_modelo_840_pdf_profile_labels_are_grounded_in_printed_form() -> None:
    modelo, catalogues = _load_modelo_840()
    source = catalogues.sources["aeat-modelo-840-printed-form"]
    official_text = extract_text(bundled_path() / source.corpus_path)
    expected_printed_labels = {
        "decl.ejercicio": "14 Ejercicio",
        "decl.tipo-declaracion": "15 Declaración de",
    }

    for revision in modelo.revisions.values():
        profile = next(
            profile for profile in revision.extraction_profiles if profile.id == "modelo-840-declaracion-pdf"
        )
        assert profile.source_refs == ("aeat-modelo-840-printed-form", "boe-modelo-840-2003-form")
        for target in profile.target_casillas:
            assert target.label_pattern is not None
            assert expected_printed_labels[target.casilla_id] in official_text
            assert re.search(rf"(?m)^\s*{target.label_pattern}", official_text), target.casilla_id


def test_committed_modelo_840_static_cross_reference_forbids_remote_writes() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "static_official_documentation")
        assert decision.requires_authentication is False
        assert decision.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_840_authenticated_read_surface_is_read_only_and_guarded() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "authenticated_read_surface")
        assert decision.requires_authentication is True
        assert decision.requires_aeat_authorization is True
        assert decision.synthetic_data_allowed is False
        assert set(decision.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}, revision.id
        assert set(decision.allowed_hosts) == {
            "www1.agenciatributaria.gob.es",
            "www6.agenciatributaria.gob.es",
        }, revision.id
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_840_filing_schedule_is_ad_hoc() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        assert revision.filing_schedules, revision.id
        for schedule in revision.filing_schedules:
            # IAE is event-driven (alta/variación/baja within 1 month per RD 243/1995)
            # rather than a fixed annual plazo; cadence is ad_hoc with the standard 0A
            # ejercicio reference.
            assert schedule.period_kind == "ad_hoc"
            assert schedule.periods == ("0A",)


def test_committed_modelo_840_construct_includes_revision_members() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1, revision.id
        construct = revision.constructs[0]
        assert construct.casillas == tuple(c.id for c in revision.casillas)
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {"portal", "filing", "extractor", "verification"} <= link_surfaces, revision.id
