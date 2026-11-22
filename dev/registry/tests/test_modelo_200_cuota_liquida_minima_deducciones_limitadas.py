"""Modelo 200 deductions held to the cuota liquida minima [00619] (LIS art. 30 bis.2).

The cuota liquida [00592] subtracts thirteen deductions from the cuota integra
ajustada positiva [00582] with no floor, because the manual defines it as that
difference. The minimum is a limit on what the filer may consign: art. 30 bis.2.b
applies "las restantes deducciones ... hasta el importe de dicha cuota liquida
minima", while the Canarias deductions of Ley 20/1991 and Ley 19/1994 apply
"aunque la cuota liquida resultante sea inferior". The registry states that rule
as one verification predicate authored at the 2022 edition and re-pointed to the
DP200014B record from 2023.

The classification below is the oracle, read from the Manual practico de
Sociedades 2022 and LIS art. 30 bis.2, not from the declaration under test; the
coverage gate checks that the predicate classifies exactly the boxes the
edition's own [00592] formula subtracts. The amounts are the manual's Ejemplos 1
to 3 (pp. 352-364). Every case runs the compiled registry and the real predicate
evaluator.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile
from cadrumo.application.modelo.verification_predicates import evaluate_verification_predicates
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_verification import (
    VerificationFindingKind,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind

from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_PREDICATE_ID = "modelo-200-deducciones-limitadas-por-cuota-liquida-minima"
_CUOTA_LIQUIDA_FORMULA = "modelo-200-cuota-liquida"
_BREACH = "application.modelo.findings.limited_subtractions_below_floor"
_UNRESOLVED = "application.modelo.findings.floor_subtraction_unresolved"

_FLOOR = "00619"
_BASE = "00582"
#: LIS art. 30 bis.2.a: the base is first reduced by the art. 38 bis deduction (manual p. 351).
_PRE_FLOOR = frozenset({"02315"})
#: LIS art. 30 bis.2.b: "las restantes deducciones ... hasta el importe de dicha cuota liquida minima".
_LIMITED = frozenset({"00585", "00584", "00588", "01039", "00565", "01040", "01041"})
#: Boxes whose relation to the minimum no official text states: [00583] has no manual
#: description and [00399] carries deductions of foral law.
_UNCLASSIFIED = frozenset({"00583", "00399"})
#: Canarias deductions under Ley 20/1991 art. 94 and DA 14a Ley 19/1994 (art. 30 bis.2.b), and the
#: art. 39.2 I+D+i deduction the minimum does not affect (manual p. 359).
_EXEMPT = frozenset({"02314", "00590", "00082"})


def _declaring_revisions() -> tuple[ModeloRevision, ...]:
    return tuple(
        revision
        for revision in authored_revisions("200")
        if any(predicate.predicate_id == _PREDICATE_ID for predicate in revision.verification_predicates)
    )


_DECLARING = _declaring_revisions()
_REVISION_IDS = [str(revision.id) for revision in _DECLARING]


def _predicate(revision: ModeloRevision) -> VerificationPredicateDefinition:
    return next(predicate for predicate in revision.verification_predicates if predicate.predicate_id == _PREDICATE_ID)


def _box(casilla_id: str) -> str:
    return casilla_id.rsplit(":", 1)[-1]


def _groups(predicate: VerificationPredicateDefinition) -> tuple[tuple[str, ...], ...]:
    parsed = parse_verification_predicate_expression(predicate.expression)
    assert parsed is not None
    assert parsed.operator is VerificationPredicateOperator.LIMITED_SUBTRACTIONS_RESPECT_FLOOR
    return parsed.casilla_groups()


def _cuota_liquida_operands(revision: ModeloRevision) -> tuple[str, tuple[str, ...]]:
    """The minuend and the subtracted boxes of the edition's own [00592] formula."""
    formula = next(formula for formula in revision.formulas if formula.id == _CUOTA_LIQUIDA_FORMULA)

    def leaves(node: FormulaExpression) -> tuple[str, ...]:
        if node.casilla_id is not None:
            return (str(node.casilla_id),)
        return tuple(leaf for argument in node.args for leaf in leaves(argument))

    subtraction = next(argument for argument in formula.expression.args if argument.op is not None)
    minuend, subtrahend = subtraction.args
    assert minuend.casilla_id is not None
    return str(minuend.casilla_id), leaves(subtrahend)


