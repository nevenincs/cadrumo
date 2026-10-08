#!/usr/bin/env python
"""The single canonical vulture runner: invoke it, parse it, classify it honestly.

Mirrors ``dev.audit.duplication``'s "the runner owns the whole measurement"
shape, scaled to vulture's simpler risk profile: unlike ``npx``/jscpd or
``uvx``/semgrep, vulture is a project dev-dependency resolved through
``uv run --no-sync`` (the same way ``dev.audit.complexity`` invokes
``radon``), so there is no realistic "binary missing" case to model with an
injectable resolver -- a synced environment always has it.

vulture's own exit codes carry most of the classification: ``0`` is a clean
scan, ``3`` is a scan that found dead code, anything else (``2`` invalid
config, or a subprocess-level failure) is a genuine tool error that must never
be read as clean.

The exit code alone cannot say whether the scan was complete. vulture skips a
module it cannot decode or parse, reports it on stderr, and carries on with the
rest: it then exits ``1`` when the other modules hold no finding, but ``3``
when they do, so a partial scan with findings looks exactly like a complete
one on the exit code. Every skip diagnostic on stderr therefore makes the
result unavailable, naming the skipped modules, and so does any stderr line
this module does not recognise -- an unknown diagnostic may be a skip whose
wording changed. Python warnings emitted while parsing (a ``SyntaxWarning``
for an invalid escape, say) are recognised and ignored: the module was parsed.

The whitelist (``dev/audit/vulture_whitelist.py``) already clears individually
reviewed false positives before this module ever sees the output, so every
finding remaining here has already passed that filter -- see the whitelist's
own docstring for the reviewed exceptions it carries.

See Also:
    :mod:`dev.audit.duplication`
        The stricter sibling runner for an external, possibly-absent tool.
    :func:`run_dead_code_scan`
        The one entry point both ``just audit-dead-weight`` (through
        ``dev.audit.dead_weight``) and ``just audit-code`` (through
        ``dev.audit.advisory``) call.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Final

from vulture.config import InputError, make_config

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import ADVISORY_BROKEN, OK
from dev.first_party_source import DEVELOPMENT_TOOLING, HARNESS_PACKAGE, PACKAGING_HOOKS, PRODUCT_PACKAGE
from dev.packaging.command_execution import CommandResult, run_command

_UTF_8: Final[str] = UTF_8
_TARGETS: Final[tuple[str, ...]] = (PRODUCT_PACKAGE, "dev/audit/vulture_whitelist.py")
_FINDING_CAP: Final[int] = 40
_VULTURE_TIMEOUT_SECONDS: Final[float] = 180.0

# vulture's stable line shape: `path:line: message (NN% confidence)`.
_LINE: Final = re.compile(r"^(?P<path>.+):(?P<line>\d+): (?P<message>.+) \((?P<confidence>\d+)% confidence\)$")

# The stderr shapes vulture 2.16 writes when it skips a module (``Core.scan``
# and ``Core.scavenge``): an undecodable file, a SyntaxError (``None`` as the
# line for a null byte), and the older ValueError wording for a null byte.
_SKIPPED_UNREADABLE: Final = re.compile(r"^Error: Could not read file (?P<path>.+?) -(?: (?P<reason>.*))?$")
_SKIPPED_UNREADABLE_HINT: Final = "Try to change the encoding to UTF-8."
_SKIPPED_INVALID_SOURCE: Final = re.compile(r'^(?P<path>.+?): invalid source code "(?P<reason>.*)"$')
_SKIPPED_UNPARSEABLE: Final = re.compile(r"^(?P<path>.+?):(?:\d+|None): (?P<reason>.+)$")
# ``warnings.formatwarning``: ``path:line: Category: message``, optionally
# followed by the offending source line indented by two spaces.
_PYTHON_WARNING: Final = re.compile(r"^.+?:\d+: \w*Warning: ")
_WARNING_SOURCE_LINE: Final = "  "
# ``uv run`` itself prefixes its launcher warnings (a mismatched VIRTUAL_ENV,
# say) this way; vulture never does, and they say nothing about coverage.
_UV_LAUNCHER_WARNING: Final = "warning: "

_EXIT_CLEAN: Final = 0
_EXIT_INVALID_INPUT: Final = 1
_EXIT_FINDINGS: Final = 3

# The floor counts what vulture is meant to analyse: production modules as
# ``dev.first_party_source`` classifies them, not the test modules vulture's
# config excludes. src/cadrumo held 2810 such modules, plus the whitelist file,
# when this floor was set. A bare ``> 0`` check would be satisfied by that
# single whitelist file alone, so it could not see src/cadrumo disappear --
# which is the degradation that makes a clean scan vacuous. The floor sits
# near half the live population, matching the sibling stub-population floor,
# so ordinary churn cannot trip it and a wholesale loss cannot hide.
MINIMUM_OFFERED_MODULES: Final = 1400


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
class SkippedModule:
    """One module vulture reported on stderr and then left out of its analysis."""

    path: str
    reason: str


@dataclass(frozen=True)
class VultureDiagnostics:
    """vulture's stderr, split into skipped modules and lines nothing here recognises."""

    skipped: tuple[SkippedModule, ...] = ()
    unrecognised: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeadCodeResult:
    """A dead-code scan's typed outcome.

    Construct through :meth:`clean`, :meth:`from_findings`, or :meth:`error`
    rather than directly, so the invariants binding each outcome to its
    evidence hold by construction.
    """

    outcome: DeadCodeOutcome
    modules_offered: int = 0
    findings: tuple[DeadCodeFinding, ...] = ()
    reason: str = ""

    @classmethod
    def clean(cls, *, modules_offered: int) -> DeadCodeResult:
        """A scan that inspected ``modules_offered`` modules and found no dead code."""
        if modules_offered <= 0:
            msg = "clean requires a scan that demonstrably inspected modules"
            raise ValueError(msg)
        return cls(outcome=DeadCodeOutcome.CLEAN, modules_offered=modules_offered)

    @classmethod
    def from_findings(
        cls,
        findings: tuple[DeadCodeFinding, ...],
        *,
        modules_offered: int = 0,
    ) -> DeadCodeResult:
        """A scan that found dead code."""
        if not findings:
            msg = "from_findings requires at least one finding"
            raise ValueError(msg)
        return cls(
            outcome=DeadCodeOutcome.FINDINGS,
            modules_offered=modules_offered,
            findings=findings,
        )

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
            return f"Python product dead-code signal unavailable this cycle: {self.reason}"
        if self.outcome is DeadCodeOutcome.CLEAN:
            # The denominator travels with the verdict: a green that does not say
            # how much it read cannot be told from a green that read nothing.
            return f"no Python product dead code found across {self.modules_offered} module(s)"
        breakdown = ", ".join(f"{count} {label}" for label, count in self.count_by_confidence.items())
        return (
            f"{len(self.findings)} Python product dead-code finding(s) past the reviewed whitelist "
            f"({breakdown}) across {self.modules_offered} module(s)"
        )


