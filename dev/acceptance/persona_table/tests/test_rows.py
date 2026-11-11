"""A row's verdict counts only a live, grounded pass as green, and the plan covers every supported year."""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import Persona, PersonaCatalogueError, YearEnvelope, persona_ids, read_persona

from ..rows import (
    GREEN,
    PlannedRow,
    Stage,
    TableRow,
    Verdict,
    ended,
    in_force,
    latest_rows,
    planned_rows,
    read_rows,
    replay_horizons,
    select,
    stage_refusal_codes,
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


def test_every_return_of_a_persona_history_is_a_row_the_table_runs_live() -> None:
    envelope = _envelope()
    for persona_id in persona_ids():
        persona = _persona(persona_id)
        planned = {(row.modelo, row.year, row.period) for row in planned_rows(persona, envelope.horizon, envelope)}
        history = {
            (block.modelo, block.year.resolve(envelope), period)
            for block in (*persona.filed_returns, *persona.calculated_returns)
            for period in block.periods
        }
        assert history <= planned, persona_id


def test_a_return_an_obligation_states_not_applicable_is_no_row_even_with_a_stated_cross_check() -> None:
    envelope = _envelope()
    for persona_id in persona_ids():
        persona = _persona(persona_id)
        planned = {(row.modelo, row.year, row.period) for row in planned_rows(persona, envelope.horizon, envelope)}
        filed = {
            (block.modelo, block.year.resolve(envelope), period)
            for block in (*persona.filed_returns, *persona.calculated_returns)
            for period in block.periods
        }
        absent = {
            (item.modelo, item.year.resolve(envelope), period)
            for item in persona.expectations.obligations
            if item.applicable is False
            for period in item.periods
        }
        assert not (absent - filed) & planned, persona_id


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


def test_a_return_whose_period_has_not_ended_by_the_scenario_day_is_not_owed_yet() -> None:
    year = _plan().year
    today = date(year, 4, 1)
    ended_quarter, open_quarter, last_year, this_year = (
        dataclasses.replace(_plan(), period="1T"),
        dataclasses.replace(_plan(), period="2T"),
        dataclasses.replace(_plan(), year=year - 1, period="0A"),
        dataclasses.replace(_plan(), period="0A"),
    )
    kept = ended([ended_quarter, open_quarter, last_year, this_year], today)
    assert kept == [ended_quarter, last_year]


def test_a_refusal_the_export_or_verify_stage_settled_with_is_read_back_by_its_code() -> None:
    export = "export: modelo.export refused REFUSED_MODELO_EXPORT_NAME_TOO_WIDE :: detail"
    verify = "verify: modelo.work.verify failed INTEGRITY_STORAGE_VALIDATION"
    findings = "verify: blocked; 2 findings; blocking: none"
    assert stage_refusal_codes(export, verify, findings, "") == {
        "REFUSED_MODELO_EXPORT_NAME_TOO_WIDE",
        "INTEGRITY_STORAGE_VALIDATION",
    }


def _floor_plan(*, dropped: bool = True) -> PlannedRow:
    envelope = _envelope()
    return dataclasses.replace(_plan(), year=envelope.floor, floor_source_dropped=dropped)


def test_a_floor_year_refusal_after_a_dropped_prior_year_source_is_neither_fail_nor_green() -> None:
    row = TableRow.from_plan(_floor_plan(), Stage.REFUSED)
    verify_refused = TableRow.from_plan(_floor_plan(), Stage.PASSED, verify=Stage.INCOMPLETE)
    assert row.verdict is Verdict.FLOOR_SOURCE
    assert verify_refused.verdict is Verdict.FLOOR_SOURCE
    assert row.verdict not in GREEN


def test_a_value_mismatch_stays_a_fail_beside_a_dropped_source() -> None:
    row = TableRow.from_plan(_floor_plan(), Stage.MISMATCH, verify=Stage.INCOMPLETE, export=Stage.REFUSED)
    assert row.verdict is Verdict.FAIL


def test_a_refusal_without_a_dropped_source_stays_a_fail() -> None:
    row = TableRow.from_plan(_floor_plan(dropped=False), Stage.REFUSED)
    assert row.verdict is Verdict.FAIL


def test_the_dropped_source_flag_survives_both_json_forms_and_old_lines_load_without_it(tmp_path: Path) -> None:
    row = TableRow.from_plan(_floor_plan(), Stage.REFUSED)
    write_rows(tmp_path / "rows.jsonl", [row])
    assert list(read_rows([tmp_path / "rows.jsonl"])) == [row]
    restored = TableRow.from_json(row.to_baseline_json(row.horizon), horizon=row.horizon)
    assert (restored.floor_source_dropped, restored.verdict) == (True, Verdict.FLOOR_SOURCE)
    plain = TableRow.from_plan(_plan(), Stage.REFUSED)
    old_line = json.loads(plain.to_json())
    del old_line["floor_source_dropped"]
    assert TableRow.from_json(json.dumps(old_line)).floor_source_dropped is False
    assert "floor_source_dropped" not in plain.to_baseline_json(plain.horizon)


def test_the_planner_marks_floor_year_rows_whose_prior_year_history_the_floor_dropped() -> None:
    envelope = _envelope()
    marked = unmarked = 0
    for persona_id in persona_ids():
        for horizon in replay_horizons(envelope):
            lowered = dataclasses.replace(envelope, horizon=horizon)
            try:
                persona = read_persona(persona_id, envelope=lowered, omit_below_floor=horizon != envelope.horizon)
            except PersonaCatalogueError:
                continue
            before = {
                record.year.resolve(lowered, biographical=True) for record in persona.below_floor if record.history
            }
            for row in planned_rows(persona, horizon, envelope):
                expected = row.year == envelope.floor and envelope.floor - 1 in before
                assert row.floor_source_dropped is expected, (persona_id, horizon, row.key)
                marked += expected
                unmarked += not expected and row.year == envelope.floor
    assert marked
    assert unmarked
    persona = read_persona("autonomo-fontanero", envelope=envelope)
    assert not any(row.floor_source_dropped for row in planned_rows(persona, envelope.horizon, envelope))
