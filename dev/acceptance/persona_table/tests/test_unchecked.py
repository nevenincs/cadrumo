"""A row is green only when every value the persona states for the return is compared."""

from __future__ import annotations

import dataclasses
from datetime import date
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import (
    ExpectedValue,
    Persona,
    ProvisionPeriods,
    YearEnvelope,
    YearToken,
    persona_ids,
    read_persona,
)

from ..rows import (
    GREEN,
    PlannedRow,
    Stage,
    TableRow,
    Verdict,
    planned_rows,
    unchecked_items,
    with_unchecked,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERIOD = "0A"


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _value(
    modelo: str = "130",
    *,
    counterparty: str | None = None,
    casillas: tuple[tuple[str, str], ...] = (),
    concepts: tuple[tuple[str, str], ...] = (),
    not_sourced: tuple[tuple[str, str], ...] = (),
) -> ExpectedValue:
    return ExpectedValue(
        modelo=modelo,
        period=_PERIOD,
        year=YearToken(anchor="horizon", offset=-1),
        counterparty=counterparty,
        casillas=casillas,
        concepts=concepts,
        parameters=(),
        derivation=None,
        legal_ref=("ley:art-1",),
        grounding="verified",
        reason=None,
        not_sourced=not_sourced,
    )


def _persona(*values: ExpectedValue) -> Persona:
    persona = read_persona(persona_ids()[0], envelope=_envelope())
    expectations = dataclasses.replace(persona.expectations, values=values, obligations=())
    return dataclasses.replace(persona, expectations=expectations, filed_returns=(), calculated_returns=())


def _items(modelo: str, *values: ExpectedValue) -> tuple[str, ...]:
    envelope = _envelope()
    key = (modelo, envelope.horizon - 1, _PERIOD)
    return unchecked_items(_persona(*values), envelope, key)


def _planned(*values: ExpectedValue) -> PlannedRow:
    (plan,) = planned_rows(_persona(*values), _envelope().horizon, _envelope())
    return plan


def _passed(plan: PlannedRow) -> TableRow:
    return TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)


def test_concepts_beside_casillas_are_listed_and_the_row_is_not_a_pass() -> None:
    value = _value(casillas=(("01", "10.00"),), concepts=(("clave", "A"), ("base", "5")))
    assert _items("130", value) == ("concept:base", "concept:clave")
    row = _passed(_planned(value))
    assert row.unchecked == ("concept:base", "concept:clave")
    assert row.verdict is Verdict.UNCHECKED
    assert row.verdict not in GREEN


def test_a_counterparty_compared_through_the_design_is_a_pass() -> None:
    value = _value("347", counterparty="cliente", concepts=(("clave", "A"), ("importe_anual", "10.00")))
    declared = _value("347", counterparty="otro", concepts=(("declared", "false"),))
    assert _items("347", value, declared) == ()
    assert _passed(_planned(value, declared)).verdict is Verdict.PASSED


def test_a_counterparty_concept_the_design_does_not_map_is_unchecked() -> None:
    value = _value("347", counterparty="cliente", concepts=(("clave", "A"), ("trimestre", "1")))
    assert _items("347", value) == ("counterparty:cliente:trimestre",)
    assert _passed(_planned(value)).verdict is Verdict.UNCHECKED


def test_a_counterparty_value_of_a_modelo_without_a_design_is_unchecked() -> None:
    value = _value("130", counterparty="pagador", concepts=(("importe", "1"),))
    assert _items("130", value) == ("counterparty:pagador",)


def test_a_return_with_only_concepts_is_unchecked_and_not_without_an_oracle() -> None:
    value = _value(concepts=(("clave", "A"),))
    plan = _planned(value)
    assert not plan.has_values
    row = TableRow.from_plan(plan, Stage.CALCULATED, verify=Stage.PASSED, export=Stage.PASSED)
    assert row.verdict is Verdict.UNCHECKED
    assert row.unchecked == ("concept:clave",)


def test_a_value_stated_not_sourced_is_not_unchecked() -> None:
    value = _value(not_sourced=(("02", "5.00"),))
    assert _items("130", value) == ()


def test_a_failing_row_stays_failing_and_an_expected_refusal_with_unchecked_items_is_unchecked() -> None:
    plan = dataclasses.replace(_planned(_value(casillas=(("01", "10.00"),))), unchecked=("concept:clave",))
    assert TableRow.from_plan(plan, Stage.MISMATCH).verdict is Verdict.FAIL
    assert TableRow.from_plan(plan, Stage.EXPECTED_REFUSAL).verdict is Verdict.UNCHECKED
    assert TableRow.from_plan(plan, Stage.REFUSED).verdict is Verdict.FAIL


def test_a_value_a_provision_replaces_is_not_listed() -> None:
    envelope = _envelope()
    year = envelope.horizon - 1
    periods = ProvisionPeriods(first=date(year, 1, 1), last=None)
    governed_envelope = dataclasses.replace(envelope, provisions=(("ley:art-2", periods),))
    plain = _value(casillas=(("01", "1.00"),), concepts=(("clave", "A"),))
    governed = dataclasses.replace(_value(casillas=(("01", "2.00"),)), governed_by="ley:art-2")
    persona = _persona(plain, governed)
    assert unchecked_items(persona, governed_envelope, ("130", year, _PERIOD)) == ()


def test_unchecked_items_are_read_back_from_the_persona_at_the_rows_horizon() -> None:
    envelope = _envelope()
    value = _value(casillas=(("01", "10.00"),), concepts=(("clave", "A"),))
    persona = _persona(value)
    plan = _planned(value)
    bare = dataclasses.replace(_passed(plan), unchecked=())
    assert bare.verdict is Verdict.PASSED
    assert unchecked_items(persona, envelope, (plan.modelo, plan.year, plan.period)) == ("concept:clave",)
    assert with_unchecked([dataclasses.replace(bare, persona="no-such-persona")], envelope)[0].unchecked == ()
