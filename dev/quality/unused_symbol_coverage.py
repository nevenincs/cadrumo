"""Fail while exact unused symbols or orphaned tests remain in the live tree."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.audit.unreachable_code import (
    Confidence,
    SymbolFinding,
    TestFinding,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    run_unreachable_code_scan,
)


@dataclass(frozen=True, slots=True)
class UnusedSymbolVerdict:
    """The complete exact-confidence symbol and orphan-test populations."""

    symbols: tuple[SymbolFinding, ...]
    orphan_tests: tuple[TestFinding, ...]

    @property
    def is_clean(self) -> bool:
        """Whether both live exact populations are empty."""
        return not self.symbols and not self.orphan_tests

    def report(self) -> str:
        """Name every exact symbol and orphaned test finding."""
        if self.is_clean:
            return "unused-symbol coverage: no exact findings"
        lines = [
            "unused-symbol coverage: "
            f"{len(self.symbols)} exact symbol finding(s), "
            f"{len(self.orphan_tests)} orphaned test module(s); expected zero",
        ]
        lines.extend(
            f"  + {finding.module}:{finding.qualname} ({finding.path}:{finding.line})" for finding in self.symbols
        )
        lines.extend(f"  + test:{finding.module} ({finding.path})" for finding in self.orphan_tests)
        return "\n".join(lines)


def from_result(result: UnreachableCodeResult) -> UnusedSymbolVerdict:
    """Take every exact finding; no package, status, or identity is excluded."""
    return UnusedSymbolVerdict(
        symbols=tuple(
            sorted(
                (finding for finding in result.symbols if finding.confidence is Confidence.EXACT),
                key=lambda finding: (finding.module, finding.qualname, finding.line),
            ),
        ),
        orphan_tests=tuple(sorted(result.tests, key=lambda finding: finding.module)),
    )


def run_gate(repo_root: Path = REPO_ROOT) -> UnusedSymbolVerdict:
    """Measure the live tree, refusing an unavailable scan."""
    result = run_unreachable_code_scan(repo_root)
    if result.outcome is UnreachableCodeOutcome.ERROR:
        raise RuntimeError(f"reachability scan unavailable, coverage unproven: {result.reason}")
    return from_result(result)


def main() -> int:
    """Print the live set and fail until it is empty."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    return 0 if verdict.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
