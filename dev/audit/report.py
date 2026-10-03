#!/usr/bin/env python
"""Monthly code-health report: duplication, import quality, complexity.

Composes the EXISTING scanners already shipped under ``dev/`` into one
red/amber/green dashboard, so a contributor gets a single command and a single
verdict instead of unrelated tool invocations with no shared severity
model:

* **Duplication** (D2) -- delegates the entire measurement to
  ``dev.audit.duplication.run_duplication_scan``, the one runner
  ``just audit-dead-weight`` also calls. Any clone cluster is advisory debt
  (AMBER, carrying the measured count); a scan that demonstrably inspected the
  tree and found nothing is GREEN; a scan that could not run or produced no
  parseable evidence is AMBER-unavailable, never GREEN. jscpd has no meaningful
  "graph broken" failure mode, so this dimension never reports RED on its own --
  it is advisory by design (mirrors ``dev/audit/duplication.py``'s own
  "duplication is advisory debt, not a gate" contract).
* **Import quality** -- consumes the authoritative ``just check-import-boundaries``
  process result, invoking the recipe unmodified: no added arguments and no
  report-side timeout, so the report and the recipe cannot reach different
  verdicts on one tree. Any non-zero result is RED; zero is GREEN. A findings
  status means the gate ran and import quality failed; any other status, or a
  gate that cannot be launched, is RED with ``available`` false -- the gate
  could not complete, and an unavailable blocking gate is never offered as an
  advisory AMBER substitute. This report does not parse Import Linter output or
  maintain a second contract inventory.
* **Complexity** -- reuses ``dev.audit.complexity``'s live cyclomatic,
  maintainability, and cognitive scan. Any current hotspot is RED; zero is
  GREEN. This dimension has no development-state partition.

This module does not re-implement any scanner; it shells out to or imports the
existing tools and applies one shared severity vocabulary on top. Keeping the
composition here separate from the primitive scanners gives each consumer one
authoritative measurement path.

Usage::

    python -m dev.audit.report [--json] [--full]

Exit code is 1 if any dimension is RED, 0 otherwise (AMBER does not fail the
run -- it is a debt signal a contributor reads on the monthly cadence, not a
release blocker). Complexity and import quality remain hard live signals;
duplication remains advisory.

See Also:
    :func:`~dev.audit.duplication.run_duplication_scan`
        The single duplication runner consumed for the D2 dimension.
    :mod:`~dev.audit.complexity`
        Live complexity scanner reused for the complexity dimension.
    :class:`DimensionReport`
        Per-dimension red/amber/green result type.
    :class:`HealthReport`
        Aggregate report returned by :func:`build_report`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.ci.lane_recipe_commands import resolve_just_executable
from dev.exit_codes import FINDINGS_CODES, OK
from dev.test_runs.paths import allocate_run_directory, test_log_root

from .complexity import scan_complexity
from .duplication import DuplicationOutcome, run_duplication_scan

_UTF_8: Final[str] = UTF_8


class Status(StrEnum):
    """Traffic-light verdict for one report dimension."""

    RED = "red"
    AMBER = "amber"
    GREEN = "green"


@dataclass(frozen=True)
class DimensionReport:
    """One dimension's classified status, headline, and detail lines."""

    name: str
    status: Status
    headline: str
    details: list[str] = field(default_factory=list)
    available: bool = True


# ---------------------------------------------------------------------------
# D2: duplication (jscpd copy-paste clones)
# ---------------------------------------------------------------------------


def audit_duplication(repo_root: Path) -> DimensionReport:
    """Classify D2 (copy-paste duplication) from the one duplication runner.

    Delegates the whole measurement to :func:`~dev.audit.duplication.run_duplication_scan`
    and only maps its typed outcome onto this module's severity vocabulary; there
    is no second jscpd invocation or parser here.

    GREEN exclusively on ``observed_zero`` -- a scan that demonstrably inspected
    the production tree and found nothing. Clones are AMBER carrying the measured
    count (advisory debt: the count is not a gate). An unavailable scan is
    AMBER naming the reason, never green -- "we could not measure" and "there is
    nothing to find" are different facts.
    """
    result = run_duplication_scan(repo_root)

    if result.outcome is DuplicationOutcome.UNAVAILABLE:
        return DimensionReport(
            name="duplication",
            status=Status.AMBER,
            headline=result.headline(),
            details=["no duplication evidence was produced this cycle; this is not a clean-tree signal"],
            available=False,
        )
    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        return DimensionReport(name="duplication", status=Status.GREEN, headline=result.headline())

    return DimensionReport(
        name="duplication",
        status=Status.AMBER,
        headline=result.headline(),
        details=["see `just audit-dead-weight` for the full clone list"],
    )


