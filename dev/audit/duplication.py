#!/usr/bin/env python
"""The single duplication runner: invoke jscpd, parse it, classify it honestly.

This module owns the WHOLE duplication measurement: source selection, command
construction, execution, timeout, stdout/stderr/returncode handling, parsing,
clone records, and availability classification. Both consumers -- the
``just audit-duplication`` recipe and the ``dev.audit.report`` health
dashboard's D2 dimension -- go through :func:`run_duplication_scan`. There is
deliberately no second jscpd command anywhere in the tree: a measurement tool
that duplicates itself is the very defect it exists to detect.

The result is a typed value with exactly three states, and the distinction
between the first and the third is the point of this module:

* :attr:`DuplicationOutcome.OBSERVED_ZERO` -- jscpd ran, demonstrably inspected
  the production tree (``files_analyzed > 0``), and reported no clones.
* :attr:`DuplicationOutcome.CLONES` -- jscpd ran and reported clones.
* :attr:`DuplicationOutcome.UNAVAILABLE` -- no signal: missing executable,
  timeout, non-zero exit, or output carrying no parseable summary (which
  includes the scan-inspected-nothing case).

An unavailable scan is NEVER reported as zero. jscpd prints ``Found 0 clones.``
plus a summary table on a genuine clean run, but prints ONLY a timing line when
it matches no files at all -- so "no clones seen" and "nothing was looked at"
are different facts that a naive ``total == 0`` parse silently merges into a
false green. ``files_analyzed`` is the discriminator, and it is why
``observed_zero`` carries it.

The clone COUNT is advisory debt, not a gate: this module always exits 0 and
the health report renders clones as AMBER. Honest closure is valid evidence
plus no false green -- not zero clones.

Two limits are deliberate, recorded here so neither is re-derived as a defect:

* **Scope is the product tree.** :data:`_PRODUCT_SOURCE_ROOT` is
  ``src/cadrumo`` alone, because the governing audit scopes every instrument to
  "the intended production scope" and the duplication the campaign cares about
  is duplicate AUTHORITY in shipped code -- a second writer with weaker guards,
  not two similar-looking dev scripts. ``dev/`` is therefore unmeasured by the
  standing recipe and by the health report's D2 dimension. It is not
  unmeasurABLE: pass a different ``source_root`` to scan it on demand, which is
  how the two clone groups recorded in ``duplication_dispositions.toml`` were
  found. Widening the default would fold tooling debt into the product number.

* **jscpd matches token sequences.** A concept implemented twice in different
  syntax is invisible to it, and that is exactly the duplication this project's
  rules treat as a blocker. Five ledger projections once shared one casilla fold
  differing only in an accumulator loop versus a comprehension; this runner
  reported none of them, and flagged their shared import preambles instead. A
  low percentage from this module means little COPY-PASTE survives. It has never
  meant little duplication survives, and no change to this module can make it
  mean that.

See Also:
    :func:`run_duplication_scan`
        The one runner both consumers call.
    :class:`DuplicationResult`
        The typed three-state result.
    :mod:`~dev.audit.report`
        The health dashboard that consumes this runner for its D2 dimension.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8
_ANSI: Final = re.compile(r"\x1b\[[0-9;]*m")
_FOUND: Final = re.compile(r"Found (\d+) clones?")
_TABLE_PCT: Final = re.compile(r"\((\d+(?:\.\d+)?)%\)")
_CLONE_CAP: Final[int] = 20

_JSCPD_SPEC: Final[str] = "jscpd@4.2.0"
_JSCPD_TIMEOUT_SECONDS: Final[float] = 300.0
_PRODUCT_SOURCE_ROOT: Final[Path] = Path("src/cadrumo")
_JSCPD_IGNORE: Final[str] = "**/test_*.py,**/_test_*.py,**/tests/**,**/_data/**"

# The jscpd summary table's "Total:" row, post-ANSI-strip, reads:
#   | Total: | 1252 | 290727 | 1676107 | 65 | 1185 (0.41%) | 10882 (0.65%) |
# with box-drawing verticals. Cells are indexed against the header:
# Format | Files analyzed | Total lines | Total tokens | Clones found |
# Duplicated lines | Duplicated tokens.
_TABLE_VERTICAL: Final[str] = "│"
_TABLE_TOTAL_LABEL: Final[str] = "Total:"
_CELL_FILES_ANALYZED: Final[int] = 2
_CELL_DUPLICATED_LINES: Final[int] = 6
_MIN_TABLE_CELLS: Final[int] = 8


class DuplicationOutcome(StrEnum):
    """The three honest states a duplication scan can land in."""

    OBSERVED_ZERO = "observed_zero"
    CLONES = "clones"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CloneGroup:
    """One jscpd ``Clone found`` block, ANSI-stripped and path-normalised."""

    lines: tuple[str, ...]

    def render(self) -> str:
        """Render the block as its original multi-line console text."""
        return "\n".join(self.lines)


@dataclass(frozen=True)
class DuplicationResult:
    """A duplication scan's typed outcome.

    Construct through :meth:`observed_zero`, :meth:`from_clones`, or
    :meth:`unavailable` rather than directly, so the invariants binding each
    outcome to its evidence hold by construction.
    """

    outcome: DuplicationOutcome
    files_analyzed: int = 0
    clone_count: int = 0
    duplicated_pct: str = ""
    groups: tuple[CloneGroup, ...] = ()
    reason: str = ""

    @classmethod
    def observed_zero(cls, files_analyzed: int) -> DuplicationResult:
        """A successful scan that inspected ``files_analyzed`` files and saw no clones."""
        if files_analyzed <= 0:
            msg = "observed_zero requires a scan that demonstrably inspected files"
            raise ValueError(msg)
        return cls(outcome=DuplicationOutcome.OBSERVED_ZERO, files_analyzed=files_analyzed)

    @classmethod
    def from_clones(
        cls,
        *,
        files_analyzed: int,
        clone_count: int,
        duplicated_pct: str,
        groups: tuple[CloneGroup, ...],
    ) -> DuplicationResult:
        """A successful scan that found ``clone_count`` clones."""
        if clone_count <= 0:
            msg = "from_clones requires a positive clone count"
            raise ValueError(msg)
        return cls(
            outcome=DuplicationOutcome.CLONES,
            files_analyzed=files_analyzed,
            clone_count=clone_count,
            duplicated_pct=duplicated_pct,
            groups=groups,
        )

    @classmethod
    def unavailable(cls, reason: str) -> DuplicationResult:
        """No duplication signal this cycle; ``reason`` says why."""
        return cls(outcome=DuplicationOutcome.UNAVAILABLE, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict.

        Only a scan that looked at the tree and found nothing qualifies. An
        unavailable scan is not green, and clones are advisory AMBER.
        """
        return self.outcome is DuplicationOutcome.OBSERVED_ZERO

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is DuplicationOutcome.UNAVAILABLE:
            return f"duplication signal unavailable this cycle: {self.reason}"
        if self.outcome is DuplicationOutcome.OBSERVED_ZERO:
            return f"no clones found across {self.files_analyzed} analysed file(s)"
        pct_clause = f", {self.duplicated_pct}% duplicated lines" if self.duplicated_pct else ""
        return (
            f"{self.clone_count} clone cluster(s){pct_clause} "
            f"across {self.files_analyzed} analysed file(s) (advisory debt)"
        )


