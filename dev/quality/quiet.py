#!/usr/bin/env python
"""Run a command, staying silent on success and speaking only on failure.

A general signal primitive for the build harness: green/passing tools must
not report anything, so their normal "Success!" / "N files already
formatted" chatter is suppressed when the command exits 0. On a non-zero
exit the captured stdout and stderr are replayed verbatim so the failure is
fully actionable, and the original exit code is propagated.

Usage::

    python -m dev.quality.quiet <command> [args...]

The command runs inside the active environment, so venv console scripts
(``ruff``, ``deptry``, ``lint-imports``) are invoked by bare name.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """Run argv[1:] as a command; echo output only on non-zero exit."""
    command = sys.argv[1:]
    if not command:
        sys.stderr.write("quiet_ok.py: no command given\n")
        return 2

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
