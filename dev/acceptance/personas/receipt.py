"""The typed receipt one catalogue persona's installed-CLI journey writes.

A receipt holds what each materialisation step did, every step the CLI offers
no route for (a ``cli_gap``, which is a product finding rather than a journey
failure), and one row per asserted obligation, deadline and casilla with its
expected and observed value and a status.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

type ValueKind = Literal["casilla", "not_sourced", "refusal"]
type ObligationCheckKind = Literal["verdict", "calendar", "calendar_row", "calendar_advice", "deadline"]


class CheckStatus(StrEnum):
    """The verdict on one asserted expectation."""

    PASSED = "PASS"
    FAIL = "FAIL"
    REFUSAL_OK = "REFUSAL-OK"
    """The application refused the period with the code the expectation states."""
    REFUSAL_WRONG = "REFUSAL-WRONG"
    """The expectation states a refusal and the application calculated, or refused with another code."""
    GAP = "GAP"
    """The CLI offers no route to observe the figure, so the expectation could not be asserted."""


class StepOutcome(StrEnum):
    """What one materialisation step's CLI command did."""

    OK = "ok"
    REFUSED = "refused"
    GAP = "gap"
    """No CLI command performs the step; a :class:`CliGap` names it."""
    SKIPPED = "skipped"
    """An earlier refusal left the step without the input it needs."""


@dataclass(frozen=True, slots=True)
class CliGap:
    """A materialisation step the installed CLI cannot perform, and what is missing."""

    persona: str
    step: str
    missing: str


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One materialisation step: its command, its outcome and, when refused, its typed cause."""

    step: str
    command: str
    outcome: StepOutcome
    error_code: str | None = None
    refusal: str | None = None


@dataclass(frozen=True, slots=True)
class ValueCheck:
    """One asserted casilla, not-sourced casilla or refusal of a period's calculation."""

    year: int
    modelo: str
    period: str
    casilla: str | None
    kind: ValueKind
    expected: str
    actual: str | None
    status: CheckStatus
    legal_ref: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObligationCheck:
    """One asserted applicability verdict, calendar row, calendar advice or deadline."""

    year: int
    modelo: str
    period: str | None
    check: ObligationCheckKind
    expected: str
    actual: str | None
    status: CheckStatus
    legal_ref: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PersonaReceipt:
    """Everything one persona's journey observed."""

    persona: str
    floor: int
    horizon: int
    as_of: str
    authority_generation: str
    executable: str
    steps: tuple[StepRecord, ...] = ()
    cli_gaps: tuple[CliGap, ...] = ()
    obligations: tuple[ObligationCheck, ...] = ()
    values: tuple[ValueCheck, ...] = ()
    commands: int = 0
    notes: tuple[str, ...] = field(default=())

    def summary(self) -> dict[str, int]:
        """Count the checks by status and the steps by outcome."""
        checks = Counter(item.status.value for item in (*self.obligations, *self.values))
        steps = Counter(f"step_{item.outcome.value}" for item in self.steps)
        return {**dict(sorted(checks.items())), **dict(sorted(steps.items())), "cli_gaps": len(self.cli_gaps)}

    def passed(self) -> bool:
        """Whether no asserted expectation failed; a gap is a finding, not a failure."""
        failing = {CheckStatus.FAIL, CheckStatus.REFUSAL_WRONG}
        return not any(item.status in failing for item in (*self.obligations, *self.values))

    def to_dict(self) -> dict[str, object]:
        """A JSON-safe representation, with the status summary first."""
        return {
            "persona": self.persona,
            "summary": self.summary(),
            "passed": self.passed(),
            "envelope": {"floor": self.floor, "horizon": self.horizon},
            "as_of": self.as_of,
            "authority_generation": self.authority_generation,
            "executable": self.executable,
            "commands": self.commands,
            "notes": list(self.notes),
            "cli_gaps": [_gap_dict(item) for item in self.cli_gaps],
            "steps": [_step_dict(item) for item in self.steps],
            "obligations": [_obligation_dict(item) for item in self.obligations],
            "values": [_value_dict(item) for item in self.values],
        }


def _gap_dict(gap: CliGap) -> dict[str, object]:
    return {"persona": gap.persona, "step": gap.step, "missing": gap.missing}


def _step_dict(step: StepRecord) -> dict[str, object]:
    return {
        "step": step.step,
        "command": step.command,
        "outcome": step.outcome.value,
        "error_code": step.error_code,
        "refusal": step.refusal,
    }


def _obligation_dict(check: ObligationCheck) -> dict[str, object]:
    return {
        "year": check.year,
        "modelo": check.modelo,
        "period": check.period,
        "check": check.check,
        "expected": check.expected,
        "actual": check.actual,
        "status": check.status.value,
        "legal_ref": list(check.legal_ref),
    }


def _value_dict(check: ValueCheck) -> dict[str, object]:
    return {
        "year": check.year,
        "modelo": check.modelo,
        "period": check.period,
        "casilla": check.casilla,
        "kind": check.kind,
        "expected": check.expected,
        "actual": check.actual,
        "status": check.status.value,
        "legal_ref": list(check.legal_ref),
    }
