"""Outcome classes, exit codes and the verdict rules of the live agent lane.

A lane run ends in exactly one class. ``unavailable`` means a prerequisite was
missing (a model credential, a usable credential store, a current package) and
is never a pass. A product finding outranks an agent failure: when the product
disagrees with itself the run says nothing about the agent.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

_FROZEN = ConfigDict(frozen=True, strict=True, extra="forbid")


class Outcome(StrEnum):
    """The one class a lane run reports."""

    PASSED = "passed"
    AGENT_FAILURE = "agent_failure"
    PRODUCT_FINDING = "product_finding"
    UNAVAILABLE = "unavailable"
    HARNESS_ERROR = "harness_error"


EXIT_CODES: Final[dict[Outcome, int]] = {
    Outcome.PASSED: 0,
    Outcome.AGENT_FAILURE: 1,
    Outcome.PRODUCT_FINDING: 2,
    Outcome.UNAVAILABLE: 3,
    Outcome.HARNESS_ERROR: 4,
}
"""Distinct exit status per class, so a scheduler can tell them apart."""


class FailureOwner(StrEnum):
    """Who a hard-invariant failure is charged to."""

    AGENT = "agent"
    PRODUCT = "product"


class UnavailableError(Exception):
    """A prerequisite of the lane is missing; the run reports unavailable with this reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        """Keep a stable reason token and a human detail that carries no secret."""
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class InvariantFailure(BaseModel):
    """One broken hard invariant and who it is charged to."""

    model_config = _FROZEN

    invariant: str = Field(min_length=1)
    owner: FailureOwner
    detail: str = Field(min_length=1)


class RunVerdict(BaseModel):
    """The verdict of one run of one scenario."""

    model_config = _FROZEN

    run_index: int = Field(ge=0)
    invariant_failures: tuple[InvariantFailure, ...] = ()
    end_state_reached: bool = False
    oracle_disagreements: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def invariants_held(self) -> bool:
        """True when no hard invariant failed."""
        return not self.invariant_failures

    @property
    def product_finding(self) -> bool:
        """True when the product disagreed with itself or broke an invariant on its own side."""
        return bool(self.oracle_disagreements) or any(
            failure.owner is FailureOwner.PRODUCT for failure in self.invariant_failures
        )


def required_end_states(runs: int) -> int:
    """Return how many runs must reach the end state: two of the default three."""
    if runs < 1:
        raise ValueError("a lane run needs at least one run")
    return runs - runs // 3


class LaneVerdict(BaseModel):
    """The verdict over every run of one lane invocation."""

    model_config = _FROZEN

    outcome: Outcome
    runs: int = Field(ge=0)
    runs_reaching_end_state: int = Field(ge=0)
    required: int = Field(ge=0)
    reasons: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        """The process exit status for this outcome."""
        return EXIT_CODES[self.outcome]


def unavailable_verdict(error: UnavailableError, *, runs: int) -> LaneVerdict:
    """Report a missing prerequisite; never a pass."""
    return LaneVerdict(
        outcome=Outcome.UNAVAILABLE,
        runs=0,
        runs_reaching_end_state=0,
        required=required_end_states(runs),
        reasons=(str(error),),
    )


def lane_verdict(verdicts: tuple[RunVerdict, ...], *, runs: int) -> LaneVerdict:
    """Apply the pass rule: every run holds every invariant and enough runs reach the end state.

    A product finding in any run fails the lane as a product finding whatever
    the agent did. An agent's broken invariant, or too few end states, is an
    agent failure. A lane with fewer verdicts than requested runs cannot pass.
    """
    required = required_end_states(runs)
    reached = sum(1 for verdict in verdicts if verdict.end_state_reached and verdict.invariants_held)
    reasons: list[str] = []
    for verdict in verdicts:
        reasons.extend(f"run {verdict.run_index}: oracle: {item}" for item in verdict.oracle_disagreements)
        reasons.extend(
            f"run {verdict.run_index}: {failure.owner}: {failure.invariant}: {failure.detail}"
            for failure in verdict.invariant_failures
        )
    if any(verdict.product_finding for verdict in verdicts):
        outcome = Outcome.PRODUCT_FINDING
    elif any(not verdict.invariants_held for verdict in verdicts):
        outcome = Outcome.AGENT_FAILURE
    elif len(verdicts) < runs:
        outcome = Outcome.HARNESS_ERROR
        reasons.append(f"only {len(verdicts)} of {runs} runs produced a verdict")
    elif reached < required:
        outcome = Outcome.AGENT_FAILURE
        reasons.append(f"{reached} of {runs} runs reached the end state; {required} required")
    else:
        outcome = Outcome.PASSED
    return LaneVerdict(
        outcome=outcome, runs=len(verdicts), runs_reaching_end_state=reached, required=required, reasons=tuple(reasons)
    )
