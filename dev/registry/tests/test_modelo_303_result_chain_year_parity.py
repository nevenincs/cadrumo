"""Modelo 303's devengado total and result chain follow each year's own diseño.

Box [27] (total cuota devengada), [64] (suma de resultados), [66] (atribuible a
la Administración del Estado), [69] (resultado) and [71] (resultado de la
liquidación) are printed with an explicit arithmetic expression in every
bundled diseño de registro. Where two years print the same expression the
registry must compute the box the same way, and where a year adds a rung the
registry must add exactly that rung in that year. The oracle is the design
text itself, read from the bundled corpus; the registry is read through the
compiled typed authority and the real calculation engine.
"""

from __future__ import annotations

import re
from decimal import Decimal
from itertools import pairwise

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.period import calculation_filing_date

from ..compiler.authority import compiled_bundled_authority
from ._modelo_303_registry_support import _M303_RECORD_DESIGN_SOURCE_BY_REVISION

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_REVISIONS = tuple(_M303_RECORD_DESIGN_SOURCE_BY_REVISION)

# The AEAT box each semantic carrier stands for where the registry sums a
# carrier instead of the printed box. The pairs are read off the design labels:
# [03]/[06]/[09] are the 4 %, 10 % and 21 % cuotas, [11] the intracomunitaria
# cuota, [13] the other inversión del sujeto pasivo cuota, [155]/[167] the
# transitional reducido and super-reducido cuotas, [46] the régimen general
# result, [69] the autoliquidación result and [78] the compensación applied
# this period. Every summand must stand for a printed box: the promotor's
# autoconsumo is declared inside the rate row of its rate, never beside them.
_CARRIER_BOX = {
    "iva.cuota-devengada.super-reducido": "03",
    "iva.cuota-devengada.reducido": "06",
    "iva.cuota-devengada.general": "09",
    "iva.autorepercutido.intracomunitaria": "11",
    "iva.autorepercutido.interior.devengado": "13",
    "iva.repercutido.reducido.transitorio": "155",
    "iva.repercutido.super-reducido.transitorio": "167",
    "iva.resultado-regimen-general": "46",
    "iva.compensacion-aplicada-periodo": "78",
    "iva.resultado": "69",
}
_DESIGN_TERM = re.compile(r"([+-]?)\s*\[(\d+)\]")


def _design_expression(revision_id: str, box: str) -> tuple[tuple[int, str], ...]:
    """Return the signed terms the revision's own diseño prints for ``box``."""
    source = compiled_bundled_authority().catalogues.sources[_M303_RECORD_DESIGN_SOURCE_BY_REVISION[revision_id]]
    design = (bundled_path() / f"{source.corpus_path}.extracted.md").read_text(encoding="utf-8")
    matches = re.findall(rf"\(([^()]*)\)\s*\[{box}\]", design)
    assert len(set(matches)) == 1, f"{revision_id}: design prints {len(set(matches))} expressions for [{box}]"
    return tuple((-1 if sign == "-" else 1, str(number)) for sign, number in _DESIGN_TERM.findall(matches[0]))


def _signed_terms(expression: FormulaExpression, sign: int = 1) -> list[tuple[int, str]]:
    """Flatten a pure add/subtract tree into signed casilla terms."""
    if expression.casilla_id is not None:
        return [(sign, str(expression.casilla_id))]
    if expression.op == "add":
        return [term for arg in expression.args for term in _signed_terms(arg, sign)]
    if expression.op == "subtract":
        head, *tail = expression.args
        return [*_signed_terms(head, sign), *(term for arg in tail for term in _signed_terms(arg, -sign))]
    raise AssertionError(f"not a pure sum: {expression.model_dump(exclude_none=True)}")


def _as_design_terms(terms: list[tuple[int, str]]) -> set[tuple[int, str]]:
    return {(sign, _CARRIER_BOX.get(casilla_id, casilla_id)) for sign, casilla_id in terms}


def _revision(revision_id: str) -> ModeloRevision:
    return compiled_bundled_authority().modelo("303").revisions[revision_id]


def _formula_for(revision: ModeloRevision, casilla_id: str) -> FormulaExpression:
    (formula,) = [formula for formula in revision.formulas if str(formula.target_casilla_id) == casilla_id]
    return formula.expression


def test_the_design_comparison_detects_a_missing_summand() -> None:
    revision = _revision("2022")
    terms = _signed_terms(_formula_for(revision, "iva.cuota-devengada-total"))
    design = set(_design_expression("2022", "27"))
    assert _as_design_terms(terms) == design
    without_box_26 = [term for term in terms if term != (1, "26")]
    assert design - _as_design_terms(without_box_26) == {(1, "26")}


