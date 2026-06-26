"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_180_SYNTHETIC_FIXTURE,
    _MODELO_193_SYNTHETIC_FIXTURE,
    _MODELO_369_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _casilla_id,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = _casilla_id("decl.periodo")


def test_parser_extracts_modelo_180_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M180 synthetic fixture and verify all three casillas.

    Ground truth is the AEAT-published printed-form template at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_180/files/
        02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf
    Page 1, REGISTRO DE TIPO 1 (REGISTRO DE DECLARANTE) printed layout.

    AEAT label text (verbatim from the printed form bitmap):
      "NUMERO TOTAL DE PERCEPTORES"             (positions 136-144)
      "BASE DE RETENCIONES E INGRESOS A CUENTA" (positions 145-160)
      "RETENCIONES E INGRESOS A CUENTA"         (positions 161-175)

    Confirmed in the Orden HAP/1732/2014 EDI spec
    (01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023…pdf):
      p.4 "NÚMERO TOTAL DE PERCEPTORES"
      p.5 "BASE RETENCIONES E INGRESOS A CUENTA"
      p.6 "RETENCIONES E INGRESOS A CUENTA"

    The synthetic fixture prints those labels so the named_label parser captures
    the trailing value token on each line.  Non-tautological: a pattern that
    drifts from the AEAT-published label format will produce a zero-match
    parse failure.
    """
    filing = parse_declaracion(
        _MODELO_180_SYNTHETIC_FIXTURE,
        modelo_override="180",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "180"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "180"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All three casillas defined by the M180 declaracion_pdf profile must be present.
    assert set(values.keys()) == {
        _DECL_TOTAL_PERCEPTORES_CASILLA,
        _DECL_BASE_TOTAL_CASILLA,
        _DECL_RETENCIONES_TOTAL_CASILLA,
    }, f"expected exactly the three M180 profile casillas, got {set(values.keys())!r}"

    # decl.total-perceptores: fixture prints "Numero total de perceptores 3";
    # parse_spanish_decimal("3") = Decimal("3").
    # Ground truth: AEAT printed form "NUMERO TOTAL DE PERCEPTORES" (positions 136-144).
    assert values[_DECL_TOTAL_PERCEPTORES_CASILLA] == Decimal("3"), (
        f"decl.total-perceptores: expected Decimal('3'), got {values[_DECL_TOTAL_PERCEPTORES_CASILLA]!r}"
    )

    # decl.base-total: fixture prints
    # "Base retenciones e ingresos a cuenta total 12.000,00";
    # parse_spanish_decimal("12.000,00") = Decimal("12000.00").
    # Ground truth: AEAT printed form "BASE DE RETENCIONES E INGRESOS A CUENTA"
    # (positions 145-160, Orden HAP/1732/2014 p.5).
    assert values[_DECL_BASE_TOTAL_CASILLA] == Decimal("12000.00"), (
        f"decl.base-total: expected Decimal('12000.00'), got {values[_DECL_BASE_TOTAL_CASILLA]!r}"
    )

    # decl.retenciones-total: fixture prints
    # "Retenciones e ingresos a cuenta total 2.280,00";
    # parse_spanish_decimal("2.280,00") = Decimal("2280.00").
    # Ground truth: AEAT printed form "RETENCIONES E INGRESOS A CUENTA"
    # (positions 161-175, Orden HAP/1732/2014 p.6).
    assert values[_DECL_RETENCIONES_TOTAL_CASILLA] == Decimal("2280.00"), (
        f"decl.retenciones-total: expected Decimal('2280.00'), got {values[_DECL_RETENCIONES_TOTAL_CASILLA]!r}"
    )


def test_parser_extracts_modelo_193_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M193 synthetic fixture and verify all three casillas.

    Ground truth is the AEAT-published Diseño de Registro Modelo 193 at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_193/files/
        03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf
    Pages 5-6, Tipo de registro 1 (Registro de Declarante):
      136-144: "NÚMERO TOTAL DE PERCEPTORES"
      145-159: "BASE RETENCIONES E INGRESOS A CUENTA"
      160-174: "RETENCIONES E INGRESOS A CUENTA"

    The synthetic fixture appends " total" to the base and retenciones labels
    (identical M180 fixture-disambiguation convention) so the named_label parser
    can distinguish the declarante-level aggregate from per-perceptor rows.

    Non-tautological: the label_patterns in the M193 declaracion_pdf profile are
    grounded against the AEAT-published Diseño de Registro — NOT the registry
    casilla label fields.  A pattern that drifts from the AEAT-published label
    format will produce a zero-match parse failure on this fixture.
    """
    filing = parse_declaracion(
        _MODELO_193_SYNTHETIC_FIXTURE,
        modelo_override="193",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "193"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "193"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All three casillas defined by the M193 declaracion_pdf profile must be present.
    assert set(values.keys()) == {
        _DECL_TOTAL_PERCEPTORES_CASILLA,
        _DECL_BASE_TOTAL_CASILLA,
        _DECL_RETENCIONES_TOTAL_CASILLA,
    }, f"expected exactly the three M193 profile casillas, got {set(values.keys())!r}"

    # decl.total-perceptores: fixture prints "Numero total de perceptores 2";
    # parse_spanish_decimal("2") = Decimal("2").
    # Ground truth: AEAT DR Tipo 1 positions 136-144 "NÚMERO TOTAL DE PERCEPTORES".
    assert values[_DECL_TOTAL_PERCEPTORES_CASILLA] == Decimal("2"), (
        f"decl.total-perceptores: expected Decimal('2'), got {values[_DECL_TOTAL_PERCEPTORES_CASILLA]!r}"
    )

    # decl.base-total: fixture prints
    # "Base retenciones e ingresos a cuenta total 8.000,00";
    # parse_spanish_decimal("8.000,00") = Decimal("8000.00").
    # Ground truth: AEAT DR Tipo 1 positions 145-159 "BASE RETENCIONES E INGRESOS A CUENTA".
    assert values[_DECL_BASE_TOTAL_CASILLA] == Decimal("8000.00"), (
        f"decl.base-total: expected Decimal('8000.00'), got {values[_DECL_BASE_TOTAL_CASILLA]!r}"
    )

    # decl.retenciones-total: fixture prints
    # "Retenciones e ingresos a cuenta total 1.520,00";
    # parse_spanish_decimal("1.520,00") = Decimal("1520.00").
    # Ground truth: AEAT DR Tipo 1 positions 160-174 "RETENCIONES E INGRESOS A CUENTA".
    assert values[_DECL_RETENCIONES_TOTAL_CASILLA] == Decimal("1520.00"), (
        f"decl.retenciones-total: expected Decimal('1520.00'), got {values[_DECL_RETENCIONES_TOTAL_CASILLA]!r}"
    )


def test_parser_extracts_modelo_369_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M369 OSS Union synthetic fixture and verify both casillas.

    Ground truth is AEAT-published material fetched 2026-05-27:

    Source 1 — DR369e21.xlsx (Diseño de Registro Modelo 369, Versión 1.1), sheet T36904 Un:
      Row 14: "2. Ejercicio y período. Ejercicio"
      Row 16: "2. Ejercicio y período. Periodo"
    Saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/
        Descripcion_PresentacionFichero369_v1.pdf

    Source 2 — AEAT online manual "Presentación régimen de la Unión", section 2:
      Section heading: "2. Ejercicio y periodo"
    Saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/
        2-ejercicio-periodo.html

    The synthetic fixture prints:
      "Ejercicio: 2024"
      "Periodo: 1T"
    so the named_label parser matches the AEAT-grounded labels and captures the
    trailing token on each line.

    Non-tautology proof: the label_patterns 'Ejercicio:' and 'Per[ii]odo:' are
    grounded against the AEAT DR field names and manual section heading — NOT the
    registry casilla label fields.  A profile pattern that drifts from this
    AEAT-published vocabulary will produce a zero-match parse failure.
    """
    filing = parse_declaracion(
        _MODELO_369_SYNTHETIC_FIXTURE,
        modelo_override="369",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "369"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "369"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Both casillas defined by the M369 declaracion_pdf profile must be present.
    assert set(values.keys()) == {
        _DECL_EJERCICIO_CASILLA,
        _DECL_PERIODO_CASILLA,
    }, f"expected exactly {{decl.ejercicio, decl.periodo}}, got {set(values.keys())!r}"

    # decl.ejercicio: fixture prints "Ejercicio: 2024";
    # parse_spanish_decimal("2024") = Decimal("2024").
    # Ground truth: DR369e21.xlsx row 14 "2. Ejercicio y período. Ejercicio" and
    # AEAT manual section 2 heading "2. Ejercicio y periodo".
    assert values[_DECL_EJERCICIO_CASILLA] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from AEAT-grounded fixture, got "
        f"{values[_DECL_EJERCICIO_CASILLA]!r}"
    )

    # decl.periodo: fixture prints "Periodo: 1T";
    # '1T' is not a valid Decimal so parse_spanish_decimal raises ValueError and
    # the parser stores the raw token as a string for value_kind='text' casillas.
    # Ground truth: DR369e21.xlsx row 16 "2. Ejercicio y período. Periodo".
    assert values[_DECL_PERIODO_CASILLA] == "1T", (
        f"decl.periodo: expected '1T' from AEAT-grounded fixture, got {values[_DECL_PERIODO_CASILLA]!r}"
    )
