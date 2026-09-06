#!/usr/bin/env python
"""Module and callable size auditor with a generated, two-sided ratchet.

Reports every module and production callable measured against the committed
limit table in ``dev/audit/size_budget_baseline.json``, which the pytest gate
``src/cadrumo/tests/test_codebase_size_budgets.py`` enforces.

Why the limits are generated
----------------------------
The predecessor was a hand-maintained dict of pins carrying prose comments that
claimed each entry sat at exactly its present size with no headroom. Peers then
split or shrank those modules without lowering the pins, so the claim went
false: aggregate positive slack reached 9139 lines, several entries had fallen
BELOW the default limit (making the override pure dead weight), and the widest
single gap permitted 1261 lines of regrowth while the gate reported green. The
mechanism was sound; the hand-maintained numbers were what decayed. Generating
them removes the decay surface.

Ratchet semantics
-----------------
The audit FAILS (exit 1) on either side of the band:

* OVER BUDGET — a module or callable measuring above its limit. This is the
  original ceiling and is unchanged in spirit.
* STALE PIN — a limit that has drifted further above its subject than the
  declared slack tolerance, that covers a subject the default limit now governs,
  or that names a subject no longer in the tree. A stale pin IS the window of
  invisible regrowth, so it fails rather than merely being reported.

debt down, or when deliberately accepting growth. Review and commit the diff:
the baseline is declared debt, not a mute button.

The ``notes`` section of the baseline is the one hand-maintained surface. It is
prose only — never numbers — so it cannot go numerically stale, and it is
carried forward verbatim across regeneration, dropped only when its key leaves
the tree.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from cadrumo.tests import (  # noqa: E402
    CALLABLE_POLICY,
    MODULE_POLICY,
    assert_real_corpus,
    evaluate_budget,
    measure_callable_lines,
    measure_module_lines,
    scan_module_lines,
)
from cadrumo.tests.size_budget import BudgetVerdict  # noqa: E402

#: The development tree, measured on the MODULE axis beside the shipped package.
#:
#: `dev/` was outside every size axis until it produced a 6,060-line quality
#: module in two days, so "it does not ship" turned out to describe the absence
#: of counter-pressure rather than the absence of a problem. The enumeration
#: lives HERE rather than beside the shipped corpus helper: `src/` may carry no
#: awareness of `dev/`, and pointing the package's own file walker at this tree
#: would put that awareness in exactly the place the boundary forbids.
#:
#: `scan_module_lines` takes its files and root as parameters, so the real
#: measurement code is reused rather than re-implemented for this corpus.
_DEV_ROOT: Final[Path] = _REPO_ROOT / "dev"

SIZE_BUDGET_BASELINE_PATH: Final[Path] = _REPO_ROOT / "dev" / "audit" / "size_budget_baseline.json"
"""Committed, generated limit table consumed by the pytest size ratchet."""


@dataclass(frozen=True)
class SizeBudgetBaseline:
    """The committed, generated limit tables plus their preserved prose notes."""

    modules: dict[str, int]
    callables: dict[str, int]
    notes: dict[str, str]


_BASELINE_COMMENT = (
    "GENERATED limit table for the dev-side size ratchet. Do NOT hand-edit the 'modules' or "
    "'callables' numbers are measured, never pinned. ",
    "then review and commit the diff. Every limit is a measured size plus a declared headroom, "
    "and the gate fails BOTH when an entry grows past its limit and when a limit drifts further "
    "above its subject than the declared slack tolerance, so a pin cannot silently outlive the "
    "size it was taken from. 'notes' is the one hand-maintained section: prose only, never "
    "numbers, carried forward verbatim across regeneration and dropped when its key disappears. "
    "Keys are repo-relative POSIX paths, and 'path::function' for callables.",
)


def load_size_budget_baseline(path: Path = SIZE_BUDGET_BASELINE_PATH) -> SizeBudgetBaseline:
    """Return an empty budget: this audit grandfathers no module or callable.

    The committed per-module limit table was retired. Every module and callable
    is measured against the declared budget alone, with no pinned ceiling.

    Args:
        path: Retained for signature compatibility with callers.

    Returns:
        An empty :class:`SizeBudgetBaseline`.
    """
    del path
    return SizeBudgetBaseline(modules={}, callables={}, notes={})


def write_size_budget_baseline(
    baseline: SizeBudgetBaseline,
    *,
    scanned_modules: int,
    scanned_callables: int,
    path: Path = SIZE_BUDGET_BASELINE_PATH,
) -> None:
    """Write the generated baseline, preserving notes whose keys survived."""
    live_keys = set(baseline.modules) | set(baseline.callables)
    document = {
        "_comment": _BASELINE_COMMENT,
        "generated": {
            "scanned_modules": scanned_modules,
            "scanned_callables": scanned_callables,
            "module_entries": len(baseline.modules),
            "callable_entries": len(baseline.callables),
        },
        "notes": {key: value for key, value in sorted(baseline.notes.items()) if key in live_keys},
        "modules": dict(sorted(baseline.modules.items())),
        "callables": dict(sorted(baseline.callables.items())),
    }
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _emit(label: str, lines: tuple[str, ...]) -> None:
    """Print one partition of the verdict."""
    if not lines:
        return
    print(f"\n{label} ({len(lines)}):")
    for line in lines:
        print(f"  {line}")


def dev_python_files() -> tuple[Path, ...]:
    """Return every `.py` file under `dev/`, excluding compiled caches.

    Tests are INCLUDED. The largest single artefact the campaign that motivated
    this corpus produced was a 5,510-line test module, so exempting tests would
    carve out the worst instance of the defect.
    """
    return tuple(sorted(path for path in _DEV_ROOT.rglob("*.py") if "__pycache__" not in path.parts))


def measure_dev_module_lines() -> dict[str, int]:
    """Measure every `dev/` module against the repository root."""
    return scan_module_lines(files=dev_python_files(), root=_REPO_ROOT)


@dataclass(frozen=True)
class SizeBudgetResult:
    """The composed size-budget verdict across both measured trees.

    Args:
        modules: Verdict for the module axis, spanning `src/` and `dev/`.
        callables: Verdict for production callables in the shipped package.
        module_count: Modules scanned, for an honest "measured nothing" signal.
        callable_count: Production callables scanned.
    """

    modules: BudgetVerdict
    callables: BudgetVerdict
    module_count: int
    callable_count: int

    @property
    def findings(self) -> tuple[str, ...]:
        """Every failing line, modules first."""
        return (*self.modules.failing, *self.callables.failing)

    @property
    def is_clean(self) -> bool:
        """True when every measured subject sits inside its declared band."""
        return not self.findings

    def headline(self) -> str:
        """One-line summary naming what was measured and what failed."""
        scanned = f"scanned {self.module_count} modules, {self.callable_count} production callables"
        if self.is_clean:
            return f"size budget clean: {scanned}"
        return f"{len(self.findings)} size-budget finding(s): {scanned}"


@functools.cache
def run_size_budget_scan() -> SizeBudgetResult:
    """Measure both trees against the declared budget.

    Cached: the scan reads ~6,800 modules and AST-parses ~16,000 callables, and
    every caller here is a one-shot process that wants the same answer. The CLI
    asks once and the dashboard asks once, so the cache changes no behaviour --
    it only stops a second consumer in the same run from paying the minute
    again.

    The one scan path, shared by the CLI and the advisory dashboard, so the
    composed report cannot drift from what `python -m dev.audit.size_budget`
    prints.
    """
    modules = measure_module_lines() | measure_dev_module_lines()
    callables = measure_callable_lines()
    assert_real_corpus(modules, callables)

    baseline = load_size_budget_baseline()
    return SizeBudgetResult(
        modules=evaluate_budget(modules, baseline.modules, MODULE_POLICY),
        callables=evaluate_budget(callables, baseline.callables, CALLABLE_POLICY),
        module_count=len(modules),
        callable_count=len(callables),
    )


def main(argv: list[str] | None = None) -> int:
    """Report every module and callable that exceeds the declared size budget."""
    parser = argparse.ArgumentParser(description="Audit module/callable sizes against a generated limit baseline.")
    parser.parse_args(argv)

    result = run_size_budget_scan()
    module_verdict = result.modules
    callable_verdict = result.callables

    print(f"size budget: scanned {result.module_count} modules, {result.callable_count} production callables.")

    _emit("modules OVER BUDGET", module_verdict.over_budget)
    _emit("modules with a STALE PIN", module_verdict.stale)
    _emit("callables OVER BUDGET", callable_verdict.over_budget)
    _emit("callables with a STALE PIN", callable_verdict.stale)

    failing = len(module_verdict.failing) + len(callable_verdict.failing)
    if failing:
        print(
            f"\nsize budget: FAIL - {failing} finding(s).\n"
            "  Split the oversize subject into a cohesive sibling. There is no "
            "baseline, ceiling table, or accept flag.",
        )
        return 1

    print("\nsize budget: PASS - every subject is inside its declared band.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
