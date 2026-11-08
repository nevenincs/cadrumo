"""Modelo 100: a resident of Ceuta or Melilla is calculated, not refused.

LIRPF disposición adicional trigésima segunda sends the autonomic scale of a
taxpayer whose residencia habitual is in Ceuta or Melilla to the table of
artículo 65. That table is the law's own, unchanged since 1 January 2015 (art.
1.41 of Ley 26/2014), so one authored edition serves every supported ejercicio:

    hasta 12.450,00 -> cuota 0,00, resto al 9,50 por ciento
    hasta 20.200,00 -> cuota 1.182,75, resto al 12,00 por ciento
    hasta 35.200,00 -> cuota 2.112,75, resto al 15,00 por ciento
    hasta 60.000,00 -> cuota 4.362,75, resto al 18,50 por ciento
    en adelante     -> cuota 8.950,75, resto al 22,50 por ciento

The two expected cuotas are computed from that printed table, not from the
registry: a base liquidable general of 70.000 euros gives 8.950,75 + 10.000 x
22,5 % = 11.200,75, and one of 30.000 euros gives 2.112,75 + 9.800 x 15 % =
3.582,75.

Neither city approves a mínimo del contribuyente of its own, so casilla 0512
takes the artículo 57 state amounts, exactly as the comunidades that approved
none already do. The expectation is the amount the same formula computes for
one of those comunidades, so a change to the state amount reaches both sides.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.formula_expression import evaluate_expression
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.temporal import select_revision_for_year

from .modelo_100_registry_support import authored_ccaa_choices, loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SURFACE = "test_modelo_100_escala_autonomica_ceuta_melilla"
_ESCALA_SOBRE_BASE_GENERAL = validated_casilla_id("0529", surface=_SURFACE)
_BASE_LIQUIDABLE_GENERAL = validated_casilla_id("0505", surface=_SURFACE)
_ANUALIDADES = validated_casilla_id("0527", surface=_SURFACE)
_MINIMO_AUTONOMICO = validated_casilla_id("0512", surface=_SURFACE)
_CCAA_BINDING = "renta-profile-tax-residence-ccaa"
_BIRTH_DATE_BINDING = "renta-profile-taxpayer-birth-date"
#: The two ciudades autónomas, taken from the catalogue rather than listed.
_CIUDADES = tuple(str(token) for token in authored_ccaa_choices() if str(token) in {"ceuta", "melilla"})
#: A comunidad that approved no mínimo of its own, so it reads the state amounts.
_COMUNIDAD_WITHOUT_OWN_MINIMO = "aragon"
#: Every supported ejercicio, enumerated from the registry's own envelope.
_SUPPORTED_YEARS = loaded_registry()[1].require_supported_filing_years().years


def _revision(year: int) -> ModeloRevision:
    modelos, catalogues = loaded_registry()
    return select_revision_for_year(
        modelos["100"],
        filing_year=year,
        support=catalogues.require_supported_filing_years(),
    )


def _evaluate(
    revision: ModeloRevision,
    target: CasillaId,
    ccaa: str,
    values: dict[CasillaId, Decimal],
    year: int,
) -> Decimal:
    (formula,) = (item for item in revision.formulas if item.target_casilla_id == target)
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
        enum_binding_values={_CCAA_BINDING: ccaa},
        date_binding_values={_BIRTH_DATE_BINDING: date(year - 40, 12, 31)},
        boolean_binding_values={"renta-profile-anualidades-sin-minimo-descendientes": False},
        filing_year=year,
    )


def test_both_ciudades_autonomas_are_recorded_residences() -> None:
    """Without them the cases below would pass over an empty parametrization."""
    assert _CIUDADES == ("ceuta", "melilla")


def test_the_supported_envelope_is_not_empty() -> None:
    assert _SUPPORTED_YEARS


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("ciudad", _CIUDADES)
@pytest.mark.parametrize(
    ("base_liquidable_general", "cuota"),
    [(Decimal("70000"), Decimal("11200.75")), (Decimal("30000"), Decimal("3582.75"))],
)
def test_casilla_0529_applies_the_articulo_65_table(
    year: int, ciudad: str, base_liquidable_general: Decimal, cuota: Decimal
) -> None:
    values = {_BASE_LIQUIDABLE_GENERAL: base_liquidable_general, _ANUALIDADES: Decimal("0")}

    assert _evaluate(_revision(year), _ESCALA_SOBRE_BASE_GENERAL, ciudad, values, year) == cuota


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("ciudad", _CIUDADES)
def test_casilla_0512_takes_the_state_minimo_del_contribuyente(year: int, ciudad: str) -> None:
    revision = _revision(year)
    state = _evaluate(revision, _MINIMO_AUTONOMICO, _COMUNIDAD_WITHOUT_OWN_MINIMO, {}, year)

    assert state > 0
    assert _evaluate(revision, _MINIMO_AUTONOMICO, ciudad, {}, year) == state
