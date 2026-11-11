"""Drive one catalogue persona through the installed ``aeat`` CLI, then assess its hand-grounded expectations.

The journey replays the steps the in-process materialiser takes, each as the
CLI command an operator would type, against one fresh isolated store. A
command that refuses is recorded with its error code and the journey goes on
with what does not depend on it; a fact no command takes is a ``cli_gap``. A
runtime that stops answering ends the journey: no later command could be
trusted. The expectations are only compared, never adjusted.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.tests.personas import (
    Persona,
    YearEnvelope,
)
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError, typed_refusal

from . import commands
from .receipt import CliGap, StepOutcome, StepRecord

ACTOR = "operator:persona"
"""The actor every journey mutation is recorded by."""

_BLOCKING_CODES = frozenset({"REFUSED_LOCAL_RUNTIME", "acceptance.installed_cli.non_json_failure"})
MESSAGE_LIMIT = 400


class JourneyAbortedError(RuntimeError):
    """The runtime stopped answering, so no later command's outcome could be trusted."""


@dataclass(frozen=True, slots=True)
class Reply:
    """What one command reported: its result payload, or the refusal it settled with."""

    result: Mapping[str, Any]
    refusal: str | None = None

    @property
    def ok(self) -> bool:
        """Whether the command succeeded."""
        return self.refusal is None


def found(document: object, key: str) -> object | None:
    """The first value stored under ``key`` anywhere in a JSON document, depth first; ``None`` when absent."""
    if isinstance(document, Mapping):
        if key in document:
            return document[key]
        children: Sequence[object] = tuple(document.values())
    elif isinstance(document, list):
        children = document
    else:
        return None
    for child in children:
        hit = found(child, key)
        if hit is not None:
            return hit
    return None


def found_text(document: object, key: str) -> str | None:
    """The first string stored under ``key``; ``None`` when it is absent or not a string."""
    value = found(document, key)
    return value if isinstance(value, str) and value else None


def _command_identity(args: Sequence[str]) -> str:
    """The command path an argument vector invokes, without its option values."""
    path: list[str] = []
    for token in args[:5]:
        if token.startswith("-"):
            break
        path.append(token)
    return " ".join(path)


def _error_text(document: Mapping[str, Any]) -> str:
    """The error code, typed refusal and message of an error envelope, bounded."""
    error = document.get("error")
    error = error if isinstance(error, Mapping) else {}
    parts = [str(error.get("code", "unknown"))]
    typed = typed_refusal(dict(document))
    if typed is not None:
        parts.append(typed)
    message = error.get("message")
    if isinstance(message, str) and message:
        parts.append(message[:MESSAGE_LIMIT])
    return " ".join(parts)


@dataclass
class Journey:
    """One persona's journey state: what was run, what it minted and what no command could take."""

    persona: Persona
    envelope: YearEnvelope
    operation: PinnedAuthorityOperation
    cli: InstalledCli
    workdir: Path
    say: Callable[[str], None]
    steps: list[StepRecord] = field(default_factory=list)
    gaps: list[CliGap] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    transactions: dict[str, str] = field(default_factory=dict)
    invoices: dict[str, str] = field(default_factory=dict)
    revisions: dict[tuple[str, int, str], str] = field(default_factory=dict)
    setup_complete: bool = False

    def run(
        self, step: str, args: Sequence[str], *, authenticated: bool = True, stdin_payload: str | None = None
    ) -> Reply:
        """Run one command, record its outcome under ``step`` and return what it reported."""
        command = _command_identity(args)
        try:
            document = self.cli.run(
                args, authenticated=authenticated, allow_error=True, stdin_payload=stdin_payload, command=command
            )
        except (InstalledCliError, subprocess.TimeoutExpired, OSError) as error:
            self._record(StepRecord(step, command, StepOutcome.REFUSED, type(error).__name__, str(error)[:200]))
            raise JourneyAbortedError(f"{step}: {type(error).__name__}") from error
        if document.get("status") == "error":
            text = _error_text(document)
            code = text.split(" ", 1)[0]
            self._record(StepRecord(step, command, StepOutcome.REFUSED, code, text))
            if code in _BLOCKING_CODES:
                raise JourneyAbortedError(f"{step}: {code}")
            return Reply(result={}, refusal=text)
        self._record(StepRecord(step, command, StepOutcome.OK))
        result = document.get("result")
        return Reply(result=result if isinstance(result, Mapping) else {})

    def _record(self, record: StepRecord) -> None:
        self.steps.append(record)
        detail = "" if record.refusal is None else f" {record.refusal}"
        self.say(f"{self.persona.id} {record.step}: {record.outcome.value}{detail}")

    def skip(self, step: str, reason: str) -> None:
        """Record a step not attempted because one it depends on did not succeed."""
        self._record(StepRecord(step, "", StepOutcome.SKIPPED, None, reason))

    def gap(self, step: str, missing: str) -> None:
        """Record a fact no CLI command takes."""
        self.gaps.append(CliGap(self.persona.id, step, missing))
        self._record(StepRecord(step, "", StepOutcome.GAP, None, missing))

    def missing(self, routes: Sequence[commands.MissingRoute]) -> None:
        """Record every missing route as a gap."""
        for route in routes:
            self.gap(route.step, route.missing)

    def note(self, text: str) -> None:
        """Record an observation that is neither a step nor a gap."""
        self.notes.append(text)
        self.say(f"{self.persona.id} note: {text}")
