"""Modelo 151 computes the impatriado ahorro cuota in every supported year, by the escala of that year.

Art. 93.2.e) LIRPF splits the impatriado cuota íntegra in two: the general part
(1.º) and the part of the base liquidable corresponding to the rentas of art.
25.1.f) TRLIRNR (2.º), which has its own progressive escala. That escala changed
twice inside the supported years:

* 2021-2022, art. 61 of Ley 11/2020: 19 % to 6.000, 21 % to 50.000, 23 % to
  200.000 and 26 % above.
* 2023-2024, art. 63.3 of Ley 31/2022: the 26 % tranche becomes 27 % to 300.000
  and 28 % above.
* From 2025, disposición final 7.3 of Ley 7/2024: the top rate is 30 %.

The oracle below sums each tranche's slice of the base from those published
rates. It never reads the registry's cumulative ``fixed_addition`` column, so a
wrong cuota acumulada in the registry fails here rather than being copied into
the expectation. The years come from the published support envelope, so the
test follows the envelope instead of pinning a year list.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "151"
_SURFACE = "modelo-151-ahorro-cuota-across-supported-years"
_BASE_GENERAL = validated_casilla_id("impatriado.base-liquidable-general", surface=_SURFACE)
_BASE_AHORRO = validated_casilla_id("impatriado.base-liquidable-ahorro", surface=_SURFACE)
_RETENCIONES = validated_casilla_id("impatriado.retenciones", surface=_SURFACE)
_CUOTA_GENERAL = validated_casilla_id("impatriado.cuota-integra-general", surface=_SURFACE)
_CUOTA_AHORRO = validated_casilla_id("impatriado.cuota-integra-ahorro", surface=_SURFACE)
_CUOTA_DIFERENCIAL = validated_casilla_id("impatriado.cuota-diferencial", surface=_SURFACE)

_Tranches = tuple[tuple[Decimal, Decimal | None, Decimal], ...]

_LEY_11_2020: _Tranches = (
    (Decimal("0"), Decimal("6000"), Decimal("0.19")),
    (Decimal("6000"), Decimal("50000"), Decimal("0.21")),
    (Decimal("50000"), Decimal("200000"), Decimal("0.23")),
    (Decimal("200000"), None, Decimal("0.26")),
)
_LEY_31_2022: _Tranches = (
    *_LEY_11_2020[:3],
    (Decimal("200000"), Decimal("300000"), Decimal("0.27")),
    (Decimal("300000"), None, Decimal("0.28")),
)
_LEY_7_2024: _Tranches = (*_LEY_31_2022[:4], (Decimal("300000"), None, Decimal("0.30")))

#: A base reaching the top tranche of every redaction, so every rate is exercised.
_BASE_AHORRO_VALUE = Decimal("350000.00")


def _escala_del_ahorro(year: int) -> _Tranches:
    if year <= 2020:
        raise AssertionError(f"no redaction of art. 93.2.e).2.º is enrolled here for {year}")
    if year <= 2022:
        return _LEY_11_2020
    if year <= 2024:
        return _LEY_31_2022
    return _LEY_7_2024


def _expected_cuota(base: Decimal, tranches: _Tranches) -> Decimal:
    cuota = Decimal("0")
    for lower, upper, rate in tranches:
        if base <= lower:
            break
        top = base if upper is None else min(base, upper)
        cuota += (top - lower) * rate
    return cuota.quantize(Decimal("0.01"))


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return tuple(support.years)


def _calculate(year: int, inputs: dict[CasillaId, Decimal]):
    snapshot = published_snapshot(_MODELO, filing_year=year, period="0A")
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values={},
        date_context={"filing_period": date(year, 12, 31)},
    )


def test_the_oracle_reproduces_the_official_cuotas_acumuladas() -> None:
    """The BOE tables print the cuota at each tranche floor; the oracle must agree with them."""
    assert _expected_cuota(Decimal("6000"), _LEY_11_2020) == Decimal("1140.00")
    assert _expected_cuota(Decimal("50000"), _LEY_11_2020) == Decimal("10380.00")
    assert _expected_cuota(Decimal("200000"), _LEY_11_2020) == Decimal("44880.00")
    assert _expected_cuota(Decimal("300000"), _LEY_31_2022) == Decimal("71880.00")


@pytest.mark.parametrize("year", _supported_years())
def test_every_supported_year_states_the_ahorro_chain(year: int) -> None:
    """The ahorro base, its computed cuota, formula, construct and completeness entries all hydrate."""
    revision = published_snapshot(_MODELO, filing_year=year, period="0A").revision
    casillas = {str(casilla.id): casilla for casilla in revision.casillas}

    assert str(_BASE_AHORRO) in casillas
    assert casillas[str(_CUOTA_AHORRO)].formula == "modelo-151-cuota-integra-ahorro"
    assert "modelo-151-cuota-integra-ahorro" in {str(formula.id) for formula in revision.formulas}
    construct = next(item for item in revision.constructs if str(item.id) == "m151-impatriado-calculation")
    assert "modelo-151-cuota-integra-ahorro" in {str(formula) for formula in construct.formulas}
    assert revision.completeness_manifest is not None
    manifest = {str(entry.casilla_id) for entry in revision.completeness_manifest.casillas}
    assert {str(_BASE_AHORRO), str(_CUOTA_AHORRO)} <= manifest


@pytest.mark.parametrize("year", _supported_years())
def test_the_ahorro_cuota_follows_the_escala_of_its_year(year: int) -> None:
    result = _calculate(
        year, {_BASE_GENERAL: Decimal("0"), _BASE_AHORRO: _BASE_AHORRO_VALUE, _RETENCIONES: Decimal("0")}
    )

    assert result.values[_CUOTA_AHORRO] == _expected_cuota(_BASE_AHORRO_VALUE, _escala_del_ahorro(year))


def test_the_floor_year_nets_retenciones_from_both_cuotas() -> None:
    """At the support floor the cuota diferencial is general plus ahorro, less retenciones."""
    year = _supported_years()[0]
    base_general = Decimal("700000.00")
    retenciones = Decimal("50000.00")
    result = _calculate(
        year, {_BASE_GENERAL: base_general, _BASE_AHORRO: _BASE_AHORRO_VALUE, _RETENCIONES: retenciones}
    )

    # art. 93.2.e).1.º as worded by Ley 11/2020: 24 % to 600.000 and 47 % above.
    general = (Decimal("600000") * Decimal("0.24") + (base_general - Decimal("600000")) * Decimal("0.47")).quantize(
        Decimal("0.01"),
    )
    ahorro = _expected_cuota(_BASE_AHORRO_VALUE, _escala_del_ahorro(year))
    assert result.values[_CUOTA_GENERAL] == general
    assert result.values[_CUOTA_AHORRO] == ahorro
    assert result.values[_CUOTA_DIFERENCIAL] == general + ahorro - retenciones


@pytest.mark.parametrize("year", _supported_years())
def test_no_ahorro_income_is_a_zero_cuota_not_a_refusal(year: int) -> None:
    result = _calculate(year, {_BASE_GENERAL: Decimal("0"), _BASE_AHORRO: Decimal("0"), _RETENCIONES: Decimal("0")})

    assert result.values[_CUOTA_AHORRO] == Decimal("0.00")
