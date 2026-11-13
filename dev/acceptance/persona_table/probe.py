"""The verify probe: what verifying a calculated return does before anything more is stated.

The table states a persona's work-income boxes, prior attestations and operator statements before its first
verify, so a crash that only the unstated state meets cannot show in a row. The probe verifies each owed return
once, straight after a calculation that entered none of them, and requires a typed answer: findings, or a refusal
the application registers. This module classifies one observation and renders the probes; the collector that
drives the application is ``probe_sweep``.
"""

from __future__ import annotations

import json
import re
import traceback
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2

PROBE_OUT_ENV = "PERSONA_PROBE_OUT"
"""The variable the collector reads for the file it appends the probe lines to."""
_MESSAGE_LIMIT = 300
OWNER_LIFECYCLE = "LIFECYCLE"
OWNER_UNKNOWN = "unknown"
_VERIFY = "verify"

_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")
EXECUTOR_LOGGER = "cadrumo.application.operations.supervisor_execution"
"""The logger the operation supervisor names a failed operation's exception type and code frames on."""
_FAILED_RECORD = re.compile(
    r"operation failed definition=\S+ operation=\S+ diagnostic_ref=\S+ "
    r"exception_type=(?P<type>\S+) raising_frame=(?P<raising>\S+) application_frame=(?P<frame>\S+)"
)
_UNSETTLED_CONDITIONS = frozenset({"cancelled", "timed_out", "interrupted"})
_UNOBSERVED = "could not be observed"
_SOURCE_ROOTS = frozenset({"src", "site-packages"})


class Outcome(StrEnum):
    """How one operation answered the probe."""

    TYPED_FINDINGS = "typed-findings"
    TYPED_REFUSAL = "typed-refusal"
    UNTYPED_EXCEPTION = "untyped-exception"
    UNKNOWN_SETTLEMENT = "unknown-settlement"


FAILURES = frozenset({Outcome.UNTYPED_EXCEPTION, Outcome.UNKNOWN_SETTLEMENT})


@dataclass(frozen=True, slots=True)
class Classification:
    """The outcome of one observation, what it names, where it was raised and who owns a failure."""

    outcome: Outcome
    code: str
    """The refusal code, or the exception type, or the type of the typed result."""
    message: str
    raised_in: str | None
    owner: str | None
    """The owner of a failure; none for a typed answer."""


@dataclass(frozen=True, slots=True)
class ProbeLine:
    """One probed return as one JSON line."""

    persona: str
    modelo: str
    year: int
    period: str
    horizon: int
    stage: str
    outcome: Outcome
    code: str
    message: str
    raised_in: str | None
    owner: str | None

    @property
    def failed(self) -> bool:
        """Whether the return answered untyped or unsettled."""
        return self.outcome in FAILURES

    def to_json(self) -> str:
        """The line as compact JSON with stable key order."""
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> ProbeLine:
        """The line a ``to_json`` wrote."""
        data = json.loads(text)
        return cls(
            persona=str(data["persona"]),
            modelo=str(data["modelo"]),
            year=int(data["year"]),
            period=str(data["period"]),
            horizon=int(data["horizon"]),
            stage=str(data["stage"]),
            outcome=Outcome(data["outcome"]),
            code=str(data["code"]),
            message=str(data["message"]),
            raised_in=data["raised_in"],
            owner=data["owner"],
        )


def _owner(stage: str, outcome: Outcome) -> str | None:
    """LIFECYCLE for any failure of verify, which the order assigns finding producers; unknown for another stage."""
    if outcome not in FAILURES:
        return None
    return OWNER_LIFECYCLE if stage == _VERIFY else OWNER_UNKNOWN


def _frame_location(frame: str) -> str | None:
    """The in-tree location of a ``file:line:function`` frame, from its ``cadrumo`` directory on; none for ``-``."""
    if frame in {"", "-"}:
        return None
    return _in_tree(frame.replace("\\", "/").split("/")) or frame


def innermost_cadrumo_frame(error: BaseException) -> str | None:
    """The innermost ``src/cadrumo`` frame of the traceback of ``error``, as ``path:line:function``."""
    found = None
    for frame in traceback.extract_tb(error.__traceback__):
        location = _in_tree(Path(frame.filename).parts)
        if location is not None:
            found = f"{location}:{frame.lineno}:{frame.name}"
    return found


