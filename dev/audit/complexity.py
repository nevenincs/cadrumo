#!/usr/bin/env python
"""Report every live code-complexity hotspot against fixed detector semantics.

The production tree is measured directly with Radon cyclomatic complexity,
Radon maintainability index, and Complexipy cognitive complexity. There is no
baseline, allowlist, disposition, or development-state partition: every hit is
a current finding and an empty hit set is the only clean result.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cadrumo.core.directory_scan import scan_directory
from dev._paths import UTF_8
from dev.exit_codes import ADVISORY_BROKEN, OK

_TARGET = "src/cadrumo"
_PROD_EXCLUDE = (
    "src/cadrumo/test_*.py,src/cadrumo/**/test_*.py,src/cadrumo/**/_test_*.py,src/cadrumo/tests/*,src/cadrumo/_data/*"
)
_TEST_EXCLUDE = (
    "src/cadrumo/application/*,src/cadrumo/domain/*,src/cadrumo/adapters/*,src/cadrumo/core/*,src/cadrumo/_data/*"
)
_CC_LINE = re.compile(r"^\s+\w \d+:\d+ (?P<name>\S+) - (?P<grade>[A-F]) \((?P<score>\d+)\)")
_MI_LINE = re.compile(r"^(?P<path>\S+) - (?P<grade>[A-F]) \((?P<score>[\d.]+)\)")

file_complexity: Callable[[str], Any] | None
try:
    from complexipy import file_complexity as _imported_file_complexity
except ImportError:  # pragma: no cover - optional audit dependency
    file_complexity = None
else:
    file_complexity = _imported_file_complexity


@dataclass(frozen=True)
class CcHit:
    """One function reported by Radon's cyclomatic-complexity threshold."""

    path: str
    name: str
    grade: str
    score: int

    def render(self) -> str:
        """Render the stable path and measured score."""
        return f"{self.grade} ({self.score:>2})  {self.path}::{self.name}"


@dataclass(frozen=True)
class MiHit:
    """One file reported by Radon's maintainability-index threshold."""

    path: str
    grade: str
    score: float

    def render(self) -> str:
        """Render the stable path and measured score."""
        return f"{self.grade} ({self.score:>5.1f})  {self.path}"


@dataclass(frozen=True)
class CogHit:
    """One function reported by Complexipy's cognitive threshold."""

    path: str
    name: str
    score: int

    def render(self) -> str:
        """Render the stable path and measured score."""
        return f"{self.score:>4}  {self.path}::{self.name}"


@dataclass(frozen=True)
class ComplexityScan:
    """The three live finding populations from one scan."""

    cyclomatic: tuple[CcHit, ...]
    maintainability: tuple[MiHit, ...]
    cognitive: tuple[CogHit, ...]

    @property
    def finding_count(self) -> int:
        """Return the total live finding count."""
        return len(self.cyclomatic) + len(self.maintainability) + len(self.cognitive)

    def rendered_findings(self) -> list[str]:
        """Render every finding without development-state labels."""
        return [
            *(f"cyclomatic: {hit.render()}" for hit in self.cyclomatic),
            *(f"maintainability: {hit.render()}" for hit in self.maintainability),
            *(f"cognitive: {hit.render()}" for hit in self.cognitive),
        ]


def _radon(args: list[str], exclude: str) -> list[str]:
    if not Path(_TARGET).is_dir():
        raise FileNotFoundError(f"complexity target {_TARGET} is not a directory: a scan of nothing is not clean")
    command = ["uv", "run", "--no-sync", "radon", *args]
    if exclude:
        command.extend(["-e", exclude])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no diagnostic output"
        raise RuntimeError(f"radon exited {completed.returncode}: {tail}")
    return completed.stdout.splitlines()


def collect_cc(exclude: str) -> list[CcHit]:
    """Collect cyclomatic hits, worst score first."""
    hits: list[CcHit] = []
    current = "?"
    for line in _radon(["cc", _TARGET, "-n", "C", "-s"], exclude):
        if not line.strip() or line.startswith("Average complexity:"):
            continue
        if not (line.startswith(" ") or line.startswith("\t")):
            current = line.strip().replace("\\", "/")
            continue
        if match := _CC_LINE.match(line):
            hits.append(CcHit(current, match["name"], match["grade"], int(match["score"])))
    return sorted(hits, key=lambda hit: (-hit.score, hit.path, hit.name))


def collect_mi(exclude: str) -> list[MiHit]:
    """Collect maintainability hits, worst score first."""
    hits = [
        MiHit(match["path"].replace("\\", "/"), match["grade"], float(match["score"]))
        for line in _radon(["mi", _TARGET, "-s"], exclude)
        if (match := _MI_LINE.match(line)) and match["grade"] != "A"
    ]
    return sorted(hits, key=lambda hit: (hit.score, hit.path))


def collect_cog(root: Path, is_test_run: bool, threshold: int) -> list[CogHit]:
    """Collect cognitive hits, refusing an empty source population."""
    if file_complexity is None:
        raise RuntimeError("complexipy is unavailable; cognitive-complexity coverage is unproven")

    def is_production(path: Path) -> bool:
        return "_data" not in path.parts and "tests" not in path.parts and not path.name.startswith(("test_", "_test_"))

    files = (
        scan_directory(root, pattern="test_*.py")
        if is_test_run
        else tuple(
            path
            for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
            if is_production(path)
        )
    )
    if not files:
        raise FileNotFoundError(f"no Python files under {root}: a complexity scan of nothing is not clean")
    hits: list[CogHit] = []
    for path in files:
        try:
            result = file_complexity(str(path))
        except Exception as exc:
            raise RuntimeError(f"complexipy could not analyze {path}: {exc}") from exc
        if result is not None:
            hits.extend(
                CogHit(str(path).replace("\\", "/"), function.name, function.complexity)
                for function in result.functions
                if function.complexity > threshold
            )
    return sorted(hits, key=lambda hit: (-hit.score, hit.path, hit.name))


def scan_complexity(*, tests: bool = False, cognitive_threshold: int = 20) -> ComplexityScan:
    """Measure one source scope and return its live findings."""
    exclude = _TEST_EXCLUDE if tests else _PROD_EXCLUDE
    return ComplexityScan(
        cyclomatic=tuple(collect_cc(exclude)),
        maintainability=tuple(collect_mi(exclude)),
        cognitive=tuple(collect_cog(Path(_TARGET), tests, cognitive_threshold)),
    )


def main() -> int:
    """Render the live scan; findings are advisory and tool failure is not."""
    parser = argparse.ArgumentParser(description="Report every current code-complexity hotspot.")
    parser.add_argument("--tests", action="store_true", help="Audit test files instead of production packages.")
    parser.add_argument("--threshold", type=int, default=20, help="Cognitive complexity threshold for Complexipy.")
    args = parser.parse_args()
    try:
        scan = scan_complexity(tests=args.tests, cognitive_threshold=args.threshold)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"complexity audit unavailable: {exc}", file=sys.stderr)
        return ADVISORY_BROKEN
    scope = "test files" if args.tests else "production code"
    print(f"complexity ({scope}): {scan.finding_count} current hotspot(s)")
    for line in scan.rendered_findings():
        print(f"  {line}")
    return OK


if __name__ == "__main__":
    sys.exit(main())
