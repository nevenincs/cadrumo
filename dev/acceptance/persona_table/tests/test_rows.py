"""A row's verdict counts only a live, grounded pass as green, and the plan covers every supported year."""

from __future__ import annotations

import dataclasses
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import Persona, YearEnvelope, persona_ids, read_persona

from ..rows import (
    GREEN,
    PlannedRow,
    Stage,
    TableRow,
    Verdict,
    in_force,
    latest_rows,
    planned_rows,
    read_rows,
    replay_horizons,
    select,
    write_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


@cache
def _persona(persona_id: str) -> Persona:
    return read_persona(persona_id, envelope=_envelope())


def _plan(
    *, grounding: str = "verified", sources: tuple[str, ...] = ("ley:art-1",), has_values: bool = True
) -> PlannedRow:
    envelope = _envelope()
    return PlannedRow(
        persona="persona",
        modelo="130",
        year=envelope.horizon - 1,
        period="1T",
        horizon=envelope.horizon,
        has_values=has_values,
        grounding=grounding,
        sources=sources,
    )


def test_only_three_passing_stages_on_grounded_values_are_green() -> None:
    green = TableRow.from_plan(_plan(), Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)
    red_export = TableRow.from_plan(_plan(), Stage.PASSED, verify=Stage.PASSED, export=Stage.REFUSED)
    red_verify = TableRow.from_plan(_plan(), Stage.PASSED, verify=Stage.INCOMPLETE, export=Stage.PASSED)
    assert green.verdict is Verdict.PASSED
    assert red_export.verdict is Verdict.FAIL
    assert red_verify.verdict is Verdict.FAIL


def test_a_pass_on_unsourced_values_is_unverified_and_not_green() -> None:
    unverified = TableRow.from_plan(
        _plan(grounding="unverified"), Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED
    )
    unsourced = TableRow.from_plan(_plan(sources=()), Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)
    assert unverified.verdict is Verdict.UNVERIFIED
    assert unsourced.verdict is Verdict.UNVERIFIED
    assert unverified.verdict not in GREEN


def test_history_filed_expected_refusal_and_missing_oracle_are_never_green() -> None:
    history = TableRow.from_plan(_plan(), Stage.HISTORY_FILED, verify=Stage.HISTORY_FILED)
    refusal = TableRow.from_plan(_plan(), Stage.EXPECTED_REFUSAL)
    no_oracle = TableRow.from_plan(
        _plan(has_values=False, grounding="none", sources=()),
        Stage.CALCULATED,
        verify=Stage.PASSED,
        export=Stage.PASSED,
    )
    assert (history.verdict, refusal.verdict, no_oracle.verdict) == (
        Verdict.HISTORY_FILED,
        Verdict.EXPECTED_REFUSAL,
        Verdict.NO_ORACLE,
    )
    assert not {history.verdict, refusal.verdict, no_oracle.verdict} & GREEN


def test_unsupported_and_not_run_rows_are_counted_apart() -> None:
    assert TableRow.from_plan(_plan(), Stage.UNSUPPORTED).verdict is Verdict.UNSUPPORTED
    assert TableRow.from_plan(_plan(), Stage.NOT_RUN).verdict is Verdict.NOT_RUN


def test_a_row_survives_its_json_line(tmp_path: Path) -> None:
    row = TableRow.from_plan(_plan(), Stage.MISMATCH, verify=Stage.INCOMPLETE, export=Stage.REFUSED, reason="c01")
    write_rows(tmp_path / "rows.jsonl", [row])
    assert list(read_rows([tmp_path / "rows.jsonl"])) == [row]


def test_the_replay_under_the_higher_horizon_and_the_later_run_win() -> None:
    plan = _plan()
    lower = dataclasses.replace(plan, horizon=plan.horizon - 1)
    first = TableRow.from_plan(plan, Stage.REFUSED)
    later = TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)
    shifted = TableRow.from_plan(lower, Stage.MISMATCH)
    assert latest_rows([first, shifted, later]) == {plan.key: later}


def test_horizons_span_the_registry_envelope_newest_first() -> None:
    envelope = _envelope()
    horizons = replay_horizons(envelope)
    assert horizons[0] == envelope.horizon
    assert horizons[-1] == envelope.floor
    assert len(horizons) == envelope.horizon - envelope.floor + 1


def test_every_applicable_obligation_period_is_a_row_at_the_real_horizon() -> None:
    envelope = _envelope()
    for persona_id in persona_ids():
        persona = _persona(persona_id)
        planned = {(row.modelo, row.year, row.period) for row in planned_rows(persona, envelope.horizon, envelope)}
        owed = {
            (item.modelo, item.year.resolve(envelope), period)
            for item in persona.expectations.obligations
            if item.applicable is True
            for period in item.periods
        }
        assert owed <= planned, persona_id


def test_a_shifted_horizon_moves_every_row_down_by_the_shift() -> None:
    envelope = _envelope()
    persona = _persona("autonomo-fontanero")
    real = planned_rows(persona, envelope.horizon, envelope)
    shifted = planned_rows(persona, envelope.horizon - 1, envelope)
    moved = {(row.modelo, row.year - 1, row.period) for row in real if row.year - 1 >= envelope.floor}
    assert moved <= {(row.modelo, row.year, row.period) for row in shifted}
    assert all(row.horizon == envelope.horizon - 1 for row in shifted)


def test_a_filter_keeps_only_the_named_modelos_and_years() -> None:
    envelope = _envelope()
    rows = planned_rows(_persona("autonomo-fontanero"), envelope.horizon, envelope)
    kept = select(rows, modelos=("130",), years=(envelope.horizon - 1,))
    assert kept
    assert {(row.modelo, row.year) for row in kept} == {("130", envelope.horizon - 1)}
    assert select(rows) == rows


def test_a_baseline_line_holds_year_tokens_and_reads_back_on_the_horizon() -> None:
    plan = _plan()
    row = TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED, reason="free text")
    line = row.to_baseline_json(plan.horizon)
    assert str(plan.year) not in line
    assert '"year": "horizon-1"' in line
    restored = TableRow.from_json(line, horizon=plan.horizon)
    assert (restored.key, restored.verdict, restored.horizon) == (row.key, row.verdict, row.horizon)
    with pytest.raises(ValueError, match="needs the registry horizon"):
        TableRow.from_json(line)


def test_every_return_with_stated_casillas_has_an_oracle_even_beside_concept_only_values() -> None:
    envelope = _envelope()
    for persona_id in persona_ids():
        persona = _persona(persona_id)
        planned = {row.key: row for row in planned_rows(persona, envelope.horizon, envelope)}
        for year, value in in_force(persona.expectations.values, envelope):
            if value.casillas and value.counterparty is None:
                key = (persona_id, value.modelo, year, value.period)
                assert planned[key].has_values, key
                assert set(value.legal_ref) <= set(planned[key].sources), key


def test_a_replay_runs_each_quarter_before_the_annual_returns_of_its_year() -> None:
    envelope = _envelope()
    rows = planned_rows(_persona("traductora-profesional"), envelope.horizon, envelope)
    order = [(row.year, row.modelo, row.period) for row in rows]
    for year, modelo, period in order:
        if period != "0A":
            continue
        annual_at = order.index((year, modelo, period))
        quarters_at = [index for index, (other, _modelo, code) in enumerate(order) if other == year and code != "0A"]
        assert all(index < annual_at for index in quarters_at), (modelo, year)
    assert [period for (_year, modelo, period) in order if modelo == "111"][:4] == ["1T", "2T", "3T", "4T"]
