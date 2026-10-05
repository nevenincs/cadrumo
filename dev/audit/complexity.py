#!/usr/bin/env python
"""Report every live code-complexity hotspot against fixed detector semantics.

Every first-party source root -- the product package, the agent harness, the
development tooling, and the packaging build hooks -- is measured directly
with Radon cyclomatic complexity, Radon maintainability index, and Complexipy
cognitive complexity. There is no baseline, allowlist, disposition, or
development-state partition: every hit is a current finding and an empty hit
set is the only clean result.

All three detectors measure one population. The file set is enumerated once
from :mod:`dev.first_party_source`, each file is decoded once the way the
interpreter decodes source (BOM and coding cookie honoured), and that text is
handed to every detector in-process. No detector discovers files of its own,
so none can see a different tree. A file any detector cannot measure fails the
whole scan: a partial scan would read as clean, or as a smaller count.

Cyclomatic complexity is reported per block, as Radon defines blocks: every
function, method, closure, and class at any nesting depth, each scored once by
Radon's visitor under its dotted qualified name such as ``Outer.method.closure``.
A closure's branches are not counted in its parent's score.
"""

from __future__ import annotations

import argparse
import ast
import functools
import sys
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev.exit_codes import ADVISORY_BROKEN, OK
from dev.first_party_source import (
    FIRST_PARTY_ROOTS,
    PRODUCT_PACKAGE,
    is_bundled_data,
    is_production_source,
    is_test_source,
)

DEFAULT_COGNITIVE_THRESHOLD: Final[int] = 20
"""Complexipy scores above this are reported."""

_CC_REPORTED_RANK: Final[str] = "C"
_MI_CLEAN_RANK: Final[str] = "A"
# Radon's ``mi`` command counts multiline strings as comments unless told otherwise.
_MI_MULTILINE_STRINGS_AS_COMMENTS: Final[bool] = True

code_complexity: Callable[[str], Any] | None
try:
    from complexipy import code_complexity as _imported_code_complexity
except ImportError:  # pragma: no cover - optional audit dependency
    code_complexity = None
else:
    code_complexity = _imported_code_complexity

radon_metrics: ModuleType | None
radon_visitors: ModuleType | None
radon_complexity: ModuleType | None
try:
    import radon.complexity as _imported_radon_complexity
    import radon.metrics as _imported_radon_metrics
    import radon.visitors as _imported_radon_visitors
except ImportError:  # pragma: no cover - optional audit dependency
    radon_complexity = radon_metrics = radon_visitors = None
else:
    radon_complexity = _imported_radon_complexity
    radon_metrics = _imported_radon_metrics
    radon_visitors = _imported_radon_visitors


class IncompleteScanError(RuntimeError):
    """A detector could not measure a file of the population, so the scan is not clean."""


@dataclass(frozen=True)
class CcHit:
    """One function, method, or closure at or above Radon's reported cyclomatic rank."""

    path: str
    name: str
    grade: str
    score: int

    def render(self) -> str:
        """Render the stable path and measured score."""
        return f"{self.grade} ({self.score:>2})  {self.path}::{self.name}"


@dataclass(frozen=True)
class MiHit:
    """One file below Radon's clean maintainability-index rank."""

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


def _is_test_population(path: Path, *, root: Path) -> bool:
    return is_test_source(path, root=root) and not is_bundled_data(path, root=root)


def source_population(roots: tuple[str, ...], *, tests: bool = False) -> tuple[Path, ...]:
    """Return the one file set every detector measures, refusing an empty root.

    Args:
        roots: The source roots to enumerate; each must exist and contribute files.
        tests: Enumerate the test surface instead of production source.
    """
    admit = _is_test_population if tests else is_production_source
    population: list[Path] = []
    for root in roots:
        anchor = Path(root)
        if not anchor.is_dir():
            raise FileNotFoundError(f"complexity target {root} is not a directory: a scan of nothing is not clean")
        candidates = scan_directory(
            anchor, pattern="*.py", recursive=True, select=DirectoryEntryKind.FILES, prune_directories=("__pycache__",)
        )
        admitted = [path for path in candidates if admit(path, root=anchor)]
        if not admitted:
            raise FileNotFoundError(f"no Python files under {root}: a complexity scan of nothing is not clean")
        population.extend(admitted)
    return tuple(population)


def read_source(path: Path) -> str:
    """Decode *path* as the interpreter would, honouring a BOM or coding cookie."""
    with tokenize.open(path) as handle:
        return handle.read()


