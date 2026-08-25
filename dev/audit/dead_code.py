#!/usr/bin/env python
"""The single canonical vulture runner: invoke it, parse it, classify it honestly.

Mirrors ``dev.audit.duplication``'s "the runner owns the whole measurement"
shape, scaled to vulture's simpler risk profile: unlike ``npx``/jscpd or
``uvx``/semgrep, vulture is a project dev-dependency resolved through
``uv run --no-sync`` (the same way ``dev.audit.complexity`` invokes
``radon``), so there is no realistic "binary missing" case to model with an
injectable resolver -- a synced environment always has it.

vulture's own exit codes carry the classification: ``0`` is a clean scan,
``3`` is a scan that found dead code, anything else (``1`` invalid input,
``2`` invalid config, or a subprocess-level failure) is a genuine tool error
that must never be read as clean.

The whitelist (``dev/audit/vulture_whitelist.py``) already clears individually
reviewed false positives before this module ever sees the output, so every
finding remaining here has already passed that filter -- see the whitelist's
own docstring for the reviewed exceptions it carries.

See Also:
    :mod:`dev.audit.duplication`
        The stricter sibling runner for an external, possibly-absent tool.
    :func:`run_dead_code_scan`
        The one entry point both ``just audit-dead-code`` and
        ``dev.audit.advisory`` call.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8
_TARGETS: Final[tuple[str, ...]] = ("src/cadrumo", "dev/audit/vulture_whitelist.py")
_FINDING_CAP: Final[int] = 40
_VULTURE_TIMEOUT_SECONDS: Final[float] = 180.0

# vulture's stable line shape: `path:line: message (NN% confidence)`.
_LINE: Final = re.compile(r"^(?P<path>.+):(?P<line>\d+): (?P<message>.+) \((?P<confidence>\d+)% confidence\)$")

_EXIT_CLEAN: Final = 0
_EXIT_FINDINGS: Final = 3


class DeadCodeOutcome(StrEnum):
    """The three honest states a vulture scan can land in."""

    CLEAN = "clean"
    FINDINGS = "findings"
    ERROR = "error"


@dataclass(frozen=True)
class DeadCodeFinding:
    """One vulture finding: a path, a line, a message, and a confidence percentage."""

    path: str
    line: int
    message: str
    confidence: int


@dataclass(frozen=True)
class DeadCodeResult:
    """A dead-code scan's typed outcome.

    Construct through :meth:`clean`, :meth:`from_findings`, or :meth:`error`
    rather than directly, so the invariants binding each outcome to its
    evidence hold by construction.
    """

    outcome: DeadCodeOutcome
    findings: tuple[DeadCodeFinding, ...] = ()
    reason: str = ""

    @classmethod
    def clean(cls) -> DeadCodeResult:
        """A scan that found no dead code."""
        return cls(outcome=DeadCodeOutcome.CLEAN)

    @classmethod
    def from_findings(cls, findings: tuple[DeadCodeFinding, ...]) -> DeadCodeResult:
        """A scan that found dead code."""
        if not findings:
            msg = "from_findings requires at least one finding"
            raise ValueError(msg)
        return cls(outcome=DeadCodeOutcome.FINDINGS, findings=findings)

    @classmethod
    def error(cls, reason: str) -> DeadCodeResult:
        """A scan that could not produce a trustworthy result; ``reason`` says why."""
        return cls(outcome=DeadCodeOutcome.ERROR, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict."""
        return self.outcome is DeadCodeOutcome.CLEAN

    @property
    def count_by_confidence(self) -> dict[str, int]:
        """Finding counts bucketed into a coarse severity-like axis.

        vulture reports a bare confidence percentage rather than a named
        severity; ``high`` (>=80%) versus ``moderate`` (<80%) is the closest
        honest analogue, computed here rather than invented by a caller.
        """
        buckets = {"high (>=80%)": 0, "moderate (<80%)": 0}
        for finding in self.findings:
            key = "high (>=80%)" if finding.confidence >= 80 else "moderate (<80%)"
            buckets[key] += 1
        return {key: count for key, count in buckets.items() if count}

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is DeadCodeOutcome.ERROR:
            return f"dead-code signal unavailable this cycle: {self.reason}"
        if self.outcome is DeadCodeOutcome.CLEAN:
            return "no dead code found"
        breakdown = ", ".join(f"{count} {label}" for label, count in self.count_by_confidence.items())
        return f"{len(self.findings)} dead-code finding(s) past the reviewed whitelist ({breakdown})"


