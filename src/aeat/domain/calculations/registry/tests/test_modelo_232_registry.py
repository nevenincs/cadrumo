"""Tests for committed Modelo 232 registry foundation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from itertools import pairwise

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .. import (
    CasillaFieldKind,
    DataBindingDefinition,
    ExportRecordDefinition,
    InputKind,
    ModeloRevision,
    RegistryValidator,
    build_snapshot,
    load_registry_tree,
)
from .._binding_selector_utils import selector_as_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


@lru_cache(maxsize=1)
def _load_modelo_232():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "232")
    return modelo, catalogues


def test_committed_modelo_232_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_232()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2018-y-siguientes", "2016-2017"}


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2016, "2016-2017"),
        (2017, "2016-2017"),
        (2018, "2018-y-siguientes"),
        (2024, "2018-y-siguientes"),
    ],
)
def test_committed_modelo_232_resolves_revision_by_filing_year(
    filing_year: int,
    expected_revision: str,
) -> None:
    modelo, catalogues = _load_modelo_232()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )
    assert snapshot.revision.id == expected_revision
    assert snapshot.revision.orden_aplicabilidad == ("orden-hfp-816-2017:art-1",)


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
            assert profile.parser == "aeat.adapters.inbound.declaracion.parse_declaracion"
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
            "verification",
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


@pytest.mark.parametrize(
    ("filing_year", "expected_open", "expected_close"),
    [
        (2016, date(2017, 11, 1), date(2017, 11, 30)),
        (2017, date(2018, 11, 1), date(2018, 11, 30)),
        (2018, date(2019, 11, 1), date(2019, 11, 30)),
        (2023, date(2024, 11, 1), date(2024, 11, 30)),
        (2026, date(2027, 11, 1), date(2027, 11, 30)),
    ],
)
def test_committed_modelo_232_deadline_window_is_november_following_ejercicio(
    filing_year: int,
    expected_open: date,
    expected_close: date,
) -> None:
    modelo, _ = _load_modelo_232()
    windows = [
        window
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.filing_year == filing_year
    ]
    assert len(windows) == 1, f"filing_year {filing_year} resolves to {len(windows)} windows"
    window = windows[0]
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


_EXPECTED_ENVELOPE_FIELD_POSITIONS: dict[str, tuple[int, int, CasillaFieldKind]] = {
    "envelope-open": (1, 2, CasillaFieldKind.LITERAL),
    "envelope-modelo": (3, 3, CasillaFieldKind.LITERAL),
    "envelope-discriminante": (6, 1, CasillaFieldKind.LITERAL),
    "envelope-year": (7, 4, CasillaFieldKind.DRAFT),
    "envelope-period": (11, 2, CasillaFieldKind.LITERAL),
    "envelope-marker": (13, 5, CasillaFieldKind.LITERAL),
    "envelope-aux-open": (18, 5, CasillaFieldKind.LITERAL),
    "envelope-reserved-1": (23, 70, CasillaFieldKind.FILLER),
    "envelope-program-version": (93, 4, CasillaFieldKind.HEADER),
    "envelope-reserved-2": (97, 4, CasillaFieldKind.FILLER),
    "envelope-presenter-nif": (101, 9, CasillaFieldKind.HEADER),
    "envelope-reserved-3": (110, 213, CasillaFieldKind.FILLER),
    "envelope-aux-close": (323, 6, CasillaFieldKind.LITERAL),
}


def test_committed_modelo_232_envelope_export_layout_declares_every_revision_with_fixed_width() -> None:
    """Every revision must publish at least one fixed-width export layout."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        assert revision.export_layouts, revision.id
        assert revision.export_layouts[0].format == "fixed_width", revision.id


def test_committed_modelo_232_envelope_export_layout_carries_envelope_header_and_footer() -> None:
    """The official AEAT envelope wraps page records with a header + closing-tag footer."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        layout = revision.export_layouts[0]
        record_types = {record.record_type for record in layout.records}
        assert {"envelope_header", "envelope_footer"} <= record_types, revision.id


def test_committed_modelo_232_envelope_header_record_orders_first() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        header_record = _envelope_header(revision)
        assert header_record.order == 0, revision.id


def test_committed_modelo_232_envelope_header_field_layout_matches_official_workbook() -> None:
    """Every header field must match the official ``(offset, length, kind)`` triple."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        for field in _envelope_header(revision).fields:
            key = f"envelope-{field.id.split('-envelope-', 1)[1]}"
            assert key in _EXPECTED_ENVELOPE_FIELD_POSITIONS, (revision.id, key)
            expected_offset, expected_length, expected_kind = _EXPECTED_ENVELOPE_FIELD_POSITIONS[key]
            assert field.offset == expected_offset, (revision.id, field.id, field.offset)
            assert field.length == expected_length, (revision.id, field.id, field.length)
            assert field.kind == expected_kind, (revision.id, field.id, field.kind)


def test_committed_modelo_232_envelope_footer_record_orders_last() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        assert _envelope_footer(revision).order == 99, revision.id


def test_committed_modelo_232_envelope_footer_emits_single_closing_tag_field() -> None:
    """Footer carries exactly one field; that field renders the modelo's XML close tag."""
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        footer_record = _envelope_footer(revision)
        assert len(footer_record.fields) == 1, revision.id
        close_field = footer_record.fields[0]
        assert close_field.kind is CasillaFieldKind.COMPUTED, revision.id
        assert close_field.computed_key == "envelope_closing_tag", revision.id
        assert close_field.length == 18, revision.id


