#!/usr/bin/env python
"""Consolidated static-gate dashboard for the build harness.

Runs every fast static quality gate to completion (not fail-fast), then
reports signal only:

* On full success: silent, exit 0. Green gates are not reported.
* On any failure: a compact dashboard naming each failing gate, replaying
  its actionable output, and listing the gates that passed by name only,
  then exit 1.

Each gate is invoked through its own ``just`` recipe so the per-gate signal
wrappers (``check_types.py``, ``quiet_ok.py``) own the formatting; this
script only aggregates pass/fail and surfaces the failing detail.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

GATES = (
    "check-style",
    "check-format",
    "check-types",
    "check-imports",
    "check-relative-imports",
    "check-dependencies",
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of one gate run."""

    name: str
    returncode: int
    output: str


def _strip_just_noise(output: str) -> str:
    """Drop just's own ``error: Recipe ... failed`` epilogue from gate output."""
    kept = [line for line in output.splitlines() if not line.startswith("error: Recipe `")]
    return "\n".join(kept).strip()


def run_gate(name: str) -> GateResult:
    """Run a single ``just`` gate recipe, capturing combined output."""
    result = subprocess.run(
        ["just", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return GateResult(
        name=name,
        returncode=result.returncode,
        output=_strip_just_noise(result.stdout + result.stderr),
    )


def main() -> int:
    """Run all gates and emit the consolidated dashboard."""
    results = [run_gate(name) for name in GATES]
    failed = [r for r in results if r.returncode != 0]
    passed = [r for r in results if r.returncode == 0]

    if not failed:
        return 0

    print(f"check-all: {len(failed)} of {len(results)} gates failed\n")
    for result in failed:
        print(f"FAIL  {result.name}")
        if result.output:
            print(result.output)
        print()
    if passed:
        print("passed: " + ", ".join(r.name for r in passed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
