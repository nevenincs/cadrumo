"""Tests for committed Modelo 349 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from .....core import ExportLayoutFormat, normalise_corpus_text
from .....core.resources import bundled_path
from .....tests import REPO_ROOT
from .....tests.aeat_literal_fixtures import AEAT_HOST_SUFFIX_EXPECTED
from .. import (
    CasillaFieldKind,
    InputKind,
    RegistrySnapshot,
    RegistryValidator,
    build_snapshot,
    bundled_authority,
    derive_export_layouts_from_bindings,
    parse_export_payload,
    resolve_export_layout,
    select_revision,
)
from .._corpus_catalogue import verify_source_file
from .._legal import verify_legal_catalogue
from ._modelo_349_registry_support import (
    _DECL_IMPORTE_OPERACIONES_CASILLA,
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA,
    _DECL_NUMERO_OPERADORES_CASILLA,
    _DECL_NUMERO_RECTIFICACIONES_CASILLA,
    _DECLARANT_SUMMARY_CASILLAS,
    _M349_CADENCE_LEGAL_REF,
    _M349_CADENCE_REQUIRED_TEXT,
    _M349_GB_XI_ORDINARY_BINDINGS,
    _M349_GB_XI_ORDINARY_REQUIRED_TEXT,
    _M349_GB_XI_RECTIFICATION_BINDINGS,
    _M349_GB_XI_RECTIFICATION_REQUIRED_TEXT,
    _M349_GB_XI_SOURCE_REF,
    _OFFICIAL_FIELD_POSITIONS,
    _OFFICIAL_FIELD_WIDTHS,
    _OP_APELLIDOS_RAZON_SOCIAL_CASILLA,
    _OP_BASE_IMPONIBLE_CASILLA,
    _OP_CLAVE_OPERACION_CASILLA,
    _OP_CODIGO_PAIS_CASILLA,
    _OP_NIF_COMUNITARIO_CASILLA,
    _RECT_BASE_ANTERIOR_CASILLA,
    _RECT_BASE_RECTIFICADA_CASILLA,
    _RECT_EJERCICIO_RECTIFICADO_CASILLA,
    _RECT_PERIODO_RECTIFICADO_CASILLA,
    _WWW6_HOST,
    _fixed_width_record,
    _load_modelo_349,
    _modelo_349_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _snapshot_349(filing_year: int, period: str) -> RegistrySnapshot:
    modelo, catalogues = _load_modelo_349()
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )


def test_committed_modelo_349_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_349()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2020-y-siguientes"}


def test_committed_modelo_349_resolves_revision_for_monthly_and_quarterly_periods() -> None:
    for filing_year, period, expected_revision in (
        (2020, "1T", "2020-y-siguientes"),
        (2024, "05", "2020-y-siguientes"),
        (2026, "01", "2020-y-siguientes"),
        (2026, "12", "2020-y-siguientes"),
        (2026, "1T", "2020-y-siguientes"),
        (2026, "4T", "2020-y-siguientes"),
    ):
        snapshot = _snapshot_349(filing_year, period)

        assert snapshot.revision.id == expected_revision, (filing_year, period)
        assert snapshot.revision.orden_aplicabilidad == (
            "orden-eha-769-2010:art-1",
            "orden-hac-174-2020:art-1",
        )


def test_committed_modelo_349_is_informative_static_documentation_only() -> None:
    modelo, _ = _load_modelo_349()
    snapshot = _snapshot_349(2026, "01")
    decision = snapshot.live_cross_references["modelo-349-static-documentation"]
    construct = snapshot.constructs["modelo-349-informative"]

    # Modelo 349 must NOT be reclassified to calculation_class="informative": its
    # declarante summary totals (numero-operadores / importe-operaciones / ...) are
    # ledger-derived BOUND casillas, and the informative-class invariant
    # (validate_informative_class_invariant) forbids any input_kind outside
    # {INFORMATIONAL, MANUAL} for an informative modelo. Reclassifying would be
    # rejected at registry-build time; the schema default ("filing") is correct here.
    assert modelo.calculation_class == "filing"
    assert snapshot.revision.formulas == ()
    assert snapshot.revision.relations == ()
    assert {casilla.input_kind for casilla in snapshot.revision.casillas} == {InputKind.MANUAL, InputKind.BOUND}
    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "declaration-submission" in decision.forbidden_actions
    assert set(construct.casilla_ids) == {casilla.id for casilla in snapshot.revision.casillas}
    assert {
        "modelo-349-portal",
        "modelo-349-filed-declarations-observation",
        "modelo-349-filing",
    }.issubset(construct.application_links)


def test_committed_modelo_349_casilla_numbers_match_official_record_design() -> None:
    revision = _modelo_349_revision()
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id, (expected_start, expected_end) in _OFFICIAL_FIELD_POSITIONS.items():
        assert casilla_id in casillas_by_id, f"missing casilla {casilla_id!r}"
        casilla = casillas_by_id[casilla_id]
        expected_number = str(expected_start) if expected_start == expected_end else f"{expected_start}-{expected_end}"
        assert casilla.number == expected_number, (
            f"casilla {casilla_id!r} number {casilla.number!r} does not match Orden HAC/174/2020 "
            f"position {expected_number}"
        )


def test_committed_modelo_349_casilla_data_types_match_official_record_design() -> None:
    expected_types = (
        (_DECL_NUMERO_OPERADORES_CASILLA, "integer"),
        (_DECL_IMPORTE_OPERACIONES_CASILLA, "money"),
        (_DECL_NUMERO_RECTIFICACIONES_CASILLA, "integer"),
        (_DECL_IMPORTE_RECTIFICACIONES_CASILLA, "money"),
        (_OP_CODIGO_PAIS_CASILLA, "country_code"),
        (_OP_NIF_COMUNITARIO_CASILLA, "nif_iva"),
        (_OP_APELLIDOS_RAZON_SOCIAL_CASILLA, "text"),
        (_OP_CLAVE_OPERACION_CASILLA, "text"),
        (_OP_BASE_IMPONIBLE_CASILLA, "money"),
        (_RECT_EJERCICIO_RECTIFICADO_CASILLA, "year"),
        (_RECT_PERIODO_RECTIFICADO_CASILLA, "period_code"),
        (_RECT_BASE_RECTIFICADA_CASILLA, "money"),
        (_RECT_BASE_ANTERIOR_CASILLA, "money"),
    )
    revision = _modelo_349_revision()

    for casilla_id, expected_data_type in expected_types:
        casilla = next(item for item in revision.casillas if item.id == casilla_id)
        assert casilla.data_type == expected_data_type, casilla_id


def test_committed_modelo_349_base_intracomunitaria_role_coverage() -> None:
    revision = _modelo_349_revision()
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    expected_ids = {
        _OP_BASE_IMPONIBLE_CASILLA,
        _RECT_BASE_RECTIFICADA_CASILLA,
        _RECT_BASE_ANTERIOR_CASILLA,
    }

    found_ids = {casilla.id for casilla in revision.casillas if casilla.semantic_role == "base_intracomunitaria"}
    assert found_ids == expected_ids

    for casilla_id in expected_ids:
        casilla = casillas[casilla_id]
        assert casilla.data_type == "money"
        assert casilla.legal_refs == (
            "orden-eha-769-2010:art-1",
            "orden-hac-174-2020:art-1",
            "ley-58-2003:art-93",
        )


def test_committed_modelo_349_casilla_widths_match_official_record_design() -> None:
    revision = _modelo_349_revision()
    for casilla in revision.casillas:
        if casilla.id not in _OFFICIAL_FIELD_WIDTHS:
            continue
        if "-" in casilla.number:
            start, end = casilla.number.split("-", 1)
            actual_length = int(end) - int(start) + 1
        else:
            actual_length = 1
        assert actual_length == _OFFICIAL_FIELD_WIDTHS[casilla.id], (
            f"casilla {casilla.id!r} byte length {actual_length} does not match official "
            f"record-design length {_OFFICIAL_FIELD_WIDTHS[casilla.id]}"
        )


def test_committed_modelo_349_authenticated_read_surface_contract() -> None:
    revision = _modelo_349_revision()
    auth_surface = next(ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read")

    assert auth_surface.surface == "authenticated_read_surface"
    assert set(auth_surface.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}
    assert auth_surface.requires_authentication is True
    assert auth_surface.requires_aeat_authorization is True
    assert auth_surface.synthetic_data_allowed is False
    forbidden = set(auth_surface.forbidden_actions)
    assert {
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    } <= forbidden, "missing forbidden actions: required - forbidden"
    assert _WWW6_HOST in auth_surface.allowed_hosts
    for host in auth_surface.allowed_hosts:
        assert host.endswith(AEAT_HOST_SUFFIX_EXPECTED), f"non-AEAT host allowed: {host!r}"


def test_committed_modelo_349_workbook_parity_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    assert len(revision.workbook_parity_refs) == 1
    ref = revision.workbook_parity_refs[0]
    assert ref.workbook_source == "aeat-dr-349-2020-current"
    assert ref.formula_coverage == "record_design_layout"
    assert ref.runner_required is False

    source = catalogues.sources["aeat-dr-349-2020-current"]
    assert source.evidence_tier == "layout_authority"
    artefact_path = bundled_path() / source.corpus_path
    assert artefact_path.is_file(), artefact_path


def test_committed_modelo_349_gb_xi_country_prefix_rules_are_cited_to_aeat_instructions() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    source = catalogues.sources[_M349_GB_XI_SOURCE_REF]
    layout_source = catalogues.sources["boe-modelo-349-form-2010"]

    assert source.evidence_tier == "official_source_guidance"
    assert layout_source.evidence_tier == "layout_authority"
    assert source.kind == "instructions"
    assert source.corpus_path == "corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.txt"
    assert source.sha256 == "735dc0b1be1bed8997bd77a97fb0cb54e54d77a083082f5b72cf6aa236717adf"
    assert source.bytes == 69284
    assert source.source_url.endswith("/GI28/instr_mod_349.pdf")
    verify_source_file(REPO_ROOT, source)

    source_text = normalise_corpus_text((bundled_path() / source.corpus_path).read_text(encoding="utf-8"))
    for required_text in _M349_GB_XI_ORDINARY_REQUIRED_TEXT + _M349_GB_XI_RECTIFICATION_REQUIRED_TEXT:
        assert normalise_corpus_text(required_text) in source_text

    bindings = {binding.id: binding for binding in revision.bindings}
    expected_by_binding = {
        **{binding_id: _M349_GB_XI_ORDINARY_REQUIRED_TEXT for binding_id in _M349_GB_XI_ORDINARY_BINDINGS},
        **{binding_id: _M349_GB_XI_RECTIFICATION_REQUIRED_TEXT for binding_id in _M349_GB_XI_RECTIFICATION_BINDINGS},
    }
    for binding_id, expected_required_text in expected_by_binding.items():
        binding = bindings[binding_id]
        assert _M349_GB_XI_SOURCE_REF in binding.source_refs
        instruction_required_texts = {
            citation.required_text
            for citation in binding.source_citations
            if citation.source_ref == _M349_GB_XI_SOURCE_REF
        }
        assert expected_required_text in instruction_required_texts


def test_committed_modelo_349_cadence_threshold_links_to_riva_art_81_corpus() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    reference = catalogues.legal[_M349_CADENCE_LEGAL_REF]

    assert _M349_CADENCE_LEGAL_REF in modelo.legal_refs
    assert _M349_CADENCE_LEGAL_REF in revision.legal_refs
    assert _M349_CADENCE_LEGAL_REF in revision.constructs[0].legal_refs
    assert reference.corpus_ref == "corpus/normatives/html/rd-1624-1992-art-81.html#a81"
    assert reference.effective_from == date(2020, 3, 1)
    assert reference.required_text == _M349_CADENCE_REQUIRED_TEXT

    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())
    corpus_path_text = reference.corpus_ref.split("#", 1)[0]
    corpus_text = normalise_corpus_text((bundled_path() / corpus_path_text).read_text(encoding="utf-8"))
    for required_text in _M349_CADENCE_REQUIRED_TEXT:
        assert normalise_corpus_text(required_text) in corpus_text


def test_committed_modelo_349_construct_collects_all_revision_members() -> None:
    revision = _modelo_349_revision()
    assert len(revision.constructs) == 1
    construct = revision.constructs[0]

    assert set(construct.casilla_ids) == {casilla.id for casilla in revision.casillas}
    assert set(construct.workbook_parity_refs) == {ref.id for ref in revision.workbook_parity_refs}
    assert set(construct.live_cross_references) == {ref.id for ref in revision.live_cross_references}
    assert set(construct.application_links) == {link.id for link in revision.application_links}
    assert set(construct.filing_schedules) == {schedule.id for schedule in revision.filing_schedules}
    assert set(construct.deadline_windows) == {window.id for window in revision.deadline_windows}


def test_committed_modelo_349_filing_schedules_split_monthly_and_quarterly_by_threshold() -> None:
    revision = _modelo_349_revision()

    schedules_by_id = {schedule.id: schedule for schedule in revision.filing_schedules}
    assert set(schedules_by_id) == {"modelo-349-trimestral", "modelo-349-mensual"}

    quarterly = schedules_by_id["modelo-349-trimestral"]
    assert quarterly.period_kind == "quarterly"
    assert quarterly.periods == ("1T", "2T", "3T", "4T")
    assert quarterly.profile_condition_mode == "all"
    assert _M349_CADENCE_LEGAL_REF in quarterly.legal_refs
    quarterly_predicates = {condition.field: condition for condition in quarterly.profile_conditions}
    assert quarterly_predicates["does_intracomunitario"].value is True
    quarterly_threshold = quarterly_predicates["iva.intracommunity_operations_exceed_50000_eur"]
    assert quarterly_threshold.op == "equals"
    assert quarterly_threshold.value is False
    assert _M349_CADENCE_LEGAL_REF in quarterly_threshold.legal_refs

    monthly = schedules_by_id["modelo-349-mensual"]
    assert monthly.period_kind == "monthly"
    assert monthly.periods == ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
    assert _M349_CADENCE_LEGAL_REF in monthly.legal_refs
    monthly_predicates = {condition.field: condition for condition in monthly.profile_conditions}
    assert monthly_predicates["does_intracomunitario"].value is True
    monthly_threshold = monthly_predicates["iva.intracommunity_operations_exceed_50000_eur"]
    assert monthly_threshold.value is True
    assert _M349_CADENCE_LEGAL_REF in monthly_threshold.legal_refs


def test_committed_modelo_349_deadline_windows_cover_every_supported_period_per_year() -> None:
    revision = _modelo_349_revision()

    expected_periods = {f"{m:02d}" for m in range(1, 13)} | {f"{q}T" for q in range(1, 5)}
    by_year: dict[int, set[str]] = {}
    for window in revision.deadline_windows:
        by_year.setdefault(window.filing_year, set()).add(window.period.registry_token)

    assert len(revision.deadline_windows) == 78
    assert set(by_year) == {2022, 2023, 2024, 2025, 2026}
    for filing_year, periods in by_year.items():
        missing = expected_periods - periods
        expected_missing = {"12", "4T"} if filing_year == 2026 else set()
        assert missing == expected_missing, f"filing_year {filing_year} unexpected period coverage gap: {missing}"


def test_committed_modelo_349_deadline_windows_match_official_plazo_rules() -> None:
    # These are explicit AEAT-calendar close facts, not a nominal-day
    # calculation.  In particular, they preserve every published weekend or
    # holiday shift.  December and 4T use the following physical calendar year.
    expected_closes_by_year = {
        2022: (
            ("01", date(2022, 2, 21)),
            ("02", date(2022, 3, 21)),
            ("03", date(2022, 4, 20)),
            ("04", date(2022, 5, 20)),
            ("05", date(2022, 6, 20)),
            ("06", date(2022, 7, 20)),
            ("07", date(2022, 9, 20)),
            ("08", date(2022, 9, 20)),
            ("09", date(2022, 10, 20)),
            ("10", date(2022, 11, 21)),
            ("11", date(2022, 12, 20)),
            ("12", date(2023, 1, 30)),
            ("1T", date(2022, 4, 20)),
            ("2T", date(2022, 7, 20)),
            ("3T", date(2022, 10, 20)),
            ("4T", date(2023, 1, 30)),
        ),
        2023: (
            ("01", date(2023, 2, 20)),
            ("02", date(2023, 3, 20)),
            ("03", date(2023, 4, 20)),
            ("04", date(2023, 5, 22)),
            ("05", date(2023, 6, 20)),
            ("06", date(2023, 7, 20)),
            ("07", date(2023, 9, 20)),
            ("08", date(2023, 9, 20)),
            ("09", date(2023, 10, 20)),
            ("10", date(2023, 11, 20)),
            ("11", date(2023, 12, 20)),
            ("12", date(2024, 1, 30)),
            ("1T", date(2023, 4, 20)),
            ("2T", date(2023, 7, 20)),
            ("3T", date(2023, 10, 20)),
            ("4T", date(2024, 1, 30)),
        ),
        2024: (
            ("01", date(2024, 2, 20)),
            ("02", date(2024, 3, 20)),
            ("03", date(2024, 4, 22)),
            ("04", date(2024, 5, 20)),
            ("05", date(2024, 6, 20)),
            ("06", date(2024, 7, 22)),
            ("07", date(2024, 9, 20)),
            ("08", date(2024, 9, 20)),
            ("09", date(2024, 10, 21)),
            ("10", date(2024, 11, 20)),
            ("11", date(2024, 12, 20)),
            ("12", date(2025, 1, 30)),
            ("1T", date(2024, 4, 22)),
            ("2T", date(2024, 7, 22)),
            ("3T", date(2024, 10, 21)),
            ("4T", date(2025, 1, 30)),
        ),
        2025: (
            ("01", date(2025, 2, 20)),
            ("02", date(2025, 3, 20)),
            ("03", date(2025, 4, 21)),
            ("04", date(2025, 5, 20)),
            ("05", date(2025, 6, 20)),
            ("06", date(2025, 7, 21)),
            ("07", date(2025, 9, 22)),
            ("08", date(2025, 9, 22)),
            ("09", date(2025, 10, 20)),
            ("10", date(2025, 11, 20)),
            ("11", date(2025, 12, 22)),
            ("12", date(2026, 1, 30)),
            ("1T", date(2025, 4, 21)),
            ("2T", date(2025, 7, 21)),
            ("3T", date(2025, 10, 20)),
            ("4T", date(2026, 1, 30)),
        ),
        2026: (
            ("01", date(2026, 2, 20)),
            ("02", date(2026, 3, 20)),
            ("03", date(2026, 4, 20)),
            ("04", date(2026, 5, 20)),
            ("05", date(2026, 6, 22)),
            ("06", date(2026, 7, 20)),
            ("07", date(2026, 9, 21)),
            ("08", date(2026, 9, 21)),
            ("09", date(2026, 10, 20)),
            ("10", date(2026, 11, 20)),
            ("11", date(2026, 12, 21)),
            ("1T", date(2026, 4, 20)),
            ("2T", date(2026, 7, 20)),
            ("3T", date(2026, 10, 20)),
        ),
    }
    revision = _modelo_349_revision()

    actual = {
        year: tuple(
            sorted(
                (window.period.registry_token, window.closes_on)
                for window in revision.deadline_windows
                if window.filing_year == year
            )
        )
        for year in expected_closes_by_year
    }
    expected = {year: tuple(sorted(expected_closes)) for year, expected_closes in expected_closes_by_year.items()}
    assert actual == expected


def test_committed_modelo_349_deadlines_have_calendar_provenance_and_canonical_projection() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    expected_periods = {f"{month:02d}" for month in range(1, 13)} | {f"{quarter}T" for quarter in range(1, 5)}

    for filing_year in range(2022, 2027):
        windows = tuple(window for window in revision.deadline_windows if window.filing_year == filing_year)
        expected_missing = {"12", "4T"} if filing_year == 2026 else set()
        assert len(windows) == 16 - len(expected_missing)
        assert {window.period.registry_token for window in windows} == expected_periods - expected_missing

        for window in windows:
            assert (
                select_revision(
                    modelo,
                    filing_year=filing_year,
                    period=window.period.registry_token,
                ).id
                == revision.id
            )
            if window.closes_on.year <= 2026:
                assert f"aeat-calendario-contribuyente-{window.closes_on.year}" in window.source_refs

        projected = bundled_authority().deadline_windows(filing_year, modelos=("349",))
        assert len(projected) == 16 - len(expected_missing)
        assert {window.period.registry_token for _, _, window in projected} == expected_periods - expected_missing
        assert {owner.id for _, owner, _ in projected} == {revision.id}

    construct = revision.constructs[0]
    assert set(construct.deadline_windows) == {window.id for window in revision.deadline_windows}
    calendar_refs = {f"aeat-calendario-contribuyente-{year}" for year in range(2022, 2027)}
    assert calendar_refs <= set(revision.source_refs)
    assert calendar_refs <= set(construct.source_refs)


def test_committed_modelo_349_deadline_windows_are_unique_by_period() -> None:
    revision = _modelo_349_revision()
    seen: set[tuple[int, str]] = set()
    for window in revision.deadline_windows:
        key = (window.period.filing_year, window.period.registry_token)
        assert key not in seen, f"duplicate deadline window for period {window.period}"
        seen.add(key)


def test_committed_modelo_349_deadline_app_link_is_registered() -> None:
    revision = _modelo_349_revision()
    deadline_links = [link for link in revision.application_links if link.surface == "deadline"]
    assert len(deadline_links) == 1
    assert deadline_links[0].id == "modelo-349-deadline"
    assert deadline_links[0].requires_snapshot is True


def test_committed_modelo_349_export_layout_declares_three_fixed_width_records() -> None:
    revision = _modelo_349_revision()
    assert len(revision.export_layouts) == 1
    layout = revision.export_layouts[0]
    assert layout.id == "modelo-349-fichero-2020"
    assert layout.format is ExportLayoutFormat.FIXED_WIDTH

    record_types = {record.record_type: record for record in layout.records}
    assert set(record_types) == {"declarante", "operador", "rectificacion"}
    for record in layout.records:
        assert record.encoding == "latin-1"
        assert record.line_ending == "none"


def test_committed_modelo_349_export_records_match_fixed_width_contract() -> None:
    revision = _modelo_349_revision()
    # The DERIVED layout, not the raw one. `revision.export_layouts` holds only
    # the INLINE fields; M349's declarante record takes positions 1..58 from
    # bindings, so the raw record starts at offset 59 and the contiguity walk
    # below cannot hold against it. The derived layout is what the renderer and
    # the completeness gate consume, so it is the surface this contract governs.
    layout = derive_export_layouts_from_bindings(revision)[0]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    expected_record_type_literals = {
        "declarante": "1",
        "operador": "2",
        "rectificacion": "2",
    }

    for record in layout.records:
        record_type = record.record_type
        # Ordered by offset: derivation appends the binding-derived fields after
        # the inline ones, so tuple order is not wire order. Sorting reads the
        # record as it is actually emitted, and hides nothing -- an overlap or a
        # hole still breaks the cursor walk below.
        fields = sorted(record.fields, key=lambda field: field.offset)
        first_field = fields[0]
        assert first_field.offset == 1, record_type
        assert first_field.length == 1, record_type
        assert first_field.kind is CasillaFieldKind.LITERAL, record_type
        assert first_field.literal == expected_record_type_literals[record_type], record_type
        total = sum(field.length or 0 for field in fields)
        assert total == 500, f"record {record.record_type!r} totals {total} bytes; expected 500"
        cursor = 1
        for field in fields:
            assert field.offset == cursor, (
                f"record {record.record_type!r} field {field.id!r} offset {field.offset} "
                f"breaks contiguity (expected {cursor})"
            )
            assert field.length is not None
            if field.kind is CasillaFieldKind.CASILLA:
                assert field.casilla_id in casilla_ids, (
                    f"export field {field.id!r} references unknown casilla {field.casilla_id!r}"
                )
            cursor += field.length
        assert cursor == 501, f"record {record.record_type!r} last field ends at {cursor - 1}; expected 500"


def test_committed_modelo_349_export_app_link_is_registered() -> None:
    revision = _modelo_349_revision()
    export_links = [link for link in revision.application_links if link.surface == "export"]
    assert len(export_links) == 1
    assert export_links[0].id == "modelo-349-export"
    assert export_links[0].requires_snapshot is True


def test_committed_modelo_349_construct_includes_export_layout() -> None:
    revision = _modelo_349_revision()
    construct = revision.constructs[0]
    assert set(construct.export_layouts) == {layout.id for layout in revision.export_layouts}


def test_committed_modelo_349_extraction_profiles_target_declarant_summary_casillas() -> None:
    revision = _modelo_349_revision()

    profiles_by_id = {profile.id: profile for profile in revision.extraction_profiles}
    assert set(profiles_by_id) == {"modelo-349-declaracion-pdf", "modelo-349-submitted-file"}

    pdf_profile = profiles_by_id["modelo-349-declaracion-pdf"]
    assert pdf_profile.surface == "declaracion_pdf"
    assert pdf_profile.parser == "cadrumo.adapters.inbound.declaracion.parse_declaracion"
    assert pdf_profile.failure_semantics == "fail_hard"
    assert {t.casilla_id for t in pdf_profile.target_casillas} == set(_DECLARANT_SUMMARY_CASILLAS)

    submitted_profile = profiles_by_id["modelo-349-submitted-file"]
    assert submitted_profile.surface == "export_record"
    assert submitted_profile.parser == "cadrumo.domain.calculations.registry.parse_export_payload"
    assert submitted_profile.confidence == "strict"
    declarant_casilla_ids = {casilla.id for casilla in revision.casillas if casilla.section[0] == "declarante"}
    assert {t.casilla_id for t in submitted_profile.target_casillas} == declarant_casilla_ids


def test_committed_modelo_349_extractor_app_link_is_registered() -> None:
    revision = _modelo_349_revision()
    extractor_links = [link for link in revision.application_links if link.surface == "extractor"]
    assert len(extractor_links) == 1
    assert extractor_links[0].id == "modelo-349-extractor"
    assert extractor_links[0].consumer == "cadrumo.adapters.inbound.declaracion.parse_declaracion"


def test_committed_modelo_349_construct_includes_extraction_profiles() -> None:
    revision = _modelo_349_revision()
    construct = revision.constructs[0]
    assert set(construct.extraction_profiles) == {profile.id for profile in revision.extraction_profiles}


def test_committed_modelo_349_record_design_round_trips_declarante_operador_rectificacion() -> None:
    snapshot = _snapshot_349(2026, "1T")
    layout = resolve_export_layout(snapshot).layout

    declarante = _fixed_width_record(
        500,
        {
            (1, 1): "1",
            (2, 4): "349",
            (5, 8): "2026",
            (9, 17): "B12345678",
            (136, 137): "1T",
            (138, 146): "2".zfill(9),
            (147, 161): "150050".zfill(15),
            (162, 170): "1".zfill(9),
            (171, 185): "10000".zfill(15),
        },
    )
    operador = _fixed_width_record(
        500,
        {
            (1, 1): "2",
            (2, 4): "349",
            (5, 8): "2026",
            (9, 17): "B12345678",
            (76, 77): "DE",
            (78, 92): "123456789012345",
            (93, 132): "ALEMAN GMBH".ljust(40),
            (133, 133): "E",
            (134, 146): "150050".zfill(13),
        },
    )
    rectificacion = _fixed_width_record(
        500,
        {
            (1, 1): "2",
            (2, 4): "349",
            (5, 8): "2026",
            (9, 17): "B12345678",
            (76, 77): "FR",
            (78, 92): "FR12345678901".ljust(15),
            (93, 132): "FRANCE SARL".ljust(40),
            (133, 133): "A",
            (147, 150): "2024",
            (151, 152): "1T",
            (153, 165): "10000".zfill(13),
            (166, 178): "8000".zfill(13),
        },
    )

    payload = (declarante + operador + rectificacion).encode("latin-1")
    parsed = parse_export_payload(layout, payload)
    by_record_casilla = {(field.record_id, field.casilla_id): field.value for field in parsed.casillas}
    by_record_binding = {
        (field.record_id, field.binding_id): field.value for field in parsed.fields if field.binding_id is not None
    }

    decl = "modelo-349-declarante"
    op = "modelo-349-operador"
    rect = "modelo-349-rectificacion"

    # Declarant casillas remain casilla-kind fields and parse via casilla_id.
    assert by_record_casilla[(decl, _DECL_NUMERO_OPERADORES_CASILLA)] == Decimal("2")
    assert by_record_casilla[(decl, _DECL_IMPORTE_OPERACIONES_CASILLA)] == Decimal("1500.50")
    assert by_record_casilla[(decl, _DECL_NUMERO_RECTIFICACIONES_CASILLA)] == Decimal("1")
    assert by_record_casilla[(decl, _DECL_IMPORTE_RECTIFICACIONES_CASILLA)] == Decimal("100.00")

    # Operador and rectificacion records render via binding-row fields and the
    # parser distinguishes them via the rectification-block discriminator
    # (positions 147-178 must be blank for operador, non-blank for rectificacion).
    assert by_record_binding[(op, "iva-349-operador-row-codigo-pais")] == "DE"
    assert by_record_binding[(op, "iva-349-operador-row-nif")] == "123456789012345"
    assert by_record_binding[(op, "iva-349-operador-row-clave")] == "E"
    assert by_record_binding[(op, "iva-349-operador-row-base")] == Decimal("1500.50")

    assert by_record_binding[(rect, "iva-349-rectificacion-row-codigo-pais")] == "FR"
    assert by_record_binding[(rect, "iva-349-rectificacion-row-clave")] == "A"
    assert by_record_binding[(rect, "iva-349-rectificacion-row-ejercicio")] == Decimal("2024")
    assert by_record_binding[(rect, "iva-349-rectificacion-row-periodo")] == "1T"
    assert by_record_binding[(rect, "iva-349-rectificacion-row-base-rectificada")] == Decimal("100.00")
    assert by_record_binding[(rect, "iva-349-rectificacion-row-base-anterior")] == Decimal("80.00")
