"""Synthetic declaration parser fixture tests split from the boundary suite."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ._parser_boundary_support import (
    _MODELO_184_SYNTHETIC_FIXTURE,
    _MODELO_232_2016_SYNTHETIC_FIXTURE,
    _MODELO_232_2018_SYNTHETIC_FIXTURE,
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
_DECL_TIPO_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.tipo-ejercicio")
_DECL_CNAE_CASILLA: CasillaId = _casilla_id("decl.cnae")


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


@pytest.mark.parametrize(
    "fixture_path,year,revision_id,profile_id",
    [
        (
            _MODELO_232_2016_SYNTHETIC_FIXTURE,
            2016,
            "2016-2017",
            "modelo-232-2016-declaracion-pdf",
        ),
        (
            _MODELO_232_2018_SYNTHETIC_FIXTURE,
            2018,
            "2018-y-siguientes",
            "modelo-232-2018-declaracion-pdf",
        ),
    ],
)
def test_parser_extracts_modelo_232_synthetic_fixture_targets(
    fixture_path: Path,
    year: int,
    revision_id: str,
    profile_id: str,
) -> None:
    """Round-trip: parse the sanitized M232 synthetic fixtures and verify all three casillas.

    Ground truth is the AEAT-published Diseño de Registro for Modelo 232 (both revisions):
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_232/files/
        01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx
        02-232-orden-hfp-816-2017-ejercicios-2016-2017-146-kb-xlsx.xlsx

    AEAT DR field descriptions (verbatim, both XLSX files carry identical DR23201):
      DR23200 row 9:  "Ejercicio de devengo (EEEE)"
      DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
      DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"

    Pattern verdicts:
      - decl.ejercicio: 'Ejercicio\\s+de\\s+devengo' — CONFIRMED (DR23200 row 9).
      - decl.tipo-ejercicio: 'Tipo\\s+de\\s+ejercicio' — CONFIRMED (DR23201 row 17, case-insensitive).
      - decl.cnae: 'C\\.N\\.A\\.E\\.?\\s+actividad\\s+principal' — FIXED from prior pattern;
        DR23201 row 20 reads "C.N.A.E. actividad principal" with no "de la" connector.

    Non-tautological: the label_patterns are grounded against AEAT DR field descriptions,
    NOT the registry casilla label fields ('ejercicio-devengo', 'tipo-ejercicio',
    'cnae-actividad-principal').  A pattern that drifts from the DR vocabulary will
    produce a zero-match parse failure on this fixture.  The "de la" removal is
    non-tautological: had the original (wrong) pattern been used the fixture would fail
    because the fixture text carries the correct AEAT DR string without "de la".
    """
    filing = parse_declaracion(
        fixture_path,
        modelo_override="232",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "232"
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "232"
    assert filing.registry_snapshot_ref.revision_id == revision_id
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All three casillas defined by the M232 declaracion_pdf profile must be present.
    assert set(values.keys()) == {
        _DECL_EJERCICIO_CASILLA,
        _DECL_TIPO_EJERCICIO_CASILLA,
        _DECL_CNAE_CASILLA,
    }, f"expected exactly {{decl.ejercicio, decl.tipo-ejercicio, decl.cnae}}, got {set(values.keys())!r}"

    # decl.ejercicio: fixture prints "Ejercicio de devengo 2016" / "...2018";
    # parse_spanish_decimal("2016") = Decimal("2016").
    # Ground truth: DR23200 row 9 "Ejercicio de devengo (EEEE)".
    from decimal import Decimal as _Decimal

    assert values[_DECL_EJERCICIO_CASILLA] == _Decimal(str(year)), (
        f"decl.ejercicio: expected Decimal('{year}') from AEAT-grounded DR23200 fixture, "
        f"got {values[_DECL_EJERCICIO_CASILLA]!r}"
    )

    # decl.tipo-ejercicio: fixture prints "Tipo de Ejercicio 1";
    # value_kind='enum' means the parser stores the raw token string.
    # Ground truth: DR23201 row 17 "2.Devengo - Tipo de Ejercicio".
    assert values[_DECL_TIPO_EJERCICIO_CASILLA] is not None, (
        "decl.tipo-ejercicio: expected a non-None extracted value"
    )

    # decl.cnae: fixture prints "C.N.A.E. actividad principal 6201";
    # value_kind='text' means the parser stores the raw token string.
    # Ground truth: DR23201 row 20 "2.Devengo - C.N.A.E. actividad principal"
    # (NO "de la" connector — pattern fixed from original 'C\.N\.A\.E\.?\s+de\s+la\s+actividad\s+principal').
    assert values[_DECL_CNAE_CASILLA] == "6201", (
        f"decl.cnae: expected '6201' from AEAT-grounded DR23201 fixture "
        f"(DR field: 'C.N.A.E. actividad principal'), "
        f"got {values[_DECL_CNAE_CASILLA]!r}"
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
