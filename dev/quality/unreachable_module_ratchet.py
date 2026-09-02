"""Ratchet: the set of shipped modules no entrypoint reaches may shrink, never grow.

``src/cadrumo`` is the shipped tax-filing application. A module inside it that
no declared console script can reach executes no user-facing behaviour by
construction, and it arrives there in two ways that look identical on disk:

* harness code written where the code it inspects lives, so a development need
  ends up inside the wheel at the domain boundary;
* product capability that lost its last caller and now survives only because
  its own tests still import it.

Both are invisible to every other gate. The module imports, its tests pass, it
ships, and nothing is red. :mod:`dev.audit.unreachable_code` walks the import
graph from the declared entrypoints and reports the whole set; this gate is what
stops that set from growing while the backlog inside it is worked down.

The baseline is an identity set, not a count. A count ratchet ("no more than N
unreachable modules") accepts a swap: retire one module, admit another, and the
number is undisturbed while the boundary quietly moves. So the baseline names
every module currently unreached, and the comparison is set equality in both
directions:

* a module the tree reports that the baseline does not name is a regression --
  new unreachable code entered the shipped package;
* a module the baseline names that the tree no longer reports is a stale
  entry -- the debt was paid and the baseline must shrink to record it.

The second direction is what makes the first honest. Without it the baseline
only accumulates, and a later reader cannot distinguish an accepted exception
from a line nobody removed.

``frozen_prefixes`` carves out clusters under active independent work, where
churn in both directions is expected and is not this gate's to adjudicate. A
frozen prefix is scope, not permission: the audit still reports everything
inside it, and the baseline records why it is deferred.

This gate does not overlap the import-direction gate in
``cadrumo.tests.test_production_never_imports_test_support``. That one proves
production never imports test support -- a direction. This one proves no
shipped module has become unreachable -- a population. A misplaced test helper
in a product namespace violates this gate and not that one, because importing
nothing from the test tree says nothing about whether anything can reach it.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from ..audit.unreachable_code import (
    ModuleReach,
    ShippedTreeSpec,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    scan_unreachable_code,
)

BASELINE_PATH: Final[Path] = Path(__file__).with_name("unreachable_module_ratchet.toml")


@dataclass(frozen=True, slots=True)
class UnreachableBaseline:
    """The accepted set of shipped modules the entrypoints do not reach.

    Args:
        allowed: Module names accepted for now, each expected to still be
            reported. An entry that stops being reported is stale.
        frozen_prefixes: Dotted prefixes wholly outside this gate's scope.
            Modules under one are neither required to be baselined nor
            required to persist.
    """

    allowed: frozenset[str]
    frozen_prefixes: tuple[str, ...]

    def is_frozen(self, module: str) -> bool:
        """Whether ``module`` falls under a deferred cluster."""
        return any(module == prefix or module.startswith(prefix + ".") for prefix in self.frozen_prefixes)

    @classmethod
    def load(cls, path: Path = BASELINE_PATH) -> UnreachableBaseline:
        """Read the committed baseline."""
        data = tomllib.loads(path.read_text(encoding=UTF_8))
        return cls(
            allowed=frozenset(data.get("allowed", ())),
            frozen_prefixes=tuple(data.get("frozen_prefixes", ())),
        )


@dataclass(frozen=True, slots=True)
class RatchetVerdict:
    """What the live tree reports measured against the baseline.

    Args:
        regressions: Reported modules the baseline does not name.
        stale: Baselined modules the tree no longer reports.
        frozen: Reported modules under a deferred cluster, carried for
            visibility and excluded from both failure directions.
    """

    regressions: tuple[str, ...]
    stale: tuple[str, ...]
    frozen: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        """True when the unreached set is exactly what the baseline says."""
        return not self.regressions and not self.stale

    def report(self) -> str:
        """Human-readable rendering naming every module in every direction."""
        lines: list[str] = []
        if self.regressions:
            lines.append(
                f"{len(self.regressions)} shipped module(s) no declared entrypoint reaches "
                f"that the baseline does not name.",
            )
            lines.append(
                "Each is harness code to relocate beside its consumer, or capability that lost "
                "its caller and should be deleted. Do not baseline it to make this pass:",
            )
            lines.extend(f"  + {name}" for name in self.regressions)
        if self.stale:
            lines.append(
                f"{len(self.stale)} baseline entry/entries the tree no longer reports. "
                f"Delete them from {BASELINE_PATH.name} so the baseline records the repair:",
            )
            lines.extend(f"  - {name}" for name in self.stale)
        if not lines:
            return f"unreachable-module set matches the baseline ({len(self.frozen)} deferred)"
        return "\n".join(lines)


def unreachable_modules(result: UnreachableCodeResult) -> frozenset[str]:
    """Every shipped module the runtime walk never reaches from a declared entrypoint.

    Only :attr:`ModuleReach.UNREACHABLE` counts. A module reached solely
    through ``python -m`` or solely under ``TYPE_CHECKING`` is classified
    separately by the audit and is a weaker signal with its own remedy, so
    folding it in here would blur two populations into one number.
    """
    return frozenset(
        finding.module for finding in result.modules if finding.reach is ModuleReach.UNREACHABLE
    )


def evaluate(result: UnreachableCodeResult, baseline: UnreachableBaseline) -> RatchetVerdict:
    """Compare the live unreachable set against ``baseline`` in both directions."""
    reported = unreachable_modules(result)
    frozen = frozenset(name for name in reported if baseline.is_frozen(name))
    live = reported - frozen
    allowed = frozenset(name for name in baseline.allowed if not baseline.is_frozen(name))
    return RatchetVerdict(
        regressions=tuple(sorted(live - allowed)),
        stale=tuple(sorted(allowed - live)),
        frozen=tuple(sorted(frozen)),
    )


def run_gate(repo_root: Path = REPO_ROOT, *, baseline_path: Path = BASELINE_PATH) -> RatchetVerdict:
    """Scan the real shipped tree and measure it against the committed baseline.

    Raises:
        RuntimeError: If the scan cannot produce a trustworthy result. A gate
            that cannot see the tree must refuse rather than report clean.
    """
    result = scan_unreachable_code(ShippedTreeSpec.from_repository(repo_root))
    if result.outcome is UnreachableCodeOutcome.ERROR:
        msg = f"reachability scan unavailable, ratchet unproven: {result.reason}"
        raise RuntimeError(msg)
    return evaluate(result, UnreachableBaseline.load(baseline_path))


def main() -> int:
    """Print the verdict; exit non-zero when the unreachable set moved."""
    verdict = run_gate()
    if verdict.is_clean:
        return 0
    sys.stderr.write(verdict.report() + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
