"""The TUI pilot's lines of the frontend intake: one per persona, then one per return, each validated first.

The schema is the persona table's (``persona_table.frontend.parse_result``); a line it refuses is never written.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Final

from ..persona_table.frontend import SurfaceResult, parse_result

OUT_ENV: Final = "PERSONA_PILOT_OUT"
"""The JSON-lines file each pilot appends its lines to, when set."""
TREE_ENV: Final = "PERSONA_PILOT_TREE"
"""The commit the pilot ran, as the caller names it; the pilot never asks version control."""
LOG_ENV: Final = "PERSONA_PILOT_LOG"
"""The path of the run log, as the caller names it."""

SURFACE: Final = "tui"
PASSED: Final = "pass"
INCOMPLETE: Final = "incomplete"
REFUSED: Final = "refused"
ERROR: Final = "error"
NOT_OWED: Final = "not-owed"
NOT_SHOWN: Final = "not-shown"
"""The file word of a recorded filing the workbench shows no filed state for."""


class IntakeConfigurationError(RuntimeError):
    """The environment names an output file but not what the intake requires with it."""


@dataclass
class PilotRow:
    """One line of the TUI column: a persona-level line when ``modelo`` is ``None``, else one return."""

    persona: str
    modelo: str | None = None
    year: int | None = None
    period: str | None = None
    horizon: int | None = None
    """The replay horizon the line was run at; the table pairs a return line only with its row of that horizon, and a
    persona line speaks only for the rows of its horizon. ``None`` on the line announcing the persona before any
    replay, which speaks for every row no horizon line answers for."""
    loads: bool = True
    calculate: str | None = None
    verify: str | None = None
    export: str | None = None
    refusal_code: str | None = None
    figures: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    seconds: float = 0.0
    stopped_at: str | None = None
    """The served next action the pilot stopped at because it is no step it can take; ``None`` when none stopped it."""
    filed: bool = False
    """Whether the workbench recorded the return filed locally, so later returns read it filed."""
    file: str | None = None
    """The file stage as the workbench itself showed it: ``pass`` when its next-step line says the filing is recorded,
    ``refused`` when it withheld or refused the recording, ``not-shown`` when the recording settled and the line
    shows nothing of it, ``error`` when the recording failed, ``not-reached`` when the drive never took the step.
    ``None`` until a filing is attempted, and for a return the table did not file locally (no file stage)."""
    cause: str | None = None
    """The one cause key of a row that differs from the table's; ``None`` for a matched row."""
    cause_words: str = ""
    export_served: bool | None = None
    """Whether the form served an export door for the return once its check had run; ``None`` when the drive never
    reached that question. Served state, not a pilot choice."""
    blocking_findings: tuple[str, ...] = ()
    """The ids of the blocking findings the workbench's issues list showed once the check had not passed; empty when
    it showed none. The line carries them only when there are some."""

    @property
    def label(self) -> str:
        """``persona modelo year period``, and ``at horizon <year>`` when it has one, as a failure names the row."""
        at = "" if self.horizon is None else f" at horizon {self.horizon}"
        return f"{self.persona} {self.modelo} {self.year} {self.period}{at}"

    def reason(self) -> str:
        """The row's free text: its cause key, what each stage said, then its time."""
        parts = [f"cause={self.cause}; {self.cause_words}".rstrip("; ")] if self.cause is not None else []
        parts += self.reasons
        if self.modelo is not None:
            parts.append(f"{self.seconds:.1f}s in the workbench")
        return " | ".join(part for part in parts if part)

    def document(self, *, tree: str, log: str) -> dict[str, object]:
        """The row as the intake's object, with exactly its keys."""
        document: dict[str, object] = {
            "surface": SURFACE,
            "tree": tree,
            "persona": self.persona,
            "modelo": self.modelo,
            "year": self.year,
            "period": self.period,
            "loads": self.loads,
            "calculate": self.calculate,
            "verify": self.verify,
            "export": self.export,
            "refusal_code": self.refusal_code,
            "figures": self.figures,
            "reason": self.reason(),
            "log": log,
        }
        if self.horizon is not None:
            document["horizon"] = self.horizon
        if self.export_served is not None and _schema_takes_export_served():
            document["export_served"] = self.export_served
        if self.blocking_findings:
            document["blocking_findings"] = list(self.blocking_findings)
        if self.file is not None and _schema_takes_file(self.file):
            document["file"] = self.file
        return document

    def line(self, *, tree: str, log: str) -> str:
        """The row as one JSON line of the intake."""
        return json.dumps(self.document(tree=tree, log=log), ensure_ascii=False)

    def result(self, *, tree: str = "-") -> SurfaceResult:
        """The row as the persona table reads a surface result, through its own schema."""
        return parse_result(self.line(tree=tree, log=""))


@cache
def _schema_takes_export_served() -> bool:
    """Whether the persona table's intake schema already knows the served-export field; older ones refuse it."""
    probe = json.loads(PilotRow(persona="probe").line(tree="-", log=""))
    probe["export_served"] = False
    try:
        parse_result(json.dumps(probe))
    except ValueError:
        return False
    return True


@cache
def _schema_takes_file(word: str) -> bool:
    """Whether the persona table's intake schema knows ``word`` as a file stage; older schemas refuse some words.

    A row whose word the schema refuses is written without the field, and its reason keeps the file words, so the
    line stays readable and the field is never invented.
    """
    probe = json.loads(PilotRow(persona="probe").line(tree="-", log=""))
    probe["file"] = word
    try:
        parse_result(json.dumps(probe))
    except ValueError:
        return False
    return True


def output_path() -> Path | None:
    """The file :data:`OUT_ENV` names, or ``None`` when it names none; the operator supplies an absolute path."""
    out = os.environ.get(OUT_ENV, "")
    if not out:
        return None
    destination = Path(out)
    if not destination.is_absolute():
        raise IntakeConfigurationError(f"{OUT_ENV} must name an absolute path, not {out!r}")
    return destination


def append_lines(destination: Path, lines: Iterable[str]) -> None:
    """Append ``lines`` to ``destination`` in one write, so parallel workers append whole lines."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write("".join(line + "\n" for line in lines))


def write_rows(rows: Iterable[PilotRow]) -> None:
    """Append ``rows`` to the file :data:`OUT_ENV` names, when it names one, refusing any line the schema refuses."""
    destination = output_path()
    if destination is None:
        return
    tree = os.environ.get(TREE_ENV, "")
    if not tree:
        raise IntakeConfigurationError(f"{OUT_ENV} is set but {TREE_ENV} does not name the tree the pilot ran")
    log = os.environ.get(LOG_ENV, "")
    lines = [row.line(tree=tree, log=log) for row in rows]
    for line in lines:
        parse_result(line)
    append_lines(destination, lines)