def _envelope_header(revision: ModeloRevision) -> ExportRecordDefinition:
    """Return the ``envelope_header`` record from ``revision``'s first export layout."""
    return next(record for record in revision.export_layouts[0].records if record.record_type == "envelope_header")


def _envelope_footer(revision: ModeloRevision) -> ExportRecordDefinition:
    """Return the ``envelope_footer`` record from ``revision``'s first export layout."""
    return next(record for record in revision.export_layouts[0].records if record.record_type == "envelope_footer")


def test_committed_modelo_232_construct_includes_export_layout_and_export_link() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        construct = revision.constructs[0]
        assert construct.export_layouts == tuple(layout.id for layout in revision.export_layouts)
        export_links = [link for link in revision.application_links if link.surface == "export"]
        assert len(export_links) == 1, revision.id
        assert export_links[0].consumer == "aeat.application.filing.export_draft"
        assert export_links[0].id in construct.application_links


def test_committed_modelo_232_page_01_record_matches_official_layout() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        page_01 = next(record for record in revision.export_layouts[0].records if record.record_type == "page_01")
        last_field = page_01.fields[-1]
        assert last_field.offset is not None and last_field.length is not None
        assert last_field.offset + last_field.length - 1 == 1500, (
            f"page_01 must extend to official position 1500 (got {last_field.offset + last_field.length - 1})"
        )
        # Closing tag fragments must appear in order at the end of the record.
        closing_literals = [
            field.literal
            for field in page_01.fields[-4:]
            if field.kind is CasillaFieldKind.LITERAL and field.literal is not None
        ]
        assert closing_literals == ["</T", "232", "01", "000>"], closing_literals


def test_committed_modelo_232_page_02_record_matches_official_layout() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        page_02 = next(record for record in revision.export_layouts[0].records if record.record_type == "page_02")
        last_field = page_02.fields[-1]
        assert last_field.offset is not None and last_field.length is not None
        assert last_field.offset + last_field.length - 1 == 3500, (
            f"page_02 must extend to official position 3500 (got {last_field.offset + last_field.length - 1})"
        )
        opening_literals = [
            field.literal
            for field in page_02.fields[:4]
            if field.kind is CasillaFieldKind.LITERAL and field.literal is not None
        ]
        assert opening_literals == ["<T", "232", "02", "000>"], opening_literals
        closing_literals = [
            field.literal
            for field in page_02.fields[-4:]
            if field.kind is CasillaFieldKind.LITERAL and field.literal is not None
        ]
        assert closing_literals == ["</T", "232", "02", "000>"], closing_literals


_SECTION_3_4_RANGE = (144, 1171)
_SECTION_5_6_RANGE = (13, 3072)


def _layout_bindings_for(revision: ModeloRevision, record_name: str) -> tuple[DataBindingDefinition, ...]:
    return tuple(
        binding
        for binding in revision.bindings
        if selector_as_dict(binding).get("record") == record_name
    )


def _selector_int(binding: DataBindingDefinition, key: str) -> int:
    """Extract an integer selector value from a binding; asserts the value is numeric."""
    value = selector_as_dict(binding)[key]
    assert isinstance(value, (int, str))
    return int(value)


def test_committed_modelo_232_section_3_4_bindings_cover_page_01_slots() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "page_01")
        assert bindings, revision.id
        ranges = sorted((_selector_int(b, "offset"), _selector_int(b, "length")) for b in bindings)
        first_offset = ranges[0][0]
        last_offset, last_length = ranges[-1]
        assert first_offset == _SECTION_3_4_RANGE[0], (revision.id, first_offset)
        assert last_offset + last_length - 1 == _SECTION_3_4_RANGE[1], (
            revision.id,
            last_offset + last_length - 1,
        )
        for current, nxt in pairwise(ranges):
            assert current[0] + current[1] == nxt[0], (revision.id, current, nxt)


def test_committed_modelo_232_section_5_6_bindings_cover_page_02_slots() -> None:
    modelo, _ = _load_modelo_232()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "page_02")
        assert bindings, revision.id
        ranges = sorted((_selector_int(b, "offset"), _selector_int(b, "length")) for b in bindings)
        first_offset = ranges[0][0]
        last_offset, last_length = ranges[-1]
        assert first_offset == _SECTION_5_6_RANGE[0], (revision.id, first_offset)
        assert last_offset + last_length - 1 == _SECTION_5_6_RANGE[1], (
            revision.id,
            last_offset + last_length - 1,
        )
        for current, nxt in pairwise(ranges):
            assert current[0] + current[1] == nxt[0], (revision.id, current, nxt)


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
        page_01 = next(record for record in revision.export_layouts[0].records if record.record_type == "page_01")
        page_field_ids = {field.id for field in page_01.fields}
        for casilla in revision.casillas:
            # Page 01 carries the declarante casillas; the vinculadas related-party
            # rows export through the page_02 row layout, not page_01.
            if not (casilla.section and casilla.section[0] == "declarante"):
                continue
            assert casilla.export_refs, f"casilla {casilla.id!r} missing export_refs"
            for export_ref in casilla.export_refs:
                assert export_ref in page_field_ids, (
                    f"casilla {casilla.id!r} export_ref {export_ref!r} not in page_01 fields"
                )
