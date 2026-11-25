"""Fail while any shipped module is neither reachable from a product command nor used by ``dev/``.

The unreachable-code audit owns discovery, including the ``dev/`` clear: a
module ``dev/`` tooling imports, and what it imports in turn, is in use, while
a module only tests import is still reported.  This gate deliberately has no
baseline, namespace exclusion, or intentional-disposition input: every live
module finding is emitted, and only an empty finding set is green.

A scan that audited nothing, or reached nothing from its roots, measured no
population and is reported as unavailable, never as clean.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from dev.audit.unreachable_code import run_unreachable_code_scan
from dev.audit.unreachable_models import ModuleFinding, ModuleReach, UnreachableCodeOutcome, UnreachableCodeResult
from dev.paths import REPO_ROOT

_NOT_COMMAND_REACHED = frozenset(
    {ModuleReach.UNREACHABLE, ModuleReach.MODULE_EXEC_ONLY, ModuleReach.TYPE_ONLY},
)

_EXIT_FINDINGS = 1
_EXIT_UNAVAILABLE = 2


@dataclass(frozen=True, slots=True)
class UnreachableModuleVerdict:
    """The complete current set of modules no product command reaches and ``dev/`` does not use."""

    findings: tuple[ModuleFinding, ...]
    audited_modules: int = 0
    reachable_modules: int = 0
    #: Non-empty when the measurement itself cannot be trusted; never a finding.
    unavailable: str = ""

    @property
    def is_unavailable(self) -> bool:
        """Whether the population is missing or empty, so no verdict was earned."""
        return bool(self.unavailable)

    @property
    def is_clean(self) -> bool:
        """Whether every shipped module is command-reachable or used by ``dev/``."""
        return not self.findings and not self.is_unavailable

    @property
    def population(self) -> str:
        """State what the verdict covered, so a green result is not silent."""
        return f"{self.audited_modules} audited modules, {self.reachable_modules} reachable at runtime"

    def report(self) -> str:
        """Name every live finding without assigning development status."""
        if self.is_unavailable:
            return f"unreachable-module coverage: unavailable, coverage unproven: {self.unavailable}"
        if self.is_clean:
            return f"unreachable-module coverage: no findings ({self.population})"
        lines = [
            f"unreachable-module coverage: {len(self.findings)} finding(s); expected zero ({self.population})",
        ]
        lines.extend(f"  + {finding.module} ({finding.reach.value}; {finding.path})" for finding in self.findings)
        return "\n".join(lines)


def _population_problem(result: UnreachableCodeResult) -> str:
    if result.outcome is UnreachableCodeOutcome.ERROR:
        return result.reason
    if result.shipped_modules <= 0:
        return "the scan audited no shipped module"
    if result.reachable_modules <= 0:
        return f"none of the {result.shipped_modules} audited modules is reachable from any root"
    return ""


def evaluate(result: UnreachableCodeResult) -> UnreachableModuleVerdict:
    """Project the audit's current module findings into the zero-target gate."""
    problem = _population_problem(result)
    if problem:
        return UnreachableModuleVerdict(findings=(), unavailable=problem)
    return UnreachableModuleVerdict(
        findings=tuple(
            sorted(
                (finding for finding in result.modules if finding.reach in _NOT_COMMAND_REACHED),
                key=lambda finding: finding.module,
            ),
        ),
        audited_modules=result.shipped_modules,
        reachable_modules=result.reachable_modules,
    )


def run_gate(repo_root: Path = REPO_ROOT) -> UnreachableModuleVerdict:
    """Scan the real shipped tree; an unavailable measurement is reported as such."""
    return evaluate(run_unreachable_code_scan(repo_root))


def main() -> int:
    """Print the live set and population; fail on findings (1) or an unavailable measurement (2)."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    if verdict.is_unavailable:
        return _EXIT_UNAVAILABLE
    return 0 if verdict.is_clean else _EXIT_FINDINGS


if __name__ == "__main__":
    raise SystemExit(main())