def _findings(revision: ModeloRevision, amounts: Mapping[str, str]) -> list[ModeloVerificationFinding]:
    predicate = _predicate(revision)
    by_box = {_box(casilla_id): casilla_id for group in _groups(predicate) for casilla_id in group}
    values: dict[CasillaId, Decimal] = {
        validated_casilla_id(by_box[box]): Decimal(amount) for box, amount in amounts.items()
    }
    return evaluate_verification_predicates(
        (predicate,),
        values,
        workflow_profile(),
        declared_casilla_ids={casilla.id for casilla in revision.casillas},
    )


def test_every_authored_edition_from_2022_carries_the_gate() -> None:
    assert _DECLARING, "no Modelo 200 edition declares the cuota liquida minima gate"
    assert all(
        _PREDICATE_ID in {predicate.predicate_id for predicate in revision.verification_predicates}
        for revision in authored_revisions("200")
        if revision.valid_from >= _DECLARING[0].valid_from
    )


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
def test_gate_classifies_exactly_the_boxes_the_cuota_liquida_subtracts(revision: ModeloRevision) -> None:
    predicate = _predicate(revision)
    floor_and_base, pre_floor, limited, unclassified, exempt = _groups(predicate)
    minuend, subtracted = _cuota_liquida_operands(revision)

    assert predicate.finding_kind is VerificationFindingKind.BLOCKING_RULE
    assert tuple(_box(casilla_id) for casilla_id in floor_and_base) == (_FLOOR, _BASE)
    assert floor_and_base[1] == minuend
    assert sorted((*pre_floor, *limited, *unclassified, *exempt)) == sorted(subtracted)
    # The floor and the subtractions sit on the record the formula's subtractions use.
    assert {casilla_id.rsplit(":", 1)[0] for casilla_id in (floor_and_base[0], *subtracted)} == {
        subtracted[0].rsplit(":", 1)[0]
    }
    assert {_box(casilla_id) for casilla_id in pre_floor} == _PRE_FLOOR
    assert {_box(casilla_id) for casilla_id in limited} == _LIMITED
    assert {_box(casilla_id) for casilla_id in unclassified} == _UNCLASSIFIED
    assert {_box(casilla_id) for casilla_id in exempt} == _EXEMPT
    assert set(predicate.legal_refs) >= {"ley-27-2014:art-30-bis"}