def _blocks(
    node: ast.AST, prefix: str = ""
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]]:
    """Yield every function, method, closure, and class below *node* with its dotted qualified name."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            continue
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            name = f"{prefix}{child.name}"
            yield name, child
            yield from _blocks(child, f"{name}.")
        else:
            yield from _blocks(child, prefix)


def cyclomatic_hits(path: str, source: str) -> list[CcHit]:
    """Return every block in *source* at or above the reported cyclomatic rank.

    Each block is scored on its own by Radon's visitor, which leaves a nested
    function's branches out of its parent function, so no branch is counted
    twice and no nested definition goes unmeasured.
    """
    if radon_visitors is None or radon_complexity is None:
        raise RuntimeError("radon is unavailable; cyclomatic-complexity coverage is unproven")
    hits: list[CcHit] = []
    for name, node in _blocks(ast.parse(source, filename=path)):
        visitor = radon_visitors.ComplexityVisitor.from_ast(node)
        (block,) = visitor.classes if isinstance(node, ast.ClassDef) else visitor.functions
        grade = radon_complexity.cc_rank(block.complexity)
        if grade >= _CC_REPORTED_RANK:
            hits.append(CcHit(path, name, grade, block.complexity))
    return hits


def maintainability_hits(path: str, source: str) -> list[MiHit]:
    """Return *path*'s maintainability finding, or nothing when it ranks clean."""
    if radon_metrics is None:
        raise RuntimeError("radon is unavailable; maintainability-index coverage is unproven")
    score = radon_metrics.mi_visit(source, _MI_MULTILINE_STRINGS_AS_COMMENTS)
    grade = radon_metrics.mi_rank(score)
    return [] if grade == _MI_CLEAN_RANK else [MiHit(path, grade, float(score))]


def cognitive_hits(path: str, source: str, threshold: int) -> list[CogHit]:
    """Return every function in *source* whose cognitive complexity exceeds *threshold*."""
    if code_complexity is None:
        raise RuntimeError("complexipy is unavailable; cognitive-complexity coverage is unproven")
    result = code_complexity(source)
    return [
        CogHit(path, function.name, function.complexity)
        for function in result.functions
        if function.complexity > threshold
    ]


def _attempt[Hit](
    detector: str, measure: Callable[[str, str], list[Hit]], path: str, source: str, failures: list[str]
) -> list[Hit]:
    """Run one detector over one file, recording rather than hiding a failure."""
    try:
        return measure(path, source)
    except Exception as exc:
        failures.append(f"{path} ({detector}: {type(exc).__name__}: {exc})")
        return []


def measure_population(files: tuple[Path, ...], *, cognitive_threshold: int) -> ComplexityScan:
    """Measure every file with all three detectors, failing closed on any file one cannot measure."""
    cognitive_detector = functools.partial(cognitive_hits, threshold=cognitive_threshold)
    cyclomatic: list[CcHit] = []
    maintainability: list[MiHit] = []
    cognitive: list[CogHit] = []
    failures: list[str] = []
    for file in files:
        path = file.as_posix()
        try:
            source = read_source(file)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            failures.append(f"{path} (unreadable source: {exc})")
            continue
        cyclomatic.extend(_attempt("radon cyclomatic", cyclomatic_hits, path, source, failures))
        maintainability.extend(_attempt("radon maintainability", maintainability_hits, path, source, failures))
        cognitive.extend(_attempt("complexipy cognitive", cognitive_detector, path, source, failures))
    if failures:
        raise IncompleteScanError(
            f"{len(failures)} measurement(s) failed, so the scan is incomplete and not clean: {'; '.join(failures)}"
        )
    return ComplexityScan(
        cyclomatic=tuple(sorted(cyclomatic, key=lambda hit: (-hit.score, hit.path, hit.name))),
        maintainability=tuple(sorted(maintainability, key=lambda hit: (hit.score, hit.path))),
        cognitive=tuple(sorted(cognitive, key=lambda hit: (-hit.score, hit.path, hit.name))),
    )


def scan_complexity(
    *,
    tests: bool = False,
    cognitive_threshold: int = DEFAULT_COGNITIVE_THRESHOLD,
    roots: tuple[str, ...] | None = None,
) -> ComplexityScan:
    """Measure one source scope and return its live findings.

    The production scope covers every root in ``roots``, all first-party roots
    by default; the test scope covers the product package's test surface. Each
    root must exist and yield source files, so a dropped or renamed root fails
    the scan instead of silently shrinking it.
    """
    scope = roots if roots is not None else ((PRODUCT_PACKAGE,) if tests else FIRST_PARTY_ROOTS)
    return measure_population(source_population(scope, tests=tests), cognitive_threshold=cognitive_threshold)


def main() -> int:
    """Render the live scan; findings are advisory and tool failure is not."""
    parser = argparse.ArgumentParser(description="Report every current code-complexity hotspot.")
    parser.add_argument("--tests", action="store_true", help="Audit test files instead of production packages.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_COGNITIVE_THRESHOLD,
        help="Cognitive complexity threshold for Complexipy.",
    )
    args = parser.parse_args()
    try:
        scan = scan_complexity(tests=args.tests, cognitive_threshold=args.threshold)
    except (OSError, RuntimeError) as exc:
        print(f"complexity audit unavailable: {exc}", file=sys.stderr)
        return ADVISORY_BROKEN
    scope = f"test files in {PRODUCT_PACKAGE}" if args.tests else f"production code in {', '.join(FIRST_PARTY_ROOTS)}"
    print(f"complexity ({scope}): {scan.finding_count} current hotspot(s)")
    for line in scan.rendered_findings():
        print(f"  {line}")
    return OK


if __name__ == "__main__":
    sys.exit(main())
