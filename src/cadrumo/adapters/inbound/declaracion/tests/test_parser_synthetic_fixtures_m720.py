"""Modelo 720 synthetic declaration parser fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import _MODELO_720_SYNTHETIC_FIXTURE, CasillaId, _expected_period, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)


def test_parser_extracts_modelo_720_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M720 synthetic fixture and verify decl.ejercicio.

    Ground truth for the ejercicio label pattern is:
    (1) AEAT-published diseño de registro (modelo_720.pdf), downloaded 2026-05-27
        from the configured AEAT Sede static corpus source.
        Record-type-1 positions 5-8: EJERCICIO.
    (2) Orden HAP/72/2013 Art. 7: "al que se refiera la información a suministrar" -
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

    # Only decl.ejercicio is in the extraction profile; decl.tipo-declaracion removed.
    assert set(values.keys()) == {_DECL_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # Ground truth: aeat-dr-720 positions 5-8 "EJERCICIO" and Orden HAP/72/2013 Art. 7.
    assert values[_DECL_EJERCICIO_CASILLA] == "2024", (
        f"decl.ejercicio: expected '2024' from AEAT-grounded fixture, got {values[_DECL_EJERCICIO_CASILLA]!r}"
    )
