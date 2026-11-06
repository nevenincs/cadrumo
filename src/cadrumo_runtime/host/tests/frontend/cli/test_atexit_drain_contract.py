"""Guard the CPython-private exit-hook drain the settled console exit depends on.

``exit_settled_console_process`` runs the exit hooks itself through
``atexit._run_exitfuncs`` before ending the process with ``os._exit``. The
function is private to CPython, so this test fails loudly if a release removes
or renames it, or stops it from emptying the hook registry it drains (which
would make the interpreter run every hook a second time on a fallback exit).
The probe runs in a fresh interpreter so the drain never touches pytest's hooks.
"""

from __future__ import annotations

import sys
from textwrap import dedent

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROBE = dedent(
    """
    import atexit, sys

    drain = getattr(atexit, "_run_exitfuncs", None)
    count = getattr(atexit, "_ncallbacks", None)
    if not callable(drain) or not callable(count):
        print("MISSING", file=sys.stderr)
        raise SystemExit(3)

    calls = []
    atexit.register(calls.append, "hook")
    registered = count()
    drain()
    drain()
    print(f"registered={registered} calls={len(calls)} remaining={count()}")
    atexit.register(print, "after-drain-hook-ran")
    """
)


def test_the_exit_hook_drain_exists_and_empties_the_registry() -> None:
    completed = run_audited_process(
        [sys.executable, "-I", "-c", _PROBE],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert "MISSING" not in str(completed.stderr), "atexit._run_exitfuncs or atexit._ncallbacks is gone"
    assert completed.returncode == 0, completed.stderr
    lines = str(completed.stdout).splitlines()
    # One hook registered, run exactly once across two drains, none left behind.
    assert lines[0] == "registered=1 calls=1 remaining=0"
    # A hook registered after a drain still runs at the interpreter's own exit,
    # so the drain consumes only what was registered before it.
    assert lines[1:] == ["after-drain-hook-ran"]
