#!/usr/bin/env python
"""The composed `just fix-all` pass.

`fix-all` was a `just` dependency chain, `fix-all: fix-style fix-format`, and
`just` dependencies are unconditionally fail-fast. `ruff check --fix` exits 1
whenever violations remain that carry no safe fix - the ordinary state of a
repository midway through a burndown - so the formatter, the step most likely
to have work to do, was routinely never reached. The aggregate reported a
failure it had not finished.

This module applies the fleet aggregate rule instead, stated in
`dev/EXIT-CODES.md`: run every step, then exit with the FIRST non-zero status
seen. It sits beside :mod:`dev.quality.suite`, the `check-all` counterpart, and
mirrors its shape - the two aggregates over the same tools should not need to
be read differently.

`fix` MUTATES, which is why it is not a gate: a repair pass that exited
non-zero because it repaired something would make every clean local loop red.
Under ``VAULTSPEC_FIX_STRICT`` - set by CI, where a repairable defect is an
uncommitted repair - a pass that changed tracked files exits
:data:`~dev.exit_codes.DRIFT` instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Final

from ..exit_codes import DRIFT, FIX_STRICT_ENV, OK

#: Each fixer's command, in the order a repair pass wants them: lint fixes can
#: rewrite lines the formatter then re-wraps, so formatting comes last.
FIXERS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("fix-style", ("ruff", "check", "--fix", ".")),
    ("fix-format", ("ruff", "format", ".")),
)


def _tracked_state() -> str:
    """Return a fingerprint of the working tree's tracked modifications."""
    result = subprocess.run(
        ("git", "status", "--porcelain"),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def main() -> int:
    """Run every fixer and report the first non-zero status.

    Returns:
        0 when every fixer succeeded, the first non-zero status otherwise, or
        :data:`~dev.exit_codes.DRIFT` when ``VAULTSPEC_FIX_STRICT`` is set and
        the pass had to change something.
    """
    strict = bool(os.environ.get(FIX_STRICT_ENV))
    before = _tracked_state() if strict else ""

    worst = OK
    for name, command in FIXERS:
        print(f"$ {' '.join(command)}", flush=True)
        status = subprocess.run(command, check=False).returncode
        if status != 0:
            print(f"FAIL  {name} (exit {status})", file=sys.stderr, flush=True)
            worst = worst or status

    if worst == OK and strict and _tracked_state() != before:
        print(
            "fix-all repaired files that were committed unrepaired; commit the result.",
            file=sys.stderr,
            flush=True,
        )
        return DRIFT
    return worst


if __name__ == "__main__":
    sys.exit(main())
