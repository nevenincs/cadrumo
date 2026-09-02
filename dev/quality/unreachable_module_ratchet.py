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

The actionable baseline is an identity set, not a count. A count ratchet ("no more than N
unreachable modules") accepts a swap: retire one module, admit another, and the
number is undisturbed while the boundary quietly moves. So the baseline names
every actionable module currently unreached, and the comparison is set equality in both
directions:

* a module the tree reports that the baseline does not name is a regression --
  new unreachable code entered the shipped package;
* a module the baseline names that the tree no longer reports is a stale
  entry -- the debt was paid and the baseline must shrink to record it.

Some unreachable modules are intentional design-time authorities rather than
runtime capabilities. They belong in a separately typed, reviewable
``[[intentional]]`` disposition with an exact kind and rationale. Intentional
modules remain in the scanner's factual output and must remain reported; the
verdict carries them separately so they cannot disappear into the actionable
backlog. The second direction is what makes both lists honest. Without it the baseline
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
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from ..audit.unreachable_code import (
    ModuleReach,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    run_unreachable_code_scan,
)

BASELINE_PATH: Final[Path] = Path(__file__).with_name("unreachable_module_ratchet.toml")

#: Every reach category that is not "a console script leads here". A module in
#: any of them is a finding; the category names the remedy, not an exemption.
_NOT_SCRIPT_REACHED: Final[frozenset[ModuleReach]] = frozenset(
    {ModuleReach.UNREACHABLE, ModuleReach.MODULE_EXEC_ONLY, ModuleReach.TYPE_ONLY},
)


class IntentionalReachabilityKind(StrEnum):
    """Closed reasons an unreached shipped module is intentional."""

    DESIGN_TIME_AUTHORITY = "design_time_authority"


@dataclass(frozen=True, slots=True)
class IntentionalReachabilityDisposition:
    """A reviewable intentional unreached module disposition."""

    module: str
    kind: IntentionalReachabilityKind
    rationale: str

    def __post_init__(self) -> None:
        """Reject a disposition that cannot identify or justify its exception."""
        if not self.module.strip():
            raise ValueError("intentional reachability disposition module must be non-empty")
        if not self.rationale.strip():
            raise ValueError(f"intentional reachability disposition {self.module!r} needs a rationale")


def _string_list(data: object, *, field: str) -> tuple[str, ...]:
    """Read one non-empty TOML string list without accepting scalar lookalikes."""
    if not isinstance(data, list) or any(not isinstance(item, str) or not item.strip() for item in data):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return tuple(item for item in data if isinstance(item, str))


@dataclass(frozen=True, slots=True)
class UnreachableBaseline:
    """The accepted set of shipped modules the entrypoints do not reach.

    Args:
        allowed: Module names accepted for now, each expected to still be
            reported. An entry that stops being reported is stale.
        frozen_prefixes: Dotted prefixes wholly outside this gate's scope.
            Modules under one are neither required to be baselined nor
            required to persist.
        intentional: Explicit, typed dispositions for modules that remain
            intentionally unreached as design-time authorities. They are
            visible but do not enter the actionable backlog.
    """

    allowed: frozenset[str]
    frozen_prefixes: tuple[str, ...]
    intentional: tuple[IntentionalReachabilityDisposition, ...] = ()

    def __post_init__(self) -> None:
        """Reject overlapping or frozen entries before they can weaken the gate."""
        allowed = frozenset(self.allowed)
        intentional_by_module = {disposition.module: disposition for disposition in self.intentional}
        if len(intentional_by_module) != len(self.intentional):
            raise ValueError("intentional reachability dispositions must name each module once")
        intentional_modules = frozenset(intentional_by_module)
        overlap = sorted(allowed & intentional_modules)
        if overlap:
            raise ValueError(f"allowed and intentional reachability entries overlap: {overlap}")
        frozen_intentional = sorted(
            disposition.module for disposition in self.intentional if self.is_frozen(disposition.module)
        )
        if frozen_intentional:
            raise ValueError(f"intentional reachability entries cannot be frozen: {frozen_intentional}")
        frozen_allowed = sorted(module for module in allowed if self.is_frozen(module))
        if frozen_allowed:
            raise ValueError(f"allowed reachability entries cannot be frozen: {frozen_allowed}")

    def is_frozen(self, module: str) -> bool:
        """Whether ``module`` falls under a deferred cluster."""
        return any(module == prefix or module.startswith(prefix + ".") for prefix in self.frozen_prefixes)

    @classmethod
    def load(cls, path: Path = BASELINE_PATH) -> UnreachableBaseline:
        """Read the committed baseline."""
        data = tomllib.loads(path.read_text(encoding=UTF_8))
        allowed = _string_list(data.get("allowed", []), field="allowed")
        frozen_prefixes = _string_list(data.get("frozen_prefixes", []), field="frozen_prefixes")
        raw_intentional = data.get("intentional", [])
        if not isinstance(raw_intentional, list):
            raise ValueError("intentional must be a list of tables")
        intentional: list[IntentionalReachabilityDisposition] = []
        for row in raw_intentional:
            if not isinstance(row, dict):
                raise ValueError("intentional entries must be tables")
            module = row.get("module")
            kind = row.get("kind")
            rationale = row.get("rationale")
            if not isinstance(module, str) or not isinstance(kind, str) or not isinstance(rationale, str):
                raise ValueError("intentional entries require string module, kind, and rationale")
            try:
                disposition_kind = IntentionalReachabilityKind(kind)
            except ValueError as exc:
                raise ValueError(f"unknown intentional reachability kind: {kind!r}") from exc
            intentional.append(
                IntentionalReachabilityDisposition(
                    module=module,
                    kind=disposition_kind,
                    rationale=rationale,
                )
            )
        return cls(
            allowed=frozenset(allowed),
            frozen_prefixes=frozen_prefixes,
            intentional=tuple(intentional),
        )


@dataclass(frozen=True, slots=True)
class RatchetVerdict:
    """What the live tree reports measured against the baseline.

    Args:
        regressions: Reported modules the baseline does not name.
        stale: Baselined modules the tree no longer reports.
        frozen: Reported modules under a deferred cluster, carried for
            visibility and excluded from both failure directions.
        intentional: Typed intentional dispositions currently reported by the
            scanner, carried separately from actionable entries.
        stale_intentional: Intentional dispositions whose module the scanner
            no longer reports and which must be removed or reconsidered.
    """

    regressions: tuple[str, ...]
    stale: tuple[str, ...]
    frozen: tuple[str, ...]
    intentional: tuple[IntentionalReachabilityDisposition, ...] = ()
    stale_intentional: tuple[IntentionalReachabilityDisposition, ...] = ()

    @property
    def is_clean(self) -> bool:
        """True when the unreached set is exactly what the baseline says."""
        return not self.regressions and not self.stale and not self.stale_intentional

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
        if self.stale_intentional:
            lines.append(
                f"{len(self.stale_intentional)} intentional reachability disposition(s) the tree no longer reports. "
                f"Remove or reconsider them in {BASELINE_PATH.name}:",
            )
            lines.extend(f"  - {entry.module} ({entry.kind})" for entry in self.stale_intentional)
        if self.intentional:
            lines.append(f"{len(self.intentional)} intentional unreached module(s) remain visible:")
            lines.extend(f"  = {entry.module} ({entry.kind}): {entry.rationale}" for entry in self.intentional)
        if not lines:
            return f"unreachable-module set matches the baseline ({len(self.frozen)} deferred)"
        return "\n".join(lines)


def unreachable_modules(result: UnreachableCodeResult) -> frozenset[str]:
    """Every reported module no declared console script reaches.

    All three reach categories count, because all three are findings and none
    of them is a product command leading to the module:

    * ``UNREACHABLE`` -- no root reaches it at all;
    * ``MODULE_EXEC_ONLY`` -- only a ``python -m`` surface does, so an
      installed user can run it but no product command leads there;
    * ``TYPE_ONLY`` -- only an ``if TYPE_CHECKING:`` import names it, which
      never executes.

    Restricting the subject to ``UNREACHABLE`` would clear the other two
    silently: they would be neither baselined nor gated, so a module could
    leave the backlog by acquiring a ``__main__.py`` sibling or a
    type-checking-only importer rather than by being resolved. The audit
    categorises these separately because the remedies differ; the ratchet
    takes the union because the question it asks -- can a product command
    reach this? -- has the same answer for all three.
    """
    return frozenset(finding.module for finding in result.modules if finding.reach in _NOT_SCRIPT_REACHED)


def evaluate(result: UnreachableCodeResult, baseline: UnreachableBaseline) -> RatchetVerdict:
    """Compare the live unreachable set against ``baseline`` in both directions."""
    reported = unreachable_modules(result)
    frozen = frozenset(name for name in reported if baseline.is_frozen(name))
    live = reported - frozen
    intentional_by_module = {disposition.module: disposition for disposition in baseline.intentional}
    intentional_modules = frozenset(intentional_by_module)
    allowed = baseline.allowed
    return RatchetVerdict(
        regressions=tuple(sorted(live - allowed - intentional_modules)),
        stale=tuple(sorted(allowed - live)),
        frozen=tuple(sorted(frozen)),
        intentional=tuple(intentional_by_module[name] for name in sorted(live & intentional_modules)),
        stale_intentional=tuple(intentional_by_module[name] for name in sorted(intentional_modules - live)),
    )


def run_gate(repo_root: Path = REPO_ROOT, *, baseline_path: Path = BASELINE_PATH) -> RatchetVerdict:
    """Scan the real shipped tree and measure it against the committed baseline.

    Raises:
        RuntimeError: If the scan cannot produce a trustworthy result. A gate
            that cannot see the tree must refuse rather than report clean.
    """
    result = run_unreachable_code_scan(repo_root)
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
