"""Tests for committed Modelo 349 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import cast

import pytest

from .....core import BindingSourceKind
from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import AEAT_HOST_SUFFIX_EXPECTED, aeat_host
from .. import (
    CasillaFieldKind,
    CasillaId,
    InputKind,
    InvoiceObservation,
    ModeloRevision,
    RegistryValidator,
    build_snapshot,
    invoice_binding_requirements,
    load_registry_tree,
    parse_export_payload,
    resolve_bound_inputs_by_casilla_id,
    resolve_export_layout,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
    validated_casilla_id,
)
from .._corpus_catalogue import verify_source_file
from .._legal import verify_legal_catalogue
from .._schema import DataBindingDefinition
from .._text import normalise_corpus_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW6_HOST = aeat_host("www6")

# Field positions taken from Orden HAC/174/2020 Anexo (DR_Anexo_349.pdf
# pages 9-22), the layout authority cited by Modelo 349's registry revision.
# Tipo 1 = registro de declarante (500 bytes); Tipo 2 = registro de operador
# intracomunitario / rectificaciones (500 bytes).


def _casilla_id(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test_modelo_349_registry._OFFICIAL_FIELD_POSITIONS")


_DECL_NUMERO_OPERADORES_CASILLA: CasillaId = _casilla_id("decl.numero-operadores")
_DECL_IMPORTE_OPERACIONES_CASILLA: CasillaId = _casilla_id("decl.importe-operaciones")
_DECL_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = _casilla_id("decl.numero-rectificaciones")
_DECL_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = _casilla_id("decl.importe-rectificaciones")
_OP_CODIGO_PAIS_CASILLA: CasillaId = _casilla_id("op.codigo-pais")
_OP_NIF_COMUNITARIO_CASILLA: CasillaId = _casilla_id("op.nif-comunitario")
_OP_APELLIDOS_RAZON_SOCIAL_CASILLA: CasillaId = _casilla_id("op.apellidos-razon-social")
_OP_CLAVE_OPERACION_CASILLA: CasillaId = _casilla_id("op.clave-operacion")
_OP_BASE_IMPONIBLE_CASILLA: CasillaId = _casilla_id("op.base-imponible")
_RECT_EJERCICIO_RECTIFICADO_CASILLA: CasillaId = _casilla_id("rect.ejercicio-rectificado")
_RECT_PERIODO_RECTIFICADO_CASILLA: CasillaId = _casilla_id("rect.periodo-rectificado")
_RECT_BASE_RECTIFICADA_CASILLA: CasillaId = _casilla_id("rect.base-rectificada")
_RECT_BASE_ANTERIOR_CASILLA: CasillaId = _casilla_id("rect.base-anterior")
_DECLARANT_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_NUMERO_OPERADORES_CASILLA,
    _DECL_IMPORTE_OPERACIONES_CASILLA,
    _DECL_NUMERO_RECTIFICACIONES_CASILLA,
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA,
)
_M349_SUBSTANTIVE_BINDING_LEGAL_REFS = frozenset(
    {
        "rd-1624-1992:art-79",
        "rd-1624-1992:art-80",
        "ley-37-1992:art-9-bis",
        "ley-37-1992:art-13",
        "ley-37-1992:art-15",
        "ley-37-1992:art-25",
        "ley-37-1992:art-26",
        "ley-37-1992:art-27",
        "ley-37-1992:art-69",
        "ley-37-1992:art-70",
        "ley-37-1992:art-80",
        "ley-37-1992:art-84",
        "ley-37-1992:art-86",
    },
)

_OFFICIAL_FIELD_POSITIONS: dict[CasillaId, tuple[int, int]] = {
    _DECL_NUMERO_OPERADORES_CASILLA: (138, 146),
    _DECL_IMPORTE_OPERACIONES_CASILLA: (147, 161),
    _DECL_NUMERO_RECTIFICACIONES_CASILLA: (162, 170),
    _DECL_IMPORTE_RECTIFICACIONES_CASILLA: (171, 185),
    _OP_CODIGO_PAIS_CASILLA: (76, 77),
    _OP_NIF_COMUNITARIO_CASILLA: (78, 92),
    _OP_APELLIDOS_RAZON_SOCIAL_CASILLA: (93, 132),
    _OP_CLAVE_OPERACION_CASILLA: (133, 133),
    _OP_BASE_IMPONIBLE_CASILLA: (134, 146),
    _RECT_EJERCICIO_RECTIFICADO_CASILLA: (147, 150),
    _RECT_PERIODO_RECTIFICADO_CASILLA: (151, 152),
    _RECT_BASE_RECTIFICADA_CASILLA: (153, 165),
    _RECT_BASE_ANTERIOR_CASILLA: (166, 178),
}
_OFFICIAL_FIELD_WIDTHS: dict[CasillaId, int] = {
    casilla_id: end - start + 1 for casilla_id, (start, end) in _OFFICIAL_FIELD_POSITIONS.items()
}
_M349_GB_XI_SOURCE_REF = "aeat-modelo-349-instructions"
_M349_GB_XI_ORDINARY_BINDINGS = (
    "iva-349-operador-row-codigo-pais",
    "iva-349-operador-row-codigo-pais-adquisicion",
)
_M349_GB_XI_RECTIFICATION_BINDINGS = (
    "iva-349-rectificacion-row-codigo-pais",
    "iva-349-rectificacion-row-codigo-pais-adquisicion",
)
_M349_GB_XI_ORDINARY_REQUIRED_TEXT = (
    "exclusivamente para los bienes (no para servicios)",
    "NIVA que comenzará por XI",
    "Para los períodos 1M y 1T de 2021, el modelo 349 admitirá los prefijos GB y XI",
    "Para los periodos 2M a 12M y 2T a 4T de 2021 sólo se admitirá el prefijo XI",
)
_M349_GB_XI_RECTIFICATION_REQUIRED_TEXT = (
    "Para las rectificaciones de operaciones anteriores a 2021, sólo se admitirá el prefijo GB",
    "Para las rectificaciones de operaciones del 1M o 1T de 2021",
    "Para las rectificaciones de operaciones de 2M a 12M y 2T a 4T de 2021, sólo se admitirá el prefijo XI",
)
_M349_CADENCE_LEGAL_REF = "rd-1624-1992:art-81"
_M349_CADENCE_REQUIRED_TEXT = (
    "Lugar, forma y plazos de presentacion de la declaracion recapitulativa",
    "por cada mes natural durante los veinte primeros dias naturales",
    "en cada uno de los cuatro trimestres naturales anteriores",
    "50.000 euros",
    "durante los veinte primeros dias naturales del mes inmediato siguiente al correspondiente periodo trimestral",
)


@lru_cache(maxsize=1)
def _load_modelo_349():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "349")
    return modelo, catalogues


def _modelo_349_revision() -> ModeloRevision:
    modelo, _ = _load_modelo_349()
    return modelo.revisions["2020-y-siguientes"]


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


@pytest.mark.parametrize(
    ("casilla_id", "expected_data_type"),
    [
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
    ],
)
def test_committed_modelo_349_casilla_data_types_match_official_record_design(
    casilla_id: CasillaId,
    expected_data_type: str,
) -> None:
    revision = _modelo_349_revision()
    casilla = next(item for item in revision.casillas if item.id == casilla_id)
    assert casilla.data_type == expected_data_type


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


def test_committed_modelo_349_authenticated_read_surface_allows_read_only_methods_only() -> None:
    revision = _modelo_349_revision()
    auth_surface = next(ref for ref in revision.live_cross_references if ref.id == "modelo-349-filed-declarations-read")

    assert auth_surface.surface == "authenticated_read_surface"
    assert set(auth_surface.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}
    assert auth_surface.requires_authentication is True
    assert auth_surface.requires_aeat_authorization is True
    assert auth_surface.synthetic_data_allowed is False


def test_committed_modelo_349_authenticated_read_surface_forbids_aeat_state_mutations() -> None:
    revision = _modelo_349_revision()
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
    revision = _modelo_349_revision()
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


def test_committed_modelo_349_gb_xi_country_prefix_rules_are_cited_to_aeat_instructions() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    source = catalogues.sources[_M349_GB_XI_SOURCE_REF]

    assert source.evidence_tier == "official_source_guidance"
    assert source.kind == "instructions"
    assert source.corpus_path == "corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.txt"
    assert source.sha256 == "da88207bffeb21d0ea94a28229f8657cec0d88769d132d10ecdb74b66ce9e5e8"
    assert source.bytes == 70701
    assert source.source_url.endswith("/GI28/instr_mod_349.pdf")
    verify_source_file(PROJECT_ROOT, source)

    source_text = normalise_corpus_text((bundled_path() / source.corpus_path).read_text(encoding="utf-8"))
    for required_text in _M349_GB_XI_ORDINARY_REQUIRED_TEXT + _M349_GB_XI_RECTIFICATION_REQUIRED_TEXT:
        assert normalise_corpus_text(required_text) in source_text

    bindings = {binding.id: binding for binding in revision.bindings}
    expected_by_binding = {
        **{binding_id: _M349_GB_XI_ORDINARY_REQUIRED_TEXT for binding_id in _M349_GB_XI_ORDINARY_BINDINGS},
        **{
            binding_id: _M349_GB_XI_RECTIFICATION_REQUIRED_TEXT
            for binding_id in _M349_GB_XI_RECTIFICATION_BINDINGS
        },
    }
    for binding_id, expected_required_text in expected_by_binding.items():
        binding = bindings[binding_id]
        assert _M349_GB_XI_SOURCE_REF in binding.source_refs
        (instruction_citation,) = (
            citation for citation in binding.source_citations if citation.source_ref == _M349_GB_XI_SOURCE_REF
        )
        assert instruction_citation.required_text == expected_required_text


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
    revision = _modelo_349_revision()
    window = next(w for w in revision.deadline_windows if w.id == window_id)
    assert window.opens_on == expected_open
    assert window.closes_on == expected_close


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
    revision = _modelo_349_revision()
    layout = revision.export_layouts[0]
    record = next(item for item in layout.records if item.record_type == record_type)
    first_field = record.fields[0]
    assert first_field.offset == 1
    assert first_field.length == 1
    assert first_field.kind is CasillaFieldKind.LITERAL
    assert first_field.literal == expected_record_type_literal


def test_committed_modelo_349_export_records_total_five_hundred_bytes_each() -> None:
    revision = _modelo_349_revision()
    layout = revision.export_layouts[0]
    for record in layout.records:
        total = sum(field.length or 0 for field in record.fields)
        assert total == 500, f"record {record.record_type!r} totals {total} bytes; expected 500"


def test_committed_modelo_349_export_records_have_contiguous_non_overlapping_fields() -> None:
    revision = _modelo_349_revision()
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
    revision = _modelo_349_revision()
    layout = revision.export_layouts[0]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    for record in layout.records:
        for field in record.fields:
            if field.kind is not CasillaFieldKind.CASILLA:
                continue
            assert field.casilla_id in casilla_ids, (
                f"export field {field.id!r} references unknown casilla {field.casilla_id!r}"
            )


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
    assert pdf_profile.parser == "aeat.adapters.inbound.declaracion.parse_declaracion"
    assert pdf_profile.failure_semantics == "fail_hard"
    assert {t.casilla_id for t in pdf_profile.target_casillas} == set(_DECLARANT_SUMMARY_CASILLAS)

    submitted_profile = profiles_by_id["modelo-349-submitted-file"]
    assert submitted_profile.surface == "export_record"
    assert submitted_profile.parser == "aeat.domain.calculations.registry.parse_export_payload"
    assert submitted_profile.confidence == "strict"
    declarant_casilla_ids = {casilla.id for casilla in revision.casillas if casilla.section[0] == "declarante"}
    assert {t.casilla_id for t in submitted_profile.target_casillas} == declarant_casilla_ids


def test_committed_modelo_349_extractor_app_link_is_registered() -> None:
    revision = _modelo_349_revision()
    extractor_links = [link for link in revision.application_links if link.surface == "extractor"]
    assert len(extractor_links) == 1
    assert extractor_links[0].id == "modelo-349-extractor"
    assert extractor_links[0].consumer == "aeat.adapters.inbound.declaracion.parse_declaracion"


def test_committed_modelo_349_construct_includes_extraction_profiles() -> None:
    revision = _modelo_349_revision()
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


def _fixed_width_record(length: int, fields: dict[tuple[int, int], str]) -> str:
    record = [" "] * length
    for (start, end), value in fields.items():
        if len(value) != end - start + 1:
            raise AssertionError(f"field {start}-{end} has length {len(value)}")
        record[start - 1 : end] = value
    return "".join(record)


def test_committed_modelo_349_declares_invoice_source_bindings_for_declarant_summary() -> None:
    revision = _modelo_349_revision()

    collectible_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    payable_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "payable_invoice" and b.aggregation is not None and b.aggregation.op != "rows"
    }
    expected_collectible = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    expected_payable = {f"{binding_id}-adquisicion" for binding_id in expected_collectible}
    assert set(collectible_bindings) == expected_collectible
    assert set(payable_bindings) == expected_payable

    expected_claves = ("E", "M", "H", "A", "T", "S", "I", "R", "D", "C")
    for binding_id in (
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
    ):
        binding = collectible_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    ):
        binding = collectible_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_claves

    expected_payable_claves = ("A", "I", "T")
    for binding_id in (
        "iva-349-declarante-numero-operadores-adquisicion",
        "iva-349-declarante-importe-operaciones-adquisicion",
    ):
        binding = payable_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_payable_claves
    for binding_id in (
        "iva-349-declarante-numero-rectificaciones-adquisicion",
        "iva-349-declarante-importe-rectificaciones-adquisicion",
    ):
        binding = payable_bindings[binding_id]
        assert binding.selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", binding.selector["claves"]) == expected_payable_claves


def test_committed_modelo_349_invoice_binding_requirements_split_by_rectification_scope() -> None:
    revision = _modelo_349_revision()
    requirements = invoice_binding_requirements(revision)

    by_scope_and_claves = {(req.rectification_scope, req.claves): req for req in requirements}
    expected_collectible_claves = ("A", "C", "D", "E", "H", "I", "M", "R", "S", "T")
    expected_payable_claves = ("A", "I", "T")
    assert set(by_scope_and_claves) == {
        ("exclude_rectifications", expected_collectible_claves),
        ("only_rectifications", expected_collectible_claves),
        ("exclude_rectifications", expected_payable_claves),
        ("only_rectifications", expected_payable_claves),
    }
    expected_collectible_exclude = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    }
    expected_collectible_only = {
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
    expected_payable_exclude = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_exclude}
    expected_payable_only = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_only}
    assert (
        set(by_scope_and_claves[("exclude_rectifications", expected_collectible_claves)].binding_ids)
        == expected_collectible_exclude
    )
    assert (
        set(by_scope_and_claves[("only_rectifications", expected_collectible_claves)].binding_ids)
        == expected_collectible_only
    )
    assert (
        set(by_scope_and_claves[("exclude_rectifications", expected_payable_claves)].binding_ids)
        == expected_payable_exclude
    )
    assert (
        set(by_scope_and_claves[("only_rectifications", expected_payable_claves)].binding_ids) == expected_payable_only
    )


def test_committed_modelo_349_invoice_bindings_resolve_substantive_legal_refs() -> None:
    modelo, catalogues = _load_modelo_349()
    revision = modelo.revisions["2020-y-siguientes"]
    invoice_bindings = [
        binding for binding in revision.bindings if binding.source in {"collectible_invoice", "payable_invoice"}
    ]

    assert len(invoice_bindings) == 34
    assert sum(1 for binding in invoice_bindings if binding.source == "collectible_invoice") == 17
    assert sum(1 for binding in invoice_bindings if binding.source == "payable_invoice") == 17
    assert set(catalogues.legal) >= _M349_SUBSTANTIVE_BINDING_LEGAL_REFS

    for binding in invoice_bindings:
        refs = set(binding.legal_refs)
        unresolved_refs = sorted(ref for ref in refs if ref not in catalogues.legal)
        assert not unresolved_refs, f"binding {binding.id!r} has unresolved legal refs: {unresolved_refs!r}"
        assert refs >= _M349_SUBSTANTIVE_BINDING_LEGAL_REFS, (
            f"binding {binding.id!r} is missing substantive M349 legal refs: "
            f"{sorted(_M349_SUBSTANTIVE_BINDING_LEGAL_REFS - refs)!r}"
        )
        assert "ley-37-1992:art-141" not in refs, (
            f"binding {binding.id!r} must not cite LIVA art. 141; that article is the travel-agency "
            "special regime, not M349 triangular or intracommunity operation grounding"
        )


def test_committed_modelo_349_invoice_binding_resolver_aggregates_synthetic_ledger() -> None:
    revision = _modelo_349_revision()

    non_rect_obs = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        invoice_id="inv-it-1-rect",
        party_tax_id="IT12345678901",
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

    # Assert the source-specific scalar binding keys are all present.
    expected_collectible_keys = {
        "iva-349-declarante-numero-operadores",
        "iva-349-declarante-importe-operaciones",
        "iva-349-declarante-numero-rectificaciones",
        "iva-349-declarante-importe-rectificaciones",
    }
    expected_payable_keys = {f"{binding_id}-adquisicion" for binding_id in expected_collectible_keys}
    assert expected_collectible_keys | expected_payable_keys == set(resolved.keys()), (
        "resolver must populate the four public declarant bindings plus payable acquisition mirrors"
    )

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
    for binding_id in expected_payable_keys:
        assert resolved[binding_id] == Decimal("0")


def test_committed_modelo_349_invoice_binding_resolver_separates_payable_service_acquisitions() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            invoice_id="inv-it-service-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="IT12345678901",
            country_code="IT",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("3000.00"),
            intracommunity_clave="I",
        ),
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolved["iva-349-declarante-importe-operaciones"] == Decimal("0")
    assert resolved["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolved["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("3000.00")


def test_committed_modelo_349_row_resolver_appends_payable_acquisitions_to_public_export_rows() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            invoice_id="inv-de-sale",
            party_tax_id="DE111111111",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
            party_legal_name="SALE GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-de-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="DE222222222",
            country_code="DE",
            transaction_date=date(2026, 3, 2),
            base_amount=Decimal("750.00"),
            intracommunity_clave="A",
            party_legal_name="SUPPLIER GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-it-service-acq",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            party_tax_id="IT12345678901",
            country_code="IT",
            transaction_date=date(2026, 3, 3),
            base_amount=Decimal("3000.00"),
            intracommunity_clave="I",
            party_legal_name="SERVIZI SRL",
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    assert rows[("iva-349-operador-row-clave", 1)] == "E"
    assert rows[("iva-349-operador-row-nif", 1)] == "111111111"
    assert rows[("iva-349-operador-row-clave-adquisicion", 1)] == "A"
    assert rows[("iva-349-operador-row-nif-adquisicion", 1)] == "222222222"
    assert rows[("iva-349-operador-row-clave-adquisicion", 2)] == "I"
    assert rows[("iva-349-operador-row-nif-adquisicion", 2)] == "12345678901"
    assert rows[("iva-349-operador-row-clave", 2)] == "A"
    assert rows[("iva-349-operador-row-nif", 2)] == "222222222"
    assert rows[("iva-349-operador-row-clave", 3)] == "I"
    assert rows[("iva-349-operador-row-nif", 3)] == "12345678901"


def test_committed_modelo_349_construct_includes_invoice_bindings() -> None:
    revision = _modelo_349_revision()
    construct = revision.constructs[0]
    assert set(construct.bindings) == {
        b.id for b in revision.bindings if b.source in {"collectible_invoice", "payable_invoice"}
    }


def test_committed_modelo_349_declarant_summary_casillas_are_bound_to_invoice_bindings() -> None:
    revision = _modelo_349_revision()

    casillas_by_id = {c.id: c for c in revision.casillas}
    expected_bindings: dict[CasillaId, str] = {
        _DECL_NUMERO_OPERADORES_CASILLA: "iva-349-declarante-numero-operadores",
        _DECL_IMPORTE_OPERACIONES_CASILLA: "iva-349-declarante-importe-operaciones",
        _DECL_NUMERO_RECTIFICACIONES_CASILLA: "iva-349-declarante-numero-rectificaciones",
        _DECL_IMPORTE_RECTIFICACIONES_CASILLA: "iva-349-declarante-importe-rectificaciones",
    }
    for casilla_id, expected_binding in expected_bindings.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.input_kind == InputKind.BOUND
        assert casilla.binding == expected_binding


def test_committed_modelo_349_declares_operador_and_rectificacion_row_bindings() -> None:
    revision = _modelo_349_revision()

    row_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "collectible_invoice" and b.aggregation is not None and b.aggregation.op == "rows"
    }
    payable_row_bindings: dict[str, DataBindingDefinition] = {
        b.id: b
        for b in revision.bindings
        if b.source == "payable_invoice" and b.aggregation is not None and b.aggregation.op == "rows"
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
    assert set(payable_row_bindings) == {
        f"{binding_id}-adquisicion"
        for binding_id in expected_operador_row_bindings | expected_rectificacion_row_bindings
    }

    for binding_id in expected_operador_row_bindings:
        assert row_bindings[binding_id].selector["grouping"] == "operator_clave"
        assert row_bindings[binding_id].selector["rectification_scope"] == "exclude_rectifications"
        payable_binding = payable_row_bindings[f"{binding_id}-adquisicion"]
        assert payable_binding.selector["grouping"] == "operator_clave"
        assert payable_binding.selector["rectification_scope"] == "exclude_rectifications"
        assert cast("tuple[str, ...]", payable_binding.selector["claves"]) == ("A", "I", "T")
    for binding_id in expected_rectificacion_row_bindings:
        assert row_bindings[binding_id].selector["grouping"] == "operator_clave_period"
        assert row_bindings[binding_id].selector["rectification_scope"] == "only_rectifications"
        payable_binding = payable_row_bindings[f"{binding_id}-adquisicion"]
        assert payable_binding.selector["grouping"] == "operator_clave_period"
        assert payable_binding.selector["rectification_scope"] == "only_rectifications"
        assert cast("tuple[str, ...]", payable_binding.selector["claves"]) == ("A", "I", "T")


def test_committed_modelo_349_operador_row_resolver_groups_by_operator_and_clave() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-de-2",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.00"),
            intracommunity_clave="E",
            party_legal_name="ALEMAN GMBH",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 7),
            base_amount=Decimal("300.50"),
            intracommunity_clave="S",
            party_legal_name="FRANCE SARL",
        ),
    )

    rows = resolve_invoice_binding_row_values(revision, observations)

    # Two row groups: (DE, DE123456789, E) at row 1 and (FR, FR12345678901, S) at row 2.
    assert rows[("iva-349-operador-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-operador-row-nif", 1)] == "123456789"
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
    assert rows[("iva-349-operador-row-nif", 2)] == "12345678901"
    assert rows[("iva-349-operador-row-apellidos", 2)] == "FRANCE SARL"
    assert rows[("iva-349-operador-row-clave", 2)] == "S"
    # Single-observation row: identity passthrough of the fixture value.
    assert rows[("iva-349-operador-row-base", 2)] == Decimal("300.50")


def test_committed_modelo_349_rectificacion_row_resolver_groups_by_operator_clave_period() -> None:
    revision = _modelo_349_revision()

    observations = (
        InvoiceObservation(
            invoice_id="inv-de-rect",
            party_tax_id="DE123456789",
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
            party_tax_id="IT12345678901",
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

    # DE/DE123456789/E/2025/2T at row 1, IT/IT12345678901/E/2025/4T at row 2.
    assert rows[("iva-349-rectificacion-row-codigo-pais", 1)] == "DE"
    assert rows[("iva-349-rectificacion-row-nif", 1)] == "123456789"
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
    revision = _modelo_349_revision()

    non_rect_obs = (
        InvoiceObservation(
            invoice_id="inv-de-1",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 1),
            base_amount=Decimal("1000.00"),
            intracommunity_clave="E",
        ),
        InvoiceObservation(
            invoice_id="inv-fr-1",
            party_tax_id="FR12345678901",
            country_code="FR",
            transaction_date=date(2026, 3, 5),
            base_amount=Decimal("500.50"),
            intracommunity_clave="S",
        ),
    )
    rect_obs = InvoiceObservation(
        invoice_id="inv-it-1-rect",
        party_tax_id="IT12345678901",
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
    casilla_values = resolve_bound_inputs_by_casilla_id(revision, binding_values)

    # Assert the four expected casilla keys are present — wiring check.
    expected_casilla_keys = set(_DECLARANT_SUMMARY_CASILLAS)
    assert expected_casilla_keys == set(casilla_values.keys()), (
        "invoice-to-casilla pipeline must produce exactly the four declarant casillas"
    )

    # Operator and importe values must equal what the resolver computed from the
    # non-rectification observations.
    assert casilla_values[_DECL_NUMERO_OPERADORES_CASILLA] == binding_values["iva-349-declarante-numero-operadores"]
    assert casilla_values[_DECL_IMPORTE_OPERACIONES_CASILLA] == binding_values["iva-349-declarante-importe-operaciones"]

    # Rectification casillas must pass through from binding to casilla unchanged.
    assert (
        casilla_values[_DECL_NUMERO_RECTIFICACIONES_CASILLA]
        == (binding_values["iva-349-declarante-numero-rectificaciones"])
    )
    assert (
        casilla_values[_DECL_IMPORTE_RECTIFICACIONES_CASILLA]
        == (binding_values["iva-349-declarante-importe-rectificaciones"])
    )

    # Rectification delta must equal the absolute difference between new and previous base.
    assert rect_obs.rectified_base_previous is not None
    expected_rect_delta = abs(rect_obs.base_amount - rect_obs.rectified_base_previous)
    assert casilla_values[_DECL_IMPORTE_RECTIFICACIONES_CASILLA] == expected_rect_delta
