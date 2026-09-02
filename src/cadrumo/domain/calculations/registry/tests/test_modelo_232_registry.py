"""Tests for committed Modelo 232 registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.export_layout_format import ExportLayoutFormat
from .....core.resources.bundled_data import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .._validate import RegistryValidator
from ..schema import ModeloRevision
from ..schema_exports import ExportRecordDefinition
from ..schema_input_kind import InputKind
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _load_modelo_232():
    return _committed_modelo("232")


def test_committed_modelo_232_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_232()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2018-y-siguientes", "2016-2017"}


def test_committed_modelo_232_resolves_revision_by_filing_year() -> None:
    modelo, _ = _load_modelo_232()
    cases = (
        (2016, "2016-2017"),
        (2017, "2016-2017"),
        (2018, "2018-y-siguientes"),
        (2024, "2018-y-siguientes"),
    )
    for filing_year, expected_revision in cases:
        selected = select_revision(modelo, filing_year=filing_year, period="0A")
        assert selected.id == expected_revision
        assert selected.orden_aplicabilidad == ("orden-hfp-816-2017:art-1",)


def test_committed_modelo_232_is_informative_only() -> None:
    # The registry-wide invariant in RegistryValidator._validate_informative_class_invariant
    # enforces these same contracts for every modelo whose calculation_class == "informative".
    # This per-modelo assertion is kept as defense-in-depth to surface Modelo 232 violations
    # with targeted diagnostics.
    modelo, _ = _load_modelo_232()
    assert modelo.calculation_class == "informative", (
        "Modelo 232 must be declared calculation_class='informative' in its manifest"
    )
    for revision in modelo.revisions.values():
        assert revision.formulas == (), (
            f"revision {revision.id!r} declares calculation formulas; "
            "Modelo 232 is informative-only and must not own filing-grade calculations"
        )
        assert revision.relations == (), (
            f"revision {revision.id!r} declares cross-model relations; "
            "Modelo 232 is informative-only and Modelo 200 dependency is evidence-only"
        )
        for casilla in revision.casillas:
            assert casilla.input_kind in {InputKind.INFORMATIONAL, InputKind.MANUAL}, (
                f"casilla {casilla.id!r} has input_kind={casilla.input_kind!r}; "
                "Modelo 232 casillas must be informational/manual without computation"
            )


def test_committed_modelo_232_workbook_parity_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_232()
    assert catalogues.sources["aeat-modelo-232-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-232-2017-form"].evidence_tier == "layout_authority"
    expected_sources = {
        "2018-y-siguientes": "aeat-dr-232-2018",
        "2016-2017": "aeat-dr-232-2016",
    }
    for revision_id, expected_source in expected_sources.items():
        revision = modelo.revisions[revision_id]
        ref = next(
            (r for r in revision.workbook_parity_refs if r.workbook_source == expected_source),
            None,
        )
        assert ref is not None, f"{revision_id}: no parity ref for {expected_source}"
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        source = catalogues.sources[expected_source]
        assert source.evidence_tier == "layout_authority"
        artefact_path = bundled_path() / source.corpus_path
        assert artefact_path.is_file(), artefact_path


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
        "ley-27-2014:art-19",
        "ley-58-2003:art-93",
        "orden-hfp-816-2017:art-1",
        "orden-hfp-816-2017:art-3",
    ]
)


def test_committed_modelo_232_static_cross_reference_forbids_remote_writes() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "static_official_documentation")
        assert decision.requires_authentication is False
        assert decision.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_232_authenticated_read_surface_is_read_only_and_guarded() -> None:
    modelo, _ = _load_modelo_232()
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


def test_committed_modelo_232_declaration_pdf_extraction_profile_targets_declarante_casillas() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        pdf_profiles = [profile for profile in revision.extraction_profiles if profile.surface == "declaracion_pdf"]
        assert pdf_profiles, revision.id
        for profile in pdf_profiles:
            assert profile.parser == "cadrumo.adapters.inbound.declaracion.parser.parse_declaracion"
            assert profile.confidence == "strict"
            assert profile.failure_semantics == "fail_hard"
            assert {t.casilla_id for t in profile.target_casillas} <= casilla_ids


def test_committed_modelo_232_declaration_pdf_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_232()
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


def test_committed_modelo_232_verification_expectation_is_informative_strict() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        assert revision.verification_expectations, revision.id
        for expectation in revision.verification_expectations:
            assert expectation.tolerance == 0, (revision.id, expectation.id)
            assert expectation.rounding == "none"
            assert expectation.discrepancy_causes == ("extraction_unreliable",)
            assert set(expectation.computed_casilla_ids) <= casilla_ids


def test_committed_modelo_232_construct_includes_profile_and_expectation_and_extractor_link() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1, revision.id
        construct = revision.constructs[0]
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {
            "portal",
            "filing",
            "extractor",
            "deadline",
            "review",
            "approval",
            "reconciliation",
            "workflow",
        } <= link_surfaces, revision.id


def test_modelo_232_workflow_surfaces_are_snapshot_gated_and_construct_scoped() -> None:
    modelo, _ = _load_modelo_232()
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


def test_committed_modelo_232_deadline_window_is_november_following_ejercicio() -> None:
    modelo, _ = _load_modelo_232()
    windows_by_year = {
        window.filing_year: window for revision in modelo.revisions.values() for window in revision.deadline_windows
    }
    cases = (
        (2016, date(2017, 11, 1), date(2017, 11, 30)),
        (2017, date(2018, 11, 1), date(2018, 11, 30)),
        (2018, date(2019, 11, 1), date(2019, 11, 30)),
        (2023, date(2024, 11, 1), date(2024, 11, 30)),
        (2025, date(2026, 11, 1), date(2026, 11, 30)),
        (2026, date(2027, 11, 1), date(2027, 11, 30)),
    )
    for filing_year, expected_open, expected_close in cases:
        window = windows_by_year[filing_year]
        assert window.period_kind == "annual"
        assert window.opens_on == expected_open
        assert window.closes_on == expected_close
        assert window.payment_cutoff_on is None


def test_committed_modelo_232_deadline_windows_are_unique_by_filing_year() -> None:
    modelo, _ = _load_modelo_232()
    seen: set[int] = set()
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            assert window.filing_year not in seen, f"duplicate deadline window for filing_year {window.filing_year}"
            seen.add(window.filing_year)
    # Modelo 232 was created by Orden HFP/816/2017 effective for ejercicio 2016 onwards;
    # both revision boundaries (2016-2017 and 2018+) must have at least one window.
    assert any(year <= 2017 for year in seen)
    assert any(year >= 2018 for year in seen)


def test_committed_modelo_232_filing_schedule_is_annual() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        assert revision.filing_schedules, revision.id
        for schedule in revision.filing_schedules:
            assert schedule.period_kind == "annual"
            assert schedule.periods == ("0A",)


def test_committed_modelo_232_construct_includes_deadline_and_schedule_members() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)


_EXPECTED_AUXILIARY_PREFIX_ROLES = (
    "opening_tag",
    "modelo",
    "discriminant",
    "filing_year",
    "period",
    "record_type",
    "aux_opening_tag",
    "pre_program_filler",
    "program_identifier",
    "between_identities_filler",
    "developer_tax_id",
    "post_developer_filler",
    "aux_closing_tag",
)


def test_committed_modelo_232_envelope_export_layout_declares_every_revision_with_fixed_width() -> None:
    """Every revision must publish at least one fixed-width export layout."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        assert revision.export_layouts, revision.id
        assert revision.export_layouts[0].format is ExportLayoutFormat.FIXED_WIDTH, revision.id


