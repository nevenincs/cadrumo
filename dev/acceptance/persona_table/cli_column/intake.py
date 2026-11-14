"""Map what the installed CLI printed to the frontend intake vocabulary, and write the intake lines.

The harness decides nothing about tax: it reads the envelope the backend printed, turns its status, its served error
code and the typed values of the result into a stage word, and writes them. An effect that is not settled
(``UNKNOWN``, ``SETTLING``, a timed-out or interrupted operation, a command that did not answer) is never a ``pass``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

from ..frontend import NOT_REACHED, parse_result
from ..rows import canonical_figures
from .hygiene import Redactor

SURFACE = "cli"
REASON_LIMIT = 900
STILL_RUNNING_CODE = "LOCKED_CLI_OPERATION_STILL_RUNNING"
"""The code of an admitted operation the command stopped waiting for; its effect is not known."""
NO_ENVELOPE_CODE = "acceptance.cli_column.no_envelope"
NON_JSON_CODE = "acceptance.installed_cli.non_json_failure"
"""The code the shared installed-CLI adapter gives a command that printed no envelope."""
TIMEOUT_CODE = "acceptance.cli_column.timeout"
TIMEOUT_STATUS = "timeout"
"""The status the runner gives a command that did not answer in time; the command may still have committed."""
_SUCCESS = frozenset({"success", "warning"})
_UNCERTAIN_CONDITIONS = frozenset({"timed_out", "interrupted"})
_UNCERTAIN_EFFECTS = frozenset({"unknown", "settling"})
_PASSED = "pass"
_WORDS_WITHOUT_CODE = frozenset({_PASSED, NOT_REACHED})


class Kind(StrEnum):
    """How one command ended."""

    OK = "ok"
    REFUSED = "refused"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one command printed, reduced to what the stage mapping reads."""

    kind: Kind
    code: str | None = None
    reason: str = ""
    result: Mapping[str, object] = field(default_factory=dict)
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class StageResult:
    """One stage of a return in the intake vocabulary, with the served code and words that explain a failure."""

    word: str
    code: str | None = None
    reason: str = ""
    uncertain: bool = False
    """True when the effect of the stage's command is not settled: the chain must not go on."""


UNREACHED = StageResult(NOT_REACHED)


@dataclass(frozen=True, slots=True)
class RowResult:
    """Every stage of one return and the figures its calculation printed."""

    calculate: StageResult
    verify: StageResult = UNREACHED
    export: StageResult = UNREACHED
    file: StageResult | None = None
    figures: tuple[tuple[str, str], ...] = ()
    workaround: str | None = None
    """The diagnostic substitute that produced the stage values in place of what a person runs; never a match."""

    def stages(self) -> tuple[StageResult, ...]:
        """The stages that ran, in lifecycle order."""
        return tuple(stage for stage in (self.calculate, self.verify, self.export, self.file) if stage is not None)

    @property
    def uncertain(self) -> bool:
        """Whether a stage left its effect unsettled."""
        return any(stage.uncertain for stage in self.stages())

    @property
    def refusal_code(self) -> str | None:
        """The served code of the first stage that did not pass, if it served one."""
        codes = (stage.code for stage in self.stages() if stage.word not in _WORDS_WITHOUT_CODE)
        return next((code for code in codes if code is not None), None)

    @property
    def reason(self) -> str:
        """The reasons of every stage, in lifecycle order."""
        return " | ".join(stage.reason for stage in self.stages() if stage.reason)[:REASON_LIMIT]


def classify(document: object) -> Outcome:
    """Reduce the envelope a command printed (or nothing) to an :class:`Outcome`."""
    if not isinstance(document, Mapping):
        return Outcome(Kind.ERROR, NO_ENVELOPE_CODE, "the command printed no JSON envelope")
    status = document.get("status")
    if status in _SUCCESS:
        result = document.get("result")
        return Outcome(Kind.OK, result=result if isinstance(result, Mapping) else {})
    if status == TIMEOUT_STATUS:
        return Outcome(Kind.UNKNOWN, TIMEOUT_CODE, "UNKNOWN effect: the command did not answer in time")
    error = document.get("error")
    if status == "error" and isinstance(error, Mapping):
        return _from_error(error)
    return Outcome(Kind.ERROR, None, f"envelope status {status!r} is neither success, warning nor error")


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _uncertain(code: str | None, context: Mapping[str, object]) -> bool:
    """Whether the error leaves the effect of the command unsettled, as its served facts say."""
    condition = str(context.get("terminal_condition", "")).lower()
    effect = str(context.get("effect", "")).lower()
    if code == STILL_RUNNING_CODE or condition in _UNCERTAIN_CONDITIONS:
        return True
    return effect in _UNCERTAIN_EFFECTS and condition != "refused"


def _from_error(error: Mapping[str, object]) -> Outcome:
    code = _text(error.get("code"))
    raw_context = error.get("context")
    context = raw_context if isinstance(raw_context, Mapping) else {}
    operation_id = _text(context.get("operation_id"))
    if code == NON_JSON_CODE:
        return Outcome(Kind.ERROR, code, "the command printed no JSON envelope")
    if _uncertain(code, context):
        reason = f"UNKNOWN effect, operation {operation_id or '-'}"
        return Outcome(Kind.UNKNOWN, code, reason, operation_id=operation_id)
    served = f"{code}: {_text(error.get('message')) or 'no message'}"
    internal = str(error.get("category", "")).lower() == "internal"
    return Outcome(Kind.ERROR if internal else Kind.REFUSED, code, served[:REASON_LIMIT], operation_id=operation_id)


