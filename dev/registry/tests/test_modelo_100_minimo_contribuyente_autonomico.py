"""Modelo 100 casilla 0512: the mínimo del contribuyente of the gravamen autonómico.

Each comunidad may approve its own mínimo del contribuyente and age increments for
the gravamen autonómico (Ley 22/2009 art. 46.1.a); where it approves none, the
state amounts of LIRPF art. 57 apply. The expected amounts below are transcribed
from the AEAT Renta manuals' chapter on the mínimo personal y familiar, section
"Importes del mínimo personal y familiar aprobados por las Comunidades Autónomas
para el cálculo del gravamen autonómico" (Renta 2024 manual, parte 1, pp. 1200-1206;
Renta 2025 manual, parte 1, same section), not from the registry parameters: the
2024 manual lists Andalucía, Canarias, Cataluña (state amounts), Galicia, Madrid
and the Comunitat Valenciana; the 2025 manual adds the Principado de Asturias.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA = validated_casilla_id("0512", surface="test_modelo_100_minimo_contribuyente_autonomico")
_CCAA_BINDING = "renta-profile-tax-residence-ccaa"
_BIRTH_DATE_BINDING = "renta-profile-taxpayer-birth-date"

#: LIRPF art. 57: general amount, increment from 65, further increment from 75.
_STATE = (Decimal("5550"), Decimal("1150"), Decimal("1400"))
_OWN_AMOUNTS_2024 = {
    "andalucia": (Decimal("5790"), Decimal("1200"), Decimal("1460")),
    "canarias": (Decimal("5606"), Decimal("1162"), Decimal("1414")),
    "galicia": (Decimal("5789"), Decimal("1199"), Decimal("1460")),
    "madrid": (Decimal("5956.65"), Decimal("1234.26"), Decimal("1502.58")),
    "comunidad_valenciana": (Decimal("6105"), Decimal("1265"), Decimal("1540")),
}
_OWN_AMOUNTS = {
    2024: _OWN_AMOUNTS_2024,
    2025: {**_OWN_AMOUNTS_2024, "asturias": (Decimal("6105"), Decimal("1265"), Decimal("1540"))},
}
_CCAA = (
    "andalucia",
    "aragon",
    "asturias",
    "baleares",
    "canarias",
    "cantabria",
    "castilla_la_mancha",
    "castilla_y_leon",
    "cataluna",
    "comunidad_valenciana",
    "extremadura",
    "galicia",
    "la_rioja",
    "madrid",
    "murcia",
)
#: Ages at the end of the tax period, including both increment boundaries.
_AGES = (40, 64, 65, 74, 75, 90)


def _revisions() -> dict[int, ModeloRevision]:
    return {int(revision_id): revision for revision_id, revision in _loaded_registry()[0]["100"].revisions.items()}


def _computed_years() -> tuple[int, ...]:
    return tuple(
        sorted(
            year
            for year, revision in _revisions().items()
            if any(formula.target_casilla_id == _CASILLA for formula in revision.formulas)
        )
    )


def _expected(year: int, ccaa: str, age: int) -> Decimal:
    base, from_65, from_75 = _OWN_AMOUNTS[year].get(ccaa, _STATE)
    return base + (from_65 if age >= 65 else Decimal(0)) + (from_75 if age >= 75 else Decimal(0))


def _computed(year: int, ccaa: str, age: int) -> Decimal:
    revision = _revisions()[year]
    (formula,) = (formula for formula in revision.formulas if formula.target_casilla_id == _CASILLA)
    return evaluate_expression(
        formula.expression,
        values={},
        binding_values={},
        parameters={parameter.id: parameter for parameter in revision.parameters},
        date_context={"filing_period": date(year, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        enum_binding_values={_CCAA_BINDING: ccaa},
        date_binding_values={_BIRTH_DATE_BINDING: date(year - age, 12, 31)},
        filing_year=year,
    )


def test_0512_is_computed_exactly_in_the_editions_the_manual_amounts_cover() -> None:
    assert _computed_years() == tuple(sorted(_OWN_AMOUNTS))


@pytest.mark.parametrize("year", sorted(_OWN_AMOUNTS))
@pytest.mark.parametrize("ccaa", _CCAA)
def test_0512_takes_the_comunidad_amounts_and_age_increments(year: int, ccaa: str) -> None:
    for age in _AGES:
        assert _computed(year, ccaa, age) == _expected(year, ccaa, age), (year, ccaa, age)