def test_committed_modelo_232_layout_declares_the_dr23200_auxiliary_header() -> None:
    """The total-less DR23200 page zero is a typed auxiliary header declaration."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        header = revision.export_layouts[0].auxiliary_envelope_header
        assert header is not None, revision.id
        assert header.record_identity == "DR23200", revision.id
        assert header.prefix_extent == 328, revision.id
        roles = tuple(field.role.value for field in header.prefix_fields)
        assert roles == _EXPECTED_AUXILIARY_PREFIX_ROLES, (revision.id, roles)
        assert sum(field.length for field in header.prefix_fields) == 328, revision.id


def test_committed_modelo_232_record_types_and_extents_match_the_generated_layout() -> None:
    """The two generated records carry the parser-derived record types and extents."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        layout = revision.export_layouts[0]
        records = {record.record_type: record for record in layout.records}
        assert set(records) == {"operaciones-vinculadas", "paraisos-fiscales"}, revision.id
        vinculadas = records["operaciones-vinculadas"]
        assert vinculadas.fields[-1].offset + vinculadas.fields[-1].length - 1 == 1500, revision.id
        paraisos = records["paraisos-fiscales"]
        assert paraisos.fields[-1].offset + paraisos.fields[-1].length - 1 == 3500, revision.id


def test_committed_modelo_232_construct_includes_export_layout_and_export_link() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        export_links = [link for link in revision.application_links if link.surface == "export"]
        assert len(export_links) == 1, revision.id
        assert export_links[0].consumer == "cadrumo.application.filing.export_draft"
        assert export_links[0].id in construct.application_links


