#!/usr/bin/env python
"""Code complexity and maintainability auditor.

Reports cyclomatic complexity (Radon CC), maintainability index (Radon MI), and
cognitive complexity (Complexipy) against fixed thresholds. Every hit is
reported as it stands.

No ratchet
----------
This audit carried a committed baseline of grandfathered debt and a reviewed
allowlist, and both were retired. There is no ceiling to be within, no
"resolved" notice for an entry that stopped violating, and no ``--strict``
distinction between the two - ``load_baseline`` returns an empty baseline and
says so, and the run's own closing line reports that there is no baseline,
allowlist, or accept flag.

The run therefore FAILS while any hotspot exists, which is the intended reading:
the figure is standing debt, not a regression signal. It stood at 667 production
hotspots when this docstring was reconciled with the code beneath it, which had
already been updated while these paragraphs still described the retired
mechanism.

Scope
-----
The default run audits production code; ``--tests`` audits test files instead.
The two are separate populations rather than a ratchet with two scopes, since
there is no longer a baseline for either to be measured against, and no lane
passes ``--tests`` today.

Keys are stable: ``path::qualified_function_name`` for cyclomatic and cognitive
hits, ``path`` for maintainability files. Line numbers are deliberately excluded
so unrelated edits above a function do not churn a report.

Pass ``--full`` to list every current finding (uncapped) for deep review.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import UTF_8

file_complexity: Callable[[str], Any] | None
try:
    from complexipy import file_complexity as _imported_file_complexity
except ImportError:  # pragma: no cover - environment fallback
    file_complexity = None
else:
    file_complexity = _imported_file_complexity

_UTF_8: Final[str] = UTF_8
_TARGET = "src/cadrumo"
_PROD_EXCLUDE = (
    "src/cadrumo/test_*.py,src/cadrumo/**/test_*.py,src/cadrumo/**/_test_*.py,src/cadrumo/tests/*,src/cadrumo/_data/*"
)
_TEST_EXCLUDE = (
    "src/cadrumo/application/*,src/cadrumo/domain/*,src/cadrumo/adapters/*,src/cadrumo/core/*,src/cadrumo/_data/*"
)
_CC_CAP = 20
_MI_CAP = 15
_COG_CAP = 20
_CC_LINE = re.compile(r"^\s+\w \d+:\d+ (?P<name>\S+) - (?P<grade>[A-F]) \((?P<score>\d+)\)")
_MI_LINE = re.compile(r"^(?P<path>\S+) - (?P<grade>[A-F]) \((?P<score>[\d.]+)\)")

_BASELINE_PATH = Path(__file__).with_name("complexity_baseline.json")
_REPO_ROOT = Path(__file__).resolve().parents[2]


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
        files = scan_directory(root, pattern="test_*.py")
    else:
        files = tuple(
            path
            for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
            if is_production(path)
        )

    if not files:
        # scan_directory returns empty for a root that does not exist, so a moved or
        # misspelled tree yields no files, no hits, and a result indistinguishable from
        # a genuinely clean scan: measured at 101 hits for src/cadrumo against 0 for
        # src/cadrumo_moved_away. The findings count itself must stay free to reach
        # zero, so the guard belongs on the SOURCE rather than on the count.
        message = f"no Python files under {root}: a complexity scan of nothing is not a clean scan"
        raise FileNotFoundError(message)

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


def _cc_key(hit: CcHit) -> str:
    """Stable baseline key for a cyclomatic hit."""
    return f"{hit.path}::{hit.name}"


def _cog_key(hit: CogHit) -> str:
    """Stable baseline key for a cognitive hit."""
    return f"{hit.path}::{hit.name}"


@dataclass(frozen=True)
class Baseline:
    """Grandfathered complexity debt, keyed by stable identifiers.

    ``cyclomatic`` and ``cognitive`` map ``path::function`` to the worst
    (highest) baselined score; ``maintainability`` maps ``path`` to the worst
    (lowest) baselined maintainability index. The worst-per-key convention keeps
    the ratchet sound even if two functions ever share a key.
    """

    cyclomatic: dict[str, int]
    maintainability: dict[str, float]
    cognitive: dict[str, int]

    @classmethod
    def empty(cls) -> Baseline:
        """Return an empty baseline (used when none is committed yet)."""
        return cls(cyclomatic={}, maintainability={}, cognitive={})


def build_baseline(cc: list[CcHit], mi: list[MiHit], cog: list[CogHit]) -> Baseline:
    """Build a baseline from current hits, keeping the worst score per key."""
    cyclomatic: dict[str, int] = {}
    for hit in cc:
        key = _cc_key(hit)
        cyclomatic[key] = max(cyclomatic.get(key, hit.score), hit.score)

    maintainability: dict[str, float] = {}
    for mi_hit in mi:
        # Lower MI is worse; pin the worst (lowest) score per file.
        maintainability[mi_hit.path] = min(maintainability.get(mi_hit.path, mi_hit.score), mi_hit.score)

    cognitive: dict[str, int] = {}
    for cog_hit in cog:
        key = _cog_key(cog_hit)
        cognitive[key] = max(cognitive.get(key, cog_hit.score), cog_hit.score)

    return Baseline(cyclomatic=cyclomatic, maintainability=maintainability, cognitive=cognitive)


def _scope_key(is_test_run: bool) -> str:
    """Top-level baseline section name for the current run scope."""
    return "tests" if is_test_run else "production"


def load_baseline(is_test_run: bool, path: Path = _BASELINE_PATH) -> Baseline:
    """Return an empty baseline: this audit grandfathers nothing.

    The committed baseline and the reviewed allowlist were both retired. Every
    hit the scanners report is now reported as-is, against no ceiling.

    Args:
        is_test_run: Retained for signature compatibility with callers.
        path: Retained for signature compatibility with callers.

    Returns:
        An empty :class:`Baseline`.
    """
    del is_test_run, path
    return Baseline.empty()


def _scope_payload(baseline: Baseline) -> dict[str, dict[str, float]]:
    """Serialise one scope's hits as stably-sorted dicts."""
    return {
        "cyclomatic": dict(sorted(baseline.cyclomatic.items())),
        "maintainability": dict(sorted(baseline.maintainability.items())),
        "cognitive": dict(sorted(baseline.cognitive.items())),
    }


