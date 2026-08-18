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

Regenerate with ``--write-baseline`` after splitting a module, after paying size
debt down, or when deliberately accepting growth. Review and commit the diff:
the baseline is declared debt, not a mute button.

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

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from cadrumo.tests import (  # noqa: E402
    CALLABLE_POLICY,
    MODULE_POLICY,
    assert_real_corpus,
    build_limits,
    evaluate_budget,
    measure_callable_lines,
    measure_module_lines,
)

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
    "'callables' numbers: regenerate with `python -m dev.audit.size_budget --write-baseline`, "
    "then review and commit the diff. Every limit is a measured size plus a declared headroom, "
    "and the gate fails BOTH when an entry grows past its limit and when a limit drifts further "
    "above its subject than the declared slack tolerance, so a pin cannot silently outlive the "
    "size it was taken from. 'notes' is the one hand-maintained section: prose only, never "
    "numbers, carried forward verbatim across regeneration and dropped when its key disappears. "
    "Keys are repo-relative POSIX paths, and 'path::function' for callables."
)


def load_size_budget_baseline(path: Path = SIZE_BUDGET_BASELINE_PATH) -> SizeBudgetBaseline:
    """Load the committed baseline, or an empty one when none is committed yet."""
    if not path.is_file():
        return SizeBudgetBaseline(modules={}, callables={}, notes={})
    document = json.loads(path.read_text(encoding="utf-8"))
    return SizeBudgetBaseline(
        modules={str(key): int(value) for key, value in document.get("modules", {}).items()},
        callables={str(key): int(value) for key, value in document.get("callables", {}).items()},
        notes={str(key): str(value) for key, value in document.get("notes", {}).items()},
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


def main(argv: list[str] | None = None) -> int:
    """Report the size budget against the committed baseline, or regenerate it."""
    parser = argparse.ArgumentParser(description="Audit module/callable sizes against a generated limit baseline.")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Regenerate the committed limit table from the current tree. Review and commit the diff.",
    )
    parser.add_argument(
        "--accept-growth",
        action="store_true",
        help=(
            "Also raise ceilings for subjects that have BROKEN THROUGH them. Off by default so a "
            "re-measure cannot launder a live offender; use only when deliberately absorbing growth."
        ),
    )
    args = parser.parse_args(argv)

    modules = measure_module_lines()
    callables = measure_callable_lines()
    assert_real_corpus(modules, callables)

    print(f"size budget: scanned {len(modules)} modules, {len(callables)} production callables.")

    if args.write_baseline:
        existing = load_size_budget_baseline()
        regenerated = SizeBudgetBaseline(
            modules=build_limits(
                modules,
                MODULE_POLICY,
                previous=existing.modules,
                accept_growth=args.accept_growth,
            ),
            callables=build_limits(
                callables,
                CALLABLE_POLICY,
                previous=existing.callables,
                accept_growth=args.accept_growth,
            ),
            notes=existing.notes,
        )
        write_size_budget_baseline(
            regenerated,
            scanned_modules=len(modules),
            scanned_callables=len(callables),
        )
        print(
            f"wrote {SIZE_BUDGET_BASELINE_PATH.name}: "
            f"{len(regenerated.modules)} module limits, {len(regenerated.callables)} callable limits. "
            "Review and commit.",
        )
        return 0

    baseline = load_size_budget_baseline()
    module_verdict = evaluate_budget(modules, baseline.modules, MODULE_POLICY)
    callable_verdict = evaluate_budget(callables, baseline.callables, CALLABLE_POLICY)

    _emit("modules OVER BUDGET", module_verdict.over_budget)
    _emit("modules with a STALE PIN", module_verdict.stale)
    _emit("callables OVER BUDGET", callable_verdict.over_budget)
    _emit("callables with a STALE PIN", callable_verdict.stale)

    failing = len(module_verdict.failing) + len(callable_verdict.failing)
    if failing:
        print(
            f"\nsize budget: FAIL - {failing} finding(s).\n"
            "  OVER BUDGET: split the oversize subject into a cohesive sibling. A plain "
            "`--write-baseline` will NOT lift a ceiling you broke through; absorbing growth "
            "needs an explicit `--accept-growth`.\n"
            "  STALE PIN:   run `python -m dev.audit.size_budget --write-baseline` to re-measure "
            "the band, then review and commit the baseline.",
        )
        return 1

    print("\nsize budget: PASS - every subject is inside its declared band.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
