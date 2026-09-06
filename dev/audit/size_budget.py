#!/usr/bin/env python
"""Module and callable size auditor with a generated, two-sided ratchet.

Reports every module and production callable measured against the committed
limit table in ``dev/audit/size_budget_baseline.json``.

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

Why a ratchet rather than a flat ceiling
----------------------------------------
A flat threshold with no baseline defines an offender as "merely a large file".
That is the definition the accepted size-budget decision explicitly rejects: an
offender is a subject that broke through its OWN previously agreed ceiling. The
distinction is what makes the signal actionable. Against a flat threshold this
tree reports dozens of standing findings that no single commit caused and no
single commit can clear, so the audit can never reach a clean state and stops
being read. Against the ratchet the same tree is clean until something GROWS,
and the growth is attributable to whoever caused it.

That is also the property that matters for prevention. A module accreting from
600 to 6,000 lines crosses its own ceiling on the first commit past it, and
fails there, rather than arriving as one more line in a list nobody reads.

Ratchet semantics
-----------------
The audit FAILS (exit 1) on either side of the band:

* OVER BUDGET — a module or callable measuring above its limit. This is the
  original ceiling and is unchanged in spirit.
* STALE PIN — a limit that has drifted further above its subject than the
  declared slack tolerance, that covers a subject the default limit now governs,
  or that names a subject no longer in the tree. A stale pin IS the window of
  invisible regrowth, so it fails rather than merely being reported.

Regenerate with ``--regenerate`` after paying debt down, or with
``--regenerate --accept-growth`` when deliberately absorbing growth. Review and
commit the diff: the baseline is declared debt, not a mute button. Regeneration
alone cannot launder a live offender — a subject already over its ceiling keeps
that ceiling and stays red unless ``--accept-growth`` is passed.

The ``notes`` section of the baseline is the one hand-maintained surface. It is
prose only — never numbers — so it cannot go numerically stale, and it is
carried forward verbatim across regeneration, dropped only when its key leaves
the tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

if str(REPO_ROOT / "src") not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.tests import (  # noqa: E402
    CALLABLE_POLICY,
    MODULE_POLICY,
    assert_real_corpus,
    build_limits,
    evaluate_budget,
    measure_callable_lines,
    measure_module_lines,
    python_files_under,
    scan_module_lines,
)
from cadrumo.tests.size_budget import BudgetVerdict, EmptyScanError  # noqa: E402

#: The development tree, measured on the MODULE axis beside the shipped package.
#:
#: The enumeration lives HERE rather than beside the shipped corpus helper:
#: `src/` may carry no awareness of `dev/`, and pointing the package's own file
#: walker at this tree would put that awareness in the one place the boundary
#: forbids. `python_files_under` and `scan_module_lines` both take their root as
#: a parameter, so the canonical walk and the real measurement are reused rather
#: than re-implemented for this corpus.
_DEV_ROOT: Final[Path] = REPO_ROOT / "dev"

#: Floor for the `dev/` corpus alone. The shipped tree contributes several
#: thousand modules, so a union checked against one aggregate floor would still
#: clear it with the dev walk returning nothing at all -- the dev axis would
#: report zero findings and read as clean. Absent and zero are different facts,
#: so each tree is proved non-empty on its own before they are combined.
MIN_SCANNED_DEV_MODULES: Final[int] = 400

SIZE_BUDGET_BASELINE_PATH: Final[Path] = REPO_ROOT / "dev" / "audit" / "size_budget_baseline.json"
"""Committed, generated limit table this audit measures against."""


@dataclass(frozen=True)
class SizeBudgetBaseline:
    """The committed, generated limit tables plus their preserved prose notes."""

    modules: dict[str, int]
    callables: dict[str, int]
    notes: dict[str, str]


_BASELINE_COMMENT = (
    "GENERATED limit table for the dev-side size ratchet. Do NOT hand-edit the 'modules' or "
    "'callables' numbers: they are measured, never pinned. Regenerate with "
    "'python -m dev.audit.size_budget --regenerate', then review and commit the diff. ",
    "Every limit is a measured size plus a declared headroom, and the gate fails BOTH when an "
    "entry grows past its limit and when a limit drifts further above its subject than the "
    "declared slack tolerance, so a pin cannot silently outlive the size it was taken from. "
    "Regeneration cannot launder a live offender: a subject already over its ceiling keeps that "
    "ceiling unless '--accept-growth' is passed. 'notes' is the one hand-maintained section: "
    "prose only, never numbers, carried forward verbatim across regeneration and dropped when "
    "its key disappears. Keys are repo-relative POSIX paths, and 'path::function' for callables.",
)


def load_size_budget_baseline(path: Path = SIZE_BUDGET_BASELINE_PATH) -> SizeBudgetBaseline:
    """Read the committed limit table.

    Args:
        path: Baseline document to read.

    Returns:
        The committed tables, or empty tables when no baseline exists yet.
    """
    if not path.is_file():
        return SizeBudgetBaseline(modules={}, callables={}, notes={})
    document = json.loads(path.read_text(encoding=UTF_8))
    return SizeBudgetBaseline(
        modules=dict(document.get("modules", {})),
        callables=dict(document.get("callables", {})),
        notes=dict(document.get("notes", {})),
    )


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
    """Return every `.py` file under `dev/`, through the canonical pruned walk.

    Tests are INCLUDED: a test module accretes exactly as a source module does,
    and the module axis is the only axis that measures one at all.
    """
    return python_files_under(_DEV_ROOT)


def measure_dev_module_lines() -> dict[str, int]:
    """Measure every `dev/` module against the repository root.

    Raises:
        EmptyScanError: If the walk returns implausibly few modules. A broken
            walk reports no findings and reads as clean, which is the one
            outcome this axis must never produce silently.
    """
    files = dev_python_files()
    if len(files) < MIN_SCANNED_DEV_MODULES:
        msg = (
            f"scanned only {len(files)} dev/ modules, below the {MIN_SCANNED_DEV_MODULES} floor; "
            "the dev source walk is broken, not the tree clean"
        )
        raise EmptyScanError(msg)
    return scan_module_lines(files=files, root=REPO_ROOT)


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


def measure_corpus() -> tuple[dict[str, int], dict[str, int]]:
    """Measure both trees, proving each non-empty before combining them."""
    modules = measure_module_lines() | measure_dev_module_lines()
    callables = measure_callable_lines()
    assert_real_corpus(modules, callables)
    return modules, callables


def run_size_budget_scan() -> SizeBudgetResult:
    """Measure both trees against the committed baseline.

    The one scan path, so no consumer can drift from what the CLI prints.
    """
    modules, callables = measure_corpus()
    baseline = load_size_budget_baseline()
    return SizeBudgetResult(
        modules=evaluate_budget(modules, baseline.modules, MODULE_POLICY),
        callables=evaluate_budget(callables, baseline.callables, CALLABLE_POLICY),
        module_count=len(modules),
        callable_count=len(callables),
    )


def regenerate(*, accept_growth: bool) -> int:
    """Rewrite the baseline from the live tree and report what moved."""
    modules, callables = measure_corpus()
    previous = load_size_budget_baseline()
    rebuilt = SizeBudgetBaseline(
        modules=build_limits(modules, MODULE_POLICY, previous=previous.modules, accept_growth=accept_growth),
        callables=build_limits(callables, CALLABLE_POLICY, previous=previous.callables, accept_growth=accept_growth),
        notes=previous.notes,
    )
    write_size_budget_baseline(rebuilt, scanned_modules=len(modules), scanned_callables=len(callables))
    print(
        f"size budget: baseline regenerated from {len(modules)} modules and {len(callables)} callables "
        f"({len(rebuilt.modules)} module entries, {len(rebuilt.callables)} callable entries).",
    )
    if not accept_growth:
        print("  Live offenders kept their prior ceiling and stay red; pass --accept-growth to absorb them.")
    print(f"  Review and commit the diff to {SIZE_BUDGET_BASELINE_PATH.name}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Report every module and callable that exceeds the declared size budget."""
    parser = argparse.ArgumentParser(description="Audit module/callable sizes against a generated limit baseline.")
    parser.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline from the tree")
    parser.add_argument(
        "--accept-growth",
        action="store_true",
        help="with --regenerate, deliberately absorb subjects that broke their ceiling",
    )
    args = parser.parse_args(argv)

    if args.regenerate:
        return regenerate(accept_growth=args.accept_growth)
    if args.accept_growth:
        parser.error("--accept-growth is only meaningful with --regenerate")

    result = run_size_budget_scan()
    module_verdict = result.modules
    callable_verdict = result.callables

    print(f"size budget: scanned {result.module_count} modules, {result.callable_count} production callables.")

    _emit("modules OVER BUDGET", module_verdict.over_budget)
    _emit("modules with a STALE PIN", module_verdict.stale)
    _emit("callables OVER BUDGET", callable_verdict.over_budget)
    _emit("callables with a STALE PIN", callable_verdict.stale)

    failing = len(result.findings)
    if failing:
        print(
            f"\nsize budget: FAIL - {failing} finding(s).\n"
            "  A subject broke through its OWN agreed ceiling, or a ceiling outlived its subject.\n"
            "  Split the oversize subject into a cohesive sibling, or regenerate if debt was paid down.",
        )
        return 1

    print("\nsize budget: PASS - every subject is inside its declared band.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