@pytest.mark.parametrize("revision_id", _REVISIONS)
def test_box_27_projects_a_devengado_total_holding_exactly_its_years_design_rungs(revision_id: str) -> None:
    revision = _revision(revision_id)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "27")
    assert casilla.formula == "modelo-303-dr303-27-projection"
    assert _formula_for(revision, "27").casilla_id == "iva.cuota-devengada-total"

    terms = _signed_terms(_formula_for(revision, "iva.cuota-devengada-total"))
    assert _as_design_terms(terms) == set(_design_expression(revision_id, "27"))
    assert len(terms) == len(_design_expression(revision_id, "27")), "a rung is summed twice"


@pytest.mark.parametrize(("box", "target"), [("64", "64"), ("69", "iva.resultado"), ("71", "71")])
def test_result_boxes_are_computed_as_each_years_design_prints_them(box: str, target: str) -> None:
    designs = {revision_id: _design_expression(revision_id, box) for revision_id in _REVISIONS}
    expressions = {
        revision_id: _formula_for(_revision(revision_id), target).model_dump(exclude_none=True)
        for revision_id in _REVISIONS
    }
    for revision_id in _REVISIONS:
        terms = _signed_terms(_formula_for(_revision(revision_id), target))
        assert _as_design_terms(terms) == set(designs[revision_id]), revision_id
        assert len(terms) == len(designs[revision_id]), f"{revision_id}: a term of [{box}] is counted twice"
    for earlier, later in pairwise(_REVISIONS):
        if designs[earlier] == designs[later]:
            assert expressions[earlier] == expressions[later], f"{later} computes [{box}] unlike {earlier}"


def test_boxes_64_to_66_are_declared_identically_in_every_year() -> None:
    def declaration(revision_id: str) -> dict[str, object]:
        revision = _revision(revision_id)
        casillas = {casilla.id: casilla for casilla in revision.casillas}
        binding = next(b for b in revision.bindings if b.id == casillas["65"].binding)
        return {
            "64": (casillas["64"].input_kind, casillas["64"].formula),
            "65": (casillas["65"].input_kind, binding.provider.model_dump()),
            "66": (casillas["66"].input_kind, _formula_for(revision, "66").model_dump(exclude_none=True)),
        }

    first = declaration(_REVISIONS[0])
    assert first["64"] == ("computed", "modelo-303-iva-suma-resultados")
    for revision_id in _REVISIONS[1:]:
        assert declaration(revision_id) == first, revision_id


@pytest.mark.parametrize(
    ("filing_year", "revision_id", "result"),
    [(2022, "2022", "130"), (2023, "2023", "130"), (2025, "2025", "150"), (2026, "2026-y-siguientes", "150")],
)
def test_the_result_chain_computes_each_years_design_arithmetic(
    filing_year: int, revision_id: str, result: str
) -> None:
    """A foral taxpayer with IVA modifications, import IVA deferral, an annual regularisation and other adjustments.

    Expected amounts are the designs' own arithmetic on these inputs: [27] =
    [15] + [26] = 150; [46] = [27] - [45] = 150; [64] = [46] + [58] + [76] = 150;
    [66] = [64] x [65] / 100 = 90; [69] = [66] + [77] - [78] + [68] = 130, plus
    [108] = 20 from the 09/3T 2024 design on; [71] = [69] - [70] (+ [109] from
    2023, - [112] from 2026, both zero here) = [69].
    """
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot("303", filing_year=filing_year, period="4T")
    assert snapshot.revision.id == revision_id
    declared_bindings = {binding.id for binding in snapshot.revision.bindings}
    binding_values = {
        binding_id: value
        for binding_id, value in {
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0"),
            "modelo-303-profile-state-attribution-ratio": Decimal("60"),
            **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
        }.items()
        if binding_id in declared_bindings
    }
    declared = {casilla.id for casilla in snapshot.revision.casillas}
    manual = {
        "15": "100",
        "26": "50",
        "58": "0",
        "76": "0",
        "77": "25",
        "68": "15",
        "70": "0",
        "108": "20",
        "109": "0",
        "112": "0",
    }
    inputs: dict[CasillaId, Decimal] = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        **{validated_casilla_id(box): Decimal(value) for box, value in manual.items() if box in declared},
    }
    calculated = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": calculation_filing_date(Period.from_year_and_code(filing_year, "4T"))},
    )

    expected = {"27": "150", "64": "150", "66": "90", "iva.resultado": result, "71": result}
    assert {box: calculated.values[validated_casilla_id(box)] for box in expected} == {
        box: Decimal(value) for box, value in expected.items()
    }