def jscpd_command(npx: str, source_root: Path = _PRODUCT_SOURCE_ROOT) -> list[str]:
    r"""Build the one jscpd command line.

    ``source_root`` is passed via :meth:`~pathlib.PurePath.as_posix` so it
    renders ``src/cadrumo`` on every OS. A Windows-native ``src\cadrumo``
    matches no files inside jscpd's glob engine, and jscpd then exits 0 having
    silently scanned nothing -- the false-green this module exists to prevent.
    """
    return [
        npx,
        "--yes",
        _JSCPD_SPEC,
        source_root.as_posix(),
        "--format",
        "python",
        "--min-lines",
        "6",
        "--min-tokens",
        "80",
        "--max-size",
        "250kb",
        "--ignore",
        _JSCPD_IGNORE,
        "--gitignore",
        "--reporters",
        "console",
        "--noTips",
    ]


def _parse_total_row(lines: list[str]) -> tuple[int, str] | None:
    """Extract ``(files_analyzed, duplicated_pct)`` from the summary table's Total row.

    Returns ``None`` when the table is absent, which is jscpd's signature for a
    run that matched no files at all.
    """
    for line in lines:
        if _TABLE_VERTICAL not in line:
            continue
        cells = [cell.strip() for cell in line.split(_TABLE_VERTICAL)]
        if len(cells) < _MIN_TABLE_CELLS or cells[1] != _TABLE_TOTAL_LABEL:
            continue
        try:
            files_analyzed = int(cells[_CELL_FILES_ANALYZED])
        except ValueError:
            return None
        pct_match = _TABLE_PCT.search(cells[_CELL_DUPLICATED_LINES])
        return files_analyzed, (pct_match.group(1) if pct_match else "")
    return None


