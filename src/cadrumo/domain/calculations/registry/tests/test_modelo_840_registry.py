"""Tests for committed Modelo 840 registry foundation."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _load_modelo_840():
    return _committed_modelo("840")


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
    ],
)
_DECLARATION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    [
        "orden-hac-2572-2003:apartado-1",
        "orden-hac-2572-2003:apartado-6",
    ]
)


def test_committed_modelo_840_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_840()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2003-y-siguientes"}


def test_committed_modelo_840_resolves_revision_by_filing_year() -> None:
    modelo, catalogues = _load_modelo_840()
    for filing_year in (2003, 2010, 2018, 2024, 2026):
        # Modelo 840 is the IAE censal declaration: informative, filed on AEAT's
        # own surface, declaring no export layout, and graded `applicability`
        # accordingly. Building at the FILING default refuses on the missing
        # layout before this test's subject -- which revision a filing year
        # resolves to -- is ever reached. Ask for the rung the law-selected
        # revision declares, so a later promotion of 840 carries without an edit.
        revision = select_revision(modelo, filing_year=filing_year, period="0A")
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period="0A",
            grade=revision.effective_authority_grade,
        )
        assert snapshot.revision.id == "2003-y-siguientes", filing_year
        assert snapshot.revision.orden_aplicabilidad == ("orden-hac-2572-2003:apartado-1",)


def test_committed_modelo_840_is_informative_only() -> None:
    modelo, _ = _load_modelo_840()
    assert modelo.calculation_class == "informative", (
        "Modelo 840 must be declared calculation_class='informative' in its manifest"
    )
    for revision in modelo.revisions.values():
        assert revision.formulas == (), revision.id
        assert revision.relations == (), revision.id
        for casilla in revision.casillas:
            assert casilla.input_kind in {InputKind.INFORMATIONAL, InputKind.MANUAL}, casilla.id


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


def test_committed_modelo_840_guidance_and_layout_sources_are_separated() -> None:
    modelo, catalogues = _load_modelo_840()

    assert "aeat-modelo-840-procedure" in modelo.source_refs
    procedure = catalogues.sources["aeat-modelo-840-procedure"]
    assert procedure.evidence_tier == "official_source_guidance"
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert catalogues.sources["boe-modelo-840-2003-form"].evidence_tier == "layout_authority"


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
            _WWW1_HOST,
            _WWW6_HOST,
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
        # Membership, not sequence. The construct must carry every casilla the
        # revision declares and no other, with no duplicates; the ORDER it
        # lists them in is incidental and broke this assertion the moment the
        # sujeto set was authored, without any member being lost.
        revision_casilla_ids = tuple(c.id for c in revision.casillas)
        assert set(construct.casilla_ids) == set(revision_casilla_ids), revision.id
        assert len(construct.casilla_ids) == len(revision_casilla_ids), revision.id
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {"portal", "filing", "extractor"} <= link_surfaces, revision.id


def test_committed_modelo_840_declaration_pdf_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_840()
    for revision in modelo.revisions.values():
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        pdf_profiles = [profile for profile in revision.extraction_profiles if profile.surface == "declaracion_pdf"]
        assert pdf_profiles, revision.id
        for profile in pdf_profiles:
            target_refs = frozenset(
                legal_ref
                for target in profile.target_casillas
                for legal_ref in casillas_by_id[target.casilla_id].legal_refs
            )
            assert target_refs == _DECLARATION_PROFILE_TARGET_LEGAL_REFS
            assert set(profile.legal_refs) == _DECLARATION_PROFILE_TARGET_LEGAL_REFS
