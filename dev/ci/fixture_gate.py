"""Run the fixture checks on a machine that holds no build tree.

A family whose outputs are generated, never committed, is checked by rendering
each output afresh and comparing it with the stored one. A hosted runner starts
from a bare checkout, so nothing is stored and every such comparison reports a
missing output as stale. This gate first produces exactly those families, then
runs every family's check: a producer that fails, or one whose second rendering
differs from its first, still fails the gate.

The selection is read from the family declarations. A family that is committed
in place is never produced here, so its check keeps comparing the committed
bytes with the sources; a generated family whose check does not prove its
stored outputs is left unseeded, as its own check allows.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from dev.fixture_projections.cli import Workspace, check, seed
from dev.fixture_projections.registry import FixtureFamily

__all__ = ["main", "run", "stored_comparison_families"]


def stored_comparison_families(families: Sequence[FixtureFamily]) -> tuple[str, ...]:
    """Name the generated families whose check compares a stored output a bare checkout does not hold."""
    return tuple(
        family.name
        for family in families
        if family.producer is not None and not family.committed and family.check_proves_outputs
    )


def run(workspace: Workspace | None = None) -> int:
    """Produce the generated families a check compares, then run every check; the first failing status."""
    workspace = workspace or Workspace()
    generated = stored_comparison_families(workspace.families)
    if generated:
        seeded = seed(generated, force=False, workspace=workspace)
        if seeded != 0:
            return seeded
    return check((), determinism=False, workspace=workspace)


def main() -> int:
    """Run the gate for ``python -m dev.ci.fixture_gate``."""
    return run()


if __name__ == "__main__":
    sys.exit(main())