def dead_code_scope() -> dict[str, object]:
    """Declare the Python audit's subject and the surfaces it cannot measure."""
    return {
        "language": "python",
        "source_root": PRODUCT_PACKAGE,
        "support_files": list(_TARGETS[1:]),
        "excluded_roots": [HARNESS_PACKAGE, DEVELOPMENT_TOOLING, PACKAGING_HOOKS, "native"],
        "excluded_surfaces": [
            "tests and bundled data",
            "CMake configuration and build tools",
            "Rust, C and desktop frontend sources",
            "generated build outputs and compiled binaries",
        ],
    }


def offered_module_population(repo_root: Path) -> int:
    """Count the production modules :data:`_TARGETS` offers vulture.

    Vulture exits 0 both when it inspected the production tree and found
    nothing and when it inspected nothing at all, so the exit code alone
    cannot tell a clean scan from a vacuous one. This count is the
    denominator that distinguishes them, exactly as the sibling duplication
    and security scans use their tool-reported file counts.

    Read Vulture's effective configuration, including its defaults and CLI
    precedence. Match its case-insensitive absolute-path exclusion rules so
    an over-broad exclude cannot leave the population floor satisfied by
    modules the scanner never reads. Skipped unreadable or unparseable
    modules are caught separately from stderr.
    """
    config = make_config(["--config", str(repo_root / "pyproject.toml"), *_TARGETS])
    patterns = tuple(
        (pattern if any(char in pattern for char in "*?[") else f"*{pattern}*").lower() for pattern in config["exclude"]
    )
    offered = 0
    for target in _TARGETS:
        candidate = (repo_root / target).resolve()
        modules = (candidate,) if candidate.is_file() else candidate.rglob("*.py") if candidate.is_dir() else ()
        offered += sum(
            1 for module in modules if not any(fnmatchcase(str(module).lower(), pattern) for pattern in patterns)
        )
    return offered


def vulture_command() -> list[str]:
    """Build the one vulture command line every dead-code consumer runs."""
    return ["uv", "run", "--no-sync", "vulture", "--config", "pyproject.toml", *_TARGETS]


