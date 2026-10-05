"""Modelo 100's estimación objetiva agraria engine computes each year from its own Orden de módulos.

The Anexo I instructions (rendimiento neto previo, minorado, índices
correctores, reducción agricultores jóvenes) read the same in Orden
HFP/1335/2021 (2022), HFP/1172/2022 (2023), HFP/1359/2023 (2024) and HAC/1347/2024
(2025), so the engine is stated once and each edition cites its own orden. The
yearly differences are keyed where the law makes them:

- the reducción general for Anexo I activities is 25 per cent in 2022 (Orden
  HFP/405/2023 art. 2), 15 per cent in 2023 (Orden HAC/348/2024 art. 2) and
  5 per cent in 2024 and 2025;
- 2022 to 2024 let the rendimiento neto previo be reduced by 35 per cent of
  the gasóleo agrícola and 15 per cent of the fertilizantes bought in the year
  (boxes 0158 and 0159); in 2025 box 0159 is the mejillón en batea product.

The expected figures are the Don L.H.I. worked example of each year's AEAT
Manual práctico de Renta, chapter 9, transcribed here rather than read from
the registry. The manual's example lists maíz and productos hortícolas under
one código de producto with different índices, which one form slot cannot
hold, so the phases after the rendimiento neto previo are driven from the
manual's printed previo through a single código 12 slot. The 2022 manual
prints the half-cent product 7.949,55 x 0,90 truncated to 7.154,59, one cent
below the engine's rounding. The 2023 manual's example keeps the 10 per cent
of Orden HFP/1172/2022 DA 1ª although its own chapter text and Orden
HAC/348/2024 art. 2 set 15 per cent for Anexo I activities; the orden governs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.formula_runtime_ops import resolve_parameter
from cadrumo.domain.calculations.registry.relations import relation_prefill_bindings_for_period
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from dev.corpus.text import normalise_corpus_text

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"
_CENT = Decimal("0.01")
_PREVIO_INSTRUCTION = ":anexo-i-instruccion-2-1"
_REDUCCION_GENERAL = "renta-estimacion-objetiva-reduccion-general-rate"
_ENGINE_FORMULAS = (
    "renta-eo-agraria-rendimiento-base-porcino-carne",
    "renta-eo-agraria-rendimiento-base-cereales-citricos-horticultura",
    "renta-eo-agraria-rendimiento-base-otros-trabajos-accesorios",
    "renta-eo-agraria-rendimiento-neto-previo",
    "renta-eo-agraria-rendimiento-neto-minorado",
    "renta-eo-agraria-rendimiento-neto-modulos",
    "renta-eo-agraria-reduccion-general",
    "renta-eo-agraria-reduccion-jovenes",
    "renta-eo-agraria-reduccion-irregularidad",
    "renta-eo-agraria-rendimiento-neto-reducido-por-actividad",
)


def _c(casilla: str) -> CasillaId:
    return validated_casilla_id(casilla, surface="test")


# Don L.H.I., AEAT Manual práctico de Renta, chapter 9, per year: computable
# ingresos and índices of the products held in distinct códigos (ganado ovino
# de carne, código 3; maíz, código 6; otros trabajos y servicios accesorios,
# código 15) with their printed rendimiento base, then the printed rendimiento
# neto previo, the gasóleo reduction (35 per cent of 6.000), the amortización,
# the printed minorado and módulos (índice de personal asalariado 0,90).
_OVINO = Decimal("31632.20")
_MAIZ = Decimal("58185.86")
_OTROS = Decimal("4760.00")


@dataclass(frozen=True)
class _Example:
    indices: tuple[Decimal, Decimal, Decimal]
    bases: tuple[Decimal, Decimal, Decimal]
    previo: Decimal
    minorado: Decimal
    modulos: Decimal


_EXAMPLES = {
    "2022": _Example(
        indices=(Decimal("0.09"), Decimal("0.18"), Decimal("0.56")),
        bases=(Decimal("2846.90"), Decimal("10473.45"), Decimal("2665.60")),
        previo=Decimal("21234.55"),
        minorado=Decimal("7949.55"),
        modulos=Decimal("7154.59"),
    ),
    "2023": _Example(
        indices=(Decimal("0.13"), Decimal("0.26"), Decimal("0.56")),
        bases=(Decimal("4112.19"), Decimal("15128.32"), Decimal("2665.60")),
        previo=Decimal("27154.71"),
        minorado=Decimal("13869.71"),
        modulos=Decimal("12482.74"),
    ),
    "2024": _Example(
        indices=(Decimal("0.09"), Decimal("0.26"), Decimal("0.56")),
        bases=(Decimal("2846.90"), Decimal("15128.32"), Decimal("2665.60")),
        previo=Decimal("25889.42"),
        minorado=Decimal("12604.42"),
        modulos=Decimal("11343.98"),
    ),
}
_GASOLEO_REDUCTION = Decimal("2100")
_AMORTIZACION = Decimal("11185")
_INDICE_ASALARIADO = Decimal("0.90")
_CODIGO_12_INDICE = Decimal("0.37")
# The reducción general for Anexo I activities, from the BOE text of each year's
# governing provision (see the module docstring).
_RATES = {"2022": Decimal("25"), "2023": Decimal("15"), "2024": Decimal("5")}


@cache
def _orden_years() -> dict[str, str]:
    """Each Anexo I rendimiento-previo instruction's orden, keyed by the ejercicio its window governs."""
    years: dict[str, str] = {}
    for reference_id, reference in compiled_bundled_authority().catalogues.legal.items():
        if not reference_id.endswith(_PREVIO_INSTRUCTION) or reference.effective_to is None:
            continue
        assert reference.effective_from.year == reference.effective_to.year
        years[str(reference.effective_from.year)] = reference_id.removesuffix(_PREVIO_INSTRUCTION)
    return years


