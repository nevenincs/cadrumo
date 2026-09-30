"""Modelo 131's módulos engine computes 2022 and 2023 from each year's own Orden de módulos.

Orden HFP/1335/2021 governs 2022 and Orden HFP/1172/2022 governs 2023. Both
print the same Anexo II signos, módulos and instrucciones, so one statement of
the engine serves both years, while the reducción general differs by year and
within 2022: 5 per cent (Orden HFP/1335/2021 DA 1ª), raised to 15 per cent for
the fourth-quarter 2022 pago fraccionado (Orden HFP/1172/2022 DA 8ª), and 10 per
cent for 2023 (Orden HFP/1172/2022 DA 1ª).

The expected figures are the café-bar worked examples printed in the AEAT
Manual práctico de Renta 2022 and 2023 (chapter 8), transcribed below rather
than read from the registry. The manuals round each módulo product before
summing and the engine rounds the phase total, so the 2022 example agrees to
the cent only within that rounding; the 2023 example agrees exactly. The
manuals' further deduction of extraordinary expenses is not a módulos phase and
is not part of the engine's figure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.formula_runtime_ops import resolve_parameter
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "131"
_PERIODS = ("1T", "2T", "3T", "4T")
_REDUCCION = "m131-modulos-reduccion-general"
_OUTPUTS = (
    "modulos-rendimiento-neto-previo",
    "modulos-rendimiento-neto-minorado",
    "modulos-rendimiento-neto-modulos",
    "modulos-rendimiento-neto-actividad",
)
# Café-bar, epígrafe IAE 673.1, in both manuals.
_EPIGRAFE = "673.1"
_ZERO_BINDINGS = {
    "modelo-131-resultados-negativos-anteriores": Decimal("0"),
    "modelo-131-volumen-ingresos-agrario": Decimal("0"),
}
# Manual práctico de Renta 2022, chapter 8 worked example: units, the declared
# minoración por incentivos a la inversión and índice de pequeña dimensión, and
# the printed phases (previo 37.893,84; minorado 29.957,66; módulos 26.961,89).
_EXAMPLE_2022 = {
    "modulos-1-unidades": Decimal("1.41"),
    "modulos-1-unidades-anterior": Decimal("0.33"),
    "modulos-2-unidades": Decimal("0.91"),
    "modulos-3-unidades": Decimal("32.02"),
    "modulos-4-unidades": Decimal("7.32"),
    "modulos-5-unidades": Decimal("9.15"),
    "modulos-6-unidades": Decimal("0"),
    "modulos-7-unidades": Decimal("0.91"),
    "modulos-minoracion-inversion": Decimal("6050"),
    "modulos-indice-pequena-dimension": Decimal("0.90"),
}
_PHASES_2022 = (Decimal("37893.84"), Decimal("29957.66"), Decimal("26961.89"))
# Manual práctico de Renta 2023, chapter 8 worked example (previo 50.111,95;
# minorado 41.368,57; módulos 44.603,33; reducción general 10% = 4.460,33).
_EXAMPLE_2023 = {
    "modulos-1-unidades": Decimal("3.66"),
    "modulos-1-unidades-anterior": Decimal("3.00"),
    "modulos-2-unidades": Decimal("1"),
    "modulos-3-unidades": Decimal("35"),
    "modulos-4-unidades": Decimal("8"),
    "modulos-5-unidades": Decimal("10"),
    "modulos-6-unidades": Decimal("0"),
    "modulos-7-unidades": Decimal("1"),
    "modulos-minoracion-inversion": Decimal("6050"),
}
_PHASES_2023 = (Decimal("50111.95"), Decimal("41368.57"), Decimal("44603.33"))
_CENT = Decimal("0.01")


@cache
def _exercise(orden_article: str) -> int:
    """Return the ejercicio an Orden de módulos governs, from its legal-catalogue window."""
    reference = compiled_bundled_authority().catalogues.legal[orden_article]
    assert reference.effective_to is not None
    assert reference.effective_from.year == reference.effective_to.year
    return reference.effective_from.year


def _year_2022() -> int:
    return _exercise("orden-hfp-1335-2021:art-4")


def _year_2023() -> int:
    return _exercise("orden-hfp-1172-2022:art-4")


def _year_2024() -> int:
    return _exercise("orden-hfp-1359-2023:art-4")


@cache
def _snapshot(year: int, period: str) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(
        _MODELO,
        filing_year=year,
        period=period,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _engine(year: int, period: str, inputs: dict[str, Decimal]) -> tuple[Decimal, ...]:
    snapshot = _snapshot(year, period)
    assert snapshot.filing_period is not None
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        text_inputs={"modulos-epigrafe": _EPIGRAFE},
        date_context={"filing_period": snapshot.filing_period.end_date},
        binding_values=_ZERO_BINDINGS,
    )
    return tuple(result.values[casilla] for casilla in _OUTPUTS)


def _reduced(modulos: Decimal, percent: Decimal) -> Decimal:
    return modulos - (modulos * percent / Decimal("100")).quantize(_CENT)


def _reduction_rate(year: int, period: str) -> Decimal:
    snapshot = _snapshot(year, period)
    assert snapshot.filing_period is not None
    parameter = next(p for p in snapshot.revision.parameters if p.id == _REDUCCION)
    return resolve_parameter(parameter, {"filing_period": snapshot.filing_period.end_date})


def test_the_two_ordenes_govern_supported_years() -> None:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None
    assert {_year_2022(), _year_2023(), _year_2024()} <= set(support.years)
    assert _year_2023() == _year_2022() + 1 == _year_2024() - 1


def test_2022_reproduces_the_manual_example_with_its_dated_reduction() -> None:
    year = _year_2022()
    rates = {period: _reduction_rate(year, period) for period in _PERIODS}
    # DA 1ª of Orden HFP/1335/2021 for the first three quarters; DA 8ª of Orden
    # HFP/1172/2022 for the fourth-quarter pago fraccionado.
    assert rates == {"1T": Decimal("5"), "2T": Decimal("5"), "3T": Decimal("5"), "4T": Decimal("15")}
    for period in _PERIODS:
        previo, minorado, modulos, actividad = _engine(year, period, _EXAMPLE_2022)
        for computed, printed in zip((previo, minorado, modulos), _PHASES_2022, strict=True):
            assert abs(computed - printed) <= _CENT, (period, computed, printed)
        assert actividad == _reduced(modulos, rates[period])
    # The manual's annual figure applies the 15 per cent: 26.961,89 - 4.044,28.
    *_, actividad_4t = _engine(year, "4T", _EXAMPLE_2022)
    assert abs(actividad_4t - Decimal("22917.61")) <= _CENT


def test_2023_reproduces_the_manual_example_with_its_own_reduction() -> None:
    year = _year_2023()
    for period in _PERIODS:
        assert _reduction_rate(year, period) == Decimal("10")
        previo, minorado, modulos, actividad = _engine(year, period, _EXAMPLE_2023)
        assert (previo, minorado, modulos) == _PHASES_2023
        # 44.603,33 - 4.460,33
        assert actividad == Decimal("40143.00")


def test_2022_and_2023_are_one_authored_edition_distinct_from_2024() -> None:
    editions = {year: _snapshot(year, "1T").revision.id for year in (_year_2022(), _year_2023(), _year_2024())}
    assert editions[_year_2022()] == editions[_year_2023()] != editions[_year_2024()]


def test_2024_keeps_its_own_reduction_over_the_same_phases() -> None:
    year = _year_2024()
    for period in _PERIODS:
        assert _reduction_rate(year, period) == Decimal("5")
        previo, minorado, modulos, actividad = _engine(year, period, _EXAMPLE_2023)
        assert (previo, minorado, modulos) == _PHASES_2023
        assert actividad == _reduced(modulos, Decimal("5"))


def test_a_reduction_row_spanning_the_fourth_quarter_is_detected() -> None:
    """Folding the fourth-quarter 15 per cent into the 5 per cent row changes the 4T figure the check reads."""
    year = _year_2022()
    snapshot = _snapshot(year, "4T")
    assert snapshot.filing_period is not None
    parameter = next(p for p in snapshot.revision.parameters if p.id == _REDUCCION)
    first_row = parameter.values[0]
    folded = parameter.model_copy(
        update={
            "values": (
                first_row.model_copy(update={"valid_to": date(year, 12, 31)}),
                *(row for row in parameter.values[1:] if row.valid_from.year != year),
            ),
        },
    )
    period_end = snapshot.filing_period.end_date
    assert resolve_parameter(parameter, {"filing_period": period_end}) == Decimal("15")
    assert resolve_parameter(folded, {"filing_period": period_end}) == Decimal("5")
