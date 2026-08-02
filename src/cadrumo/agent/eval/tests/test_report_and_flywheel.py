"""Real-behavior coverage for the measurement report and the data-flywheel.

Both modules are pure over the live-harness models: the report aggregates a
run's scores and trajectories into one typed artefact and renders its markdown;
the flywheel content-addresses a failure and promotes it into a golden
regression scenario. Every fixture here is a real ``LiveScenarioScore`` /
``LiveTrajectory`` built from the shipped models and a real ``GoldenScenario``
loaded from a shipped scenario TOML - no doubles of the code under test
(``no-tautological-calculation-tests``, ``aeat-quality-gates``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from .._flywheel import failure_signature, promote_failure, write_promoted_scenario
from .._live_scoring import LiveInvariantVerdict, LiveScenarioScore
from .._models import LiveToolCallRecord, LiveTrajectory
from .._report import (
    MeasurementReport,
    ScenarioOutcomeRow,
    build_measurement_report,
    render_measurement_report_markdown,
)
from .._runner import load_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def _trajectory(session_id: str, *, command_keys: tuple[str, ...]) -> LiveTrajectory:
    return LiveTrajectory(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id=session_id,
        tool_calls=tuple(LiveToolCallRecord(tool_name=key or "search", command_key=key) for key in command_keys),
    )


def _passing_score(session_id: str) -> LiveScenarioScore:
    return LiveScenarioScore(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id=session_id,
        keys_resolve=True,
        lifecycle_ordered=True,
        expected_covered=True,
        invariants=LiveInvariantVerdict(scenario="cierre-trimestre"),
    )


def _failing_score(session_id: str) -> LiveScenarioScore:
    # A live-submit attempt trips a hard invariant; the dimension miss records a
    # human-readable failure reason. ``passed`` is derived and must be False.
    return LiveScenarioScore(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id=session_id,
        keys_resolve=True,
        lifecycle_ordered=False,
        expected_covered=True,
        tool_errors=("execute: modelo.work.file returned isError",),
        invariants=LiveInvariantVerdict(
            scenario="cierre-trimestre",
            live_submit_attempts=("modelo.work.submit",),
        ),
        failures=("lifecycle out of order: file before verify",),
    )


def test_build_measurement_report_aggregates_scores_and_trajectories() -> None:
    passing = _passing_score("s-pass")
    failing = _failing_score("s-fail")
    trajectories = (
        _trajectory("s-pass", command_keys=("", "modelo.work.calculate")),
        _trajectory("s-fail", command_keys=("modelo.work.verify", "modelo.work.file")),
    )

    report = build_measurement_report(scores=(passing, failing), trajectories=trajectories)

    assert report.scenarios_run == 2
    assert report.scenarios_passed == 1
    assert report.live_submit_attempts_total == 1
    assert report.handoff_faithfulness_blocks_total == 0
    assert report.tool_errors_total == 1
    assert report.invariants_hold is False
    assert report.all_passed is False
    assert len(report.rows) == 2
    fail_row = next(row for row in report.rows if row.session_id == "s-fail")
    assert fail_row.passed is False
    assert fail_row.tool_calls == 2
    assert fail_row.failures == ("lifecycle out of order: file before verify",)


def test_build_measurement_report_all_passed_when_clean() -> None:
    scores = (_passing_score("s1"), _passing_score("s2"))
    trajectories = (_trajectory("s1", command_keys=()), _trajectory("s2", command_keys=()))

    report = build_measurement_report(scores=scores, trajectories=trajectories)

    assert report.scenarios_run == report.scenarios_passed == 2
    assert report.invariants_hold is True
    assert report.all_passed is True


def test_measurement_report_refuses_aggregate_counts_that_conflict_with_rows() -> None:
    failed_row = ScenarioOutcomeRow(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id="s-fail",
        passed=False,
        tool_calls=0,
        narrations=0,
        elicitations=0,
        failures=("lifecycle out of order: file before verify",),
    )

    with pytest.raises(ValidationError, match="scenarios_run"):
        MeasurementReport(
            scenarios_run=0,
            scenarios_passed=0,
            live_submit_attempts_total=0,
            handoff_faithfulness_blocks_total=0,
            tool_errors_total=0,
            unfaithful_narrations_total=0,
            rows=(failed_row,),
        )
    with pytest.raises(ValidationError, match="scenarios_passed"):
        MeasurementReport(
            scenarios_run=1,
            scenarios_passed=1,
            live_submit_attempts_total=0,
            handoff_faithfulness_blocks_total=0,
            tool_errors_total=0,
            unfaithful_narrations_total=0,
            rows=(failed_row,),
        )


def test_scenario_outcome_row_refuses_failure_state_that_conflicts_with_pass_state() -> None:
    row_fields = {
        "scenario": "cierre-trimestre",
        "persona": "cadrumo-modelo-preparer",
        "session_id": "s-state",
        "tool_calls": 0,
        "narrations": 0,
        "elicitations": 0,
    }

    with pytest.raises(ValidationError, match="passing scenario outcome row"):
        ScenarioOutcomeRow(
            **row_fields,
            passed=True,
            failures=("a passing scenario cannot have this failure",),
        )
    with pytest.raises(ValidationError, match="failed scenario outcome row"):
        ScenarioOutcomeRow(**row_fields, passed=False)


def test_measurement_report_accepts_consistent_direct_construction() -> None:
    passing_row = ScenarioOutcomeRow(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id="s-pass",
        passed=True,
        tool_calls=2,
        narrations=0,
        elicitations=0,
    )
    failed_row = ScenarioOutcomeRow(
        scenario="cierre-trimestre",
        persona="cadrumo-modelo-preparer",
        session_id="s-fail",
        passed=False,
        tool_calls=2,
        narrations=0,
        elicitations=0,
        failures=("lifecycle out of order: file before verify",),
    )

    report = MeasurementReport(
        scenarios_run=2,
        scenarios_passed=1,
        live_submit_attempts_total=1,
        handoff_faithfulness_blocks_total=0,
        tool_errors_total=1,
        unfaithful_narrations_total=0,
        rows=(passing_row, failed_row),
    )

    assert report.invariants_hold is False
    assert report.all_passed is False


def test_render_measurement_report_markdown_surfaces_verdict_and_failures() -> None:
    report = build_measurement_report(
        scores=(_passing_score("s-pass"), _failing_score("s-fail")),
        trajectories=(_trajectory("s-pass", command_keys=()), _trajectory("s-fail", command_keys=())),
    )

    markdown = render_measurement_report_markdown(report)

    assert "# Live subagent-persona measurement report" in markdown
    assert "Verdict: FAIL" in markdown
    assert "HARD INVARIANT live-submit attempts (must be 0): 1" in markdown
    assert "## Failure reasons" in markdown
    assert "lifecycle out of order: file before verify" in markdown


def test_failure_signature_is_stable_and_shape_sensitive() -> None:
    first = failure_signature(_failing_score("s-a"))
    # Signature is content-addressed on the failure SHAPE (scenario + dimensions
    # + invariants), never the clock-free session id, so two sessions with the
    # same failure collide by construction.
    assert first == failure_signature(_failing_score("s-b"))
    assert first != failure_signature(_passing_score("s-a"))


def test_promote_failure_refuses_a_passing_score() -> None:
    scenario = load_scenario(_SCENARIOS_DIR / "cierre_trimestre.toml")
    with pytest.raises(ValueError, match="nothing to promote"):
        promote_failure(
            score=_passing_score("s-pass"),
            trajectory=_trajectory("s-pass", command_keys=()),
            scenario=scenario,
        )


def test_write_promoted_scenario_is_idempotent(tmp_path: Path) -> None:
    scenario = load_scenario(_SCENARIOS_DIR / "cierre_trimestre.toml")
    score = _failing_score("s-fail")
    trajectory = _trajectory("s-fail", command_keys=("modelo.work.verify", "modelo.work.file"))

    first = write_promoted_scenario(score=score, trajectory=trajectory, scenario=scenario, scenarios_dir=tmp_path)
    second = write_promoted_scenario(score=score, trajectory=trajectory, scenario=scenario, scenarios_dir=tmp_path)

    assert first == second
    assert first.parent == tmp_path
    signature = failure_signature(score)
    text = first.read_text(encoding="utf-8")
    assert signature in text
    assert scenario.name in text
    assert len(list(tmp_path.glob("*.toml"))) == 1