@cache
def _snapshot(year: str) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(
        _MODELO, filing_year=int(year), period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )


def _calculate(year: str, inputs: dict[str, Decimal]) -> dict[CasillaId, Decimal]:
    snapshot = _snapshot(year)
    revision = snapshot.revision
    decimals: dict[str, Decimal] = {}
    booleans: dict[str, bool] = {}
    dates: dict[str, date] = {}
    enums: dict[str, str] = {}
    for binding in revision.bindings:
        if binding.source is BindingSourceKind.RELATION_PREFILL:
            continue
        channel = binding.value.channel
        if channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            decimals[binding.id] = Decimal("0")
        elif channel is BindingValueChannel.BOOLEAN:
            booleans[binding.id] = False
        elif channel is BindingValueChannel.DATE:
            dates[binding.id] = date(1975, 6, 15)
        elif channel is BindingValueChannel.ENUM:
            enums[binding.id] = "madrid"
    decimals["renta-profile-declaration-type"] = Decimal("1")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_c(casilla): value for casilla, value in inputs.items()},
        binding_values=decimals,
        boolean_binding_values=booleans,
        enum_binding_values=enums,
        date_binding_values=dates,
        relation_values={
            binding.id: Decimal("0")
            for binding, _provider in relation_prefill_bindings_for_period(revision, period=snapshot.period)
        },
        date_context={"filing_period": date(int(year), 12, 31)},
    )
    return dict(result.values)


def _chain_inputs(year: str) -> dict[str, Decimal]:
    """Land the código 12 slot on the manual's printed rendimiento neto previo."""
    previo = _EXAMPLES[year].previo
    ingresos = (previo / _CODIGO_12_INDICE).quantize(_CENT)
    assert (ingresos * _CODIGO_12_INDICE).quantize(_CENT) == previo
    return {
        "1521": ingresos,
        "1522": _CODIGO_12_INDICE,
        "0158": _GASOLEO_REDUCTION,
        "1538": _AMORTIZACION,
        "1541": _INDICE_ASALARIADO,
    }


def _percent(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate / Decimal("100")).quantize(_CENT)


_YEARS = tuple(_EXAMPLES)


def test_each_example_year_is_a_supported_year_governed_by_its_own_orden() -> None:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None
    assert set(_YEARS) <= {str(year) for year in support.years}
    assert set(_YEARS) <= set(_orden_years())
    assert len({_orden_years()[year] for year in _YEARS}) == len(_YEARS)


@pytest.mark.parametrize("year", _YEARS)
def test_every_engine_formula_cites_the_year_s_own_orden(year: str) -> None:
    formulas = {formula.id: formula for formula in _snapshot(year).revision.formulas}
    own = _orden_years()[year]
    for formula_id in _ENGINE_FORMULAS:
        refs = formulas[formula_id].legal_refs
        if formula_id.endswith("irregularidad"):
            assert {ref.split(":")[0] for ref in refs} == {"ley-35-2006"}, (formula_id, refs)
            continue
        instructions = [ref for ref in refs if ":anexo-i-" in ref or ref.endswith(":da-1")]
        assert instructions, (formula_id, refs)
        assert all(ref.startswith(f"{own}:") for ref in instructions if ":anexo-i-" in ref), (formula_id, refs)


@pytest.mark.parametrize("year", _YEARS)
def test_the_reduccion_general_rate_is_the_year_s_anexo_i_rate(year: str) -> None:
    snapshot = _snapshot(year)
    parameter = next(p for p in snapshot.revision.parameters if p.id == _REDUCCION_GENERAL)
    assert resolve_parameter(parameter, {"filing_period": date(int(year), 12, 31)}) == _RATES[year]


