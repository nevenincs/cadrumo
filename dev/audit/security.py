#!/usr/bin/env python
"""The single canonical semgrep runner: invoke it, parse it, classify it honestly.

Mirrors ``dev.audit.duplication``'s "the runner owns the whole measurement"
shape: source selection, command construction, execution, timeout handling,
parsing, and availability classification all live here, and there is
deliberately no second semgrep invocation anywhere in the tree -- both
``just check-security`` and ``dev.audit.advisory``'s security dimension call
:func:`run_security_scan`.

semgrep runs through ``uvx`` (a pinned, ephemeral, network-touching tool
resolution, the same risk profile as jscpd/npx), so this module carries the
same three-state discipline ``duplication.py`` established: a scan that could
not run, or ran but proves nothing, is never reported as clean.

Findings are parsed from ``--json`` output rather than the default text
report. The text report renders each match's surrounding source lines, which
is what turns a few hundred findings into tens of thousands of terminal
lines on this tree (measured: 365 findings, 55,378 lines) -- several bundled
corpus/HTML fixtures carry single "lines" thousands of characters wide that
wrap across dozens of terminal rows. The JSON payload carries the same
findings without the rendered context, and the raw payload itself is still
available for a deep dive via the persisted ``security-findings.json`` that
:mod:`dev.audit.advisory` writes.

See Also:
    :mod:`dev.audit.duplication`
        The sibling runner this module's shape is copied from.
    :func:`run_security_scan`
        The one entry point both ``just check-security`` and
        ``dev.audit.advisory`` call.
"""

from __future__ import annotations

import json
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
_FINDING_CAP: Final[int] = 40
_SEMGREP_SPEC: Final[str] = "semgrep==1.168.0"
_SEMGREP_TIMEOUT_SECONDS: Final[float] = 600.0
_PRODUCT_SOURCE_ROOT: Final[Path] = Path("src/cadrumo")

#: `pyproject.toml` pins `requires-python = ">=3.13,<3.14"`, so semgrep's
#: stock Python 3.6/3.7 forward-compatibility rules (flagging
#: `importlib.resources`, and the `errors`/`encoding` kwargs on `Popen`) can
#: never fire on a real regression here -- every one of them is a false
#: positive by construction, not a judgement call per finding.
_PYTHON_LEGACY_COMPATIBILITY_RULE_IDS: Final[tuple[str, ...]] = (
    "python.lang.compatibility.python37.python37-compatibility-importlib2",
    "python.lang.compatibility.python36.python36-compatibility-Popen1",
    "python.lang.compatibility.python36.python36-compatibility-Popen2",
)

# semgrep's real severity axis (`extra.severity` in --json output), worst first.
_SEVERITY_ORDER: Final[tuple[str, ...]] = ("ERROR", "WARNING", "INFO")


class SecurityOutcome(StrEnum):
    """The three honest states a semgrep scan can land in."""

    OBSERVED_ZERO = "observed_zero"
    FINDINGS = "findings"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SecurityFinding:
    """One semgrep result: a rule, a location, a severity, and its message."""

    check_id: str
    path: str
    line: int
    end_line: int
    severity: str
    message: str


