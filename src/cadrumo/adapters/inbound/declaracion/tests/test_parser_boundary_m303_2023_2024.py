"""Modelo 303 parser boundary tests for the 2023-2024 printed template.

See Also:
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public declaration-copy parser boundary exercised across the current
        Modelo 303 corpus fixtures.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m303`
        Single-fixture parser boundary check for the same current profile.
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m303_support`
        Shared 2023-2024 corpus parameters and expected profile casilla set.
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m303_2023_2024`
        Engine verification chain that consumes the same parsed current-template
        specimens after this parser boundary is green.
    :class:`~adapters.inbound.declaracion.InboundDeclaracionObservation`
        Typed parser observation whose values and registry snapshot reference
        are asserted by this corpus sweep.
"""

from __future__ import annotations

import pytest

from ._parser_boundary_casillas import (
    _M303_CASILLA_27,
    _M303_CASILLA_29,
    _M303_CASILLA_37,
    _M303_CASILLA_45,
    _M303_CASILLA_64,
    _M303_CASILLA_66,
    _M303_CASILLA_71,
    _M303_COMPENSACION_ANTERIORES_CASILLA,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_POSTERIORES_CASILLA,
    _M303_RESULTADO_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
from ._parser_boundary_m303_current_expected import (
    _M303_2023_2024_EXPECTED,
    _M303_CASILLA_C46,
    _M303_CASILLA_C69,
)
from ._parser_boundary_m303_support import (
    _M303_2023_2024_IDS,
    _M303_2023_2024_PARAMS,
    _M303_CURRENT_PROFILE_CASILLAS,
)
from ._parser_boundary_support import (
    FIXTURES_DIR,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("pdf_stem,year,period", _M303_2023_2024_PARAMS, ids=_M303_2023_2024_IDS)
def test_parser_extracts_modelo_303_profile_targets_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip: parse all 8 corpus M303 PDFs and verify casilla coverage.

    Ground truth is derived from the synthetic fixture values in _generate.py.
    Each specimen uses formula-consistent values: c46 = c27 - c45, c69 = c46.
    Box 37 (intracomunitarias) is always 0.00; compensation boxes are all 0.00.

    See Also:
        :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m303_current_expected`
            Current-template expected values consumed by this parametrized
            corpus test.
        :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m303_support`
            Corpus specimen ids and current-profile casilla membership asserted
            at the parser boundary.
    """
    exp = _M303_2023_2024_EXPECTED[pdf_stem]

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="303",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    assert set(values.keys()) == _M303_CURRENT_PROFILE_CASILLAS
    for casilla_id, value in values.items():
        assert isinstance(value, Decimal), (
            f"{pdf_stem}: casilla {casilla_id!r} expected a Decimal instance, got {value!r}"
        )

    # Stable casillas: formula-consistent values derived from _generate.py fixtures.
    expected_c46 = exp[_M303_CASILLA_C46]
    expected_c69 = exp[_M303_CASILLA_C69]
    stable_expected = {
        _M303_CASILLA_27: exp[_M303_CASILLA_27],
        _M303_CASILLA_29: exp[_M303_CASILLA_29],
        _M303_CASILLA_37: exp[_M303_CASILLA_37],
        _M303_CASILLA_45: exp[_M303_CASILLA_45],
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: expected_c46,
        _M303_CASILLA_64: expected_c46,
        _M303_CASILLA_66: expected_c46,
        _M303_RESULTADO_CASILLA: expected_c69,
        _M303_CASILLA_71: expected_c69,
    }
    for casilla_id, expected_value in stable_expected.items():
        assert values[casilla_id] == expected_value, (
            f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
        )

    # Compensation boxes are all 0.00 in synthetic fixtures
    for casilla_id in (
        _M303_COMPENSACION_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_COMPENSACION_POSTERIORES_CASILLA,
    ):
        assert values[casilla_id] == Decimal("0.00"), (
            f"{pdf_stem}: compensation casilla {casilla_id!r} got {values[casilla_id]!r}"
        )
