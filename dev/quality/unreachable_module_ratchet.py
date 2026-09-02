"""Boundary gate: no shipped module may exist only to serve the development harness.

``src/cadrumo`` is the shipped tax-filing application; ``dev/`` is the harness
that develops it. The line between them erodes silently, and always in the same
direction: a harness need wants a helper, the helper is written where the code
it inspects lives, and a module no user-facing surface can execute ends up
inside the wheel at the domain boundary. Nothing fails, because nothing was
broken -- the module imports, its tests pass, and it ships.

The reachability walk in :mod:`dev.audit.unreachable_code` makes that state
addressable. A module the walk never reaches from a declared console script
executes no user-facing behaviour by construction; if the only corpus outside
the package that still imports it is ``dev/``, it is harness code living in the
shipped tree, and it belongs beside the consumer that drives it.

This gate holds that boundary as an identity set rather than a count. A count
ratchet ("no more than N") accepts a swap: retire one module, admit another,
and the number is undisturbed while the boundary quietly moves. The baseline
therefore names every module currently in that state, and the comparison is set
equality in both directions:

    * a module in the tree that the baseline does not name is a regression --
      new harness code entered the shipped package;
    * a module the baseline names that the tree no longer reports is a stale
      entry -- the debt was paid and the baseline must shrink to record it.

The second direction is what makes the first honest. Without it the baseline
only grows stale, and a later reader cannot tell an accepted exception from a
line nobody removed.

``frozen_prefixes`` carves out clusters under active independent work, where
churn in either direction is expected and is not this gate's to adjudicate.
A frozen prefix is scope, not permission: the audit still reports what is
inside it, and the entry carries the reason it is deferred.
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

#: The outside-corpus label the audit gives the development harness tree.
HARNESS_LABEL: Final = "dev"

BASELINE_PATH: Final[Path] = Path(__file__).with_name("dev_only_shipped_modules.toml")


@dataclass(frozen=True, slots=True)
class DevOnlyBaseline:
    """The accepted set of shipped modules whose only outside consumer is ``dev/``.

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
    def load(cls, path: Path = BASELINE_PATH) -> DevOnlyBaseline:
        """Read the committed baseline."""
        data = tomllib.loads(path.read_text(encoding=UTF_8))
        return cls(
            allowed=frozenset(data.get("allowed", ())),
            frozen_prefixes=tuple(data.get("frozen_prefixes", ())),
        )


@dataclass(frozen=True, slots=True)
class DevOnlyVerdict:
    """What the live tree reports measured against the baseline.

    Args:
        newly_dev_only: Reported modules the baseline does not name.
        stale: Baselined modules the tree no longer reports.
        frozen: Reported modules under a deferred cluster, carried for
            visibility and excluded from both failure directions.
    """

    newly_dev_only: tuple[str, ...]
    stale: tuple[str, ...]
    frozen: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        """True when the boundary is exactly where the baseline says it is."""
        return not self.newly_dev_only and not self.stale

    def report(self) -> str:
        """Human-readable rendering naming every module in every direction."""
        lines: list[str] = []
        if self.newly_dev_only:
            lines.append(
                f"{len(self.newly_dev_only)} shipped module(s) no console script reaches, "
                f"imported only by the {HARNESS_LABEL}/ harness, and not in the baseline.",
            )
            lines.append("Move each beside the harness consumer that drives it, or delete it if nothing uses it:")
            lines.extend(f"  + {name}" for name in self.newly_dev_only)
        if self.stale:
            lines.append(
                f"{len(self.stale)} baseline entry/entries the tree no longer reports. "
                f"Delete them from {BASELINE_PATH.name} so the baseline records the repair:",
            )
            lines.extend(f"  - {name}" for name in self.stale)
        if not lines:
            frozen = f", {len(self.frozen)} deferred" if self.frozen else ""
            return f"harness/shipped boundary matches the baseline ({len(self.frozen) + 0} deferred){frozen and ''}"
        return "\n".join(lines)


def dev_only_modules(result: UnreachableCodeResult) -> frozenset[str]:
    """Shipped modules the walk never reaches whose remaining outside user is ``dev/``.

    ``used_by`` labels the corpora outside the package that still import the
    module. A module also imported by the package's own tests carries the
    ``tests`` label too: that module is test substrate for the shipped
    distribution, so it is not harness-only and is not this gate's subject.
    """
    return frozenset(
        finding.module
        for finding in result.modules
        if finding.reach is ModuleReach.UNREACHABLE and tuple(finding.used_by) == (HARNESS_LABEL,)
    )


def evaluate(result: UnreachableCodeResult, baseline: DevOnlyBaseline) -> DevOnlyVerdict:
    """Compare the live dev-only set against ``baseline`` in both directions."""
    reported = dev_only_modules(result)
    frozen = frozenset(name for name in reported if baseline.is_frozen(name))
    live = reported - frozen
    allowed = frozenset(name for name in baseline.allowed if not baseline.is_frozen(name))
    return DevOnlyVerdict(
        newly_dev_only=tuple(sorted(live - allowed)),
        stale=tuple(sorted(allowed - live)),
        frozen=tuple(sorted(frozen)),
    )


def run_gate(repo_root: Path = REPO_ROOT, *, baseline_path: Path = BASELINE_PATH) -> DevOnlyVerdict:
    """Scan the real shipped tree and measure it against the committed baseline.

    Raises:
        RuntimeError: If the scan cannot produce a trustworthy result. A gate
            that cannot see the tree must refuse rather than report clean.
    """
    result = scan_unreachable_code(ShippedTreeSpec.from_repository(repo_root))
    if result.outcome is UnreachableCodeOutcome.ERROR:
        msg = f"reachability scan unavailable, boundary unproven: {result.reason}"
        raise RuntimeError(msg)
    return evaluate(result, DevOnlyBaseline.load(baseline_path))


def main() -> int:
    """Print the verdict; exit non-zero when the boundary moved."""
    verdict = run_gate()
    if verdict.is_clean:
        return 0
    sys.stderr.write(verdict.report() + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
