"""Measurement and policy substrate for the module/callable size ratchet.

The size budget is a two-sided band, not a one-sided ceiling. A one-sided
ceiling decays silently: an oversize module is pinned at its present size, a
later pass splits or shrinks it, the pin is never lowered, and the module can
then regrow by the whole accumulated gap while the gate reports green. That is
not hypothetical — the hand-maintained pin table this module replaces had
accumulated 9139 lines of aggregate positive slack, with several entries sitting
below the DEFAULT limit (their override was pure dead weight) while their
comments claimed they were pinned at exactly the present size with no headroom.

Two properties are therefore enforced together:

* **Over budget** — an entry whose measured size exceeds its limit. This is the
  original ratchet and is unchanged in spirit.
* **Stale pin** — an entry whose limit sits further above its measured size than
  the declared slack tolerance, or that no longer needs an entry at all. A stale
  pin is a real defect: it is precisely the window of invisible regrowth, and
  making it fail converts a decaying ceiling into a self-correcting one.

Limits are GENERATED, never hand-written, because the hand-maintained numbers
are what went stale rather than the mechanism. Regenerate with the size-budget
authoring tool; review and commit the diff.

Headroom policy, stated explicitly so no comment has to claim it: an entry is
pinned at its measured size plus five percent (floored at a small absolute
allowance), and the slack tolerance is ten percent of the limit (likewise
floored). Zero-headroom pins were tried and are what produced the churn this
module removes: in a tree with many concurrent authors they red on the next
landing, get hand-raised, and the hand-raise is where the prose goes stale. A
declared, bounded, symmetric band lets ordinary churn through while keeping the
invisible-regrowth window an order of magnitude smaller than the gap it
replaces.

Every scan asserts its corpus is non-empty and above a floor. An empty scan that
passes is the exact defect class this gate exists to refuse.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ._inventory import REPO_ROOT, package_ast_items, package_python_files

__all__ = [
    "CALLABLE_POLICY",
    "MIN_SCANNED_CALLABLES",
    "MIN_SCANNED_MODULES",
    "MODULE_POLICY",
    "BudgetPolicy",
    "EmptyScanError",
    "assert_real_corpus",
    "build_limits",
    "callable_key",
    "evaluate_budget",
    "measure_callable_lines",
    "measure_module_lines",
    "scan_callable_lines",
    "scan_module_lines",
]

MIN_SCANNED_MODULES: Final[int] = 2000
"""Floor on the scanned module count; a walk returning fewer is broken, not clean."""

MIN_SCANNED_CALLABLES: Final[int] = 7_500
"""Floor on the scanned production callable count; the AST walk must really reach the tree.