def _parse_clone_groups(lines: list[str]) -> tuple[CloneGroup, ...]:
    """Collect the ``Clone found`` blocks, normalising Windows paths to POSIX."""
    blocks: list[CloneGroup] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("Clone found"):
            if current:
                blocks.append(CloneGroup(tuple(current)))
            current = [line]
            continue
        if not current:
            continue
        if line.strip():
            current.append(line.replace("\\", "/").rstrip())
        else:
            blocks.append(CloneGroup(tuple(current)))
            current = []
    if current:
        blocks.append(CloneGroup(tuple(current)))
    return tuple(blocks)


def classify_jscpd_output(raw_stdout: str) -> DuplicationResult:
    """Classify jscpd's stdout into the typed three-state result.

    A run is only trusted when it carries BOTH a parseable ``Found N clones``
    line and a summary table proving files were analysed. Anything else is
    :attr:`DuplicationOutcome.UNAVAILABLE` -- never a zero.
    """
    lines = _ANSI.sub("", raw_stdout).splitlines()

    found = None
    for line in lines:
        match = _FOUND.search(line)
        if match:
            found = int(match.group(1))
    total_row = _parse_total_row(lines)

    if found is None or total_row is None:
        return DuplicationResult.unavailable(
            "jscpd produced no parseable summary (it reported no clone total or no analysed-file table, "
            "which is also how it renders a run that matched zero files)",
        )

    files_analyzed, duplicated_pct = total_row
    if files_analyzed <= 0:
        return DuplicationResult.unavailable(
            "jscpd analysed 0 files, so the scan proves nothing about duplication",
        )
    if found <= 0:
        return DuplicationResult.observed_zero(files_analyzed)
    return DuplicationResult.from_clones(
        files_analyzed=files_analyzed,
        clone_count=found,
        duplicated_pct=duplicated_pct,
        groups=_parse_clone_groups(lines),
    )


def run_duplication_scan(
    repo_root: Path,
    *,
    source_root: Path = _PRODUCT_SOURCE_ROOT,
    timeout: float = _JSCPD_TIMEOUT_SECONDS,
    which: Callable[[str], str | None] = shutil.which,
) -> DuplicationResult:
    """Run jscpd over ``source_root`` and classify the outcome.

    This is the single entry point for every duplication consumer. ``npx`` is
    resolved through ``which`` -- :func:`shutil.which` in production -- because
    on Windows the real executable is a ``.cmd`` shim that ``CreateProcess``
    cannot launch by bare name (the same idiom as ``dev/docs/build.py``). The
    resolver is an injected seam (the prompt_toolkit ``input=``/``output=``
    contract, not a patch): a caller may supply a real resolver that returns
    ``None`` to exercise the missing-executable path, or one pointing at a
    different real executable to exercise the non-zero-exit path, without
    mutating global process state.
    """
    npx = which("npx")
    if npx is None:
        return DuplicationResult.unavailable("npx was not found on PATH")

    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, resolved executable, no shell
            jscpd_command(npx, source_root),
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return DuplicationResult.unavailable(f"jscpd exceeded its {timeout:g}s timeout")
    except OSError as exc:
        return DuplicationResult.unavailable(f"jscpd could not be launched ({exc})")

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no diagnostic output"
        return DuplicationResult.unavailable(f"jscpd exited {completed.returncode}: {tail}")

    return classify_jscpd_output(completed.stdout)


def render_console_report(result: DuplicationResult) -> str:
    """Render the operator-facing console report for ``just audit-duplication``."""
    if result.outcome is DuplicationOutcome.UNAVAILABLE:
        return f"duplication: {result.headline()}"
    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        return f"duplication: {result.headline()}."

    pct_clause = f", {result.duplicated_pct}% duplicated lines" if result.duplicated_pct else ""
    out = [f"duplication: {result.clone_count} clones{pct_clause}."]
    for group in result.groups[:_CLONE_CAP]:
        out.append("")
        out.append(group.render())
    if len(result.groups) > _CLONE_CAP:
        out.append(f"\n... {len(result.groups) - _CLONE_CAP} more clones")
    return "\n".join(out)


def main() -> int:
    """Run the duplication scan and print the reduced console report.

    Always exits 0: duplication is advisory debt, not a gate. An unavailable
    scan still says so out loud rather than posing as a clean run.
    """
    repo_root = REPO_ROOT
    print(render_console_report(run_duplication_scan(repo_root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
