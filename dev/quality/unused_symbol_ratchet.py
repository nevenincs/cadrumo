"""Shrink-only ratchet over unused symbols and orphaned test modules.

The module ratchet adjudicates MODULES no console script reaches. It says
nothing about a symbol inside a module that is otherwise reachable, and nothing
about a test whose every shipped subject is itself a finding. Those two
populations -- 577 exact-confidence symbols and 25 orphaned test modules at the
time this gate landed -- sat outside every gate, so the suite reported green
over them.

This closes that. The baseline records, per module, how many exact-confidence
symbol findings it carries, and the gate fails in BOTH directions:

* a module carrying more than it records, or carrying findings while absent
  from the file, means new unused code entered a reachable module;
* a module recording more than it carries, or recording findings it no longer
  has, means debt was paid and the file must shrink to record it.

Only the ``exact`` tier is ratcheted. ``name-match`` and ``name-match-data``
findings are members reached by attribute access the scan cannot bind to a
type, so they are review candidates rather than facts, and gating them would
ratchet guesses.

The correct response to a failure is never to raise a number. Resolve the
symbol -- delete it with its test, wire it to the caller that needs it, or
record its class in ``dev/audit/reachability_classification.toml`` and then
remove it -- and lower the entry.

Regenerate the current set for comparison with:

    uv run --no-sync python -m dev.audit.unreachable_code --json
"""

from __future__ import annotations

import collections
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT
from ..audit.unreachable_code import run_unreachable_code_scan
from .unreachable_module_ratchet import IntentionalReachabilityKind

_BASELINE_PATH: Final[Path] = Path(__file__).with_name("unused_symbol_ratchet.toml")

#: Findings under this prefix are excluded from the comparison because the
#: subtree is under active restructuring and its churn would otherwise dominate
#: the baseline. Exclusion sets scope, not permission: the findings stay
#: visible in the audit and in the run summary. Remove this prefix once the
#: subtree is stable.
_DEFERRED_PREFIX: Final[str] = "cadrumo.entrypoints.tui"


@dataclass(frozen=True, slots=True)
class RatchetVerdict:
    """What the live tree carries against what the baseline records."""

    grew: tuple[tuple[str, int, int], ...]
    unrecorded: tuple[tuple[str, int], ...]
    shrank: tuple[tuple[str, int, int], ...]
    resolved: tuple[str, ...]
    orphan_tests_unrecorded: tuple[str, ...]
    orphan_tests_resolved: tuple[str, ...]
    intentional: tuple[tuple[str, str, str], ...] = ()
    """Symbols kept deliberately, as ``(module, symbol, rationale)``.

    The module ratchet beside this one admits a design-time authority through
    an ``[[intentional]]`` entry; this one offered only a count baseline, so a
    symbol correctly kept could sit red forever or be baselined, and baselining
    is barred. They are excluded from the comparison AND printed, because a
    disposition that disappears from the output stops being reviewable.
    """
    deferred_symbols: int = 0
    deferred_tests: int = 0
    """Findings excluded by the deferral prefix, carried so they can be stated.

    The prefix sets scope; the module says so itself - deferral is not
    permission. But the verdict never mentioned it, so a green run reported
    that the tree matches the baseline while a documented population sat
    outside the comparison entirely. Deferred is a distinct state from
    proven-clean and has to reach whoever reads the result.
    """

    @property
    def ok(self) -> bool:
        """True when the tree and the baseline agree exactly."""
        return not (
            self.grew
            or self.unrecorded
            or self.shrank
            or self.resolved
            or self.orphan_tests_unrecorded
            or self.orphan_tests_resolved
        )


def _baseline() -> tuple[dict[str, int], set[str]]:
    """Read the recorded per-module counts and orphaned-test modules."""
    data = tomllib.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    symbols = data.get("symbols", {})
    tests = data.get("orphan_tests", {}).get("modules", [])
    if not isinstance(symbols, dict) or not isinstance(tests, list):
        raise ValueError("unused-symbol baseline is malformed")
    return {str(k): int(v) for k, v in symbols.items()}, {str(t) for t in tests}


def _intentional() -> dict[tuple[str, str], str]:
    """Return ``(module, symbol) -> rationale`` for each recorded disposition.

    The kind is validated against the closed enum the module ratchet already
    defines, so the two ratchets cannot drift apart on what counts as a
    deliberate keep, and an entry without a rationale is refused rather than
    silently honoured.
    """
    data = tomllib.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    entries = data.get("intentional", [])
    if not isinstance(entries, list):
        raise ValueError("unused-symbol intentional dispositions must be a list of tables")
    recorded: dict[tuple[str, str], str] = {}
    for row in entries:
        module, symbol = row.get("module"), row.get("symbol")
        kind, rationale = row.get("kind"), row.get("rationale")
        if not all(isinstance(v, str) and v for v in (module, symbol, kind, rationale)):
            raise ValueError("an intentional symbol disposition needs module, symbol, kind and rationale")
        IntentionalReachabilityKind(kind)
        recorded[(module, symbol)] = rationale
    return recorded


