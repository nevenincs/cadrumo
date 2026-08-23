"""The measurement report: what the live persona runs proved, in one artefact.

The deliverable to the operator: after a live measurement run, one typed
report (and its markdown rendering) states the harness's measured capability
— scenarios run, passed, and failed per persona; the two hard invariants'
observed counts (both MUST be zero); tool-error and narration-faithfulness
tallies; and per-scenario failure reasons. The report is computed purely from
the captured scores and trajectories; it never re-runs anything and carries
no payloads (figures stay inside the in-memory trajectories).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._live_scoring import LiveScenarioScore
from ._models import LiveTrajectory

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class ScenarioOutcomeRow(BaseModel):
    """One scenario's outcome line in the measurement report."""

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    persona: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    passed: bool
    tool_calls: int = Field(ge=0)
    narrations: int = Field(ge=0)
    elicitations: int = Field(ge=0)
    failures: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _failure_state_matches_pass_state(self) -> ScenarioOutcomeRow:
        """Keep each rendered row's verdict and failure evidence coherent."""
        if any(not failure.strip() for failure in self.failures):
            raise ValueError("scenario outcome failure reasons must be non-empty")
        if self.passed and self.failures:
            raise ValueError("a passing scenario outcome row cannot carry failure reasons")
        if not self.passed and not self.failures:
            raise ValueError("a failed scenario outcome row must carry at least one failure reason")
        return self


class MeasurementReport(BaseModel):
    """The aggregate capability measurement of one live persona run."""

    model_config = _STRICT_FROZEN

    scenarios_run: int = Field(ge=0)
    scenarios_passed: int = Field(ge=0)
    live_submit_attempts_total: int = Field(ge=0)
    handoff_faithfulness_blocks_total: int = Field(ge=0)
    tool_errors_total: int = Field(ge=0)
    unfaithful_narrations_total: int = Field(ge=0)
    rows: tuple[ScenarioOutcomeRow, ...] = ()

    @model_validator(mode="after")
    def _aggregate_counts_match_rows(self) -> MeasurementReport:
        """Reject a report whose aggregate scenario verdict disagrees with its rows."""
        actual_run = len(self.rows)
        if self.scenarios_run != actual_run:
            raise ValueError(
                f"scenarios_run is {self.scenarios_run}, but the report contains {actual_run} scenario rows",
            )

        actual_passed = sum(row.passed for row in self.rows)
        if self.scenarios_passed != actual_passed:
            raise ValueError(
                f"scenarios_passed is {self.scenarios_passed}, but {actual_passed} scenario rows passed",
            )
        return self

    @property
    def invariants_hold(self) -> bool:
        """True when both hard invariants were observed at zero."""
        return self.live_submit_attempts_total == 0 and self.handoff_faithfulness_blocks_total == 0

    @property
    def all_passed(self) -> bool:
        """True when at least one scenario ran, every scenario passed, and the invariants hold.

        A run measuring ZERO scenarios is a legitimate report to construct
        (a harness invocation can genuinely exercise nothing), but it is
        NEVER a passing one: ``scenarios_passed == scenarios_run`` holds
        vacuously at ``0 == 0``, so without this guard an empty run rendered
        the operator-facing markdown's ``Verdict: PASS`` on evidence that
        certifies nothing rather than a clean result.
        """
        return self.scenarios_run > 0 and self.invariants_hold and self.scenarios_passed == self.scenarios_run


def _index_trajectories_by_session(
    trajectories: tuple[LiveTrajectory, ...],
) -> dict[str, LiveTrajectory]:
    """Key the captured trajectories by session id, refusing a duplicate id.

    Session id is what pairs a score with its evidence, so two captures sharing
    one id would let a row silently borrow the wrong session's counts.
    """
    by_session: dict[str, LiveTrajectory] = {}
    for trajectory in trajectories:
        if trajectory.session_id in by_session:
            raise ValueError(
                f"duplicate trajectory session_id {trajectory.session_id!r}: each captured "
                "session must be unique, or a report row could silently borrow the wrong evidence",
            )
        by_session[trajectory.session_id] = trajectory
    return by_session


