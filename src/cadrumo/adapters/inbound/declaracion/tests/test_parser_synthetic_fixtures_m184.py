"""Modelo 184 synthetic declaration parser fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import _MODELO_184_SYNTHETIC_FIXTURE, CasillaId, _expected_period, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)


def test_parser_extracts_modelo_184_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M184 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is:
    AEAT-published diseño de registro DR_Modelo_184_2025.pdf, downloaded 2026-05-27
    from the configured AEAT Sede static corpus source.
    Saved at:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_184/files/
        01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf
    Registro de tipo 1, positions 5-8: "EJERCICIO"
      "Las cuatro cifras del ejercicio fiscal al que corresponde la declaracion"

    The complementaria/sustitutiva field (record-type-1 positions 121-122) is two
    separate single-character flags, NOT a printed label+value pair; it is absent
    from target_casillas and this test confirms only decl.ejercicio is extracted.

    Non-tautological: the label_pattern 'Ejercicio' is grounded against the AEAT DR
    field name. The fixture prints "Ejercicio: 2024" so a pattern requiring any
    longer qualifying phrase will fail to match.
    """
    filing = parse_declaracion(
        _MODELO_184_SYNTHETIC_FIXTURE,
        modelo_override="184",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "184"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "184"
    assert filing.registry_snapshot_ref.modelo_year == 2024

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Only decl.ejercicio is in the extraction profile; decl.tipo-declaracion removed.
    assert set(values.keys()) == {_DECL_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # Ground truth: DR_Modelo_184_2025.pdf positions 5-8 "EJERCICIO".
    assert values[_DECL_EJERCICIO_CASILLA] == "2024", (
        f"decl.ejercicio: expected '2024' from AEAT-grounded fixture, got {values[_DECL_EJERCICIO_CASILLA]!r}"
    )