def evaluate(repo_root: Path = REPO_ROOT) -> RatchetVerdict:
    """Compare the live scan against the recorded baseline."""
    result = run_unreachable_code_scan(repo_root)
    kept = _intentional()
    intentional = tuple(
        (finding.module, finding.name, kept[(finding.module, finding.name)])
        for finding in result.symbols
        if (finding.module, finding.name) in kept
    )
    live: collections.Counter[str] = collections.Counter(
        finding.module
        for finding in result.symbols
        if finding.confidence.value == "exact"
        and not finding.module.startswith(_DEFERRED_PREFIX)
        and (finding.module, finding.name) not in kept
    )
    live_tests = {finding.module for finding in result.tests if not finding.module.startswith(_DEFERRED_PREFIX)}
    recorded, recorded_tests = _baseline()

    grew = tuple(
        (module, count, recorded[module])
        for module, count in sorted(live.items())
        if module in recorded and count > recorded[module]
    )
    unrecorded = tuple((m, c) for m, c in sorted(live.items()) if m not in recorded)
    shrank = tuple(
        (module, live[module], count)
        for module, count in sorted(recorded.items())
        if module in live and live[module] < count
    )
    resolved = tuple(module for module in sorted(recorded) if module not in live)
    return RatchetVerdict(
        intentional=intentional,
        grew=grew,
        unrecorded=unrecorded,
        shrank=shrank,
        resolved=resolved,
        orphan_tests_unrecorded=tuple(sorted(live_tests - recorded_tests)),
        orphan_tests_resolved=tuple(sorted(recorded_tests - live_tests)),
        deferred_symbols=sum(
            1
            for finding in result.symbols
            if finding.confidence.value == "exact" and finding.module.startswith(_DEFERRED_PREFIX)
        ),
        deferred_tests=sum(1 for finding in result.tests if finding.module.startswith(_DEFERRED_PREFIX)),
    )


def _deferral_note(verdict: RatchetVerdict) -> str:
    """Return the standing deferral, or empty when nothing is deferred."""
    if not (verdict.deferred_symbols or verdict.deferred_tests):
        return ""
    return (
        f" ({verdict.deferred_symbols} symbol finding(s) and {verdict.deferred_tests} orphaned test "
        f"module(s) are deferred under {_DEFERRED_PREFIX} and were not compared)"
    )


def _intentional_note(verdict: RatchetVerdict) -> str:
    """Return the standing dispositions, so a deliberate keep stays reviewable."""
    if not verdict.intentional:
        return ""
    rows = "".join(f"{chr(10)}  = {module}.{symbol}: {rationale}" for module, symbol, rationale in verdict.intentional)
    return f"{chr(10)}{len(verdict.intentional)} intentional unused symbol(s) remain visible:{rows}"


def render(verdict: RatchetVerdict) -> str:
    """Render the verdict for an operator."""
    if verdict.ok:
        return "unused-symbol ratchet: tree matches baseline" + _intentional_note(verdict) + _deferral_note(verdict)

    lines: list[str] = []
    if verdict.unrecorded:
        lines.append(f"{len(verdict.unrecorded)} module(s) carry unused symbols the baseline does not name.")
        lines.append("Resolve the symbol; do not add a line to make this pass:")
        lines += [f"  + {module} ({count})" for module, count in verdict.unrecorded]
    if verdict.grew:
        lines.append(f"{len(verdict.grew)} module(s) carry MORE unused symbols than recorded:")
        lines += [f"  ^ {module}: {live} now, {was} recorded" for module, live, was in verdict.grew]
    if verdict.shrank:
        lines.append(f"{len(verdict.shrank)} module(s) carry fewer than recorded; lower the entry:")
        lines += [f"  v {module}: {live} now, {was} recorded" for module, live, was in verdict.shrank]
    if verdict.resolved:
        lines.append(f"{len(verdict.resolved)} recorded module(s) carry none; remove the entry:")
        lines += [f"  - {module}" for module in verdict.resolved]
    if verdict.orphan_tests_unrecorded:
        lines.append("orphaned test module(s) the baseline does not name:")
        lines += [f"  + {module}" for module in verdict.orphan_tests_unrecorded]
    if verdict.orphan_tests_resolved:
        lines.append("recorded orphaned test module(s) the tree no longer reports; remove them:")
        lines += [f"  - {module}" for module in verdict.orphan_tests_resolved]
    note = _intentional_note(verdict).lstrip(chr(10))
    if note:
        lines.append(note)
    deferral = _deferral_note(verdict)
    return chr(10).join([*lines, deferral.lstrip()]) if deferral else chr(10).join(lines)


def main() -> int:
    """Run the ratchet, printing only on disagreement."""
    verdict = evaluate()
    if verdict.ok:
        return 0
    sys.stdout.write(render(verdict) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
