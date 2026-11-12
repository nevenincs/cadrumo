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
from cadrumo.tests.personas import (
    ExpectedObligation,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    persona_ids,
    read_persona,
)

from ..coverage import APPLICABLE, CalendarObservation
from ..rows import (
    GREEN,
    PlannedRow,
    Stage,
    TableRow,
    Verdict,
    ended,
    in_force,
    latest_rows,
    not_owed_stage,
    planned_rows,
    read_rows,
    replay_horizons,
    replayed,
    select,
    source_closure,
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


def test_a_refused_calculation_is_red_whatever_the_oracle_states() -> None:
    no_oracle = _plan(has_values=False, grounding="none", sources=())
    unsourced = _plan(grounding="unverified")
    uncompared = dataclasses.replace(_plan(), unchecked=("not-sourced:00255",))
    verdicts = {
        TableRow.from_plan(plan, Stage.REFUSED, reason="modelo.work.calculate refused C").verdict
        for plan in (no_oracle, unsourced, uncompared)
    }
    assert verdicts == {Verdict.FAIL}
    passed = TableRow.from_plan(uncompared, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)
    assert passed.verdict is Verdict.UNCHECKED


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


def test_a_return_an_obligation_states_not_applicable_is_only_a_not_owed_row_carrying_stated_values() -> None:
    envelope = _envelope()
    for persona_id in persona_ids():
        persona = _persona(persona_id)
        rows = planned_rows(persona, envelope.horizon, envelope)
        planned = {(row.modelo, row.year, row.period) for row in rows if row.owed}
        assert all(row.has_values for row in rows if not row.owed), persona_id
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


def _row(modelo: str, year: int, period: str) -> PlannedRow:
    return dataclasses.replace(_plan(), modelo=modelo, year=year, period=period)


_READS = {"renta": ("instalment", "renta"), "instalment": ("instalment",), "annual-vat": ("vat",), "vat": ("vat",)}


def _reads(modelo: str) -> tuple[str, ...]:
    return _READS.get(modelo, ())


def test_the_source_closure_follows_reads_transitively() -> None:
    reads = {"a": ("b",), "b": ("c",), "c": ("a",)}
    assert source_closure(["a"], lambda modelo: reads.get(modelo, ())) == {"a", "b", "c"}
    assert source_closure(["d"], lambda modelo: reads.get(modelo, ())) == {"d"}


def test_a_filtered_run_replays_the_earlier_rows_its_selection_reads_and_no_others() -> None:
    year = _envelope().horizon - 1
    rows = [
        _row("instalment", year - 1, "4T"),
        _row("vat", year - 1, "4T"),
        _row("renta", year - 1, "0A"),
        _row("instalment", year, "1T"),
        _row("vat", year, "1T"),
        _row("instalment", year, "2T"),
        _row("annual-vat", year, "0A"),
        _row("renta", year, "0A"),
        _row("instalment", year + 1, "1T"),
    ]
    selected = select(rows, modelos=("renta",), years=(year,))
    assert [row.key for row in selected] == [rows[7].key]
    run = replayed(rows, selected, _reads)
    assert run == [rows[0], rows[2], rows[3], rows[5], rows[7]]
    assert replayed(rows, select(rows, modelos=("vat",)), _reads) == [rows[1], rows[4]]
    assert replayed(rows, select(rows, modelos=("annual-vat",)), _reads) == [rows[1], rows[4], rows[6]]


def test_an_unfiltered_run_replays_every_row_and_an_empty_selection_none() -> None:
    year = _envelope().horizon - 1
    rows = [_row("vat", year, "1T"), _row("renta", year, "0A")]
    assert replayed(rows, select(rows), _reads) == rows
    assert replayed(rows, select(rows, modelos=("absent",)), _reads) == []


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


def test_a_stated_casilla_left_without_a_value_is_unresolved_not_a_mismatch() -> None:
    floor = TableRow.from_plan(_floor_plan(), Stage.UNRESOLVED, verify=Stage.REFUSED, export=Stage.REFUSED)
    plain = TableRow.from_plan(_plan(), Stage.UNRESOLVED, verify=Stage.REFUSED, export=Stage.REFUSED)
    assert floor.verdict is Verdict.FLOOR_SOURCE
    assert plain.verdict is Verdict.FAIL


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


_FONTANERO = "autonomo-fontanero"


def _stated_not_owed(persona: Persona, envelope: YearEnvelope) -> tuple[Persona, tuple[str, int, str]]:
    """``persona`` with its first stated return outside its history restated as not applicable, and that return."""
    history = {
        (block.modelo, block.year.resolve(envelope), period)
        for block in (*persona.filed_returns, *persona.calculated_returns)
        for period in block.periods
    }
    value = next(
        value
        for value in persona.expectations.values
        if value.casillas and (value.modelo, value.year.resolve(envelope), value.period) not in history
    )
    key = (value.modelo, value.year.resolve(envelope), value.period)
    kept = tuple(
        item
        for item in persona.expectations.obligations
        if not (item.modelo == key[0] and item.year.resolve(envelope) == key[1] and key[2] in item.periods)
    )
    restated = ExpectedObligation(
        modelo=value.modelo,
        periods=(value.period,),
        year=value.year,
        applicable=False,
        reason="stated not owed for the test",
        legal_ref=value.legal_ref,
        grounding="verified",
    )
    expectations = dataclasses.replace(persona.expectations, obligations=(*kept, restated))
    return dataclasses.replace(persona, expectations=expectations), key


def test_a_stated_return_an_obligation_states_not_applicable_is_a_not_owed_row() -> None:
    envelope = _envelope()
    persona, key = _stated_not_owed(_persona(_FONTANERO), envelope)
    rows = {(row.modelo, row.year, row.period): row for row in planned_rows(persona, envelope.horizon, envelope)}
    assert key in rows
    assert rows[key].owed is False
    assert rows[key].has_values
    assert all(row.owed for found, row in rows.items() if found != key)
    untouched = {
        (row.modelo, row.year, row.period): row.owed
        for row in planned_rows(_persona(_FONTANERO), envelope.horizon, envelope)
    }
    assert untouched[key] is True


def test_a_not_applicable_return_without_stated_values_stays_no_row() -> None:
    envelope = _envelope()
    persona, key = _stated_not_owed(_persona(_FONTANERO), envelope)
    modelo, _year, period = key
    without = tuple(
        value
        for value in persona.expectations.values
        if not (value.modelo == modelo and value.period == period and value.year.resolve(envelope) == key[1])
    )
    bare = dataclasses.replace(persona, expectations=dataclasses.replace(persona.expectations, values=without))
    assert key not in {(row.modelo, row.year, row.period) for row in planned_rows(bare, envelope.horizon, envelope)}


def _suppressed(key: tuple[str, int, str], verdict: str) -> CalendarObservation:
    modelo, year, period = key
    return CalendarObservation("persona", modelo, year, period, verdict, "no ingreso")


def _not_owed_plan() -> PlannedRow:
    return dataclasses.replace(_plan(), owed=False)


def test_a_not_owed_row_the_calendar_suppresses_as_not_applicable_is_green() -> None:
    plan = _not_owed_plan()
    key = (plan.modelo, plan.year, plan.period)
    stage, reason = not_owed_stage([_suppressed(key, "not_applicable")], key)
    assert (stage, reason) == (Stage.NOT_OWED, "")
    row = TableRow.from_plan(plan, Stage.PASSED, verify=stage, reason=reason)
    assert row.verdict is Verdict.NOT_OWED
    assert row.verdict in GREEN


def test_a_not_owed_row_the_calendar_shows_a_window_for_fails() -> None:
    plan = _not_owed_plan()
    key = (plan.modelo, plan.year, plan.period)
    window = _suppressed(key, APPLICABLE)
    for observations in ([window], [_suppressed(key, "not_applicable"), window]):
        stage, reason = not_owed_stage(observations, key)
        assert stage is Stage.OWED_SHOWN
        assert APPLICABLE in reason
        assert TableRow.from_plan(plan, Stage.PASSED, verify=stage, reason=reason).verdict is Verdict.FAIL


def test_a_not_owed_row_the_calendar_leaves_undecided_or_omits_fails() -> None:
    plan = _not_owed_plan()
    key = (plan.modelo, plan.year, plan.period)
    other = (plan.modelo, plan.year + 1, plan.period)
    for observations in ([_suppressed(key, "incomplete")], [_suppressed(other, "not_applicable")], []):
        stage, _reason = not_owed_stage(observations, key)
        assert stage is Stage.OWED_SHOWN
        assert TableRow.from_plan(plan, Stage.PASSED, verify=stage).verdict is Verdict.FAIL


def test_a_not_owed_row_whose_values_differ_fails_even_when_the_calendar_suppresses_it() -> None:
    plan = _not_owed_plan()
    assert TableRow.from_plan(plan, Stage.MISMATCH, verify=Stage.NOT_OWED).verdict is Verdict.FAIL
    assert TableRow.from_plan(plan, Stage.UNRESOLVED, verify=Stage.NOT_OWED).verdict is Verdict.FAIL
    unsourced = dataclasses.replace(plan, grounding="unverified")
    assert TableRow.from_plan(unsourced, Stage.PASSED, verify=Stage.NOT_OWED).verdict is Verdict.UNVERIFIED


def test_a_not_owed_row_survives_its_json_line(tmp_path: Path) -> None:
    row = TableRow.from_plan(_not_owed_plan(), Stage.PASSED, verify=Stage.NOT_OWED)
    write_rows(tmp_path / "rows.jsonl", [row])
    assert list(read_rows([tmp_path / "rows.jsonl"])) == [row]
    assert row.to_baseline_json(row.horizon).count('"not-owed"') == 2