# ---------------------------------------------------------------------------
# Import quality (authoritative import gate)
# ---------------------------------------------------------------------------


#: The recipe whose unmodified process result is the import-quality dimension.
#: It is also the aggregate suite's row for that gate, so this report,
#: ``just check-code`` and a contributor's own run consume one gate definition.
IMPORT_QUALITY_RECIPE: Final[str] = "check-import-boundaries"


def import_quality_command(just_executable: str) -> tuple[str, ...]:
    """Return the report's import-gate invocation: the recipe, with nothing added."""
    return (just_executable, IMPORT_QUALITY_RECIPE)


def audit_layering(repo_root: Path) -> DimensionReport:
    """Consume the sole import-quality gate as this report's import dimension."""
    try:
        command = import_quality_command(resolve_just_executable())
    except RuntimeError as exc:
        return _import_gate_not_run(str(exc))
    environment = os.environ.copy()
    environment["CADRUMO_IMPORT_GATE_ROOT"] = str(repo_root)
    # No report-side wall-clock bound. The gate bounds each of its subprocess
    # components itself (``dev.quality.import_gate --cpu-budget``/``--stall-seconds``)
    # and reports an overrun as its own TOOL_BROKEN verdict. Full-tree runs measured 182-260 s,
    # and 328-338 s under load; a tighter outer bound here killed only ``just``,
    # left the gate running, and replaced the gate's verdict with a report-side one.
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root if repo_root.is_dir() else REPO_ROOT,
            env=environment,
        )
    except OSError as exc:
        return _import_gate_not_run(str(exc))
    return classify_import_gate_result(result.returncode, result.stdout, result.stderr)


def classify_import_gate_result(returncode: int, stdout: str, stderr: str) -> DimensionReport:
    """Map the import gate's exit status onto this report's severity model.

    Exit 0 is GREEN. A findings status is RED: the gate ran and import quality
    failed. Every other status is RED with ``available`` false: the gate could
    not complete, and an unavailable blocking gate is never offered as an
    advisory AMBER substitute.
    """
    if returncode == OK:
        return DimensionReport(
            name="layering",
            status=Status.GREEN,
            headline="authoritative import gate completed successfully",
        )
    diagnostic = (
        _import_gate_diagnostics(stdout)
        or [line.strip()[:500] for line in (stdout + stderr).splitlines() if line.strip()][:10]
    )
    details = [*diagnostic, f"run `just {IMPORT_QUALITY_RECIPE}` locally for the full import-quality result"]
    if returncode in FINDINGS_CODES:
        return DimensionReport(
            name="layering",
            status=Status.RED,
            headline=f"authoritative import gate exited {returncode}; import quality failed",
            details=details,
        )
    return DimensionReport(
        name="layering",
        status=Status.RED,
        headline=(
            f"authoritative import gate exited {returncode} without completing; no import-quality verdict this cycle"
        ),
        details=details,
        available=False,
    )


def _import_gate_not_run(reason: str) -> DimensionReport:
    """Report a gate this process could not launch: RED and unavailable, never advisory."""
    return DimensionReport(
        name="layering",
        status=Status.RED,
        headline=f"authoritative import gate could not run: {reason}",
        available=False,
    )


def _import_gate_diagnostics(stdout: str) -> list[str]:
    """Return the gate's own headline and reasons from its ``run_finished`` envelope.

    The recipe's runner replaces the gate's text with one JSON envelope per event,
    so slicing raw lines kept only the opening of a several-kilobyte object and
    dropped the reasons it carries deeper in. An absent or unreadable envelope
    returns nothing, and the caller falls back to the raw lines.
    """
    for line in reversed(stdout.splitlines()):
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(envelope, dict) or envelope.get("event") != "run_finished":
            continue
        graph_authority = envelope.get("graph_authority")
        operational = graph_authority.get("operational_reasons", []) if isinstance(graph_authority, dict) else []
        failed = envelope.get("failed_reasons", [])
        headline = envelope.get("headline")
        reasons = [*operational, *failed] if isinstance(operational, list) and isinstance(failed, list) else []
        return [str(item) for item in ([headline] if headline else []) + reasons]
    return []


