"""Fail while any shipped module is not reachable from a product command.

The unreachable-code audit owns discovery.  This gate deliberately has no
baseline, namespace exclusion, or intentional-disposition input: every live
module finding is emitted, and only an empty finding set is green.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .._paths import REPO_ROOT
from ..audit.unreachable_code import (
    ModuleFinding,
    ModuleReach,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    run_unreachable_code_scan,
)

_NOT_COMMAND_REACHED = frozenset(
    {ModuleReach.UNREACHABLE, ModuleReach.MODULE_EXEC_ONLY, ModuleReach.TYPE_ONLY},
)


@dataclass(frozen=True, slots=True)
class UnreachableModuleVerdict:
    """The complete current set of modules no product command reaches."""

    findings: tuple[ModuleFinding, ...]

    @property
    def is_clean(self) -> bool:
        """Whether every shipped module is command-reachable."""
        return not self.findings

    def report(self) -> str:
        """Name every live finding without assigning development status."""
        if self.is_clean:
            return "unreachable-module coverage: no findings"
        lines = [
            f"unreachable-module coverage: {len(self.findings)} finding(s); expected zero",
        ]
        lines.extend(f"  + {finding.module} ({finding.reach.value}; {finding.path})" for finding in self.findings)
        return "\n".join(lines)


def evaluate(result: UnreachableCodeResult) -> UnreachableModuleVerdict:
    """Project the audit's current module findings into the zero-target gate."""
    return UnreachableModuleVerdict(
        findings=tuple(
            sorted(
                (finding for finding in result.modules if finding.reach in _NOT_COMMAND_REACHED),
                key=lambda finding: finding.module,
            ),
        ),
    )


def run_gate(repo_root: Path = REPO_ROOT) -> UnreachableModuleVerdict:
    """Scan the real shipped tree, refusing an unavailable measurement."""
    result = run_unreachable_code_scan(repo_root)
    if result.outcome is UnreachableCodeOutcome.ERROR:
        raise RuntimeError(f"reachability scan unavailable, coverage unproven: {result.reason}")
    return evaluate(result)


def main() -> int:
    """Print the live set and fail until it is empty."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    return 0 if verdict.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
