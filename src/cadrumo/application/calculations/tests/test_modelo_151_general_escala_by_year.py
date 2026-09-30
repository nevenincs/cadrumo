"""Modelo 151's general escala applies the top rate the law fixed for each year.

Art. 93.2.e).1.º LIRPF taxes the impatriado base liquidable general at 24 % up to
600.000 euros, and the rate on the excess changed twice across the years the
2015-2022 edition covers:

* 2015: 47 %, disposición adicional trigésima primera, apartado 1.f), which
  replaces the art. 93 escala for the período impositivo 2015 only.
* 2016 to 2020: 45 %, the wording art. 1.59 of Ley 26/2014 gave art. 93, in
  force until art. 61 of Ley 11/2020 amended letra e) with effect 1-1-2021.
* From 2021: 47 %, the Ley 11/2020 wording.

The oracle below applies those published rates and threshold directly; it never
reads the registry's bracket rows. The product serves filings only inside the
support envelope, so the supported years are computed end to end and the years
below the floor are checked twice: the filing request is refused naming the
envelope, and the edition that covers them resolves each year's rate through
the same bracket resolver the formula uses.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.formula_runtime_ops import resolve_bracket
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "151"
_SURFACE = "modelo-151-general-escala-by-year"
_BASE_GENERAL = validated_casilla_id("impatriado.base-liquidable-general", surface=_SURFACE)
_BASE_AHORRO = validated_casilla_id("impatriado.base-liquidable-ahorro", surface=_SURFACE)
_RETENCIONES = validated_casilla_id("impatriado.retenciones", surface=_SURFACE)
_CUOTA_GENERAL = validated_casilla_id("impatriado.cuota-integra-general", surface=_SURFACE)
_ESCALA_GENERAL = "modelo-151.escala-cuota-integra-general"

_THRESHOLD = Decimal("600000")
_RATE_LOW = Decimal("0.24")
#: A base above the threshold, so the year's top rate decides the cuota.
_BASE = Decimal("700000.00")

#: The years the 2015-2022 edition covers below any plausible support floor,
#: each with the top rate its own wording fixes.
_PRE_2021_TOP_RATES: dict[int, Decimal] = {
    2015: Decimal("0.47"),
    2016: Decimal("0.45"),
    2017: Decimal("0.45"),
    2018: Decimal("0.45"),
    2019: Decimal("0.45"),
    2020: Decimal("0.45"),
}


def _top_rate(year: int) -> Decimal:
    if year in _PRE_2021_TOP_RATES:
        return _PRE_2021_TOP_RATES[year]
    if year < min(_PRE_2021_TOP_RATES):
        raise AssertionError(f"no wording of art. 93.2.e).1.º is enrolled here for {year}")
    return Decimal("0.47")


def _expected_cuota(base: Decimal, year: int) -> Decimal:
    if base <= _THRESHOLD:
        return (base * _RATE_LOW).quantize(Decimal("0.01"))
    return (_THRESHOLD * _RATE_LOW + (base - _THRESHOLD) * _top_rate(year)).quantize(Decimal("0.01"))


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return tuple(support.years)


def _floor_snapshot() -> RegistrySnapshot:
    return published_snapshot(_MODELO, filing_year=_supported_years()[0], period="0A")


def test_the_oracle_reproduces_the_worked_cuotas() -> None:
    """600.000 x 0,24 = 144.000, then 100.000 at the year's top rate."""
    assert _expected_cuota(_BASE, 2015) == Decimal("191000.00")
    assert _expected_cuota(_BASE, 2016) == Decimal("189000.00")
    assert _expected_cuota(_BASE, 2021) == Decimal("191000.00")


@pytest.mark.parametrize("year", _supported_years())
def test_every_supported_year_computes_its_own_top_rate(year: int) -> None:
    snapshot = published_snapshot(_MODELO, filing_year=year, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_BASE_GENERAL: _BASE, _BASE_AHORRO: Decimal("0"), _RETENCIONES: Decimal("0")},
        binding_values={},
        date_context={"filing_period": date(year, 12, 31)},
    )

    assert result.values[_CUOTA_GENERAL] == _expected_cuota(_BASE, year)


@pytest.mark.parametrize("year", sorted(_PRE_2021_TOP_RATES))
def test_a_year_below_the_floor_is_refused_as_outside_the_envelope(year: int) -> None:
    """The product does not file below the floor, and says so rather than guessing."""
    if year >= _supported_years()[0]:
        pytest.fail(f"{year} is inside the support envelope; this module's pre-floor premise no longer holds")

    with pytest.raises(FilingYearOutsideSupportEnvelopeError) as refusal:
        published_snapshot(_MODELO, filing_year=year, period="0A")

    assert refusal.value.filing_year == year
    assert "2015-2022" in refusal.value.covering_revision_ids


@pytest.mark.parametrize("year", sorted(_PRE_2021_TOP_RATES))
def test_the_edition_resolves_the_top_rate_of_each_year_below_the_floor(year: int) -> None:
    """The covering edition's escala answers each earlier year with that year's wording."""
    snapshot = _floor_snapshot()
    assert snapshot.revision.valid_from <= date(year, 1, 1), "the floor edition no longer covers the year"
    escala = next(item for item in snapshot.revision.parameters if str(item.id) == _ESCALA_GENERAL)

    cuota = resolve_bracket(escala, _BASE, {"filing_period": date(year, 12, 31)})

    assert cuota.quantize(Decimal("0.01")) == _expected_cuota(_BASE, year)