# ---------------------------------------------------------------------------
# Complexity (cyclomatic / maintainability / cognitive)
# ---------------------------------------------------------------------------


def audit_complexity() -> DimensionReport:
    """Return RED for current live hotspots and GREEN only for zero."""
    try:
        scan = scan_complexity()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return DimensionReport(
            name="complexity",
            status=Status.AMBER,
            headline=f"complexity signal unavailable this cycle: {exc}",
            available=False,
        )
    if scan.finding_count:
        return DimensionReport(
            name="complexity",
            status=Status.RED,
            headline=f"{scan.finding_count} current complexity hotspot(s)",
            details=scan.rendered_findings(),
        )
    return DimensionReport(name="complexity", status=Status.GREEN, headline="no complexity hotspots")


# ---------------------------------------------------------------------------
# Report aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealthReport:
    """The full monthly code-health report: one status per dimension."""

    dimensions: tuple[DimensionReport, ...]

    @property
    def overall(self) -> Status:
        """Worst status across all dimensions (RED > AMBER > GREEN)."""
        statuses = {d.status for d in self.dimensions}
        if Status.RED in statuses:
            return Status.RED
        if Status.AMBER in statuses:
            return Status.AMBER
        return Status.GREEN

    def to_json(self) -> dict[str, object]:
        """Serialise the report as a JSON-ready mapping."""
        return {
            "overall": self.overall.value,
            "dimensions": [
                {
                    "name": d.name,
                    "status": d.status.value,
                    "available": d.available,
                    "headline": d.headline,
                    "details": d.details,
                }
                for d in self.dimensions
            ],
        }


def build_report(repo_root: Path) -> HealthReport:
    """Run every dimension audit and assemble the composed report."""
    return HealthReport(
        dimensions=(
            audit_duplication(repo_root),
            audit_layering(repo_root),
            audit_complexity(),
        ),
    )


_STATUS_GLYPH: Final[dict[Status, str]] = {
    Status.RED: "RED",
    Status.AMBER: "AMBER",
    Status.GREEN: "GREEN",
}


def render_text_report(report: HealthReport, full: bool) -> str:
    """Render the human-readable dashboard for console and persisted evidence."""
    lines = [f"code-health report: overall {_STATUS_GLYPH[report.overall]}", ""]
    for dimension in report.dimensions:
        lines.append(f"[{_STATUS_GLYPH[dimension.status]:>5}] {dimension.name}: {dimension.headline}")
        if dimension.details:
            shown = dimension.details if full else dimension.details[:10]
            for line in shown:
                lines.append(f"         {line}")
            if len(dimension.details) > len(shown):
                lines.append(f"         ... {len(dimension.details) - len(shown)} more")
    lines.append("")
    if report.overall is Status.RED:
        lines.append("code-health report: FAIL - one or more dimensions RED.")
    else:
        lines.append("code-health report: PASS (AMBER dimensions are advisory debt, not a gate).")
    return "\n".join(lines)


def persist_report(repository: Path, report: HealthReport, command: tuple[str, ...]) -> Path:
    """Persist one uniquely identified report and its producing command."""
    label = "report-code-health-monthly" if "--full" in command else "report-code-health"
    run_dir = allocate_run_directory(repository, family="audit-runs", label=label)
    run_dir.mkdir(parents=True)
    payload = {"command": list(command), "report": report.to_json()}
    (run_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding=_UTF_8, newline="\n"
    )
    (run_dir / "report.md").write_text(
        f"command: {' '.join(command)}\n\n{render_text_report(report, full=True)}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return run_dir


def main() -> int:
    """Run the composed monthly code-health report and print the verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON instead of text.")
    parser.add_argument("--full", action="store_true", help="List every detail line (uncapped) in text mode.")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    report = build_report(repo_root)

    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        print(render_text_report(report, args.full))

    run_dir = persist_report(test_log_root(), report, tuple(sys.argv))
    if not args.json:
        print(f"full report persisted to {run_dir}")

    return 1 if report.overall is Status.RED else 0


if __name__ == "__main__":
    sys.exit(main())
