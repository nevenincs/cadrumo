"""Modelo 347 synthetic declaration parser fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import _MODELO_347_SYNTHETIC_FIXTURE, CasillaId, _expected_period, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)


def test_parser_extracts_modelo_347_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M347 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is the AEAT-published Diseño de
    Registro for Modelo 347 (Orden HAC/1431/2025):
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_347/files/
        01-347-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1431-2025-de-3-de-diciembre-332-kb.pdf
      Page 1, TIPO DE REGISTRO 1, positions 5-8:
        "EJERCICIO — Las cuatro cifras del ejercicio fiscal al que corresponde la declaración."

    The short-form label "Ejercicio:" used in the fixture is consistent with M349,
    M180, and M369 justificante corpus conventions (all annual informative modelos).
    Pattern 'Ejercicio:' is grounded in the DR field name "EJERCICIO" at positions 5-8.

    The PROVISIONAL pattern 'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+declaraci[oó]n'
    was a self-reference to the registry casilla label — not attested in any AEAT-published
    M347 printed-form text.  It is replaced with the corpus-grounded 'Ejercicio:'.

    decl.tipo-declaracion is absent from the profile: M347 positions 121-122 are two
    separate single-character flags (pos 121 = "C" complementaria; pos 122 = "S"
    sustitutiva), identical to M720 positions 121-122.  Not a label+value pair.

    Non-tautological: the label_pattern 'Ejercicio:' is grounded against the AEAT DR
    field name — NOT the registry casilla label ('Ejercicio al que se refiere la
    declaracion').  A profile pattern that omits the colon will match any occurrence
    of "Ejercicio" in the page (over-match risk); one that adds non-AEAT text will
    produce a zero-match parse failure on this fixture.
    """
    filing = parse_declaracion(
        _MODELO_347_SYNTHETIC_FIXTURE,
        modelo_override="347",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "347"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "347"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Only decl.ejercicio is in the extraction profile — decl.tipo-declaracion removed
    # because M347 positions 121-122 are two separate single-character flags (like M720).
    assert set(values.keys()) == {_DECL_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # decl.ejercicio: fixture prints "Ejercicio: 2024";
    # parse_spanish_decimal("2024") = Decimal("2024").
    # Ground truth: AEAT DR positions 5-8 field name "EJERCICIO" (Orden HAC/1431/2025 p.1).
    assert values[_DECL_EJERCICIO_CASILLA] == "2024", (
        f"decl.ejercicio: expected '2024' from AEAT-grounded fixture, got {values[_DECL_EJERCICIO_CASILLA]!r}"
    )