@dataclass(frozen=True)
class Verdict:
    """Partitioned hits for one category: failing, allowed, and resolved keys."""

    new: list[str]
    regressed: list[str]
    allowed: list[str]
    resolved: list[str]

    @property
    def failing(self) -> list[str]:
        """Lines that should fail the audit (new + regressed)."""
        return [*self.new, *self.regressed]


def _classify_cc(hits: list[CcHit], baseline: dict[str, int]) -> Verdict:
    """Partition cyclomatic hits against the baseline ceiling (higher worse)."""
    new: list[str] = []
    regressed: list[str] = []
    allowed: list[str] = []
    seen: set[str] = set()
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        key = _cc_key(hit)
        seen.add(key)
        line = f"  {hit.grade} ({hit.score:>2})  {key}"
        if key not in baseline:
            new.append(f"{line}  [NEW]")
        elif hit.score > baseline[key]:
            regressed.append(f"{line}  [REGRESSED from {baseline[key]}]")
        else:
            allowed.append(line)
    resolved = sorted(key for key in baseline if key not in seen)
    return Verdict(new=new, regressed=regressed, allowed=allowed, resolved=resolved)


def _classify_mi(hits: list[MiHit], baseline: dict[str, float]) -> Verdict:
    """Partition maintainability hits against the baseline floor (lower worse)."""
    new: list[str] = []
    regressed: list[str] = []
    allowed: list[str] = []
    seen: set[str] = set()
    for hit in sorted(hits, key=lambda h: h.score):
        seen.add(hit.path)
        line = f"  {hit.grade} ({hit.score:>5.1f})  {hit.path}"
        if hit.path not in baseline:
            new.append(f"{line}  [NEW]")
        elif hit.score < baseline[hit.path]:
            regressed.append(f"{line}  [REGRESSED from {baseline[hit.path]:.1f}]")
        else:
            allowed.append(line)
    resolved = sorted(key for key in baseline if key not in seen)
    return Verdict(new=new, regressed=regressed, allowed=allowed, resolved=resolved)


def _classify_cog(hits: list[CogHit], baseline: dict[str, int]) -> Verdict:
    """Partition cognitive hits against the baseline ceiling (higher worse)."""
    new: list[str] = []
    regressed: list[str] = []
    allowed: list[str] = []
    seen: set[str] = set()
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        key = _cog_key(hit)
        seen.add(key)
        line = f"  {hit.score:>4}  {key}"
        if key not in baseline:
            new.append(f"{line}  [NEW]")
        elif hit.score > baseline[key]:
            regressed.append(f"{line}  [REGRESSED from {baseline[key]}]")
        else:
            allowed.append(line)
    resolved = sorted(key for key in baseline if key not in seen)
    return Verdict(new=new, regressed=regressed, allowed=allowed, resolved=resolved)


