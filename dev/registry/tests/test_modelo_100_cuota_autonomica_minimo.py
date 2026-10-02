"""Modelo 100 casilla 0531 applies the autonomic scale to casilla 0523, the autonomic mínimo.

Every record design describes casilla 0531 as "Aplicación de la escala autonómica
del Impuesto al importe de la casilla [0523]" (aeat-dr-100 dictionaries: 2020 :746,
2021 :761, 2022 :831, 2023 :843, 2024 :863, 2025 :889), the share of the mínimo
personal y familiar the comunidad sets for the gravamen autonómico, where casilla
0530 reads [0521], the state one.

The cross-check is the AEAT manual's own worked example, not the registry: the
Renta manual (parte 1, cap. 15, "anualidades por alimentos en favor de los
hijos") has a Comunitat Valenciana taxpayer with a base liquidable general of
63.000 euros, 12.000 euros of anualidades and a 5.550 euros state mínimo. The
autonomic mínimo of 6.105 euros plus 1.980 euros gives 8.085 euros, taxed at 9 per
cent as cuota 8 = 727,65, and the cuota general autonómica is 8.410 - 727,65 =
7.682,35. The example is printed identically for 2022 (pp. 989-991), 2023
(pp. 1161-1163), 2024 (pp. 1253-1255) and 2025 (pp. 1139-1141).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SURFACE = "test_modelo_100_cuota_autonomica_minimo"
_ESCALA_SOBRE_MINIMO_AUTONOMICA = validated_casilla_id("0531", surface=_SURFACE)
_MINIMO_BASE_GENERAL_ESTATAL = validated_casilla_id("0521", surface=_SURFACE)
_MINIMO_BASE_GENERAL_AUTONOMICO = validated_casilla_id("0523", surface=_SURFACE)
_MANUAL_EXAMPLE_YEARS = (2022, 2023, 2024, 2025)


def _revisions() -> dict[int, ModeloRevision]:
    return {int(revision_id): revision for revision_id, revision in _loaded_registry()[0]["100"].revisions.items()}


def _casilla(casilla_id: str) -> CasillaId:
    return validated_casilla_id(casilla_id, surface=_SURFACE)


def _evaluate(revision: ModeloRevision, target: CasillaId, values: dict[CasillaId, Decimal], year: int) -> Decimal:
    (formula,) = (formula for formula in revision.formulas if formula.target_casilla_id == target)
    return evaluate_expression(
        formula.expression,
        values=values,
        binding_values={},
        parameters={parameter.id: parameter for parameter in revision.parameters},
        date_context={"filing_period": date(year, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        enum_binding_values={"renta-profile-tax-residence-ccaa": "comunidad_valenciana"},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(year - 40, 6, 30)},
        boolean_binding_values={"renta-profile-anualidades-sin-minimo-descendientes": True},
        filing_year=year,
    )


def test_every_edition_applies_the_autonomic_scale_to_the_autonomic_minimo() -> None:
    for revision_id, revision in _revisions().items():
        (formula,) = (
            formula for formula in revision.formulas if formula.target_casilla_id == _ESCALA_SOBRE_MINIMO_AUTONOMICA
        )
        operands = set(expression_casilla_refs(formula.expression))

        assert _MINIMO_BASE_GENERAL_AUTONOMICO in operands, revision_id
        assert _MINIMO_BASE_GENERAL_ESTATAL not in operands, revision_id


@pytest.mark.parametrize("year", _MANUAL_EXAMPLE_YEARS)
def test_cuota_autonomica_matches_the_manual_anualidades_example(year: int) -> None:
    revision = _revisions()[year]
    c = _casilla
    values: dict[CasillaId, Decimal] = {
        c("0505"): Decimal("63000"),
        c("0527"): Decimal("12000"),
        c("0514"): Decimal("0"),
        c("0516"): Decimal("0"),
        c("0518"): Decimal("0"),
    }
    for target in ("0512", "0520", "0523", "0529", "0531", "0533"):
        values[c(target)] = _evaluate(revision, c(target), values, year)

    assert values[c("0512")] == Decimal("6105")
    assert values[c("0531")] == Decimal("727.65")
    assert values[c("0529")] == Decimal("8410")
    assert values[c("0533")] == Decimal("7682.35")
