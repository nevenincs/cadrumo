#!/usr/bin/env python
"""The composed `just audit-all` dashboard: one concise summary, full results on disk.

Replaces the old ``audit-all`` recipe, which chained five raw tool
passthroughs (`complexity`, `dead code`, `duplication`, `checkout drift`,
`security`) with no structure and no persistence. Measured on this tree, the
raw `check-security` step alone produced 55,378 lines for 365 findings --
each rendering matched code plus surrounding context, and several bundled
corpus/HTML fixtures carry single "lines" thousands of characters wide that
wrap across dozens of terminal rows.

This module composes the five EXISTING scanners rather than re-implementing
any of them -- ``dev.audit.report``'s `audit_complexity` / `audit_duplication`
are reused verbatim (report.py itself is untouched: it is wired into
``.github/workflows/code-health-report.yml`` and
``src/cadrumo/tests/test_dev_audit_report.py`` pins its `to_json()` shape and
four-dimension composition), and `dev.audit.dead_code` / `dev.audit.security`
/ `dev.audit.checkout_drift` supply the other three.

Two things this module adds that no existing `dev/audit` scanner has:

* A capped, human-scannable text dashboard by default (`--json` for a
  machine-readable single shot), mirroring `dev.audit.report`'s own
  red/amber/green shape.
* Disk persistence, every run, of the FULL uncapped result --
  `dev/audit/.runs/summary.json` (machine-parseable), `summary.md` (the same
  content, human-readable, no cap), and `security-findings.json` (the raw
  semgrep JSON payload, richer than the trimmed structured findings). Nothing
  here is committed; see the `.gitignore` entry beside `.ruff_cache/` and
  friends.

This module is deliberately advisory throughout: `main()` always exits 0,
matching today's `audit-all` contract (the old recipe chained every step with
`-@just ...` for exactly this reason), and none of the three new dimensions
invent a new blocking gate -- see each `audit_*` function's docstring for the
existing policy it reuses.

See Also:
    :mod:`dev.audit.report`
        The sibling shadowing/duplication/layering/complexity dashboard this
        module deliberately does not merge into (different dimension set,
        different CI wiring, pinned test coverage).
    :func:`build_advisory_report`
        Assembles all five dimensions.
    :func:`persist`
        Writes the full, uncapped result to disk.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from .checkout_drift import growth_against_ceiling, load_ceiling, measure
from .dead_code import DeadCodeOutcome, run_dead_code_scan
from .report import DimensionReport, Status, audit_complexity, audit_duplication
from .security import SecurityOutcome, run_security_scan
from .size_budget import run_size_budget_scan

_UTF_8: Final[str] = UTF_8
_TEXT_CAP: Final[int] = 8
_RUN_DIR_NAME: Final[str] = ".runs"

_STATUS_GLYPH: Final[dict[Status, str]] = {Status.RED: "RED", Status.AMBER: "AMBER", Status.GREEN: "GREEN"}
_STATUS_PRECEDENCE: Final[tuple[Status, ...]] = (Status.RED, Status.AMBER, Status.GREEN)


@dataclass(frozen=True)
class AdvisoryDimension:
    """One dimension's dashboard report plus the extra data persisted to disk.

    ``report`` carries exactly what the text dashboard prints (name, status,
    headline, capped-at-print-time details). ``count_by_severity`` and
    ``findings`` are the UNCAPPED structured data that only reach disk, never
    the terminal -- the split that keeps the default run concise while still
    making the full result parseable.

    ``raw_payload`` is an optional extra artefact reaching disk verbatim
    (currently only security populates it, with the raw semgrep JSON --
    richer than the trimmed ``findings`` above). Generic per-dimension rather
    than security-specific plumbing, so a future dimension can opt in the
    same way without widening any function signature.
    """

    report: DimensionReport
    count_by_severity: dict[str, int] = field(default_factory=dict)
    findings: tuple[dict[str, object], ...] = ()
    raw_payload: str = ""
    raw_payload_filename: str = ""


# ---------------------------------------------------------------------------
# Dead code (vulture)
# ---------------------------------------------------------------------------


def audit_dead_code(repo_root: Path) -> AdvisoryDimension:
    """Classify the dead-code dimension from the one vulture runner.

    AMBER on any finding -- advisory debt, matching today's non-blocking
    posture (`audit-dead-code` has never gated anything; this display invents
    no new policy). GREEN on a clean scan. AMBER on a tool error, never
    GREEN -- "could not measure" and "nothing to find" are different facts.
    """
    result = run_dead_code_scan(repo_root)

    findings: tuple[dict[str, object], ...] = tuple(
        {"path": f.path, "line": f.line, "message": f.message, "confidence": f.confidence} for f in result.findings
    )
    details = [f"{f.confidence:>3}%  {f.path}:{f.line}  {f.message}" for f in result.findings]

    if result.outcome is DeadCodeOutcome.ERROR:
        return AdvisoryDimension(
            DimensionReport(name="dead_code", status=Status.AMBER, headline=result.headline()),
        )
    if result.outcome is DeadCodeOutcome.CLEAN:
        return AdvisoryDimension(DimensionReport(name="dead_code", status=Status.GREEN, headline=result.headline()))
    return AdvisoryDimension(
        DimensionReport(name="dead_code", status=Status.AMBER, headline=result.headline(), details=details),
        count_by_severity=result.count_by_confidence,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Size budget
# ---------------------------------------------------------------------------


def audit_size_budget() -> AdvisoryDimension:
    """Classify the size-budget dimension from the one size-budget scanner.

    AMBER on any finding -- advisory debt, matching the non-blocking posture
    every other dimension here carries. This display invents no new policy: a
    blocking size gate is a separate decision with an owner, and choosing RED
    here would smuggle it in through a dashboard that always exits 0.

    GREEN only on a genuinely clean scan, never on an unmeasurable one.
    """
    result = run_size_budget_scan()
    if result.is_clean:
        return AdvisoryDimension(
            DimensionReport(name="size_budget", status=Status.GREEN, headline=result.headline()),
        )
    return AdvisoryDimension(
        DimensionReport(
            name="size_budget",
            status=Status.AMBER,
            headline=result.headline(),
            details=list(result.findings),
        ),
        count_by_severity={
            "modules": len(result.modules.failing),
            "callables": len(result.callables.failing),
        },
        findings=tuple({"subject": line} for line in result.findings),
    )


# ---------------------------------------------------------------------------
# Checkout drift
# ---------------------------------------------------------------------------


def audit_checkout_drift(repo_root: Path) -> AdvisoryDimension:
    """Classify the checkout-drift dimension from the real byte-drift measurement.

    RED only if a counter exceeds its own recorded `--check` ceiling --
    reuses `growth_against_ceiling`, so this display never invents a policy
    beyond what `python -m dev.audit.checkout_drift --check` already
    enforces. AMBER on drift with no ceiling breach (the module's own
    documented "screen, not a gate" posture). GREEN on zero drift.
    """
    measurement = measure(repo_root)
    ceiling_total, ceiling_buckets = load_ceiling()
    growth = growth_against_ceiling(measurement, ceiling_total, ceiling_buckets)

    findings: tuple[dict[str, object], ...] = tuple({"path": path} for path in measurement.drifted)
    details = list(measurement.drifted)
    count_by_severity = {"drifted": measurement.total, "carrying_crlf": measurement.carrying_crlf}
    headline = (
        f"{measurement.total} silently drifted file(s) of {measurement.scanned} scanned "
        f"({measurement.carrying_crlf} carrying CRLF)"
    )

    if growth:
        return AdvisoryDimension(
            DimensionReport(name="checkout_drift", status=Status.RED, headline=headline, details=growth),
            count_by_severity=count_by_severity,
            findings=findings,
        )
    if measurement.total:
        return AdvisoryDimension(
            DimensionReport(name="checkout_drift", status=Status.AMBER, headline=headline, details=details),
            count_by_severity=count_by_severity,
            findings=findings,
        )
    return AdvisoryDimension(DimensionReport(name="checkout_drift", status=Status.GREEN, headline=headline))


# ---------------------------------------------------------------------------
# Security (semgrep)
# ---------------------------------------------------------------------------


_SECURITY_RAW_FILENAME: Final[str] = "security-findings.json"


def audit_security(repo_root: Path) -> AdvisoryDimension:
    """Classify the security dimension from the one semgrep runner.

    RED if any ERROR-severity finding -- semgrep's own worst severity tier.
    AMBER on WARNING/INFO-only findings, or on an unavailable scan (never
    GREEN: "could not measure" and "nothing to find" are different facts).
    GREEN only on a scan that demonstrably inspected files and found nothing.

    Carries the raw semgrep JSON payload on ``raw_payload`` for any run that
    demonstrably scanned files, so :func:`persist` can write it verbatim
    alongside the trimmed structured findings.
    """
    result = run_security_scan(repo_root)

    findings: tuple[dict[str, object], ...] = tuple(
        {
            "check_id": f.check_id,
            "path": f.path,
            "line": f.line,
            "end_line": f.end_line,
            "severity": f.severity,
            "message": f.message,
        }
        for f in result.findings
    )
    details = [f"{f.severity:<8} {f.path}:{f.line}  {f.check_id}: {f.message}" for f in result.findings]
    if result.parse_errors:
        details = [f"[unparsed] {err}" for err in result.parse_errors] + details

    if result.outcome is SecurityOutcome.UNAVAILABLE:
        return AdvisoryDimension(
            DimensionReport(name="security", status=Status.AMBER, headline=result.headline()),
        )
    if result.outcome is SecurityOutcome.OBSERVED_ZERO:
        return AdvisoryDimension(
            DimensionReport(name="security", status=Status.GREEN, headline=result.headline(), details=details),
            raw_payload=result.raw_json,
            raw_payload_filename=_SECURITY_RAW_FILENAME,
        )

    status = Status.RED if "ERROR" in result.count_by_severity else Status.AMBER
    return AdvisoryDimension(
        DimensionReport(name="security", status=status, headline=result.headline(), details=details),
        count_by_severity=result.count_by_severity,
        findings=findings,
        raw_payload=result.raw_json,
        raw_payload_filename=_SECURITY_RAW_FILENAME,
    )


# ---------------------------------------------------------------------------
# Complexity / duplication: reused verbatim from dev.audit.report
# ---------------------------------------------------------------------------


def _wrap(report: DimensionReport) -> AdvisoryDimension:
    """Wrap a plain `DimensionReport` (no structured findings) for the dashboard."""
    count_by_severity = {"failing": len(report.details)} if report.status is Status.RED else {}
    return AdvisoryDimension(report, count_by_severity=count_by_severity)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_advisory_report(repo_root: Path) -> tuple[AdvisoryDimension, ...]:
    """Run every advisory-audit dimension and assemble the composed report.

    Six dimensions in a fixed order: complexity, dead code, duplication,
    checkout drift, security, size budget.

    Size budget is the newest and was the longest unwired. Its scanner has
    lived in `dev/audit/` throughout, but the pytest gate that enforced it was
    deleted when the shipped package's zero-awareness boundary was closed --
    the gate read a `dev/` baseline from inside `src/`, so the boundary fix
    removed it rather than relocating it here. It then sat exiting 1 into a
    tree where nothing ran it, which is where a 6,060-line module came from.
    """
    return (
        _wrap(audit_complexity()),
        audit_dead_code(repo_root),
        _wrap(audit_duplication(repo_root)),
        audit_checkout_drift(repo_root),
        audit_security(repo_root),
        audit_size_budget(),
    )


def _overall(dimensions: tuple[AdvisoryDimension, ...]) -> Status:
    """Worst status across all dimensions (RED > AMBER > GREEN)."""
    statuses = {d.report.status for d in dimensions}
    for status in _STATUS_PRECEDENCE:
        if status in statuses:
            return status
    return Status.GREEN


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_text(dimensions: tuple[AdvisoryDimension, ...], overall: Status, *, full: bool) -> str:
    """Render the dashboard as text. `full=True` uncaps every dimension's details."""
    lines = [f"advisory-audit report: overall {_STATUS_GLYPH[overall]}", ""]
    for dimension in dimensions:
        report = dimension.report
        lines.append(f"[{_STATUS_GLYPH[report.status]:>5}] {report.name}: {report.headline}")
        details = report.details if full else report.details[:_TEXT_CAP]
        for line in details:
            lines.append(f"         {line}")
        if len(report.details) > len(details):
            lines.append(f"         ... {len(report.details) - len(details)} more (see persisted summary.md)")
    lines.append("")
    lines.append(
        "advisory-audit report: FAIL"
        if overall is Status.RED
        else "advisory-audit report: PASS (AMBER dimensions are advisory debt, not a gate)",
    )
    return "\n".join(lines)


