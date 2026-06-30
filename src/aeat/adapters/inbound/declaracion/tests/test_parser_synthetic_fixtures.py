"""Synthetic declaration parser fixture tests split from the boundary suite."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._parser_boundary_support import (
    _MODELO_184_SYNTHETIC_FIXTURE,
    _MODELO_347_SYNTHETIC_FIXTURE,
    _MODELO_720_SYNTHETIC_FIXTURE,
    CasillaId,
    _casilla_id,
    _expected_period,
    parse_declaracion,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")


def test_parser_extracts_modelo_720_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M720 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is:
    (1) AEAT-published diseño de registro (modelo_720.pdf), downloaded 2026-05-27
        from the configured AEAT Sede static corpus source.
        Record-type-1 positions 5-8: EJERCICIO.
    (2) Orden HAP/72/2013 Art. 7: "al que se refiera la información a suministrar" —
        M720 is a declaración informativa; it uses "información", not "declaración".
    (3) aeat-dr-720 casilla label: "Ejercicio al que se refiere la informacion".

    The complementaria/sustitutiva field (record-type-1 positions 121-122) is two
    separate single-character flags, NOT a printed label+value pair; it is absent
    from target_casillas and this test confirms only decl.ejercicio is extracted.

    Non-tautological: the label_pattern
    'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+informaci[oó]n'
    is derived from AEAT-published sources, not the registry casilla label.
    A profile pattern that omits the qualifying phrase will fail to match.
    """
    filing = parse_declaracion(
        _MODELO_720_SYNTHETIC_FIXTURE,
        modelo_override="720",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "720"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "720"
    assert filing.registry_snapshot_ref.modelo_year == 2024

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Only decl.ejercicio is in the extraction profile — decl.tipo-declaracion removed.
    assert set(values.keys()) == {_DECL_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # decl.ejercicio: fixture prints "Ejercicio al que se refiere la informacion 2024";
    # parse_spanish_decimal("2024") = Decimal("2024").
    # Ground truth: aeat-dr-720 positions 5-8 "EJERCICIO" and Orden HAP/72/2013 Art. 7.
    assert values[_DECL_EJERCICIO_CASILLA] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from AEAT-grounded fixture, got "
        f"{values[_DECL_EJERCICIO_CASILLA]!r}"
    )


def test_parser_extracts_modelo_184_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M184 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is:
    AEAT-published diseño de registro DR_Modelo_184_2025.pdf, downloaded 2026-05-27
    from the configured AEAT Sede static corpus source.
    Saved at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_184/files/
        01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf
    Registro de tipo 1, positions 5-8: "EJERCICIO"
      "Las cuatro cifras del ejercicio fiscal al que corresponde la declaracion"

    The complementaria/sustitutiva field (record-type-1 positions 121-122) is two
    separate single-character flags, NOT a printed label+value pair; it is absent
    from target_casillas and this test confirms only decl.ejercicio is extracted.

    Non-tautological: the label_pattern 'Ejercicio' is grounded against the AEAT DR
    field name.  The fixture prints "Ejercicio: 2024" so a pattern requiring any
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

    # Only decl.ejercicio is in the extraction profile — decl.tipo-declaracion removed.
    assert set(values.keys()) == {_DECL_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # decl.ejercicio: fixture prints "Ejercicio: 2024";
    # parse_spanish_decimal("2024") = Decimal("2024").
    # Ground truth: DR_Modelo_184_2025.pdf positions 5-8 "EJERCICIO".
    assert values[_DECL_EJERCICIO_CASILLA] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from AEAT-grounded fixture, got "
        f"{values[_DECL_EJERCICIO_CASILLA]!r}"
    )

def test_parser_extracts_modelo_347_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M347 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is the AEAT-published Diseño de
    Registro for Modelo 347 (Orden HAC/1431/2025):
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_347/files/
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
    assert values[_DECL_EJERCICIO_CASILLA] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from AEAT-grounded fixture, got "
        f"{values[_DECL_EJERCICIO_CASILLA]!r}"
    )