_SECTION_3_4_RANGE = (144, 1171)
_SECTION_5_6_RANGE = (13, 3072)


def _record_for(revision: ModeloRevision, record_type: str) -> ExportRecordDefinition:
    return next(record for record in revision.export_layouts[0].records if record.record_type == record_type)


def test_committed_modelo_232_page_01_record_matches_official_layout() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        page_01 = _record_for(revision, "operaciones-vinculadas")
        last_field = page_01.fields[-1]
        assert last_field.offset is not None and last_field.length is not None
        assert last_field.offset + last_field.length - 1 == 1500, revision.id


def test_committed_modelo_232_page_02_record_matches_official_layout() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        page_02 = _record_for(revision, "paraisos-fiscales")
        last_field = page_02.fields[-1]
        assert last_field.offset is not None and last_field.length is not None
        assert last_field.offset + last_field.length - 1 == 3500, revision.id


def _covered_slots(record: ExportRecordDefinition) -> tuple[tuple[int, int], ...]:
    """Every (offset, length) the record covers with a value or a filler."""
    return tuple(
        sorted(
            (field.offset, field.length)
            for field in record.fields
            if field.offset is not None and field.length is not None
        )
    )


def _assert_slots_tile_contiguously(
    record: ExportRecordDefinition, section: tuple[int, int], revision: ModeloRevision
) -> None:
    """The record's bound and filler slots tile its official section with no gaps.

    The Administracion-reserved name slots are fillers by design, so the tiling
    includes them; a gap means a design position neither bound nor filled. Slots
    before the section (the record's own opening tag) are ignored.
    """
    slots = [
        (offset, length)
        for offset, length in _covered_slots(record)
        if offset >= section[0] and offset + length - 1 <= section[1]
    ]
    assert slots, revision.id
    cursor = section[0]
    for offset, length in slots:
        assert offset == cursor, (revision.id, offset, cursor)
        cursor = offset + length
    assert cursor - 1 == section[1], (revision.id, cursor - 1)


def test_committed_modelo_232_section_3_4_bindings_cover_page_01_slots() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        _assert_slots_tile_contiguously(_record_for(revision, "operaciones-vinculadas"), _SECTION_3_4_RANGE, revision)


def test_committed_modelo_232_section_5_6_bindings_cover_page_02_slots() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        _assert_slots_tile_contiguously(_record_for(revision, "paraisos-fiscales"), _SECTION_5_6_RANGE, revision)


def test_committed_modelo_232_construct_includes_layout_bindings() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        revision_binding_ids = {binding.id for binding in revision.bindings}
        assert revision_binding_ids, revision.id
        assert revision_binding_ids <= set(construct.bindings)


def test_committed_modelo_232_declarante_casillas_export_through_page_01_record() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        page_01 = _record_for(revision, "operaciones-vinculadas")
        page_field_ids = {field.id for field in page_01.fields}
        for casilla in revision.casillas:
            # The declarante casillas export through the vinculadas record; the
            # paraiso-fiscal rows export through the second record.
            if not (casilla.section and casilla.section[0] == "declarante"):
                continue
            assert casilla.export_refs, f"casilla {casilla.id!r} missing export_refs"
            for export_ref in casilla.export_refs:
                assert export_ref in page_field_ids, (
                    f"casilla {casilla.id!r} export_ref {export_ref!r} not in page_01 fields"
                )