def failed(outcome: Outcome, label: str) -> StageResult:
    """The stage a command that did not succeed gives: ``refused`` for a served refusal, else ``error``."""
    if outcome.kind is Kind.OK:
        raise ValueError("a command that succeeded has no failed stage")
    word = "refused" if outcome.kind is Kind.REFUSED else "error"
    return StageResult(word, outcome.code, f"{label}: {outcome.reason}", uncertain=outcome.kind is Kind.UNKNOWN)


def _typed(value: object) -> object:
    """A printed amount as the number it is, so it is canonical text like the table's figures."""
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return value
    return value


def figures_of(result: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Every non-zero casilla value the calculation printed, as canonical text sorted by casilla id."""
    raw = result.get("casilla_values")
    if not isinstance(raw, Mapping):
        return ()
    return canonical_figures({str(casilla): _typed(value) for casilla, value in raw.items()})


def calculate_stage(outcome: Outcome) -> tuple[StageResult, tuple[tuple[str, str], ...]]:
    """The calculate stage and its figures: ``pass`` when the command succeeded, else what it served."""
    if outcome.kind is Kind.OK:
        return StageResult(_PASSED), figures_of(outcome.result)
    return failed(outcome, "calculate"), ()


def blocking_findings(result: Mapping[str, object]) -> str:
    """The kind and casilla of each blocking finding the verification printed."""
    findings = result.get("findings")
    if not isinstance(findings, list):
        return ""
    return ", ".join(
        f"{item.get('kind')} {item.get('casilla_id') or item.get('expectation_id') or '-'}"
        for item in findings
        if isinstance(item, Mapping) and str(item.get("severity")) == "blocking"
    )


def verify_stage(outcome: Outcome) -> StageResult:
    """``pass`` when verificado completo was granted, ``incomplete`` when it was not, else what the command served."""
    if outcome.kind is not Kind.OK:
        return failed(outcome, "verify")
    result = outcome.result
    if result.get("granted_verificado_completo") is True:
        return StageResult(_PASSED)
    findings = result.get("findings")
    count = len(findings) if isinstance(findings, list) else 0
    status = result.get("completeness_status")
    reason = f"verify: {status}; {count} findings; blocking: {blocking_findings(result) or 'none'}"
    return StageResult("incomplete", reason=reason)


def export_stage(outcome: Outcome, check: str | None) -> StageResult:
    """The export stage once the written file was checked.

    ``check`` is the reason the table's own export checks give for the written file: empty when it is clean, ``None``
    when those checks were not available, which leaves the stage an ``error`` rather than a ``pass``.
    """
    if outcome.kind is not Kind.OK:
        return failed(outcome, "export")
    if check is None:
        return StageResult("error", reason="export: written, but the table's export checks were not available")
    if check:
        return StageResult("refused", reason=check)
    return StageResult(_PASSED)


def file_stage(outcome: Outcome) -> StageResult:
    """The local filing stage; a success is stated as ``filed locally``."""
    if outcome.kind is not Kind.OK:
        return failed(outcome, "file")
    return StageResult(_PASSED, reason="filed locally")


def persona_line(*, tree: str, persona: str, loads: bool, reason: str, log: str) -> dict[str, object]:
    """The persona-level line: whether the profile loaded, and how the world was seeded."""
    return {
        "surface": SURFACE,
        "tree": tree,
        "persona": persona,
        "modelo": None,
        "year": None,
        "period": None,
        "loads": loads,
        "reason": reason[:REASON_LIMIT],
        "log": log,
    }


@dataclass(frozen=True, slots=True)
class ReturnScope:
    """Which return of which persona a line reports, on which tree."""

    tree: str
    persona: str
    modelo: str
    year: int
    period: str


def return_line(scope: ReturnScope, result: RowResult, log: str) -> dict[str, object]:
    """The line of one return: its three stages, the optional file stage, the figures and the reasons."""
    line: dict[str, object] = {
        "surface": SURFACE,
        "tree": scope.tree,
        "persona": scope.persona,
        "modelo": scope.modelo,
        "year": scope.year,
        "period": scope.period,
        "loads": True,
        "calculate": result.calculate.word,
        "verify": result.verify.word,
        "export": result.export.word,
        "refusal_code": result.refusal_code,
        "figures": dict(result.figures),
        "reason": result.reason,
        "log": log,
    }
    if result.file is not None:
        line["file"] = result.file.word
    if result.workaround is not None:
        line["workaround"] = result.workaround
    return line


class LineWriter:
    """Append intake lines to a ``cli-<tree>.jsonl`` file, redacted and checked against the intake schema."""

    def __init__(self, path: Path, redactor: Redactor) -> None:
        """Write to ``path``; every line passes ``redactor`` and the intake reader before it is appended."""
        self.path = path
        self._redactor = redactor

    def write(self, line: Mapping[str, object]) -> str:
        """Append ``line`` and return the text written; a line the intake would refuse is not written."""
        record = self._redactor.value(line)
        text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        self._redactor.guard(text, "a result line")
        parse_result(text)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")
        return text
