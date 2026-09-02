"""Modelo 303 parser boundary corpus tests.

See Also:
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public declaration-copy parser boundary exercised by this fixture.
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m303_support`
        Shared current and historical Modelo 303 profile casilla expectations.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m303_2023_2024`
        Parametrized current-template corpus sweep for the same profile family.
    :class:`~adapters.inbound.declaracion.InboundDeclaracionObservation`
        Observation aggregate returned by the parser and asserted here.
"""

from __future__ import annotations

import pytest

from ._parser_boundary_m303_support import _M303_CURRENT_PROFILE_CASILLAS
from ._parser_boundary_support import (
    _MODELO_303_SYNTHETIC_FIXTURE,
    Decimal,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_303_targets_from_synthetic_fixture() -> None:
    """Extract the profile's targets from the project's own synthetic M303 fixture.

    The fixture is ``synthetic_generated``, not an AEAT render, and the test name
    now says so. What this pins is the parser-to-profile wiring: the extracted
    casilla set equals the profile's target set exactly. It does NOT establish
    that the profile can read a real AEAT render -- only the bundled manual annex
    quarters do that, and they are exercised through the coverage floor rather
    than here, because they carry no NIF and the parser rejects them at the
    identity step by design.
    """
    filing = parse_declaracion(
        _MODELO_303_SYNTHETIC_FIXTURE,
        modelo_override="303",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == _M303_CURRENT_PROFILE_CASILLAS

    expected_values = _expected_casilla_values(
        {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8400.00"),
            "iva.resultado-regimen-general": Decimal("4800.00"),
            "64": Decimal("4800.00"),
            "66": Decimal("4800.00"),
            "iva.compensacion-pendiente-periodos-anteriores": Decimal("0.00"),
            "iva.resultado": Decimal("4800.00"),
            "71": Decimal("4800.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"