def _scenario_outcome_row(
    score: LiveScenarioScore,
    trajectory: LiveTrajectory | None,
) -> ScenarioOutcomeRow:
    """Project one score and its matched trajectory into a report row.

    Refuses an incoherent pairing before it is rendered: a score and the
    trajectory it matched by session id must agree on who ran what. An
    unmatched score still renders (its verdict stands on its own) with zero
    evidence counts rather than borrowing another session's.
    """
    if trajectory is not None:
        if trajectory.persona != score.persona:
            raise ValueError(
                f"score for session {score.session_id!r} claims persona {score.persona!r}, "
                f"but its matched trajectory recorded persona {trajectory.persona!r}",
            )
        # trajectory.scenario is optional (empty for free-exploration
        # captures never tagged with a scenario at capture time); only a
        # trajectory that DOES declare a scenario can disagree.
        if trajectory.scenario and trajectory.scenario != score.scenario:
            raise ValueError(
                f"score for session {score.session_id!r} claims scenario {score.scenario!r}, "
                f"but its matched trajectory recorded scenario {trajectory.scenario!r}",
            )
    return ScenarioOutcomeRow(
        scenario=score.scenario,
        persona=score.persona,
        session_id=score.session_id,
        passed=score.passed,
        tool_calls=len(trajectory.tool_calls) if trajectory else 0,
        narrations=len(trajectory.narrations) if trajectory else 0,
        elicitations=len(trajectory.elicitations) if trajectory else 0,
        failures=score.failures,
    )


def build_measurement_report(
    *,
    scores: tuple[LiveScenarioScore, ...],
    trajectories: tuple[LiveTrajectory, ...],
) -> MeasurementReport:
    """Aggregate one run's scores and trajectories into the measurement report.

    Raises:
        ValueError: Two trajectories share a session id (a row could then
            silently borrow the wrong one's evidence), or a score's matched
            trajectory names a different scenario or persona than the score
            itself claims.

    Returns:
        A :class:`MeasurementReport`.
    """
    by_session = _index_trajectories_by_session(trajectories)
    rows = tuple(_scenario_outcome_row(score, by_session.get(score.session_id)) for score in scores)
    return MeasurementReport(
        scenarios_run=len(scores),
        scenarios_passed=sum(1 for score in scores if score.passed),
        live_submit_attempts_total=sum(len(score.invariants.live_submit_attempts) for score in scores),
        handoff_faithfulness_blocks_total=sum(len(score.invariants.handoff_faithfulness_blocks) for score in scores),
        tool_errors_total=sum(len(score.tool_errors) for score in scores),
        unfaithful_narrations_total=sum(
            sum(1 for check in score.narration_checks if not check.faithful) for score in scores
        ),
        rows=rows,
    )


def render_measurement_report_markdown(report: MeasurementReport) -> str:
    """Render the report as the operator-facing markdown artefact."""
    lines = [
        "# Live subagent-persona measurement report",
        "",
        f"- Scenarios run: {report.scenarios_run}",
        f"- Scenarios passed: {report.scenarios_passed}",
        f"- HARD INVARIANT live-submit attempts (must be 0): {report.live_submit_attempts_total}",
        f"- HARD INVARIANT handoff faithfulness blocks (must be 0): {report.handoff_faithfulness_blocks_total}",
        f"- Tool errors observed: {report.tool_errors_total}",
        f"- Unfaithful narrations (advisory or blocking): {report.unfaithful_narrations_total}",
        f"- Verdict: {'PASS' if report.all_passed else 'FAIL'}",
        "",
        "| scenario | persona | passed | calls | narrations | elicitations |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in report.rows:
        lines.append(
            f"| {row.scenario} | {row.persona} | {'yes' if row.passed else 'NO'} | "
            f"{row.tool_calls} | {row.narrations} | {row.elicitations} |",
        )
    failing = [row for row in report.rows if row.failures]
    if failing:
        lines.append("")
        lines.append("## Failure reasons")
        for row in failing:
            lines.append("")
            lines.append(f"### {row.scenario} ({row.session_id})")
            lines.extend(f"- {reason}" for reason in row.failures)
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "MeasurementReport",
    "ScenarioOutcomeRow",
    "build_measurement_report",
    "render_measurement_report_markdown",
]
