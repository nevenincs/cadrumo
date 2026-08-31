"""Grounding checks for the current Modelo 345 registry surface."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources._boundary import bundled_path
from .....domain.deadlines.festivos import shift_deadline
from ..authority import bundled_authority
from ..corpus_catalogue import verify_source_catalogue
from ..legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M345_LEGAL_REFS = {
    "orden-hfp-823-2022:art-1",
    "orden-hfp-823-2022:art-2",
    "orden-hfp-823-2022:art-3",
    "orden-hfp-823-2022:art-4",
    "orden-hfp-823-2022:art-5",
    "orden-hfp-528-2023:art-unico",
    "orden-hfp-528-2023:df-unica",
    "orden-hfp-1397-2023:art-sexto",
    "orden-hfp-1397-2023:df-unica",
    "orden-hac-1504-2024:art-octavo",
    "orden-hac-1504-2024:df-unica",
    "orden-hac-1430-2025:art-septimo",
    "orden-hac-1430-2025:df-unica",
}
_M345_SOURCE_REFS = {
    "aeat-modelo-345-procedure",
    "aeat-modelo-345-deadlines",
    "aeat-dr-345-2025",
    "boe-modelo-345-base-order",
    "boe-modelo-345-2023-amendment-hfp-528",
    "boe-modelo-345-2023-amendment-hfp-1397",
    "boe-modelo-345-2024-amendment-hac-1504",
    "boe-modelo-345-2025-amendment-hac-1430",
}


def test_modelo_345_current_registry_uses_2025_sources_without_fake_calculation() -> None:
    authority = bundled_authority()
    modelo = authority.modelo("345")
    revision = modelo.revisions["2025"]

    assert set(modelo.revisions) == {"2025"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M345_LEGAL_REFS
    assert set(modelo.source_refs) == _M345_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert revision.period_selector.years == (2025,)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "orden-hfp-823-2022:art-1",
        "orden-hfp-823-2022:art-3",
        "orden-hfp-823-2022:art-4",
        "orden-hac-1430-2025:art-septimo",
        "orden-hac-1430-2025:df-unica",
    }
    assert set(revision.legal_refs) == _M345_LEGAL_REFS
    assert set(revision.source_refs) == _M345_SOURCE_REFS
    assert revision.casillas
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {window.id for window in revision.deadline_windows} == {"modelo-345-2025-0a"}
    # The window stores the NOMINAL statutory close from orden-hfp-823-2022 art. 4
    # ("entre el 1 y el 31 de enero"), not AEAT's published operational date. The
    # 31st falls on a Saturday in 2026, and the shift that derives 2 February is
    # applied on read. Both halves are asserted because storing the pre-shifted
    # date also passes a bare "operator sees 2 February" check while reporting
    # shifted=False / business_day -- a false statement that discards the
    # statutory date.
    assert {window.closes_on for window in revision.deadline_windows} == {date(2026, 1, 31)}
    (window,) = revision.deadline_windows
    shift = shift_deadline(window.closes_on, modelo="345", ccaa_code=None)
    assert (shift.adjusted_close_date, shift.shifted, shift.shift_reason) == (date(2026, 2, 2), True, "sabado")
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"aeat-dr-345-2025"}
    # "export" joined the surfaces when the modelo's export layout was authored;
    # the link set is a consequence of that, not a drift.
    assert {link.surface for link in revision.application_links} == {"deadline", "export", "filing"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-345-anual"}

    stale_refs = {"enrolled-modelo-345-procedure", "enrolled-modelo-345-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    observed_source_refs.update(ref for link in revision.application_links for ref in link.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M345_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M345_SOURCE_REFS})


def test_modelo_345_additional_data_subfields_follow_official_record_design() -> None:
    revision = bundled_authority().modelo("345").revisions["2025"]
    casillas = {str(casilla.id): casilla for casilla in revision.casillas}

    expected = (
        ("datos-adicionales-claves-abc", "tipo2.107-160", "text", None),
        ("plan-pensiones-denominacion", "tipo2.107-146", "text", "m345_plan_pensiones_denominacion"),
        (
            "fondo-pensiones-numero-registro",
            "tipo2.147-151",
            "text",
            "m345_fondo_pensiones_numero_registro",
        ),
        ("fondo-pensiones-nif", "tipo2.152-160", "nif", "m345_fondo_pensiones_nif"),
        ("entidad-aseguradora-nif", "tipo2.161-169", "nif", "m345_entidad_aseguradora_nif"),
        ("datos-adicionales-clave-i", "tipo2.170-189", "integer", None),
        ("pias-fecha-primera-prima", "tipo2.170-177", "date", "m345_pias_fecha_primera_prima"),
        ("pias-importe-acumulado", "tipo2.178-189", "money", "m345_pias_importe_acumulado"),
        ("datos-adicionales-clave-m", "tipo2.190-270", "text", None),
        ("pepp-denominacion", "tipo2.190-229", "text", "m345_pepp_denominacion"),
        ("pepp-numero-inscripcion", "tipo2.230-269", "text", "m345_pepp_numero_inscripcion"),
        ("pepp-cuenta-subcuenta", "tipo2.270", "text", "m345_pepp_cuenta_subcuenta"),
    )

    for casilla_id, number, data_type, semantic_role in expected:
        casilla = casillas[casilla_id]
        assert casilla.number == number
        assert casilla.data_type == data_type
        assert casilla.semantic_role == semantic_role
        assert "aeat-dr-345-2025" in casilla.source_refs

    assert casillas["plan-pensiones-denominacion"].constraints is not None
    assert casillas["plan-pensiones-denominacion"].constraints.max_length == 40
    assert casillas["fondo-pensiones-numero-registro"].constraints is not None
    assert casillas["fondo-pensiones-numero-registro"].constraints.max_length == 5
    assert casillas["pias-importe-acumulado"].constraints is not None
    assert casillas["pias-importe-acumulado"].constraints.sign == "non_negative"
    assert casillas["pias-importe-acumulado"].constraints.max_value == Decimal("240000")
    assert casillas["pepp-denominacion"].constraints is not None
    assert casillas["pepp-denominacion"].constraints.max_length == 40
    assert casillas["pepp-numero-inscripcion"].constraints is not None
    assert casillas["pepp-numero-inscripcion"].constraints.max_length == 40
    assert casillas["pepp-cuenta-subcuenta"].constraints is not None
    assert casillas["pepp-cuenta-subcuenta"].constraints.enum == ("C", "S")