_LEADING_COUNT: Final = re.compile(r"^(\d+)")


def _total_findings(dimension: AdvisoryDimension) -> int:
    """The best available true count for a dimension.

    Dimensions built in this module (dead code, checkout drift, security)
    populate ``findings`` one record per finding, so its length is exact.
    Complexity and duplication are reused verbatim from ``dev.audit.report``
    and never populate ``findings`` -- their `details` list is not always
    one-line-per-finding either (`audit_duplication` collapses every clone
    into a single "see `just audit-duplication`" pointer line, so counting
    `details` would undercount 17 clusters as 1). Their own headline always
    leads with the real count in prose, so that is the honest source here.
    """
    if dimension.findings:
        return len(dimension.findings)
    match = _LEADING_COUNT.match(dimension.report.headline)
    return int(match.group(1)) if match else 0


def to_json(dimensions: tuple[AdvisoryDimension, ...], overall: Status, generated_at: str) -> dict[str, object]:
    """Serialise the full, uncapped result as a JSON-ready mapping."""
    return {
        "generated_at": generated_at,
        "overall": overall.value,
        "dimensions": [
            {
                "name": dimension.report.name,
                "status": dimension.report.status.value,
                "headline": dimension.report.headline,
                "count_by_severity": dimension.count_by_severity,
                "total_findings": _total_findings(dimension),
                "details": dimension.report.details,
                "findings": list(dimension.findings),
            }
            for dimension in dimensions
        ],
    }


