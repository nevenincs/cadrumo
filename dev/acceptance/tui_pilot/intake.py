"""The TUI pilot's lines of the frontend intake: one per persona, then one per return, each validated first.

The schema is the persona table's (``persona_table.frontend.parse_result``); a line it refuses is never written.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
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


class IntakeConfigurationError(RuntimeError):
    """The environment names an output file but not what the intake requires with it."""


@dataclass
class PilotRow:
    """One line of the TUI column: a persona-level line when ``modelo`` is ``None``, else one return."""

    persona: str
    modelo: str | None = None
    year: int | None = None
    period: str | None = None
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
    cause: str | None = None
    """The one cause key of a row that differs from the table's; ``None`` for a matched row."""
    cause_words: str = ""

    @property
    def label(self) -> str:
        """``persona modelo year period``, as a failure names the row."""
        return f"{self.persona} {self.modelo} {self.year} {self.period}"

    def reason(self) -> str:
        """The row's free text: its cause key, what each stage said, then its time."""
        parts = [f"cause={self.cause}; {self.cause_words}".rstrip("; ")] if self.cause is not None else []
        parts += self.reasons
        if self.modelo is not None:
            parts.append(f"{self.seconds:.1f}s in the workbench")
        return " | ".join(part for part in parts if part)

    def document(self, *, tree: str, log: str) -> dict[str, object]:
        """The row as the intake's object, with exactly its keys."""
        return {
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

    def line(self, *, tree: str, log: str) -> str:
        """The row as one JSON line of the intake."""
        return json.dumps(self.document(tree=tree, log=log), ensure_ascii=False)

    def result(self, *, tree: str = "-") -> SurfaceResult:
        """The row as the persona table reads a surface result, through its own schema."""
        return parse_result(self.line(tree=tree, log=""))


def write_rows(rows: Iterable[PilotRow]) -> None:
    """Append ``rows`` to the file :data:`OUT_ENV` names, when it names one, refusing any line the schema refuses."""
    out = os.environ.get(OUT_ENV, "")
    if not out:
        return
    tree = os.environ.get(TREE_ENV, "")
    if not tree:
        raise IntakeConfigurationError(f"{OUT_ENV} is set but {TREE_ENV} does not name the tree the pilot ran")
    log = os.environ.get(LOG_ENV, "")
    lines = [row.line(tree=tree, log=log) for row in rows]
    for line in lines:
        parse_result(line)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    # One write per call, so personas run in parallel workers append whole lines.
    with path.open("a", encoding="utf-8") as handle:
        handle.write("".join(line + "\n" for line in lines))
