"""Screen: whether a `live` classification matches what a load actually imports.

The load census checks two things about its rule table - that every module in
the universe is ruled, and that every ruled member exists in the universe. It
does not check the claim the rule is actually making. A rule saying a module
loads on `ValidatedRegistryAuthority.load` passes both checks whether or not a
load imports it, which is how forty of two hundred and twenty-five live members
came to disagree with the interpreter without any gate noticing.

Two things this screen must get right, both learned by getting them wrong:

The measurement runs in a subprocess importing nothing but the authority. Taken
in a process that has already imported the analysis tooling, one module reported
absent that a clean load holds - the contamination ran opposite to the obvious
direction, so the reading was not merely noisy but inverted.

Both cache regimes are measured. A cold load holds 378 first-party modules and a
warm load 335, and the warm set is a strict subset. A claim verified against a
cold load alone therefore cannot distinguish a module that always loads from one
that loads only while the caches are empty, and twenty-nine members differ on
exactly that.

Two conditions are reported:

- ``never_loaded`` - the member is absent from both regimes, so no load imports
  it and the rule is wrong rather than imprecise.
- ``cold_regime_only`` - the member is present with empty caches and absent with
  populated ones, so the rule is right about one regime and over-broad about the
  other.

The screen exits 0 whatever it finds. It reports; it does not gate. A gate
belongs here once the claims it would refuse have been corrected, and this
campaign has argued repeatedly that a category whose members are mostly correct
buries the ones that are not - here every member reported is a real
disagreement, and there are forty of them.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass

from .load_census import COLD_REGIME_ENV
from .load_census_classification import RULES

__all__ = [
    "ClaimFinding",
    "loaded_modules",
    "verify_live_claims",
]

_PROBE = (
    "import sys, json\n"
    "from cadrumo.domain.calculations.registry.authority import bundled_authority\n"
    "bundled_authority()\n"
    'print(json.dumps(sorted(n for n in sys.modules if n.startswith("cadrumo"))))\n'
)


@dataclass(frozen=True, slots=True)
class ClaimFinding:
    """One live claim the interpreter does not support."""

    module: str
    kind: str
    trigger: str


def loaded_modules(*, cold: bool) -> frozenset[str]:
    """Return the first-party modules a clean load holds, in one cache regime.

    Args:
        cold: Whether to point the cache directories at an empty location, so
            the load compiles rather than reading what a previous run left.

    Returns:
        Every ``cadrumo`` module in the subprocess's ``sys.modules`` after the
        bundled authority has loaded.

    Raises:
        RuntimeError: If the probe produced no output, which means the load
            failed. A failed probe must never read as an empty module set: that
            would report every live claim as never loaded.
    """
    environment = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="cadrumo-claim-probe-") as scratch:
        if cold:
            for index, variable in enumerate(COLD_REGIME_ENV):
                environment[variable] = os.path.join(scratch, str(index))
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline probe
            [sys.executable, "-c", _PROBE],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"the load probe produced no module list: {completed.stderr.strip()[-400:]}")
    return frozenset(json.loads(lines[-1]))


def verify_live_claims(cold: Iterable[str], warm: Iterable[str]) -> tuple[ClaimFinding, ...]:
    """Compare every ``live`` rule member against what the two regimes loaded."""
    cold_set, warm_set = frozenset(cold), frozenset(warm)
    findings: list[ClaimFinding] = []
    for rule in RULES:
        if rule.classification != "live":
            continue
        for member in rule.members:
            if member in cold_set and member in warm_set:
                continue
            kind = "cold_regime_only" if member in cold_set else "never_loaded"
            findings.append(ClaimFinding(module=member, kind=kind, trigger=rule.trigger))
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per unsupported claim and a closing census; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--kind", action="append", help="report only these kinds (repeatable)")
    args = parser.parse_args(argv)

    cold = loaded_modules(cold=True)
    warm = loaded_modules(cold=False)
    findings = verify_live_claims(cold, warm)
    wanted = set(args.kind) if args.kind else None
    for finding in findings:
        if wanted is not None and finding.kind not in wanted:
            continue
        sys.stdout.write(f"load_claim module={finding.module} kind={finding.kind} trigger={finding.trigger!r}\n")
    never = sum(1 for item in findings if item.kind == "never_loaded")
    sys.stdout.write(
        f"summary cold_modules={len(cold)} warm_modules={len(warm)} unsupported={len(findings)} "
        f"never_loaded={never} cold_regime_only={len(findings) - never}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
