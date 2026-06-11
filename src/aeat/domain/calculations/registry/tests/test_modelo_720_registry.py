"""Tests for committed Modelo 720 registry foundation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import cast

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .. import (
    InputKind,
    ModeloRevision,
    RegistryValidator,
    build_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


@lru_cache(maxsize=1)
def _load_modelo_720():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "720")
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
    ],
)


def test_committed_modelo_720_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_720()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2013-y-siguientes"}


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2012, "2013-y-siguientes"),
        (2018, "2013-y-siguientes"),
        (2024, "2013-y-siguientes"),
    ],
)
def test_committed_modelo_720_resolves_revision_by_filing_year(
    filing_year: int,
    expected_revision: str,
) -> None:
    modelo, catalogues = _load_modelo_720()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )
    assert snapshot.revision.id == expected_revision


def test_committed_modelo_720_is_informative_only() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert revision.formulas == (), (
            f"revision {revision.id!r} declares calculation formulas; "
            "Modelo 720 is informative-only and must not own filing-grade calculations"
        )
        assert revision.relations == (), (
            f"revision {revision.id!r} declares cross-model relations; Modelo 720 is informative-only"
        )
        for casilla in revision.casillas:
            assert casilla.input_kind in {InputKind.INFORMATIONAL, InputKind.MANUAL}, casilla.id


def test_committed_modelo_720_workbook_parity_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_720()
    for revision in modelo.revisions.values():
        ref = next(
            (r for r in revision.workbook_parity_refs if r.workbook_source == "aeat-dr-720"),
            None,
        )
        assert ref is not None, revision.id
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        source = catalogues.sources["aeat-dr-720"]
        assert source.evidence_tier == "layout_authority"
        artefact_path = bundled_path() / source.corpus_path
        assert artefact_path.is_file(), artefact_path


def test_committed_modelo_720_static_cross_reference_forbids_remote_writes() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "static_official_documentation")
        assert decision.requires_authentication is False
        assert decision.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_720_authenticated_read_surface_is_read_only_and_guarded() -> None:
    modelo, _ = _load_modelo_720()
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


def test_committed_modelo_720_declaration_pdf_extraction_profile_targets_declarante_casillas() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        pdf_profiles = [profile for profile in revision.extraction_profiles if profile.surface == "declaracion_pdf"]
        assert pdf_profiles, revision.id
        for profile in pdf_profiles:
            assert profile.parser == "aeat.adapters.inbound.declaracion.parse_declaracion"
            assert profile.confidence == "strict"
            assert profile.corpus_round_trip_verified is True
            assert profile.failure_semantics == "fail_hard"
            assert {t.casilla_id for t in profile.target_casillas} <= casilla_ids


def test_committed_modelo_720_verification_expectation_is_informative_strict() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        assert revision.verification_expectations, revision.id
        for expectation in revision.verification_expectations:
            assert expectation.tolerance == 0
            assert expectation.rounding == "none"
            assert expectation.discrepancy_causes == ("extraction_unreliable",)
            assert set(expectation.computed_casillas) <= casilla_ids


def test_committed_modelo_720_filing_schedule_is_annual() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert revision.filing_schedules, revision.id
        for schedule in revision.filing_schedules:
            assert schedule.period_kind == "annual"
            assert schedule.periods == ("0A",)


@pytest.mark.parametrize(
    ("filing_year", "expected_open", "expected_close"),
    [
        # First ejercicio (2012) had a transitional plazo until 30 April 2013 per Orden HAP/72/2013 DT
        (2012, date(2013, 2, 1), date(2013, 4, 30)),
        # Subsequent ejercicios run from 1 January to 31 March of the following year per art 7
        (2013, date(2014, 1, 1), date(2014, 3, 31)),
        (2018, date(2019, 1, 1), date(2019, 3, 31)),
        (2024, date(2025, 1, 1), date(2025, 3, 31)),
    ],
)
def test_committed_modelo_720_deadline_window_is_january_to_march_following_ejercicio(
    filing_year: int,
    expected_open: date,
    expected_close: date,
) -> None:
    modelo, _ = _load_modelo_720()
    windows = [
        window
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.filing_year == filing_year
    ]
    assert len(windows) == 1, filing_year
    window = windows[0]
    assert window.period_kind == "annual"
    assert window.opens_on == expected_open
    assert window.closes_on == expected_close


def _layout_bindings_for(revision: ModeloRevision, record_name: str):
    return tuple(
        binding
        for binding in revision.bindings
        if isinstance(binding.selector.get("record"), str) and binding.selector["record"] == record_name
    )


def test_committed_modelo_720_type_1_bindings_target_declarante_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "type_1")
        assert bindings, revision.id
        # Type 1 starts at position 1 (TIPO DE REGISTRO constant) per Orden HAP/72/2013 anexo
        first_offset = min(int(cast(int, b.selector["offset"])) for b in bindings)
        assert first_offset == 1, first_offset


def test_committed_modelo_720_type_2_bindings_target_detalle_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "type_2")
        assert bindings, revision.id
        first_offset = min(int(cast(int, b.selector["offset"])) for b in bindings)
        assert first_offset == 1, first_offset
        # Type 2 closes at position 480 (PORCENTAJE DE PARTICIPACIÓN, last field of detalle record)
        ranges = sorted((int(cast(int, b.selector["offset"])), int(cast(int, b.selector["length"]))) for b in bindings)
        last_offset, last_length = ranges[-1]
        assert last_offset + last_length - 1 == 480, last_offset + last_length - 1


def test_committed_modelo_720_export_layout_uses_repeating_detalle_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        layout = revision.export_layouts[0]
        type_1 = next(r for r in layout.records if r.record_type == "type_1")
        type_2 = next(r for r in layout.records if r.record_type == "type_2")
        assert type_1.binding_record == "type_1"
        assert type_1.repeat is None
        assert type_2.binding_record == "type_2"
        assert type_2.repeat == "binding_rows"


def test_committed_modelo_720_construct_includes_revision_members() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1, revision.id
        construct = revision.constructs[0]
        assert construct.casillas == tuple(c.id for c in revision.casillas)
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)
        revision_binding_ids = {binding.id for binding in revision.bindings}
        assert revision_binding_ids <= set(construct.bindings)
        assert construct.export_layouts == tuple(layout.id for layout in revision.export_layouts)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {
            "portal",
            "filing",
            "extractor",
            "verification",
            "deadline",
            "export",
            "review",
            "approval",
            "reconciliation",
            "workflow",
        } <= link_surfaces, revision.id


def test_modelo_720_workflow_surfaces_are_snapshot_gated_and_construct_scoped() -> None:
    modelo, _ = _load_modelo_720()
    required_surfaces = {"review", "approval", "reconciliation", "workflow"}
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        linked_by_surface = {link.surface: link for link in revision.application_links}
        assert required_surfaces <= set(linked_by_surface), revision.id
        for link in revision.application_links:
            if link.surface not in required_surfaces:
                continue
            assert link.requires_snapshot is True
            assert link.id in construct.application_links