@dataclass(frozen=True)
class SecurityResult:
    """A security scan's typed outcome.

    Construct through :meth:`observed_zero`, :meth:`from_findings`, or
    :meth:`unavailable` rather than directly, so the invariants binding each
    outcome to its evidence hold by construction.
    """

    outcome: SecurityOutcome
    files_scanned: int = 0
    findings: tuple[SecurityFinding, ...] = ()
    parse_errors: tuple[str, ...] = ()
    reason: str = ""
    raw_json: str = ""

    @classmethod
    def observed_zero(cls, files_scanned: int, parse_errors: tuple[str, ...], raw_json: str) -> SecurityResult:
        """A successful scan that inspected files and found no findings."""
        if files_scanned <= 0:
            msg = "observed_zero requires a scan that demonstrably inspected files"
            raise ValueError(msg)
        return cls(
            outcome=SecurityOutcome.OBSERVED_ZERO,
            files_scanned=files_scanned,
            parse_errors=parse_errors,
            raw_json=raw_json,
        )

    @classmethod
    def from_findings(
        cls,
        *,
        files_scanned: int,
        findings: tuple[SecurityFinding, ...],
        parse_errors: tuple[str, ...],
        raw_json: str,
    ) -> SecurityResult:
        """A successful scan that found findings."""
        if not findings:
            msg = "from_findings requires at least one finding"
            raise ValueError(msg)
        return cls(
            outcome=SecurityOutcome.FINDINGS,
            files_scanned=files_scanned,
            findings=findings,
            parse_errors=parse_errors,
            raw_json=raw_json,
        )

    @classmethod
    def unavailable(cls, reason: str) -> SecurityResult:
        """No security signal this cycle; ``reason`` says why."""
        return cls(outcome=SecurityOutcome.UNAVAILABLE, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict.

        Only a scan that demonstrably inspected files and found nothing
        qualifies. An unavailable scan is never green.
        """
        return self.outcome is SecurityOutcome.OBSERVED_ZERO

    @property
    def count_by_severity(self) -> dict[str, int]:
        """Finding counts keyed by semgrep's own ERROR/WARNING/INFO axis, worst first."""
        counts: dict[str, int] = {}
        for severity in _SEVERITY_ORDER:
            count = sum(1 for f in self.findings if f.severity == severity)
            if count:
                counts[severity] = count
        # Preserve any severity value semgrep introduces that this module
        # does not yet enumerate, rather than silently dropping it.
        for finding in self.findings:
            if finding.severity not in counts and finding.severity not in _SEVERITY_ORDER:
                counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is SecurityOutcome.UNAVAILABLE:
            return f"security signal unavailable this cycle: {self.reason}"
        error_note = f"; {len(self.parse_errors)} file(s) failed to parse" if self.parse_errors else ""
        if self.outcome is SecurityOutcome.OBSERVED_ZERO:
            return f"no findings across {self.files_scanned} scanned file(s){error_note}"
        breakdown = ", ".join(f"{count} {sev}" for sev, count in self.count_by_severity.items())
        return f"{len(self.findings)} finding(s) ({breakdown}) across {self.files_scanned} scanned file(s){error_note}"


def semgrep_command(uvx: str, source_root: Path = _PRODUCT_SOURCE_ROOT) -> list[str]:
    r"""Build the one semgrep command line.

    ``source_root`` is passed via :meth:`~pathlib.PurePath.as_posix` for the
    same reason ``jscpd_command`` in ``duplication.py`` does: a Windows-native
    ``src\cadrumo`` risks matching nothing under semgrep's own path handling.
    """
    command = [
        uvx,
        "--from",
        _SEMGREP_SPEC,
        "semgrep",
        "scan",
        "--quiet",
        "--config",
        "auto",
    ]
    for rule_id in _PYTHON_LEGACY_COMPATIBILITY_RULE_IDS:
        command += ["--exclude-rule", rule_id]
    command += ["--json", source_root.as_posix()]
    return command


def classify_semgrep_output(raw_stdout: str) -> SecurityResult:
    """Classify semgrep's JSON stdout into the typed three-state result.

    A run is only trusted when its JSON parses AND ``paths.scanned`` proves
    files were actually inspected -- the same "files_analyzed" discipline
    ``duplication.py`` applies to jscpd, so a scan that matched nothing can
    never read as a clean pass.
    """
    try:
        payload = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        return SecurityResult.unavailable(f"semgrep produced no parseable JSON ({exc})")

    scanned = payload.get("paths", {}).get("scanned", [])
    files_scanned = len(scanned) if isinstance(scanned, list) else 0
    if files_scanned <= 0:
        return SecurityResult.unavailable("semgrep analysed 0 files, so the scan proves nothing about security")

    parse_errors = tuple(
        f"{err.get('path', '?')}: {err.get('message', err.get('type', 'unknown error'))}"
        for err in payload.get("errors", [])
        if isinstance(err, dict)
    )

    raw_results = payload.get("results", [])
    findings: list[SecurityFinding] = []
    for entry in raw_results if isinstance(raw_results, list) else []:
        extra = entry.get("extra", {})
        findings.append(
            SecurityFinding(
                check_id=str(entry.get("check_id", "")),
                path=str(entry.get("path", "")).replace("\\", "/"),
                line=int(entry.get("start", {}).get("line", 0)),
                end_line=int(entry.get("end", {}).get("line", 0)),
                severity=str(extra.get("severity", "UNKNOWN")),
                message=str(extra.get("message", "")).strip(),
            ),
        )

    if not findings:
        return SecurityResult.observed_zero(files_scanned, parse_errors, raw_stdout)

    findings.sort(key=lambda f: (_SEVERITY_ORDER.index(f.severity) if f.severity in _SEVERITY_ORDER else 99, f.path))
    return SecurityResult.from_findings(
        files_scanned=files_scanned,
        findings=tuple(findings),
        parse_errors=parse_errors,
        raw_json=raw_stdout,
    )


def run_security_scan(
    repo_root: Path,
    *,
    source_root: Path = _PRODUCT_SOURCE_ROOT,
    timeout: float = _SEMGREP_TIMEOUT_SECONDS,
    which: Callable[[str], str | None] = shutil.which,
) -> SecurityResult:
    """Run semgrep over ``source_root`` and classify the outcome.

    This is the single entry point for every security consumer. ``uvx`` is
    resolved through ``which`` -- an injected seam matching
    ``run_duplication_scan``'s own contract, so a test may supply a resolver
    returning ``None`` or pointing at a different real executable without
    mutating global process state.
    """
    uvx = which("uvx")
    if uvx is None:
        return SecurityResult.unavailable("uvx was not found on PATH")

    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, resolved executable, no shell
            semgrep_command(uvx, source_root),
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SecurityResult.unavailable(f"semgrep exceeded its {timeout:g}s timeout")
    except OSError as exc:
        return SecurityResult.unavailable(f"semgrep could not be launched ({exc})")

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no diagnostic output"
        return SecurityResult.unavailable(f"semgrep exited {completed.returncode}: {tail}")

    return classify_semgrep_output(completed.stdout)


def render_console_report(result: SecurityResult, *, full: bool = False, cap: int = _FINDING_CAP) -> str:
    """Render the operator-facing console report for `just check-security`."""
    out = [f"security: {result.headline()}"]
    if result.parse_errors:
        for err in result.parse_errors[: 5 if not full else len(result.parse_errors)]:
            out.append(f"  [unparsed] {err}")
    if result.outcome is not SecurityOutcome.FINDINGS:
        return "\n".join(out)

    shown = result.findings if full else result.findings[:cap]
    for finding in shown:
        out.append(f"  {finding.severity:<8} {finding.path}:{finding.line}  {finding.check_id}: {finding.message}")
    if len(result.findings) > len(shown):
        out.append(f"  ... {len(result.findings) - len(shown)} more (--full for all)")
    return "\n".join(out)


def main() -> int:
    """Run the security scan and print the reduced console report.

    Always exits 0: matches today's `check-security` behaviour under
    `--config auto` with no login/policy (verified against the live tool --
    it exits 0 with findings present), so this is a representation change,
    not a new gate.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run the security scan and print a reduced console report.")
    parser.add_argument("--full", action="store_true", help="List every finding, uncapped.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    result = run_security_scan(repo_root)

    if args.json:
        print(
            json.dumps(
                {
                    "outcome": result.outcome.value,
                    "headline": result.headline(),
                    "files_scanned": result.files_scanned,
                    "count_by_severity": result.count_by_severity,
                    "parse_errors": list(result.parse_errors),
                    "findings": [
                        {
                            "check_id": f.check_id,
                            "path": f.path,
                            "line": f.line,
                            "end_line": f.end_line,
                            "severity": f.severity,
                            "message": f.message,
                        }
                        for f in result.findings
                    ],
                    "reason": result.reason,
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
    else:
        print(render_console_report(result, full=args.full))

    return 0


if __name__ == "__main__":
    sys.exit(main())
