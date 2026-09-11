"""Fail when a production-readable persistence surface has no production writer."""

from __future__ import annotations

import sys
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.audit.write_path_coverage import WritePathOutcome, WritePathResult, run_write_path_scan


def run_gate(repo_root: Path = REPO_ROOT) -> WritePathResult:
    """Return the live scan, refusing an untrustworthy measurement."""
    result = run_write_path_scan(repo_root)
    if result.outcome is WritePathOutcome.ERROR:
        raise RuntimeError(f"write-path scan unavailable, coverage unproven: {result.reason}")
    return result


def main() -> int:
    """Print every writerless surface and fail unless the live set is empty."""
    result = run_gate()
    if result.is_green:
        return 0
    sys.stderr.write(result.headline() + "\n")
    for finding in result.findings:
        sys.stderr.write(f"  {finding.module}:{finding.service}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
