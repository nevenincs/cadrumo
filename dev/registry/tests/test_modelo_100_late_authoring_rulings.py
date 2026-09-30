"""Modelo 100 members authored at the first edition their official evidence reaches.

The matrimonio boxes 0245-0247 are printed with the same field, XML route and
type in every record design from the support floor on (PTODODAFAS5, PMESINI5,
PMESFIN5), so the edition covering each supported year computes them from the
declared marriage facts. The Art. 81.1 deducción por maternidad (0611) is
computed from the first year the governed maternity formula specification and
the retirement of the cotizaciones ceiling reach; the year before keeps the box
manual, because the engine cannot apply the ceiling that still governed it. The
Art. 81.2 guardería cap carries its value for every supported year.

The amortization incentive rows cite the amending law that grounds each year's
admitted period, and the pagos fraccionados box cites the obligation and the
Modelo 130 approval in every edition.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import ScalarFactPayload
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema import (
    BindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compiled_bundled_authority
from ..compiler.fact_loader import load_governed_facts
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"
_MARRIAGE = {
    "0245": ("renta-matrimonio-vigente-todo-anio", "renta-profile-marriage-full-year"),
    "0246": ("renta-matrimonio-mes-inicio", "renta-profile-marriage-month-start"),
    "0247": ("renta-matrimonio-mes-fin", "renta-profile-marriage-month-end"),
}
_MATERNIDAD_FORMULA = "renta-deduccion-maternidad-0611"
_MATERNIDAD_BINDING = "renta-profile-deduccion-maternidad"
_CEILING_RETIRED_FACT = "lirpf-art-81-contribution-ceiling-retired-effective-year"
_GUARDERIA_CAP = "renta-guarderia-incremento-cap-anual"
_RENOVABLES_PERIOD = (
    "renta-actividad-inmovilizado-amortizacion-renovables-primer-ejercicio",
    "renta-actividad-inmovilizado-amortizacion-renovables-ultimo-ejercicio",
)
_VEHICULO_ROWS = (
    "renta-actividad-inmovilizado-amortizacion-vehiculo-electrico-primer-ejercicio",
    "renta-actividad-inmovilizado-amortizacion-vehiculo-electrico-ultimo-ejercicio",
    "renta-actividad-inmovilizado-amortizacion-infraestructura-recarga-primer-ejercicio",
    "renta-actividad-inmovilizado-amortizacion-infraestructura-recarga-ultimo-ejercicio",
)
# The amending real decreto-ley that fixed each year's renewables entry-into-service period.
_RENOVABLES_AMENDING_LAW = {
    2023: "real-decreto-ley-18-2022:art-22",
    2024: "real-decreto-ley-8-2023:art-18",
    2025: "rdl-16-2025:art-17",
}


@cache
def _modelo() -> ModeloDefinition:
    return next(m for m in compiled_bundled_authority().modelos if str(m.id) == _MODELO)


@cache
def _supported_editions() -> tuple[tuple[int, ModeloRevision], ...]:
    """Pair each supported year with the authored edition whose window covers it."""
    pairs: list[tuple[int, ModeloRevision]] = []
    for year in committed_supported_filing_years().years:
        for revision in _modelo().revisions.values():
            if revision.valid_from <= date(year, 12, 31) and (
                revision.valid_to is None or revision.valid_to >= date(year, 1, 1)
            ):
                pairs.append((year, revision))
    assert pairs, "no Modelo 100 edition covers a supported year"
    return tuple(pairs)


@cache
def _ceiling_retired_year() -> int:
    fact = next(
        f for f in load_governed_facts(bundled_path("registry", "aeat", "facts")) if f.fact_id == _CEILING_RETIRED_FACT
    )
    (variant,) = fact.variants
    payload = variant.payload
    assert isinstance(payload, ScalarFactPayload) and isinstance(payload.value, int | Decimal), payload
    return int(payload.value)


def _casillas(revision: ModeloRevision) -> dict[str, CasillaDefinition]:
    return {str(member.id): member for member in revision.casillas}


def _formulas(revision: ModeloRevision) -> dict[str, FormulaDefinition]:
    return {str(member.id): member for member in revision.formulas}


def _bindings(revision: ModeloRevision) -> dict[str, BindingDefinition]:
    return {str(member.id): member for member in revision.bindings}


def _parameters(revision: ModeloRevision) -> dict[str, ParameterDefinition]:
    return {str(member.id): member for member in revision.parameters}


def _marriage_gaps(revision: ModeloRevision) -> list[str]:
    """Return every marriage box the edition does not compute from its declared marriage fact."""
    casillas = _casillas(revision)
    formulas = _formulas(revision)
    bindings = _bindings(revision)
    gaps: list[str] = []
    for casilla_id, (formula_id, binding_id) in _MARRIAGE.items():
        casilla = casillas.get(casilla_id)
        formula = formulas.get(formula_id)
        if casilla is None or str(casilla.formula) != formula_id or casilla.input_kind.value != "computed":
            gaps.append(f"{casilla_id}: not computed by {formula_id}")
        if formula is None or formula.expression.binding != binding_id:
            gaps.append(f"{formula_id}: does not read {binding_id}")
        if binding_id not in bindings:
            gaps.append(f"{binding_id}: undeclared")
    return gaps


def _cites_own_year(member: BindingDefinition | FormulaDefinition | ParameterDefinition, year: int) -> bool:
    """Every dated AEAT source a member cites is the one printed for its own year."""
    dated = [ref for ref in member.source_refs if ref.startswith(("aeat-dr-100-", "aeat-renta-", "boe-modelo-100-"))]
    return bool(dated) and all(str(year) in ref for ref in dated)


@pytest.mark.parametrize(("year", "revision"), _supported_editions(), ids=lambda v: str(getattr(v, "id", v)))
def test_every_supported_year_computes_the_marriage_boxes(year: int, revision: ModeloRevision) -> None:
    assert _marriage_gaps(revision) == [], f"{year}: edition {revision.id}"
    for _formula_id, binding_id in _MARRIAGE.values():
        assert _cites_own_year(_bindings(revision)[binding_id], year), (year, binding_id)


def test_a_marriage_box_left_manual_is_reported() -> None:
    year, revision = _supported_editions()[0]
    casillas = tuple(c.model_copy(update={"formula": None}) if str(c.id) == "0246" else c for c in revision.casillas)
    reduced = revision.model_copy(update={"casillas": casillas})
    assert _marriage_gaps(reduced) == ["0246: not computed by renta-matrimonio-mes-inicio"], year


@pytest.mark.parametrize(("year", "revision"), _supported_editions(), ids=lambda v: str(getattr(v, "id", v)))
def test_maternidad_is_computed_from_the_year_the_cotizaciones_ceiling_is_retired(
    year: int, revision: ModeloRevision
) -> None:
    casilla = _casillas(revision)["0611"]
    binding = _bindings(revision).get(_MATERNIDAD_BINDING)
    if year < _ceiling_retired_year():
        assert casilla.formula is None and casilla.input_kind.value == "manual", year
        assert binding is None, year
        return
    assert str(casilla.formula) == _MATERNIDAD_FORMULA and casilla.input_kind.value == "computed", year
    assert binding is not None and isinstance(binding.provider, ProfileProvider), year
    assert binding.provider.profile_key == f"renta_family.deduccion_maternidad_{year}", year
    assert _cites_own_year(binding, year), year
    assert _cites_own_year(_formulas(revision)[_MATERNIDAD_FORMULA], year), year


@pytest.mark.parametrize(("year", "revision"), _supported_editions(), ids=lambda v: str(getattr(v, "id", v)))
def test_guarderia_cap_carries_its_value_in_every_supported_year(year: int, revision: ModeloRevision) -> None:
    parameter = _parameters(revision)[_GUARDERIA_CAP]
    covering = [
        value
        for value in parameter.values
        if value.valid_from <= date(year, 1, 1) and (value.valid_to is None or value.valid_to >= date(year, 12, 31))
    ]
    assert [value.value for value in covering] == [Decimal("1000")], year
    assert _cites_own_year(parameter, year), year


@pytest.mark.parametrize(("year", "revision"), _supported_editions(), ids=lambda v: str(getattr(v, "id", v)))
def test_pagos_fraccionados_box_cites_the_obligation_and_both_approvals(year: int, revision: ModeloRevision) -> None:
    formula = _formulas(revision)["renta-pagos-fraccionados-ingresados"]
    assert {"ley-35-2006:art-99", "orden-eha-672-2007:art-1", "orden-eha-672-2007:art-3"} <= set(formula.legal_refs)


@pytest.mark.parametrize(("year", "revision"), _supported_editions(), ids=lambda v: str(getattr(v, "id", v)))
def test_incentive_rows_cite_the_amending_law_of_their_own_year(year: int, revision: ModeloRevision) -> None:
    parameters = _parameters(revision)
    amending = _RENOVABLES_AMENDING_LAW.get(year)
    for parameter_id in _RENOVABLES_PERIOD:
        parameter = parameters.get(parameter_id)
        if amending is None:
            assert parameter is None, (year, parameter_id)
            continue
        assert parameter is not None, (year, parameter_id)
        others = set(_RENOVABLES_AMENDING_LAW.values()) - {amending}
        assert amending in parameter.legal_refs, (year, parameter_id)
        assert not others & set(parameter.legal_refs), (year, parameter_id, parameter.legal_refs)
    for parameter_id in _VEHICULO_ROWS:
        parameter = parameters.get(parameter_id)
        if parameter is None:
            continue
        assert {"real-decreto-ley-4-2024:art-4", "ley-35-2006:da-59"} <= set(parameter.legal_refs), (year, parameter_id)