def _in_tree(parts: Sequence[str]) -> str | None:
    """The path from the ``cadrumo`` package directory on, or none for a file outside the package."""
    for start in range(len(parts) - 2, 0, -1):
        if parts[start] == "cadrumo" and parts[start - 1] in _SOURCE_ROOTS:
            return "/".join(parts[start:])
    return None


def _settled(error: BaseException, stage: str, failure: str) -> Classification | None:
    """The classification of a settled operation that did not succeed, or none when the message is another.

    A failure serves a sentence in place of its exception, so the exception type and the frames that raised it
    come from ``failure``, the supervisor's log record of the failed operation.
    """
    text = str(error)
    settled = _SETTLED.match(text)
    if settled is None:
        return None
    condition, code = settled["condition"], settled["code"]
    recorded = _FAILED_RECORD.search(failure)
    message = text[:_MESSAGE_LIMIT]
    if condition == "refused":
        return Classification(Outcome.TYPED_REFUSAL, code, message, None, None)
    outcome = Outcome.UNKNOWN_SETTLEMENT if condition in _UNSETTLED_CONDITIONS else Outcome.UNTYPED_EXCEPTION
    if recorded is None:
        return Classification(outcome, condition, message, None, _owner(stage, outcome))
    frame = _frame_location(recorded["frame"]) or _frame_location(recorded["raising"])
    return Classification(outcome, recorded["type"], message, frame, _owner(stage, outcome))


def _raised(error: BaseException, stage: str) -> Classification:
    """The classification of an exception the operation host did not settle."""
    outcome = Outcome.UNKNOWN_SETTLEMENT if _UNOBSERVED in str(error) else Outcome.UNTYPED_EXCEPTION
    return Classification(
        outcome,
        type(error).__name__,
        f"{type(error).__name__}: {error}"[:_MESSAGE_LIMIT],
        innermost_cadrumo_frame(error),
        _owner(stage, outcome),
    )


def classify(stage: str, observed: object, *, failure: str = "") -> Classification:
    """Classify what an operation of ``stage`` answered: a result it published, or the exception it raised.

    A published verification is typed findings; another published result is a typed refusal the definition records
    as its own result. A settled refusal is typed. A settled failure, a pre-settlement exception of any other type
    (a validation error among them) is untyped, and a settlement that never concluded is unknown.
    ``failure`` is the supervisor's log record of the failed operation, which names the exception.
    """
    if isinstance(observed, ModeloWorkVerifyPublicResultV2):
        text = (
            f"{observed.completeness_status}; {observed.finding_count} findings; "
            f"granted={observed.granted_verificado_completo}"
        )
        return Classification(Outcome.TYPED_FINDINGS, type(observed).__name__, text, None, None)
    if not isinstance(observed, BaseException):
        return Classification(Outcome.TYPED_REFUSAL, type(observed).__name__, type(observed).__name__, None, None)
    return _settled(observed, stage, failure) or _raised(observed, stage)


def read_probes(path: Path) -> list[ProbeLine]:
    """Every probe line in the JSON-lines file at ``path``, ordered by persona, return and horizon."""
    lines = [ProbeLine.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(lines, key=lambda line: (line.persona, line.horizon, line.modelo, line.year, line.period))


def render_markdown(lines: Iterable[ProbeLine]) -> str:
    """The summary of the probes: counts by outcome, then each failure with its owner and where it was raised."""
    probes = list(lines)
    counts = {outcome: sum(line.outcome is outcome for line in probes) for outcome in Outcome}
    summary = ", ".join(f"{count} {outcome.value}" for outcome, count in counts.items())
    out = [f"# Verify probe\n\nProbed {len(probes)} returns: {summary}.\n"]
    failures = [line for line in probes if line.failed]
    if not failures:
        out.append("\nNo failures.\n")
        return "".join(out)
    out.append("\n| Persona | Return | Horizon | Stage | Outcome | Owner | Raised in | Code | Message |\n")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    for line in failures:
        message = line.message.replace("|", "\\|").replace("\n", " ")
        out.append(
            f"| {line.persona} | M{line.modelo} {line.year} {line.period} | {line.horizon} | {line.stage} | "
            f"{line.outcome.value} | {line.owner} | {line.raised_in or '-'} | {line.code} | {message} |\n"
        )
    return "".join(out)
