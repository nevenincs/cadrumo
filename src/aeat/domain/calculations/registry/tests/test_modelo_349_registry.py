"""Tests for committed Modelo 349 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import cast

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import AEAT_HOST_SUFFIX_EXPECTED, aeat_host
from .. import (
    InputKind,
    InvoiceObservation,
    RegistryValidator,
    build_snapshot,
    invoice_binding_requirements,
    load_registry_tree,
    parse_export_payload,
    resolve_bound_casilla_inputs,
    resolve_export_layout,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW6_HOST = aeat_host("www6")

# Field positions taken from Orden HAC/174/2020 Anexo (DR_Anexo_349.pdf
# pages 9-22), the layout authority cited by Modelo 349's registry revision.
# Tipo 1 = registro de declarante (500 bytes); Tipo 2 = registro de operador
# intracomunitario / rectificaciones (500 bytes).
_OFFICIAL_FIELD_POSITIONS: dict[str, tuple[int, int]] = {
    "decl.numero-operadores": (138, 146),
    "decl.importe-operaciones": (147, 161),
    "decl.numero-rectificaciones": (162, 170),
    "decl.importe-rectificaciones": (171, 185),
    "op.codigo-pais": (76, 77),
    "op.nif-comunitario": (78, 92),
    "op.apellidos-razon-social": (93, 132),
    "op.clave-operacion": (133, 133),
    "op.base-imponible": (134, 146),
    "rect.ejercicio-rectificado": (147, 150),
    "rect.periodo-rectificado": (151, 152),
    "rect.base-rectificada": (153, 165),
    "rect.base-anterior": (166, 178),
}


@lru_cache(maxsize=1)
def _load_modelo_349():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "349")
    return modelo, catalogues


def test_committed_modelo_349_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_349()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2020-y-siguientes"}


@pytest.mark.parametrize(
    ("filing_year", "period", "expected_revision"),
    [
        (2020, "1T", "2020-y-siguientes"),
        (2024, "05", "2020-y-siguientes"),
        (2026, "01", "2020-y-siguientes"),
        (2026, "12", "2020-y-siguientes"),
        (2026, "1T", "2020-y-siguientes"),
        (2026, "4T", "2020-y-siguientes"),
    ],
)
def test_committed_modelo_349_resolves_revision_for_monthly_and_quarterly_periods(
    filing_year: int,
    period: str,
    expected_revision: str,
) -> None:
    modelo, catalogues = _load_modelo_349()

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )

    assert snapshot.revision.id == expected_revision


def test_committed_modelo_349_is_informative_static_documentation_only() -> None:
    modelo, catalogues = _load_modelo_349()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="01",
    )
    decision = snapshot.live_cross_references["modelo-349-static-documentation"]
    construct = snapshot.constructs["modelo-349-informative"]

    assert snapshot.revision.formulas == ()
    assert snapshot.revision.relations == ()
    assert {casilla.input_kind for casilla in snapshot.revision.casillas} == {"manual", "bound"}
    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "declaration-submission" in decision.forbidden_actions
    assert set(construct.casillas) == {casilla.id for casilla in snapshot.revision.casillas}
    assert {
        "modelo-349-portal",
        "modelo-349-filed-declarations-observation",
        "modelo-349-filing",
    }.issubset(construct.application_links)


def test_committed_modelo_349_casilla_numbers_match_official_record_design() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id, (expected_start, expected_end) in _OFFICIAL_FIELD_POSITIONS.items():
        assert casilla_id in casillas_by_id, f"missing casilla {casilla_id!r}"
        casilla = casillas_by_id[casilla_id]
        expected_number = str(expected_start) if expected_start == expected_end else f"{expected_start}-{expected_end}"
        assert casilla.number == expected_number, (
            f"casilla {casilla_id!r} number {casilla.number!r} does not match Orden HAC/174/2020 "
            f"position {expected_number}"
        )


@pytest.mark.parametrize(
    ("casilla_id", "expected_data_type"),
    [
        ("decl.numero-operadores", "integer"),
        ("decl.importe-operaciones", "money"),
        ("decl.numero-rectificaciones", "integer"),
        ("decl.importe-rectificaciones", "money"),
        ("op.codigo-pais", "country_code"),
        ("op.nif-comunitario", "nif_iva"),
        ("op.apellidos-razon-social", "text"),
        ("op.clave-operacion", "text"),
        ("op.base-imponible", "money"),
        ("rect.ejercicio-rectificado", "year"),
        ("rect.periodo-rectificado", "period_code"),
        ("rect.base-rectificada", "money"),
        ("rect.base-anterior", "money"),
    ],
)
def test_committed_modelo_349_casilla_data_types_match_official_record_design(
    casilla_id: str,
    expected_data_type: str,
) -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    casilla = next(item for item in revision.casillas if item.id == casilla_id)
    assert casilla.data_type == expected_data_type


def test_committed_modelo_349_base_intracomunitaria_role_coverage() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    expected_ids = {
        "op.base-imponible",
        "rect.base-rectificada",
        "rect.base-anterior",
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
    expected_lengths = {
        "decl.numero-operadores": 9,
        "decl.importe-operaciones": 15,
        "decl.numero-rectificaciones": 9,
        "decl.importe-rectificaciones": 15,
        "op.codigo-pais": 2,
        "op.nif-comunitario": 15,
        "op.apellidos-razon-social": 40,
        "op.clave-operacion": 1,
        "op.base-imponible": 13,
        "rect.ejercicio-rectificado": 4,
        "rect.periodo-rectificado": 2,
        "rect.base-rectificada": 13,
        "rect.base-anterior": 13,
    }
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    for casilla in revision.casillas:
        if casilla.id not in expected_lengths:
            continue
        if "-" in casilla.number:
            start, end = casilla.number.split("-", 1)
            actual_length = int(end) - int(start) + 1
        else:
            actual_length = 1
        assert actual_length == expected_lengths[casilla.id], (
            f"casilla {casilla.id!r} byte length {actual_length} does not match official "
            f"record-design length {expected_lengths[casilla.id]}"
        )


def test_committed_modelo_349_authenticated_read_surface_allows_read_only_methods_only() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    auth_surface = next(ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read")

    assert auth_surface.surface == "authenticated_read_surface"
    assert set(auth_surface.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}
    assert auth_surface.requires_authentication is True
    assert auth_surface.requires_aeat_authorization is True
    assert auth_surface.synthetic_data_allowed is False


def test_committed_modelo_349_authenticated_read_surface_forbids_aeat_state_mutations() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    auth_surface = next(ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read")

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


def test_committed_modelo_349_authenticated_read_surface_pins_aeat_hosts() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    auth_surface = next(ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read")

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


def test_committed_modelo_349_construct_collects_all_revision_members() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    assert len(revision.constructs) == 1
    construct = revision.constructs[0]

    assert set(construct.casillas) == {casilla.id for casilla in revision.casillas}
    assert set(construct.workbook_parity_refs) == {ref.id for ref in revision.workbook_parity_refs}
    assert set(construct.live_cross_references) == {ref.id for ref in revision.live_cross_references}
    assert set(construct.application_links) == {link.id for link in revision.application_links}
    assert set(construct.filing_schedules) == {schedule.id for schedule in revision.filing_schedules}
    assert set(construct.deadline_windows) == {window.id for window in revision.deadline_windows}


def test_committed_modelo_349_filing_schedules_split_monthly_and_quarterly_by_threshold() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    schedules_by_id = {schedule.id: schedule for schedule in revision.filing_schedules}
    assert set(schedules_by_id) == {"modelo-349-trimestral", "modelo-349-mensual"}

    quarterly = schedules_by_id["modelo-349-trimestral"]
    assert quarterly.period_kind == "quarterly"
    assert quarterly.periods == ("1T", "2T", "3T", "4T")
    assert quarterly.profile_condition_mode == "all"
    quarterly_predicates = {condition.field: condition for condition in quarterly.profile_conditions}
    assert quarterly_predicates["does_intracomunitario"].value is True
    assert quarterly_predicates["iva.intracommunity_operations_exceed_50000_eur"].op == "equals"
    assert quarterly_predicates["iva.intracommunity_operations_exceed_50000_eur"].value is False

    monthly = schedules_by_id["modelo-349-mensual"]
    assert monthly.period_kind == "monthly"
    assert monthly.periods == ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
    monthly_predicates = {condition.field: condition for condition in monthly.profile_conditions}
    assert monthly_predicates["does_intracomunitario"].value is True
    assert monthly_predicates["iva.intracommunity_operations_exceed_50000_eur"].value is True


def test_committed_modelo_349_deadline_windows_cover_every_supported_period_per_year() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    expected_periods = {f"{m:02d}" for m in range(1, 13)} | {f"{q}T" for q in range(1, 5)}
    by_year: dict[int, set[str]] = {}
    for window in revision.deadline_windows:
        by_year.setdefault(window.filing_year, set()).add(window.period.registry_token)

    assert set(by_year) == {2024, 2025, 2026}
    for filing_year, periods in by_year.items():
        missing = expected_periods - periods
        assert periods == expected_periods, f"filing_year {filing_year} period coverage gap: {missing}"


@pytest.mark.parametrize(
    ("window_id", "expected_open", "expected_close"),
    [
        # Standard monthly window: 1st to 20th of the following month.
        ("modelo-349-2025-03", date(2025, 4, 1), date(2025, 4, 20)),
        # July monthly window has its closure extended to 20 September (BOE Orden EHA/769/2010 art-10).
        ("modelo-349-2025-07", date(2025, 8, 1), date(2025, 9, 20)),
        # December monthly window closes 30 January of the following year (extended).
        ("modelo-349-2025-12", date(2026, 1, 1), date(2026, 1, 30)),
        # Standard quarterly window: 1st to 20th of the month after the quarter ends.
        ("modelo-349-2025-2t", date(2025, 7, 1), date(2025, 7, 20)),
        # Fourth-quarter window closes 30 January of the following year (extended).
        ("modelo-349-2025-4t", date(2026, 1, 1), date(2026, 1, 30)),
    ],
)
def test_committed_modelo_349_deadline_windows_match_official_plazo_rules(
    window_id: str,
    expected_open: date,
    expected_close: date,
) -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    window = next(w for w in revision.deadline_windows if w.id == window_id)
    assert window.opens_on == expected_open
    assert window.closes_on == expected_close


def test_committed_modelo_349_deadline_windows_are_unique_by_period() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    seen: set[tuple[int, str]] = set()
    for window in revision.deadline_windows:
        key = (window.period.filing_year, window.period.registry_token)
        assert key not in seen, f"duplicate deadline window for period {window.period}"
        seen.add(key)


def test_committed_modelo_349_deadline_app_link_is_registered() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    deadline_links = [link for link in revision.application_links if link.surface == "deadline"]
    assert len(deadline_links) == 1
    assert deadline_links[0].id == "modelo-349-deadline"
    assert deadline_links[0].requires_snapshot is True


def test_committed_modelo_349_export_layout_declares_three_fixed_width_records() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    assert len(revision.export_layouts) == 1
    layout = revision.export_layouts[0]
    assert layout.id == "modelo-349-fichero-2020"
    assert layout.format == "fixed_width"

    record_types = {record.record_type: record for record in layout.records}
    assert set(record_types) == {"declarante", "operador", "rectificacion"}
    for record in layout.records:
        assert record.encoding == "latin-1"
        assert record.line_ending == "none"


@pytest.mark.parametrize(
    ("record_type", "expected_record_type_literal"),
    [
        ("declarante", "1"),
        ("operador", "2"),
        ("rectificacion", "2"),
    ],
)
def test_committed_modelo_349_export_records_open_with_official_record_type_literal(
    record_type: str,
    expected_record_type_literal: str,
) -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    layout = revision.export_layouts[0]
    record = next(item for item in layout.records if item.record_type == record_type)
    first_field = record.fields[0]
    assert first_field.offset == 1
    assert first_field.length == 1
    assert first_field.kind == "literal"
    assert first_field.literal == expected_record_type_literal


def test_committed_modelo_349_export_records_total_five_hundred_bytes_each() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    layout = revision.export_layouts[0]
    for record in layout.records:
        total = sum(field.length or 0 for field in record.fields)
        assert total == 500, f"record {record.record_type!r} totals {total} bytes; expected 500"


def test_committed_modelo_349_export_records_have_contiguous_non_overlapping_fields() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    layout = revision.export_layouts[0]
    for record in layout.records:
        cursor = 1
        for field in record.fields:
            assert field.offset == cursor, (
                f"record {record.record_type!r} field {field.id!r} offset {field.offset} "
                f"breaks contiguity (expected {cursor})"
            )
            assert field.length is not None
            cursor += field.length
        assert cursor == 501, f"record {record.record_type!r} last field ends at {cursor - 1}; expected 500"


def test_committed_modelo_349_export_casilla_fields_resolve_to_revision_casillas() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    layout = revision.export_layouts[0]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    for record in layout.records:
        for field in record.fields:
            if field.kind != "casilla":
                continue
            assert field.casilla in casilla_ids, (
                f"export field {field.id!r} references unknown casilla {field.casilla!r}"
            )


def test_committed_modelo_349_export_app_link_is_registered() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    export_links = [link for link in revision.application_links if link.surface == "export"]
    assert len(export_links) == 1
    assert export_links[0].id == "modelo-349-export"
    assert export_links[0].requires_snapshot is True


def test_committed_modelo_349_construct_includes_export_layout() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    construct = revision.constructs[0]
    assert set(construct.export_layouts) == {layout.id for layout in revision.export_layouts}


def test_committed_modelo_349_extraction_profiles_target_declarant_summary_casillas() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    profiles_by_id = {profile.id: profile for profile in revision.extraction_profiles}
    assert set(profiles_by_id) == {"modelo-349-declaracion-pdf", "modelo-349-submitted-file"}

    pdf_profile = profiles_by_id["modelo-349-declaracion-pdf"]
    assert pdf_profile.surface == "declaracion_pdf"
    assert pdf_profile.parser == "aeat.adapters.inbound.declaracion.parse_declaracion"
    assert pdf_profile.failure_semantics == "fail_hard"
    assert {t.casilla_id for t in pdf_profile.target_casillas} == {
        "decl.numero-operadores",
        "decl.importe-operaciones",
        "decl.numero-rectificaciones",
        "decl.importe-rectificaciones",
    }

    submitted_profile = profiles_by_id["modelo-349-submitted-file"]
    assert submitted_profile.surface == "export_record"
    assert submitted_profile.parser == "aeat.domain.calculations.registry.parse_export_payload"
    assert submitted_profile.confidence == "strict"
    declarant_casilla_ids = {casilla.id for casilla in revision.casillas if casilla.section[0] == "declarante"}
    assert {t.casilla_id for t in submitted_profile.target_casillas} == declarant_casilla_ids


def test_committed_modelo_349_extractor_app_link_is_registered() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    extractor_links = [link for link in revision.application_links if link.surface == "extractor"]
    assert len(extractor_links) == 1
    assert extractor_links[0].id == "modelo-349-extractor"
    assert extractor_links[0].consumer == "aeat.adapters.inbound.declaracion.parse_declaracion"


def test_committed_modelo_349_construct_includes_extraction_profiles() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    construct = revision.constructs[0]
    assert set(construct.extraction_profiles) == {profile.id for profile in revision.extraction_profiles}


def test_committed_modelo_349_record_design_round_trips_declarante_operador_rectificacion() -> None:
    modelo, catalogues = _load_modelo_349()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )
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
    assert by_record_casilla[(decl, "decl.numero-operadores")] == Decimal("2")
    assert by_record_casilla[(decl, "decl.importe-operaciones")] == Decimal("1500.50")
    assert by_record_casilla[(decl, "decl.numero-rectificaciones")] == Decimal("1")
    assert by_record_casilla[(decl, "decl.importe-rectificaciones")] == Decimal("100.00")

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


def _fixed_width_record(length: int, fields: dict[tuple[int, int], str]) -> str:
    record = [" "] * length
    for (start, end), value in fields.items():
        if len(value) != end - start + 1:
            raise AssertionError(f"field {start}-{end} has length {len(value)}")
        record[start - 1 : end] = value
    return "".join(record)


def test_committed_modelo_349_declares_invoice_source_bindings_for_declarant_summary() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    invoice_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    assert set(invoice_bindings) == {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    expected_claves = ("E", "M", "H", "A", "T", "S", "I", "R", "D", "C")
    for binding_id in (
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
    ):
        binding = invoice_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    ):
        binding = invoice_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_claves


def test_committed_modelo_349_invoice_binding_requirements_split_by_rectification_scope() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    requirements = invoice_binding_requirements(revision)

    by_scope = {req.rectification_scope: req for req in requirements}
    assert set(by_scope) == {"exclude_rectifications", "only_rectifications"}
    # Both scalar declarant-summary bindings and the 5 operador row bindings
    # share exclude_rectifications + the same clave set, so they all collapse
    # into one requirement cohort.
    expected_exclude = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    }
    expected_only = {
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    }
    assert set(by_scope["exclude_rectifications"].binding_ids) == expected_exclude
    assert set(by_scope["only_rectifications"].binding_ids) == expected_only


def test_committed_modelo_349_invoice_binding_resolver_aggregates_synthetic_ledger() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    non_rect_obs = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR222",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        invoice_id="inv-it-1-rect",
        party_tax_id="IT333",
        country_code="IT",
        transaction_date=date(2026, 3, 8),
        base_amount=Decimal("200.00"),
        intracommunity_clave="E",
        is_rectification=True,
        rectified_base_previous=Decimal("180.00"),
        rectified_period="4T",
        rectified_year=2025,
    )
    observations = (*non_rect_obs, rect_obs)

    resolved = resolve_invoice_binding_values(revision, observations)

    # Assert the four expected binding keys are all present.
    expected_keys = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    assert expected_keys == set(resolved.keys()), "resolver must populate exactly the four declarant bindings"

    # Operator count and total base are derived directly from the non-rectification
    # observations — the resolver must sum distinct operators and their base amounts.
    expected_num_operators = Decimal(len({obs.party_tax_id for obs in non_rect_obs}))
    expected_importe_operaciones = sum((obs.base_amount for obs in non_rect_obs), Decimal("0"))
    assert resolved["iva-349-declarante-numero-operadores"] == expected_num_operators
    assert resolved["iva-349-declarante-importe-operaciones"] == expected_importe_operaciones

    # Rectification count is the number of rectification observations.
    assert resolved["iva-349-declarante-numero-rectificaciones"] == Decimal("1")

    # Rectification importe is the absolute delta between new and previous base,
    # derived from the rectification observation supplied to the resolver.
    assert rect_obs.rectified_base_previous is not None
    expected_rect_delta = abs(rect_obs.base_amount - rect_obs.rectified_base_previous)
    assert resolved["iva-349-declarante-importe-rectificaciones"] == expected_rect_delta


def test_committed_modelo_349_construct_includes_invoice_bindings() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    construct = revision.constructs[0]
    assert set(construct.bindings) == {b.id for b in revision.bindings if b.source == "collectible_invoice"}


def test_committed_modelo_349_declarant_summary_casillas_are_bound_to_invoice_bindings() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    casillas_by_id = {c.id: c for c in revision.casillas}
    expected_bindings = {
        "decl.numero-operadores": "iva-349-declarante-numero-operadores",
        "decl.importe-operaciones": "iva-349-declarante-importe-operaciones",
        "decl.numero-rectificaciones": "iva-349-declarante-numero-rectificaciones",
        "decl.importe-rectificaciones": "iva-349-declarante-importe-rectificaciones",
    }
    for casilla_id, expected_binding in expected_bindings.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind == InputKind.BOUND
        assert casilla.binding == expected_binding


def test_committed_modelo_349_declares_operador_and_rectificacion_row_bindings() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    row_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op == "rows"
    }
    expected_operador_row_bindings = {
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    }
    expected_rectificacion_row_bindings = {
        "iva-349-rectificacion-row-codigo-pais",
        "iva-349-rectificacion-row-nif",
        "iva-349-rectificacion-row-apellidos",
        "iva-349-rectificacion-row-clave",
        "iva-349-rectificacion-row-ejercicio",
        "iva-349-rectificacion-row-periodo",
        "iva-349-rectificacion-row-base-rectificada",
        "iva-349-rectificacion-row-base-anterior",
    }
    assert set(row_bindings) == expected_operador_row_bindings | expected_rectificacion_row_bindings

    for binding_id in expected_operador_row_bindings:
        assert row_bindings[binding_id].selector["grouping"] == "operator_clave"
        assert row_bindings[binding_id].selector["rectification_scope"] == "exclude_rectifications"
    for binding_id in expected_rectificacion_row_bindings:
        assert row_bindings[binding_id].selector["grouping"] == "operator_clave_period"
        assert row_bindings[binding_id].selector["rectification_scope"] == "only_rectifications"


def test_committed_modelo_349_operador_row_resolver_groups_by_operator_and_clave() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    observations = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-de-2",
            party_tax_id="DE111",
            country_code="DE",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR222",
            country_code="FR",
            transaction_date=date(2026, 3, 7),
            base_amount=Decimal("300.50"),
            intracommunity_clave="S",
            party_legal_name="FRANCE SARL",
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    # Two row groups: (DE, DE111, E) at row 1 and (FR, FR222, S) at row 2.
    assert rows[("iva-349-operador-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-operador-row-nif", 1)] == "DE111"
    assert rows[("iva-349-operador-row-apellidos", 1)] == "ALEMAN GMBH"
    assert rows[("iva-349-operador-row-clave", 1)] == "E"
    # Both German observations must contribute to row 1's base.
    # Assertion pins the grouping contract by requiring the aggregate
    # to exceed the larger single-observation value.
    row_1_base = rows[("iva-349-operador-row-base", 1)]
    assert isinstance(row_1_base, Decimal)
    assert row_1_base > Decimal("1000.00"), (
        f"row 1 base = {row_1_base} not greater than max DE observation 1000.00 — "
        f"second German observation did not contribute to the group"
    )
    assert rows[("iva-349-operador-row-codigo-pais", 2)] == "FR"
    assert rows[("iva-349-operador-row-nif", 2)] == "FR222"
    assert rows[("iva-349-operador-row-apellidos", 2)] == "FRANCE SARL"
    assert rows[("iva-349-operador-row-clave", 2)] == "S"
    # Single-observation row: identity passthrough of the fixture value.
    assert rows[("iva-349-operador-row-base", 2)] == Decimal("300.50")


def test_committed_modelo_349_rectificacion_row_resolver_groups_by_operator_clave_period() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    observations = (
        InvoiceObservation(
            invoice_id="inv-de-rect",
            party_tax_id="DE111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1100.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
            is_rectification=True,
            rectified_base_previous=Decimal("1000.00"),
            rectified_period="2T",
            rectified_year=2025,
        ),
        InvoiceObservation(
            invoice_id="inv-it-rect",
            party_tax_id="IT333",
            country_code="IT",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("200.00"),
            intracommunity_clave="E",
            party_legal_name="ITALIA SRL",
            is_rectification=True,
            rectified_base_previous=Decimal("180.00"),
            rectified_period="4T",
            rectified_year=2025,
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    # DE/DE111/E/2025/2T at row 1, IT/IT333/E/2025/4T at row 2.
    assert rows[("iva-349-rectificacion-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-rectificacion-row-nif", 1)] == "DE111"
    assert rows[("iva-349-rectificacion-row-apellidos", 1)] == "ALEMAN GMBH"
    assert rows[("iva-349-rectificacion-row-clave", 1)] == "E"
    assert rows[("iva-349-rectificacion-row-ejercicio", 1)] == "2025"
    assert rows[("iva-349-rectificacion-row-periodo", 1)] == "2T"
    assert rows[("iva-349-rectificacion-row-base-rectificada", 1)] == Decimal("1100.00")
    assert rows[("iva-349-rectificacion-row-base-anterior", 1)] == Decimal("1000.00")
    assert rows[("iva-349-rectificacion-row-codigo-pais", 2)] == "IT"
    assert rows[("iva-349-rectificacion-row-base-rectificada", 2)] == Decimal("200.00")
    assert rows[("iva-349-rectificacion-row-base-anterior", 2)] == Decimal("180.00")


def test_committed_modelo_349_full_invoice_to_casilla_pipeline() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    non_rect_obs = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR222",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        invoice_id="inv-it-1-rect",
        party_tax_id="IT333",
        country_code="IT",
        transaction_date=date(2026, 3, 8),
        base_amount=Decimal("200.00"),
        intracommunity_clave="E",
        is_rectification=True,
        rectified_base_previous=Decimal("180.00"),
        rectified_period="4T",
        rectified_year=2025,
    )
    observations = (*non_rect_obs, rect_obs)

    binding_values = resolve_invoice_binding_values(revision, observations)
    casilla_values = resolve_bound_casilla_inputs(revision, binding_values)

    # Assert the four expected casilla keys are present — wiring check.
    expected_casilla_keys = {
        "decl.numero-operadores",
        "decl.importe-operaciones",
        "decl.numero-rectificaciones",
        "decl.importe-rectificaciones",
    }
    assert expected_casilla_keys == set(casilla_values.keys()), (
        "invoice-to-casilla pipeline must produce exactly the four declarant casillas"
    )

    # Operator and importe values must equal what the resolver computed from the
    # non-rectification observations.
    assert casilla_values["decl.numero-operadores"] == binding_values["iva-349-declarante-numero-operadores"]
    assert casilla_values["decl.importe-operaciones"] == binding_values["iva-349-declarante-importe-operaciones"]

    # Rectification casillas must pass through from binding to casilla unchanged.
    assert (
        casilla_values["decl.numero-rectificaciones"] == (binding_values["iva-349-declarante-numero-rectificaciones"])
    )
    assert (
        casilla_values["decl.importe-rectificaciones"] == (binding_values["iva-349-declarante-importe-rectificaciones"])
    )

    # Rectification delta must equal the absolute difference between new and previous base.
    assert rect_obs.rectified_base_previous is not None
    expected_rect_delta = abs(rect_obs.base_amount - rect_obs.rectified_base_previous)
    assert casilla_values["decl.importe-rectificaciones"] == expected_rect_delta
