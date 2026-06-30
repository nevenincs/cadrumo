"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_369_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _casilla_id,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = _casilla_id("decl.periodo")


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
