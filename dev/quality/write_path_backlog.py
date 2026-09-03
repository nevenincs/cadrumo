"""Backlog: the set of readable persistence surfaces with no writer may shrink, never grow.

:mod:`dev.audit.write_path_coverage` reports every persistence surface whose
read side a product command reaches while its write side has no production
caller. That is a data-path defect the reachability audit cannot see, and it
has shipped here twice: commands that list, show, and resolve records from a
store nothing on earth could fill.

This gate is what stops that set from growing while the surfaces inside it are
resolved. Its baseline is an identity set, not a count, for the same reason the
unreachable-module ratchet's is: a count accepts a swap, so one surface could
be repaired and another stranded with the number undisturbed. The comparison is
set equality in both directions.

* A surface the tree reports that the baseline does not name is a regression:
  a producer was just deleted, or a reader was just added over a store that
  never had one.
* A baselined surface the tree no longer reports is stale: the write path was
  restored and the baseline must shrink to record it.

The second direction is what keeps the file honest. Without it the backlog only
accumulates, and a later reader cannot tell an accepted debt from a line nobody
removed.

There is deliberately no "intentional" disposition here, unlike the
reachability ratchet. A store can legitimately be unreachable by design -- a
design-time vocabulary is a real thing -- but a store a shipped command reads
and no shipped code fills is not a design, it is a broken product surface.
Every entry is debt.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from .._paths import REPO_ROOT, UTF_8
from ..audit.write_path_coverage import WritePathOutcome, WritePathResult, run_write_path_scan

BASELINE_PATH: Final[Path] = Path(__file__).with_name("write_path_backlog.toml")


def _string_list(data: object, *, field: str) -> tuple[str, ...]:
    """Read one TOML string list without accepting scalar lookalikes."""
    if not isinstance(data, list):
        raise ValueError(f"{field} must be a list of non-empty strings")
    entries: list[str] = []
    for item in cast("list[object]", data):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} must be a list of non-empty strings")
        entries.append(item)
    return tuple(entries)


@dataclass(frozen=True, slots=True)
class WritePathBaseline:
    """The accepted set of readable surfaces that currently have no writer.

    Args:
        allowed: Surface identifiers (``module:ClassName``) accepted for now,
            each expected to still be reported. One that stops being reported
            is stale and must be removed.
    """

    allowed: frozenset[str]

    def __post_init__(self) -> None:
        """Reject an entry that cannot name a surface."""
        malformed = sorted(entry for entry in self.allowed if entry.count(":") != 1 or not all(entry.split(":")))
        if malformed:
            raise ValueError(f"write-path baseline entries must be 'module:ClassName': {malformed}")

    @classmethod
    def load(cls, path: Path = BASELINE_PATH) -> WritePathBaseline:
        """Read the committed baseline."""
        data = tomllib.loads(path.read_text(encoding=UTF_8))
        return cls(allowed=frozenset(_string_list(data.get("allowed", []), field="allowed")))


@dataclass(frozen=True, slots=True)
class WritePathVerdict:
    """What the live tree reports measured against the baseline.

    Args:
        regressions: Reported surfaces the baseline does not name.
        stale: Baselined surfaces the tree no longer reports.
    """

    regressions: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        """True when the writerless set is exactly what the baseline says."""
        return not self.regressions and not self.stale

    def report(self) -> str:
        """Human-readable rendering naming every surface in every direction."""
        lines: list[str] = []
        if self.regressions:
            lines.append(
                f"{len(self.regressions)} persistence surface(s) a product command reads "
                f"that no production code fills, and the baseline does not name.",
            )
            lines.append(
                "A producer was deleted, or a reader was added over a store that never had one. "
                "Restore or wire the write path; do not baseline it to make this pass:",
            )
            lines.extend(f"  + {name}" for name in self.regressions)
        if self.stale:
            lines.append(
                f"{len(self.stale)} baseline entry/entries the tree no longer reports. "
                f"Delete them from {BASELINE_PATH.name} so the backlog records the repair:",
            )
            lines.extend(f"  - {name}" for name in self.stale)
        if not lines:
            return "write-path backlog matches the baseline"
        return "\n".join(lines)


def writerless_surfaces(result: WritePathResult) -> frozenset[str]:
    """The reported surfaces, keyed the way the baseline names them."""
    return frozenset(f"{finding.module}:{finding.service}" for finding in result.findings)


def evaluate(result: WritePathResult, baseline: WritePathBaseline) -> WritePathVerdict:
    """Compare the live reported set against ``baseline`` in both directions."""
    reported = writerless_surfaces(result)
    return WritePathVerdict(
        regressions=tuple(sorted(reported - baseline.allowed)),
        stale=tuple(sorted(baseline.allowed - reported)),
    )


def run_gate(repo_root: Path = REPO_ROOT, *, baseline_path: Path = BASELINE_PATH) -> WritePathVerdict:
    """Scan the real shipped tree and measure it against the committed baseline.

    Raises:
        RuntimeError: If the scan cannot produce a trustworthy result. A gate
            that cannot see the tree must refuse rather than report clean.
    """
    result = run_write_path_scan(repo_root)
    if result.outcome is WritePathOutcome.ERROR:
        msg = f"write-path scan unavailable, backlog unproven: {result.reason}"
        raise RuntimeError(msg)
    return evaluate(result, WritePathBaseline.load(baseline_path))


def main() -> int:
    """Print the verdict; exit non-zero when the writerless set moved."""
    verdict = run_gate()
    if verdict.is_clean:
        return 0
    sys.stderr.write(verdict.report() + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
