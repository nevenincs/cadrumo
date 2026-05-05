"""Tests for committed Modelo 349 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryValidator, build_snapshot, load_registry_tree
from ._bindings import (
    InvoiceObservation,
    invoice_binding_requirements,
    resolve_bound_casilla_inputs,
    resolve_invoice_binding_values,
)
from ._export import resolve_export_layout
from ._export_parse import parse_export_payload

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

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


def _load_modelo_349():
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "349")
    return modelo, catalogues


def test_committed_modelo_349_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_349()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)

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
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period=period,
    )

    assert snapshot.revision.id == expected_revision


def test_committed_modelo_349_is_informative_static_documentation_only() -> None:
    modelo, catalogues = _load_modelo_349()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
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
        expected_number = (
            str(expected_start) if expected_start == expected_end else f"{expected_start}-{expected_end}"
        )
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
        ("op.codigo-pais", "text"),
        ("op.nif-comunitario", "text"),
        ("op.apellidos-razon-social", "text"),
        ("op.clave-operacion", "text"),
        ("op.base-imponible", "money"),
        ("rect.ejercicio-rectificado", "integer"),
        ("rect.periodo-rectificado", "text"),
        ("rect.base-rectificada", "money"),
        ("rect.base-anterior", "money"),
    ],
)
def test_committed_modelo_349_casilla_data_types_match_official_record_design(
    casilla_id: str, expected_data_type: str
) -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    casilla = next(item for item in revision.casillas if item.id == casilla_id)
    assert casilla.data_type == expected_data_type


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
    auth_surface = next(
        ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read"
    )

    assert auth_surface.surface == "authenticated_read_surface"
    assert set(auth_surface.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}
    assert auth_surface.requires_authentication is True
    assert auth_surface.requires_aeat_authorization is True
    assert auth_surface.synthetic_data_allowed is False


def test_committed_modelo_349_authenticated_read_surface_forbids_aeat_state_mutations() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    auth_surface = next(
        ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read"
    )

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
    auth_surface = next(
        ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read"
    )

    assert "www6.agenciatributaria.gob.es" in auth_surface.allowed_hosts
    for host in auth_surface.allowed_hosts:
        assert host.endswith("agenciatributaria.gob.es"), f"non-AEAT host allowed: {host!r}"


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
    artefact_path = PROJECT_ROOT / source.corpus_path
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
    assert len(quarterly.profile_conditions) == 1
    quarterly_predicate = quarterly.profile_conditions[0]
    assert quarterly_predicate.field == "iva.intracommunity_operations_exceed_50000_eur"
    assert quarterly_predicate.op == "equals"
    assert quarterly_predicate.value is False

    monthly = schedules_by_id["modelo-349-mensual"]
    assert monthly.period_kind == "monthly"
    assert monthly.periods == ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
    monthly_predicate = monthly.profile_conditions[0]
    assert monthly_predicate.field == "iva.intracommunity_operations_exceed_50000_eur"
    assert monthly_predicate.value is True


def test_committed_modelo_349_deadline_windows_cover_every_supported_period_per_year() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    expected_periods = {f"{m:02d}" for m in range(1, 13)} | {f"{q}T" for q in range(1, 5)}
    by_year: dict[int, set[str]] = {}
    for window in revision.deadline_windows:
        period_code = window.period.split("-", 1)[1]
        by_year.setdefault(window.filing_year, set()).add(period_code)

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
    seen: set[str] = set()
    for window in revision.deadline_windows:
        assert window.period not in seen, f"duplicate deadline window for period {window.period}"
        seen.add(window.period)


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
    record_type: str, expected_record_type_literal: str
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
    assert set(pdf_profile.target_casillas) == {
        "decl.numero-operadores",
        "decl.importe-operaciones",
        "decl.numero-rectificaciones",
        "decl.importe-rectificaciones",
    }

    submitted_profile = profiles_by_id["modelo-349-submitted-file"]
    assert submitted_profile.surface == "export_record"
    assert submitted_profile.parser == "aeat.domain.calculations.registry.parse_export_payload"
    assert submitted_profile.confidence == "strict"
    casilla_ids = {casilla.id for casilla in revision.casillas}
    assert set(submitted_profile.target_casillas) == casilla_ids


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
        source_root=PROJECT_ROOT,
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

    decl = "modelo-349-declarante"
    op = "modelo-349-operador"
    rect = "modelo-349-rectificacion"

    assert by_record_casilla[(decl, "decl.numero-operadores")] == Decimal("2")
    assert by_record_casilla[(decl, "decl.importe-operaciones")] == Decimal("1500.50")
    assert by_record_casilla[(decl, "decl.numero-rectificaciones")] == Decimal("1")
    assert by_record_casilla[(decl, "decl.importe-rectificaciones")] == Decimal("100.00")

    assert by_record_casilla[(op, "op.codigo-pais")] == "DE"
    assert by_record_casilla[(op, "op.nif-comunitario")] == "123456789012345"
    assert by_record_casilla[(op, "op.clave-operacion")] == "E"
    assert by_record_casilla[(op, "op.base-imponible")] == Decimal("1500.50")

    assert by_record_casilla[(rect, "op.codigo-pais")] == "FR"
    assert by_record_casilla[(rect, "op.clave-operacion")] == "A"
    assert by_record_casilla[(rect, "rect.ejercicio-rectificado")] == Decimal("2024")
    assert by_record_casilla[(rect, "rect.periodo-rectificado")] == "1T"
    assert by_record_casilla[(rect, "rect.base-rectificada")] == Decimal("100.00")
    assert by_record_casilla[(rect, "rect.base-anterior")] == Decimal("80.00")


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

    invoice_bindings = {b.id: b for b in revision.bindings if b.source == "invoice"}
    assert set(invoice_bindings) == {
        "vat-349-declarante-numero-operadores",
        "vat-349-declarante-importe-operaciones",
        "vat-349-declarante-numero-rectificaciones",
        "vat-349-declarante-importe-rectificaciones",
    }
    expected_claves = ("E", "M", "H", "A", "T", "S", "I", "R", "D", "C")
    for binding_id in (
        "vat-349-declarante-numero-operadores",
        "vat-349-declarante-importe-operaciones",
    ):
        binding = invoice_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "exclude_rectifications"
        assert tuple(binding.selector["claves"]) == expected_claves
    for binding_id in (
        "vat-349-declarante-numero-rectificaciones",
        "vat-349-declarante-importe-rectificaciones",
    ):
        binding = invoice_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "only_rectifications"
        assert tuple(binding.selector["claves"]) == expected_claves


def test_committed_modelo_349_invoice_binding_requirements_split_by_rectification_scope() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    requirements = invoice_binding_requirements(revision)

    by_scope = {req.rectification_scope: req for req in requirements}
    assert set(by_scope) == {"exclude_rectifications", "only_rectifications"}
    assert by_scope["exclude_rectifications"].binding_ids == (
        "vat-349-declarante-importe-operaciones",
        "vat-349-declarante-numero-operadores",
    )
    assert by_scope["only_rectifications"].binding_ids == (
        "vat-349-declarante-importe-rectificaciones",
        "vat-349-declarante-numero-rectificaciones",
    )


def test_committed_modelo_349_invoice_binding_resolver_aggregates_synthetic_ledger() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    observations = (
        # Two distinct operators in non-rectification scope, base sum 1500.50.
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
        # One rectification: previous 180, new 200 → delta 20.
        InvoiceObservation(
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
        ),
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved == {
        "vat-349-declarante-numero-operadores": Decimal("2"),
        "vat-349-declarante-importe-operaciones": Decimal("1500.50"),
        "vat-349-declarante-numero-rectificaciones": Decimal("1"),
        "vat-349-declarante-importe-rectificaciones": Decimal("20.00"),
    }


def test_committed_modelo_349_construct_includes_invoice_bindings() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    construct = revision.constructs[0]
    assert set(construct.bindings) == {b.id for b in revision.bindings if b.source == "invoice"}


def test_committed_modelo_349_declarant_summary_casillas_are_bound_to_invoice_bindings() -> None:
    modelo, _ = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]

    casillas_by_id = {c.id: c for c in revision.casillas}
    expected_bindings = {
        "decl.numero-operadores": "vat-349-declarante-numero-operadores",
        "decl.importe-operaciones": "vat-349-declarante-importe-operaciones",
        "decl.numero-rectificaciones": "vat-349-declarante-numero-rectificaciones",
        "decl.importe-rectificaciones": "vat-349-declarante-importe-rectificaciones",
    }
    for casilla_id, expected_binding in expected_bindings.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind == "bound"
        assert casilla.binding == expected_binding


def test_committed_modelo_349_full_invoice_to_casilla_pipeline() -> None:
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
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR222",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
        InvoiceObservation(
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
        ),
    )

    binding_values = resolve_invoice_binding_values(revision, observations)
    casilla_values = resolve_bound_casilla_inputs(revision, binding_values)

    assert casilla_values == {
        "decl.numero-operadores": Decimal("2"),
        "decl.importe-operaciones": Decimal("1500.50"),
        "decl.numero-rectificaciones": Decimal("1"),
        "decl.importe-rectificaciones": Decimal("20.00"),
    }