def _emit_failing(label: str, verdict: Verdict) -> None:
    """Print the failing (new/regressed) entries for one category."""
    failing = verdict.failing
    if not failing:
        return
    print(f"\n{label} - NEW or REGRESSED (FAILING):")
    for line in failing:
        print(line)


def _emit_allowed(label: str, verdict: Verdict, full: bool, cap: int) -> None:
    """Print the baselined (allowed) entries for one category, capped."""
    allowed = verdict.allowed
    if not allowed:
        return
    shown = allowed if full else allowed[:cap]
    print(f"\n{label} - baselined debt (allowed, {len(allowed)} entries):")
    for line in shown:
        print(line)
    if len(allowed) > len(shown):
        print(f"         ... {len(allowed) - len(shown)} more baselined")


def _emit_resolved(label: str, verdict: Verdict) -> None:
    """Print resolved baseline entries so the baseline can be shrunk."""
    if not verdict.resolved:
        return
    print(f"\n{label} - resolved (no longer violating, remove from baseline):")
    for key in verdict.resolved:
        print(f"  {key}")


def main() -> int:
    """Run complexity audits against the baseline ratchet."""
    parser = argparse.ArgumentParser(description="Audit code complexity against a grandfathered debt baseline.")
    parser.add_argument("--tests", action="store_true", help="Audit test files instead of production packages.")
    parser.add_argument("--threshold", type=int, default=20, help="Cognitive complexity threshold for complexipy.")
    parser.add_argument("--full", action="store_true", help="List every current finding (uncapped).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail when the baseline lists entries that no longer violate (stale baseline).",
    )
    args = parser.parse_args()

    exclude = _TEST_EXCLUDE if args.tests else _PROD_EXCLUDE
    scope = "test files" if args.tests else "production code"

    # Bracketed ONLY when writing. A peer landing a relocation mid-walk yields a
    # BASELINE naming modules that no longer exist, and that persists; the same
    # race during a comparison run costs at most one noisy verdict the next run
    # corrects. Guarding the comparison too would refuse the CI gate every time
    # any lane touched the tree -- which is how a guard gets removed rather than
    # fixed.
    cc = collect_cc(exclude)
    mi = collect_mi(exclude)
    cog = collect_cog(Path(_TARGET), args.tests, args.threshold)

    # Nothing is grandfathered: the baseline is empty by construction, so every
    # hit the scanners report is classified as a violation on its own merits.
    baseline = load_baseline(args.tests)
    cc_verdict = _classify_cc(cc, baseline.cyclomatic)
    mi_verdict = _classify_mi(mi, baseline.maintainability)
    cog_verdict = _classify_cog(cog, baseline.cognitive)

    failing = len(cc_verdict.failing) + len(mi_verdict.failing) + len(cog_verdict.failing)
    allowed = len(cc_verdict.allowed) + len(mi_verdict.allowed) + len(cog_verdict.allowed)
    resolved = len(cc_verdict.resolved) + len(mi_verdict.resolved) + len(cog_verdict.resolved)

    print(
        f"complexity ({scope}): {failing} new/regressed (FAILING), "
        f"{allowed} baselined (allowed), {resolved} resolved baseline entries.",
    )

    _emit_failing("Cyclomatic complexity (grade C+)", cc_verdict)
    _emit_failing("Maintainability index (grade < A)", mi_verdict)
    _emit_failing(f"Cognitive complexity (> {args.threshold})", cog_verdict)

    _emit_allowed("Cyclomatic complexity (grade C+)", cc_verdict, args.full, _CC_CAP)
    _emit_allowed("Maintainability index (grade < A)", mi_verdict, args.full, _MI_CAP)
    _emit_allowed(f"Cognitive complexity (> {args.threshold})", cog_verdict, args.full, _COG_CAP)

    _emit_resolved("Cyclomatic complexity (grade C+)", cc_verdict)
    _emit_resolved("Maintainability index (grade < A)", mi_verdict)
    _emit_resolved(f"Cognitive complexity (> {args.threshold})", cog_verdict)

    if failing:
        print(
            f"\ncomplexity ({scope}): FAIL - {failing} hotspot(s) over threshold. "
            "Refactor them. There is no baseline, allowlist, or accept flag.",
        )
        return 1

    if args.strict and resolved:
        print(
            f"\ncomplexity ({scope}): FAIL (--strict) - {resolved} entry(ies) no longer violate.",
        )
        return 1

    if resolved:
        print(
            f"\ncomplexity ({scope}): PASS. {resolved} previously-violating entry(ies) resolved.",
        )
    else:
        print(f"\ncomplexity ({scope}): PASS — all current violations are within the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
