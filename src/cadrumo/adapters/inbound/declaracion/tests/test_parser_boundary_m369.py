"""Modelo 369 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import _MODELO_369_SYNTHETIC_FIXTURE, CasillaId, _expected_period, parse_declaracion

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id("decl.periodo", surface="declaracion_parser_boundary.casilla")
_M369_EXPECTED_VALUES: dict[CasillaId, str] = {
    _DECL_EJERCICIO_CASILLA: "2024",
    _DECL_PERIODO_CASILLA: "1T",
}


def test_parser_extracts_modelo_369_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M369 OSS Union synthetic fixture and verify both casillas.

    Ground truth is AEAT-published material fetched 2026-05-27:

    Source 1 — DR369e21.xlsx (Diseño de Registro Modelo 369, Versión 1.1), sheet T36904 Un:
      Row 14: "2. Ejercicio y período. Ejercicio"
      Row 16: "2. Ejercicio y período. Periodo"
    Saved at:
      src/cadrumo/_data/corpus/aeat_official/instructions/modelo_369/files/
        Descripcion_PresentacionFichero369_v1.pdf

    Source 2 — AEAT online manual "Presentación régimen de la Unión", section 2:
      Section heading: "2. Ejercicio y periodo"
    Saved at:
      src/cadrumo/_data/corpus/aeat_official/instructions/modelo_369/files/
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

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M369_EXPECTED_VALUES