def persist(run_dir: Path, dimensions: tuple[AdvisoryDimension, ...], overall: Status) -> Path:
    """Write the full, uncapped result to disk. Returns the run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(tz=UTC).isoformat()

    payload = to_json(dimensions, overall, generated_at)
    (run_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    (run_dir / "summary.md").write_text(
        f"generated at {generated_at}\n\n" + render_text(dimensions, overall, full=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    for dimension in dimensions:
        if dimension.raw_payload and dimension.raw_payload_filename:
            (run_dir / dimension.raw_payload_filename).write_text(
                dimension.raw_payload,
                encoding=_UTF_8,
                newline="\n",
            )

    return run_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Run every advisory-audit dimension, print the dashboard, persist the full result.

    Always exits 0 -- `audit-all` has always been "tolerant of individual
    findings" (the old recipe chained every step with `-@just ...` for
    exactly that reason); this preserves that contract.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run every advisory audit and print the composed dashboard.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON instead of text.")
    parser.add_argument("--full", action="store_true", help="List every detail line (uncapped) in text mode.")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    dimensions = build_advisory_report(repo_root)
    overall = _overall(dimensions)

    if args.json:
        print(json.dumps(to_json(dimensions, overall, datetime.now(tz=UTC).isoformat()), indent=2, ensure_ascii=False))
    else:
        print(render_text(dimensions, overall, full=args.full))

    run_dir = persist(repo_root / "dev" / "audit" / _RUN_DIR_NAME, dimensions, overall)
    if not args.json:
        print(f"\nfull report persisted to {run_dir / 'summary.json'} and {run_dir / 'summary.md'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