def parse_vulture_stderr(stderr: str) -> VultureDiagnostics:
    """Split vulture's stderr into skipped modules and unrecognised lines.

    Python warnings raised while parsing a module, and the source line the
    warning machinery prints beneath one, are recognised and dropped: the
    module they name was still analysed. So are ``uv run``'s own launcher
    warnings, which come from the process that starts vulture.
    """
    skipped: list[SkippedModule] = []
    unrecognised: list[str] = []
    after_warning = False
    for raw in stderr.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if after_warning and line.startswith(_WARNING_SOURCE_LINE):
            after_warning = False
            continue
        after_warning = False
        if _PYTHON_WARNING.match(line):
            after_warning = True
            continue
        if line == _SKIPPED_UNREADABLE_HINT or line.startswith(_UV_LAUNCHER_WARNING):
            continue
        match = _skipped_module_match(line)
        if match is None:
            unrecognised.append(line)
            continue
        skipped.append(
            SkippedModule(
                path=match["path"].replace("\\", "/"),
                reason=match["reason"] or "could not be read",
            ),
        )
    return VultureDiagnostics(skipped=tuple(skipped), unrecognised=tuple(unrecognised))


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
    ``dev.audit.dead_weight`` and ``dev.audit.advisory`` call it, so there is
    deliberately no second vulture invocation anywhere in the tree.
    """
    try:
        offered = offered_module_population(repo_root)
    except (InputError, OSError, TypeError, ValueError, SystemExit) as exc:
        return DeadCodeResult.error(f"vulture configuration could not be read ({exc})")
    if offered < MINIMUM_OFFERED_MODULES:
        return DeadCodeResult.error(
            f"vulture was offered {offered} Python module(s), under the "
            f"{MINIMUM_OFFERED_MODULES} the production tree must hold, so exit 0 "
            "would prove nothing about dead code",
        )

    try:
        completed = run_command(
            vulture_command(),
            errors="replace",
            cwd=repo_root,
            timeout_seconds=timeout,
        )
    except subprocess.TimeoutExpired:
        return DeadCodeResult.error(f"vulture exceeded its {timeout:g}s timeout")
    except OSError as exc:
        return DeadCodeResult.error(f"vulture could not be launched ({exc})")

    error = _vulture_diagnostic_error(completed)
    if error is not None:
        return error

    if completed.returncode == _EXIT_CLEAN:
        return DeadCodeResult.clean(modules_offered=offered)

    if completed.returncode == _EXIT_FINDINGS:
        findings = parse_vulture_output(completed.stdout)
        if not findings:
            return DeadCodeResult.error(
                "vulture exited 3 (findings expected) but produced no parseable finding line",
            )
        return DeadCodeResult.from_findings(findings, modules_offered=offered)

    tail = _vulture_error_tail(completed)
    return DeadCodeResult.error(f"vulture exited {completed.returncode}: {tail}")


def render_console_report(result: DeadCodeResult, *, full: bool = False, cap: int = _FINDING_CAP) -> str:
    """Render the operator-facing console report for ``python -m dev.audit.dead_code``."""
    out = [
        f"dead code: {result.headline()}",
        f"  scope: {PRODUCT_PACKAGE} Python source and the reviewed whitelist",
        "  excluded: harness, dev/packaging tools, native Rust/C/desktop, CMake, build outputs and binaries; "
        "tests and bundled data",
    ]
    if result.outcome is not DeadCodeOutcome.FINDINGS:
        return "\n".join(out)

    shown = result.findings if full else result.findings[:cap]
    for finding in shown:
        out.append(f"  {finding.confidence:>3}%  {finding.path}:{finding.line}  {finding.message}")
    if len(result.findings) > len(shown):
        out.append(f"  ... {len(result.findings) - len(shown)} more (--full for all)")
    return "\n".join(out)


def main() -> int:
    """Run the dead-code scan and print the reduced console report.

    Findings are advisory and therefore return 0. A scan that cannot run
    returns the shared advisory-broken status so missing evidence is not read
    as a clean result.
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
                    "modules_offered": result.modules_offered,
                    "scope": dead_code_scope(),
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
        return ADVISORY_BROKEN
    if result.outcome is DeadCodeOutcome.FINDINGS:
        return OK
    return OK


def _vulture_error_tail(completed: CommandResult) -> str:
    """Prefer stderr, then stdout, and report the final diagnostic line."""
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return detail[-1] if detail else "no diagnostic output"


def _vulture_diagnostic_error(completed: CommandResult) -> DeadCodeResult | None:
    """Refuse partial or unrecognised diagnostics before interpreting the scanner verdict."""
    if completed.returncode in {_EXIT_CLEAN, _EXIT_INVALID_INPUT, _EXIT_FINDINGS}:
        diagnostics = parse_vulture_stderr(completed.stderr or "")
        if diagnostics.skipped:
            named = "; ".join(f"{module.path} ({module.reason})" for module in diagnostics.skipped)
            return DeadCodeResult.error(
                f"vulture skipped {len(diagnostics.skipped)} module(s) it could not read or parse, "
                f"so its finding list is partial: {named}",
            )
        if diagnostics.unrecognised:
            return DeadCodeResult.error(
                f"vulture exited {completed.returncode} with an unrecognised stderr diagnostic, "
                f"so the scan cannot be shown complete: {diagnostics.unrecognised[0]}",
            )
    return None


def _skipped_module_match(line: str) -> re.Match[str] | None:
    """Match exactly the existing unreadable, invalid-source and unparseable diagnostics."""
    return _SKIPPED_UNREADABLE.match(line) or _SKIPPED_INVALID_SOURCE.match(line) or _SKIPPED_UNPARSEABLE.match(line)


if __name__ == "__main__":
    sys.exit(main())