Set well below the measured population (9933 production callables) so ordinary
tree movement never trips it, while a walk that resolves to a handful of files —
the shape that reports zero findings and exits green — cannot pass.
"""

_UTF_8: Final[str] = "utf-8"


@dataclass(frozen=True)
class BudgetPolicy:
    """Declared limit-and-slack policy for one measured axis.

    ``default_limit`` governs every entry absent from the baseline. An entry is
    generated only when a measured size exceeds that default, so the baseline
    never carries a pin that the default already covers.
    """

    name: str
    default_limit: int
    headroom_ratio: float
    headroom_floor: int
    slack_ratio: float
    slack_floor: int

    def limit_for(self, actual: int) -> int:
        """Return the generated limit for a measured size."""
        headroom = max(self.headroom_floor, math.ceil(actual * self.headroom_ratio))
        return actual + headroom

    def max_slack_for(self, limit: int) -> int:
        """Return the largest tolerated gap between a limit and its measured size."""
        return max(self.slack_floor, math.ceil(limit * self.slack_ratio))


MODULE_POLICY: Final[BudgetPolicy] = BudgetPolicy(
    name="module",
    default_limit=1250,
    headroom_ratio=0.05,
    headroom_floor=25,
    slack_ratio=0.10,
    slack_floor=60,
)
CALLABLE_POLICY: Final[BudgetPolicy] = BudgetPolicy(
    name="callable",
    default_limit=180,
    headroom_ratio=0.05,
    headroom_floor=10,
    slack_ratio=0.10,
    slack_floor=25,
)


class EmptyScanError(RuntimeError):
    """Raised when a measured corpus is too small to be a real scan."""


def assert_real_corpus(modules: Mapping[str, int], callables: Mapping[str, int]) -> None:
    """Refuse a corpus that cannot be the real tree.

    A scan that resolves to nothing reports no findings and exits green, which
    is indistinguishable from a healthy pass. Both the pytest gate and the
    baseline generator route through this one guard, so neither can measure an
    empty tree — and the generator additionally cannot overwrite a real baseline
    with the emptiness.
    """
    if len(modules) < MIN_SCANNED_MODULES:
        raise EmptyScanError(
            f"scanned only {len(modules)} modules, below the {MIN_SCANNED_MODULES} floor; "
            "the source walk is broken, not the tree clean"
        )
    if len(callables) < MIN_SCANNED_CALLABLES:
        raise EmptyScanError(
            f"scanned only {len(callables)} production callables, below the {MIN_SCANNED_CALLABLES} floor; "
            "the AST walk is broken, not the tree clean"
        )


def callable_key(relative_path: str, name: str) -> str:
    """Return the stable baseline key for a callable.

    Line numbers are deliberately excluded so an unrelated edit above a function
    does not churn the baseline, mirroring the sibling complexity ratchet.
    """
    return f"{relative_path}::{name}"


def scan_module_lines(*, files: Sequence[Path], root: Path) -> dict[str, int]:
    """Return ``root``-relative POSIX path -> physical line count for *files*.

    The scan root is a parameter so the ratchet's own discrimination proof can
    point the real measurement code at a real temporary tree instead of
    re-implementing the walk in a test.
    """
    measured: dict[str, int] = {}
    for path in files:
        relative = path.relative_to(root).as_posix()
        measured[relative] = len(path.read_text(encoding=_UTF_8).splitlines())
    return measured


def scan_callable_lines(*, items: Sequence[tuple[Path, ast.AST]], root: Path) -> dict[str, int]:
    """Return ``path::name`` -> longest measured body length for parsed *items*.

    The longest body wins when a name is defined more than once in a module, so
    a shadowed definition cannot hide behind a shorter sibling.
    """
    measured: dict[str, int] = {}
    for path, tree in items:
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.end_lineno is None:
                continue
            key = callable_key(relative, node.name)
            length = node.end_lineno - node.lineno + 1
            measured[key] = max(measured.get(key, length), length)
    return measured


def measure_module_lines() -> dict[str, int]:
    """Measure every tracked package module against the repository root."""
    return scan_module_lines(files=package_python_files(include_data=True), root=REPO_ROOT)


def measure_callable_lines() -> dict[str, int]:
    """Measure every tracked production callable against the repository root.

    Test modules are excluded: a long, flat, data-shaped test body is not the
    accretion this axis exists to make visible, and the module axis already
    bounds those files.
    """
    items = tuple(
        (path, tree) for path, tree in package_ast_items(include_data=True) if "/tests/" not in path.as_posix()
    )
    return scan_callable_lines(items=items, root=REPO_ROOT)


def build_limits(
    actuals: Mapping[str, int],
    policy: BudgetPolicy,
    *,
    previous: Mapping[str, int] | None = None,
    accept_growth: bool = False,
) -> dict[str, int]:
    """Return the generated limit table for everything above *policy*'s default.

    Regeneration must never LAUNDER a live offender. The accepted size-budget
    decision rejected raising a ceiling in place of refactoring, because the
    ceiling exists to catch exactly that growth, and it deliberately left real
    offenders failing loudly until their owning campaign extracts them. A
    re-measure that quietly lifted those ceilings would paper over the signal
    while wearing the clothes of a staleness fix.

    So when *previous* is supplied, a subject already OVER its prior ceiling
    keeps that ceiling and stays red; only a subject inside its ceiling is
    re-banded. Lowering is always free — paying size debt down is what the
    ratchet is for. Raising past a broken ceiling requires *accept_growth*,
    which makes absorbing an offender a deliberate, reviewable act rather than
    a side effect of re-running the generator.
    """
    computed = {
        key: policy.limit_for(actual) for key, actual in sorted(actuals.items()) if actual > policy.default_limit
    }
    if previous is None or accept_growth:
        return computed

    clamped: dict[str, int] = {}
    for key, limit in computed.items():
        ceiling = previous.get(key, policy.default_limit)
        resolved = ceiling if actuals[key] > ceiling else limit
        if resolved > policy.default_limit:
            clamped[key] = resolved
    return clamped


@dataclass(frozen=True)
class BudgetVerdict:
    """Partitioned outcome for one measured axis."""

    over_budget: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def failing(self) -> tuple[str, ...]:
        """Every line that should fail the ratchet."""
        return (*self.over_budget, *self.stale)


def evaluate_budget(
    actuals: Mapping[str, int],
    limits: Mapping[str, int],
    policy: BudgetPolicy,
) -> BudgetVerdict:
    """Partition measured sizes against the generated limit table.

    ``over_budget`` carries entries that grew past their limit. ``stale`` carries
    limits that have drifted above their subject: an entry whose subject vanished,
    an entry the default now covers, and an entry whose gap exceeds the declared
    slack tolerance. Both partitions fail the gate, because a limit that no longer
    tracks its subject is the silent-regrowth window this ratchet exists to close.
    """
    over_budget: list[str] = []
    for key, actual in sorted(actuals.items()):
        limit = limits.get(key, policy.default_limit)
        if actual > limit:
            over_budget.append(f"{key}: {actual} lines > limit {limit}")

    stale: list[str] = []
    for key, limit in sorted(limits.items()):
        actual = actuals.get(key)
        if actual is None:
            stale.append(f"{key}: pinned at {limit} but absent from the scanned corpus")
            continue
        if actual <= policy.default_limit:
            stale.append(
                f"{key}: pinned at {limit} but measures {actual}, "
                f"within the {policy.default_limit} default; the entry is dead weight"
            )
            continue
        slack = limit - actual
        tolerated = policy.max_slack_for(limit)
        if slack > tolerated:
            stale.append(
                f"{key}: pinned at {limit} but measures {actual}; "
                f"slack {slack} exceeds the tolerated {tolerated}, permitting {slack} lines of invisible regrowth"
            )

    return BudgetVerdict(over_budget=tuple(over_budget), stale=tuple(stale))