def vulture_command() -> list[str]:
    """Build the one vulture command line, matching today's `just audit-dead-code`."""
    return ["uv", "run", "--no-sync", "vulture", "--config", "pyproject.toml", *_TARGETS]


def parse_vulture_output(stdout: str) -> tuple[DeadCodeFinding, ...]:
    """Parse vulture's `path:line: message (NN% confidence)` lines."""
    findings: list[DeadCodeFinding] = []
    for line in stdout.splitlines():
        match = _LINE.match(line.strip())
        if not match:
            continue
        findings.append(
            DeadCodeFinding(
                path=match["path"].replace("\\", "/"),
                line=int(match["line"]),
                message=match["message"],
                confidence=int(match["confidence"]),
            ),
        )
    return tuple(findings)


def run_dead_code_scan(repo_root: Path, *, timeout: float = _VULTURE_TIMEOUT_SECONDS) -> DeadCodeResult:
    """Run vulture over the production tree and classify the outcome.

    This is the single entry point for every dead-code consumer -- both
    ``just audit-dead-code`` and ``dev.audit.advisory`` call it, so there is
    deliberately no second vulture invocation anywhere in the tree.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            vulture_command(),
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return DeadCodeResult.error(f"vulture exceeded its {timeout:g}s timeout")
    except OSError as exc:
        return DeadCodeResult.error(f"vulture could not be launched ({exc})")

    if completed.returncode == _EXIT_CLEAN:
        return DeadCodeResult.clean()

    if completed.returncode == _EXIT_FINDINGS:
        findings = parse_vulture_output(completed.stdout)
        if not findings:
            return DeadCodeResult.error(
                "vulture exited 3 (findings expected) but produced no parseable finding line",
            )
        return DeadCodeResult.from_findings(findings)

    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    tail = detail[-1] if detail else "no diagnostic output"
    return DeadCodeResult.error(f"vulture exited {completed.returncode}: {tail}")


def render_console_report(result: DeadCodeResult, *, full: bool = False, cap: int = _FINDING_CAP) -> str:
    """Render the operator-facing console report for `just audit-dead-code`."""
    out = [f"dead code: {result.headline()}"]
    if result.outcome is not DeadCodeOutcome.FINDINGS:
        return out[0]

    shown = result.findings if full else result.findings[:cap]
    for finding in shown:
        out.append(f"  {finding.confidence:>3}%  {finding.path}:{finding.line}  {finding.message}")
    if len(result.findings) > len(shown):
        out.append(f"  ... {len(result.findings) - len(shown)} more (--full for all)")
    return "\n".join(out)


def main() -> int:
    """Run the dead-code scan and print the reduced console report.

    Preserves today's exit-code contract: non-zero when dead code is found
    (matching vulture's own exit 3), 0 when clean, 1 on a tool error --
    `just audit-all` already tolerates this via its own advisory posture.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Scan for dead code past the reviewed whitelist.")
    parser.add_argument("--full", action="store_true", help="List every finding, uncapped.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    result = run_dead_code_scan(repo_root)

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "outcome": result.outcome.value,
                    "headline": result.headline(),
                    "count_by_confidence": result.count_by_confidence,
                    "findings": [
                        {
                            "path": f.path,
                            "line": f.line,
                            "message": f.message,
                            "confidence": f.confidence,
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

    if result.outcome is DeadCodeOutcome.ERROR:
        return 1
    if result.outcome is DeadCodeOutcome.FINDINGS:
        return _EXIT_FINDINGS
    return 0


if __name__ == "__main__":
    sys.exit(main())