#: The manual's liquidaciones, with and without tributacion minima; each holds.
_MANUAL_LIQUIDACIONES = {
    # Ejemplo 1 "con tributacion minima" (p. 355): 350.000 - 50.000 = 300.000.
    "ejemplo-1-con": {_BASE: "350000", "00588": "50000", _FLOOR: "300000"},
    # Ejemplo 2 "con tributacion minima" (p. 360): no limited deduction once below the minimum.
    "ejemplo-2-con": {_BASE: "220000", "02315": "90000", "00588": "0", "00082": "130000", _FLOOR: "130000"},
    # Ejemplo 2 as printed, [00619] 0 (p. 360).
    "ejemplo-2-con-printed": {_BASE: "220000", "02315": "90000", "00082": "130000", _FLOOR: "0"},
    # Ejemplo 3 "con tributacion minima" (p. 364): 455.000 - 30.000 = 425.000.
    "ejemplo-3-con": {_BASE: "455000", "00588": "30000", _FLOOR: "300000"},
    # The "sin tributacion minima" tables carry no minimum (pp. 352-353, 357, 362).
    "ejemplo-1-sin": {_BASE: "350000", "00588": "80000", _FLOOR: "0"},
    "ejemplo-2-sin": {_BASE: "220000", "00588": "110000", "02315": "90000", "00082": "20000", _FLOOR: "0"},
    "ejemplo-3-sin": {_BASE: "455000", "00588": "30000", _FLOOR: "0"},
}


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
@pytest.mark.parametrize("case", sorted(_MANUAL_LIQUIDACIONES))
def test_manual_liquidaciones_are_silent(revision: ModeloRevision, case: str) -> None:
    assert _findings(revision, _MANUAL_LIQUIDACIONES[case]) == []


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
def test_limited_deduction_taking_the_cuota_below_the_minimum_is_blocked(revision: ModeloRevision) -> None:
    findings = _findings(revision, {_BASE: "350000", "00588": "80000", _FLOOR: "300000"})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.message_locale_key == _BREACH
    assert _box(str(finding.casilla_id)) == _FLOOR
    assert finding.message_facts["floor_value"] == Decimal("300000")
    assert finding.message_facts["limited_total"] == Decimal("80000")
    assert finding.message_facts["after_limited"] == Decimal("270000")


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
@pytest.mark.parametrize(
    "amounts",
    [
        # One cent past the minimum in Ejemplo 1.
        {_BASE: "350000", "00588": "50000.01", _FLOOR: "300000"},
        # Ejemplo 2 is already below the minimum after [02315]: no limited deduction fits at all.
        {_BASE: "220000", "02315": "90000", "00588": "1", _FLOOR: "130000"},
        # Several limited boxes together exceed the room.
        {_BASE: "350000", "00584": "30000", "00565": "20000.01", _FLOOR: "300000"},
    ],
    ids=["one-cent-over", "below-after-pre-floor", "combined-limited"],
)
def test_limited_deductions_past_the_room_are_blocked(revision: ModeloRevision, amounts: dict[str, str]) -> None:
    assert [finding.message_locale_key for finding in _findings(revision, amounts)] == [_BREACH]


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
@pytest.mark.parametrize(
    "amounts",
    [
        {_BASE: "220000", "02315": "90000", "00082": "130000", _FLOOR: "130000"},
        {_BASE: "220000", "02315": "90000", "00590": "100000", _FLOOR: "130000"},
        {_BASE: "220000", "02314": "100000", _FLOOR: "130000"},
        # Limited deductions within the room, then a Canarias deduction below the minimum.
        {_BASE: "350000", "00588": "50000", "00590": "40000", _FLOOR: "300000"},
        # Below the minimum after [02315] alone, with nothing limited consigned.
        {_BASE: "220000", "02315": "100000", _FLOOR: "130000"},
    ],
    ids=[
        "art-39-2-below",
        "canarias-inversion-below",
        "canarias-film-below",
        "limited-then-canarias",
        "pre-floor-below-nothing-limited",
    ],
)
def test_excluded_deductions_below_the_minimum_are_silent(revision: ModeloRevision, amounts: dict[str, str]) -> None:
    assert _findings(revision, amounts) == []


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
@pytest.mark.parametrize("box", sorted(_UNCLASSIFIED))
@pytest.mark.parametrize(
    "amounts",
    [
        # Read as exempt it holds, read as pre-floor or limited it leaves 290.000 below 300.000.
        {_BASE: "350000", _FLOOR: "300000"},
        # Limited deductions within the room, and the box would take the rest past it.
        {_BASE: "350000", "00588": "40000", _FLOOR: "300000"},
    ],
    ids=["box-alone", "after-limited"],
)
def test_unclassified_deduction_that_could_cross_the_minimum_is_unresolved(
    revision: ModeloRevision, box: str, amounts: dict[str, str]
) -> None:
    findings = _findings(revision, {**amounts, box: "60000"})

    assert [finding.message_locale_key for finding in findings] == [_UNRESOLVED]
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _box(str(findings[0].casilla_id)) == box
    assert _box(str(findings[0].message_facts["floor_box"])) == _FLOOR


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
@pytest.mark.parametrize("box", sorted(_UNCLASSIFIED))
@pytest.mark.parametrize(
    ("amounts", "unclassified"),
    [
        # Room for it whichever group it belongs to: 350.000 - 1.000 stays above 300.000.
        ({_BASE: "350000", _FLOOR: "300000"}, "1000"),
        # Exactly the room: 350.000 - 50.000 reaches 300.000.
        ({_BASE: "350000", _FLOOR: "300000"}, "50000"),
        # Room after a limited deduction too: 350.000 - 30.000 - 20.000 reaches 300.000.
        ({_BASE: "350000", "00588": "30000", _FLOOR: "300000"}, "20000"),
        # No minimum at all.
        ({_BASE: "350000", _FLOOR: "0"}, "1000"),
    ],
    ids=["leaves-room", "exactly-the-room", "room-after-limited", "no-minimum"],
)
def test_unclassified_deduction_that_cannot_change_the_outcome_is_silent(
    revision: ModeloRevision, box: str, amounts: dict[str, str], unclassified: str
) -> None:
    assert _findings(revision, {**amounts, box: unclassified}) == []


@pytest.mark.parametrize("revision", _DECLARING, ids=_REVISION_IDS)
def test_certain_breach_is_reported_ahead_of_an_unresolved_box(revision: ModeloRevision) -> None:
    findings = _findings(revision, {_BASE: "350000", "00588": "80000", "00583": "1000", _FLOOR: "300000"})

    assert [finding.message_locale_key for finding in findings] == [_BREACH]
