#!/usr/bin/env python
"""Zero-noise code complexity and maintainability auditor.

Reports cyclomatic complexity (Radon CC), maintainability index (Radon MI),
and cognitive complexity (Complexipy) as signal only:

* On success (nothing exceeds thresholds): one-line green aggregate, exit 0.
* On findings: a one-line aggregate, then only the most actionable entries
  per category (worst first, capped), with a trailing count of the
  remainder — never an unbounded wall of every borderline function.

Pass ``--full`` to list every finding (uncapped) for deep review.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from complexipy import file_complexity
except ImportError:  # pragma: no cover - environment fallback
    file_complexity = None

_TARGET = "src/aeat"
_PROD_EXCLUDE = "src/aeat/test_*.py,src/aeat/**/test_*.py,src/aeat/**/_test_*.py,src/aeat/tests/*,src/aeat/_data/*"
_TEST_EXCLUDE = "src/aeat/application/*,src/aeat/domain/*,src/aeat/adapters/*,src/aeat/core/*,src/aeat/_data/*"
_CC_CAP = 20
_MI_CAP = 15
_COG_CAP = 20
_CC_LINE = re.compile(r"^\s+\w \d+:\d+ (?P<name>\S+) - (?P<grade>[A-F]) \((?P<score>\d+)\)")
_MI_LINE = re.compile(r"^(?P<path>\S+) - (?P<grade>[A-F]) \((?P<score>[\d.]+)\)")


@dataclass(frozen=True)
class CcHit:
    """One cyclomatic-complexity violation."""

    path: str
    name: str
    grade: str
    score: int


@dataclass(frozen=True)
class MiHit:
    """One maintainability-index violation."""

    path: str
    grade: str
    score: float


@dataclass(frozen=True)
class CogHit:
    """One cognitive-complexity violation."""

    path: str
    name: str
    score: int


def _radon(args: list[str], exclude: str) -> list[str]:
    """Run a radon subcommand and return raw stdout lines."""
    cmd = ["uv", "run", "--no-sync", "radon", *args]
    if exclude:
        cmd.extend(["-e", exclude])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.splitlines()


def collect_cc(exclude: str) -> list[CcHit]:
    """Collect Radon cyclomatic-complexity hits at grade C or worse."""
    lines = _radon(["cc", _TARGET, "-n", "C", "-s"], exclude)
    hits: list[CcHit] = []
    current = "?"
    for line in lines:
        if not line.strip() or line.startswith("Average complexity:"):
            continue
        if not (line.startswith(" ") or line.startswith("\t")):
            current = line.strip().replace("\\", "/")
            continue
        match = _CC_LINE.match(line)
        if match:
            hits.append(
                CcHit(
                    path=current,
                    name=match["name"],
                    grade=match["grade"],
                    score=int(match["score"]),
                ),
            )
    return hits


def collect_mi(exclude: str) -> list[MiHit]:
    """Collect Radon maintainability-index hits below grade A."""
    hits: list[MiHit] = []
    for line in _radon(["mi", _TARGET, "-s"], exclude):
        match = _MI_LINE.match(line)
        if match and match["grade"] != "A":
            hits.append(
                MiHit(
                    path=match["path"].replace("\\", "/"),
                    grade=match["grade"],
                    score=float(match["score"]),
                ),
            )
    return hits


def collect_cog(root: Path, is_test_run: bool, threshold: int) -> list[CogHit]:
    """Collect Complexipy cognitive-complexity hits above the threshold."""
    if file_complexity is None:
        return []

    def is_production(path: Path) -> bool:
        parts = path.parts
        if "_data" in parts or "tests" in parts:
            return False
        name = path.name
        return not (name.startswith("test_") or name.startswith("_test_") or "_test_" in name)

    if is_test_run:
        files = sorted(root.glob("test_*.py"))
    else:
        files = sorted(path for path in root.rglob("*.py") if is_production(path))

    hits: list[CogHit] = []
    for path in files:
        try:
            result = file_complexity(str(path))
        except Exception:
            result = None
        if result is None:
            continue
        for function in result.functions:
            if function.complexity > threshold:
                hits.append(CogHit(path=str(path).replace("\\", "/"), name=function.name, score=function.complexity))
    return hits


def _emit_cc(hits: list[CcHit], full: bool) -> None:
    """Print cyclomatic hits worst-first, capped unless full."""
    ordered = sorted(hits, key=lambda h: h.score, reverse=True)
    shown = ordered if full else ordered[:_CC_CAP]
    print("\nCyclomatic complexity (grade C+):")
    for hit in shown:
        print(f"  {hit.grade} ({hit.score:>2})  {hit.path}::{hit.name}")
    if len(ordered) > len(shown):
        print(f"         ... {len(ordered) - len(shown)} more at grade C+")


def _emit_mi(hits: list[MiHit], full: bool) -> None:
    """Print maintainability hits worst-first, capped unless full."""
    ordered = sorted(hits, key=lambda h: h.score)
    shown = ordered if full else ordered[:_MI_CAP]
    print("\nMaintainability index (grade < A):")
    for hit in shown:
        print(f"  {hit.grade} ({hit.score:>5.1f})  {hit.path}")
    if len(ordered) > len(shown):
        print(f"             ... {len(ordered) - len(shown)} more below grade A")


def _emit_cog(hits: list[CogHit], threshold: int, full: bool) -> None:
    """Print cognitive hits worst-first, capped unless full."""
    ordered = sorted(hits, key=lambda h: h.score, reverse=True)
    shown = ordered if full else ordered[:_COG_CAP]
    print(f"\nCognitive complexity (> {threshold}):")
    for hit in shown:
        print(f"  {hit.score:>4}  {hit.path}::{hit.name}")
    if len(ordered) > len(shown):
        print(f"        ... {len(ordered) - len(shown)} more over threshold")


def main() -> int:
    """Run complexity audits and emit signal-only output."""
    parser = argparse.ArgumentParser(description="Audit code complexity with zero-noise filtering.")
    parser.add_argument("--tests", action="store_true", help="Audit test files instead of production packages.")
    parser.add_argument("--threshold", type=int, default=20, help="Cognitive complexity threshold for complexipy.")
    parser.add_argument("--full", action="store_true", help="List every finding (uncapped).")
    args = parser.parse_args()

    exclude = _TEST_EXCLUDE if args.tests else _PROD_EXCLUDE
    scope = "test files" if args.tests else "production code"

    cc = collect_cc(exclude)
    mi = collect_mi(exclude)
    cog = collect_cog(Path(_TARGET), args.tests, args.threshold)

    if not (cc or mi or cog):
        print(f"complexity ({scope}): no functions or files exceed thresholds.")
        return 0

    print(
        f"complexity ({scope}): {len(cc)} cyclomatic grade C+, "
        f"{len(mi)} maintainability < A, {len(cog)} cognitive > {args.threshold}.",
    )
    if cc:
        _emit_cc(cc, args.full)
    if mi:
        _emit_mi(mi, args.full)
    if cog:
        _emit_cog(cog, args.threshold, args.full)
    return 1


if __name__ == "__main__":
    sys.exit(main())