@pytest.mark.parametrize("year", _YEARS)
def test_each_product_slot_reproduces_the_manual_rendimiento_base(year: str) -> None:
    example = _EXAMPLES[year]
    ovino, maiz, otros = example.indices
    values = _calculate(
        year,
        {"1494": _OVINO, "1495": ovino, "1503": _MAIZ, "1504": maiz, "1530": _OTROS, "1531": otros},
    )
    bases = (values[_c("1496")], values[_c("1505")], values[_c("1532")])
    assert bases == example.bases
    assert values[_c("1537")] == sum(bases, Decimal("0"))


@pytest.mark.parametrize("year", _YEARS)
def test_the_chain_reproduces_the_manual_minorado_and_modulos(year: str) -> None:
    example = _EXAMPLES[year]
    values = _calculate(year, _chain_inputs(year))
    assert values[_c("1537")] == example.previo
    assert values[_c("1539")] == example.minorado
    assert abs(values[_c("1548")] - example.modulos) <= _CENT
    if year != "2022":
        assert values[_c("1548")] == example.modulos


@pytest.mark.parametrize("year", _YEARS)
def test_the_reduccion_general_applies_the_year_s_rate_to_the_modulos(year: str) -> None:
    values = _calculate(year, _chain_inputs(year))
    modulos = values[_c("1548")]
    expected = _percent(_EXAMPLES[year].modulos, _RATES[year])
    assert values[_c("1549")] == expected == _percent(modulos, _RATES[year])
    assert values[_c("1550")] == modulos - expected
    assert values[_c("1555")] == values[_c("1550")]


def test_the_2022_and_2024_manuals_print_the_reduccion_general_the_engine_applies() -> None:
    assert _percent(_EXAMPLES["2022"].modulos, _RATES["2022"]) == Decimal("1788.65")
    assert _percent(_EXAMPLES["2024"].modulos, _RATES["2024"]) == Decimal("567.20")


def test_the_2023_manual_states_the_anexo_i_rate_its_example_omits() -> None:
    corpus = bundled_path("manual_corpus_text", "manuals", "renta", "2023", "part1", "source.pdf.corpus_text.json")
    text = json.loads(corpus.read_text(encoding="utf-8"))["normalised_text"]
    assert normalise_corpus_text("ha elevado del 10 al 15 por 100 la reducción prevista") in text
    assert normalise_corpus_text("Reducción de carácter general: 10% s/12.482,74 = 1.248,27 euros") in text


@pytest.mark.parametrize("year", _YEARS)
def test_the_jovenes_reduction_applies_to_the_modulos_net_of_the_general_reduction_only(year: str) -> None:
    inputs = {**_chain_inputs(year), "AJ": Decimal("1"), "0160": Decimal("1000")}
    declares_dana = any(str(casilla.id) == "0162" for casilla in _snapshot(year).revision.casillas)
    if declares_dana:
        inputs["0162"] = Decimal("500")
    values = _calculate(year, inputs)
    net_of_general = values[_c("1548")] - values[_c("1549")]
    expected_jovenes = _percent(net_of_general, Decimal("25"))
    assert values[_c("1551")] == expected_jovenes
    territorial = Decimal("1000") + (Decimal("500") if declares_dana else Decimal("0"))
    assert values[_c("1550")] == net_of_general - territorial
    assert values[_c("1555")] == values[_c("1550")] - expected_jovenes


@pytest.mark.parametrize("year", _YEARS)
def test_no_jovenes_reduction_without_the_declared_eligibility(year: str) -> None:
    values = _calculate(year, _chain_inputs(year))
    assert values[_c("1551")] == Decimal("0")


@pytest.mark.parametrize("year", _YEARS)
def test_the_irregularidad_reduction_is_thirty_per_cent_of_a_base_capped_at_300000(year: str) -> None:
    values = _calculate(year, {**_chain_inputs(year), "eo-agraria-reduccion-irregularidad-base": Decimal("400000")})
    assert values[_c("1554")] == Decimal("90000.00")


@pytest.mark.parametrize("year", _YEARS)
def test_the_fertilizantes_reduction_lowers_the_minorado_like_the_gasoleo_one(year: str) -> None:
    base = _calculate(year, _chain_inputs(year))
    with_fertilizantes = _calculate(year, {**_chain_inputs(year), "0159": Decimal("300")})
    assert with_fertilizantes[_c("1539")] == base[_c("1539")] - Decimal("300")


def test_2025_keeps_its_own_fase_1_and_2_without_the_input_reductions() -> None:
    year = str(max(int(year) for year in _orden_years()))
    assert year not in _EXAMPLES
    values = _calculate(
        year,
        {
            "0157": Decimal("1000"),
            "0158": Decimal("0.50"),
            "1521": Decimal("1000"),
            "1522": _CODIGO_12_INDICE,
            "1538": Decimal("100"),
        },
    )
    assert values[_c("0159")] == Decimal("500.00")
    assert values[_c("1537")] == Decimal("870.00")
    assert values[_c("1539")] == Decimal("770.00")
