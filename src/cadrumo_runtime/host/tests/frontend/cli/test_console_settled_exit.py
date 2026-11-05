"""The one-shot ``aeat`` console process ends at settlement without changing what it reports.

Each case runs the real console entry in a fresh interpreter and compares it
with the interpreter's own exit. A witness object whose finalizer writes a
marker shows which of the two ended the process: ordinary finalization runs
the finalizer, a settled exit does not.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from cadrumo.tests.subprocess_cli import run_subprocess_cli_harness

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FINALIZED = "console-process-finalized"

_HARNESS = """
import atexit, os, sys
sys.argv = ["aeat", *sys.argv[1:]]

class _Witness:
    def __del__(self):
        sys.stderr.write("{marker}\\n")
        sys.stderr.flush()

_witness = _Witness()
{prelude}
import cadrumo_runtime.host.frontend.cli.bootstrap as bootstrap
{run}
"""

_CONSOLE = "bootstrap.console_main()"
_INTERPRETER = "bootstrap.main()"


def _run(
    tmp_path: Path,
    arguments: tuple[str, ...],
    *,
    run: str = _CONSOLE,
    prelude: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = {"CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"), **(extra_env or {})}
    return run_subprocess_cli_harness(
        _HARNESS.format(marker=_FINALIZED, prelude=dedent(prelude), run=run),
        arguments,
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
        extra_env=environment,
        cwd=tmp_path,
        timeout=180,
    )


def _settled(completed: subprocess.CompletedProcess[str]) -> bool:
    return _FINALIZED not in completed.stderr


@pytest.mark.parametrize(
    ("arguments", "expected_status"),
    [
        (("--help",), 0),
        (("app", "ledger", "no-such-command"), 2),
    ],
)
def test_success_and_usage_statuses_match_the_interpreter_exit(
    tmp_path: Path, arguments: tuple[str, ...], expected_status: int
) -> None:
    console = _run(tmp_path, arguments)
    interpreter = _run(tmp_path, arguments, run=_INTERPRETER)

    assert interpreter.returncode == expected_status, interpreter.stderr
    assert console.returncode == expected_status, console.stderr
    assert console.stdout == interpreter.stdout
    assert _settled(console), console.stderr
    assert not _settled(interpreter), interpreter.stderr


def test_a_refusal_keeps_its_status_and_document(tmp_path: Path) -> None:
    unpublished = tmp_path / "unpublished-authority"
    unpublished.mkdir()
    arguments = ("app", "modelo", "describe", "130", "--json")
    environment = {"CADRUMO_AUTHORITY_ROOT": str(unpublished)}

    console = _run(tmp_path, arguments, extra_env=environment)
    interpreter = _run(tmp_path, arguments, run=_INTERPRETER, extra_env=environment)

    assert interpreter.returncode not in (0, 2), interpreter.stderr
    assert console.returncode == interpreter.returncode, console.stderr
    refusal = json.loads(console.stdout or console.stderr.replace(_FINALIZED, ""))
    assert refusal["error"]["code"] == "ERROR_CALCULATIONS_REGISTRY_AUTHORITY_DESCRIPTOR_UNAVAILABLE"
    assert console.stdout == interpreter.stdout
    assert _settled(console), console.stderr


def test_output_larger_than_a_pipe_buffer_reaches_the_reader_whole(tmp_path: Path) -> None:
    console = _run(tmp_path, ("--cadrumo-command-surface",))
    interpreter = _run(tmp_path, ("--cadrumo-command-surface",), run=_INTERPRETER)

    assert console.returncode == 0, console.stderr
    assert len(console.stdout.encode("utf-8")) > 1 << 16
    assert json.loads(console.stdout) == json.loads(interpreter.stdout)
    assert _settled(console), console.stderr


def test_every_exit_hook_and_finalize_callback_runs_before_the_process_ends(tmp_path: Path) -> None:
    """The hook registered before any product import runs last, so it ran only if every product hook ran."""
    last_hook = tmp_path / "last-hook"
    scratch_parent = tmp_path / "scratch"
    scratch_parent.mkdir()
    prelude = f"""
    import tempfile
    from pathlib import Path
    atexit.register(Path({str(last_hook)!r}).write_text, "ran", encoding="utf-8")
    _scratch = tempfile.TemporaryDirectory(dir={str(scratch_parent)!r})
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert _settled(console), console.stderr
    assert last_hook.read_text(encoding="utf-8") == "ran"
    assert list(scratch_parent.iterdir()) == []


def test_an_unflushed_file_leaves_the_exit_to_the_interpreter(tmp_path: Path) -> None:
    target = tmp_path / "buffered.txt"
    prelude = f"""
    _open_file = open({str(target)!r}, "w", encoding="utf-8")
    _open_file.write("buffered payload")
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert not _settled(console), console.stderr
    assert target.read_text(encoding="utf-8") == "buffered payload"


def test_a_running_foreground_thread_leaves_the_exit_to_the_interpreter(tmp_path: Path) -> None:
    target = tmp_path / "thread.txt"
    prelude = f"""
    import threading, time
    from pathlib import Path

    def _finish_later():
        # Still running when the command returns: it ends only once the main
        # thread has, which is what the interpreter waits for before exiting.
        while threading.main_thread().is_alive():
            time.sleep(0.01)
        Path({str(target)!r}).write_text("finished", encoding="utf-8")

    threading.Thread(target=_finish_later).start()
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert not _settled(console), console.stderr
    assert target.read_text(encoding="utf-8") == "finished"


def test_a_writable_sqlite_connection_leaves_the_exit_to_the_interpreter(tmp_path: Path) -> None:
    prelude = f"""
    import sqlite3
    _connection = sqlite3.connect({str(tmp_path / "writable.sqlite3")!r})
    _connection.execute("PRAGMA journal_mode=WAL")
    _connection.execute("CREATE TABLE t (v INTEGER)")
    _connection.commit()
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert not _settled(console), console.stderr
    # The interpreter's close of the last connection checkpointed and removed the log.
    assert not (tmp_path / "writable.sqlite3-wal").exists()


def test_a_query_only_sqlite_connection_does_not_hold_the_exit(tmp_path: Path) -> None:
    prelude = f"""
    import sqlite3
    _connection = sqlite3.connect({str(tmp_path / "read.sqlite3")!r})
    _connection.execute("PRAGMA query_only = ON")
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert _settled(console), console.stderr


def test_a_running_child_process_leaves_the_exit_to_the_interpreter(tmp_path: Path) -> None:
    prelude = """
    import subprocess
    _child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    """

    console = _run(tmp_path, ("--version",), prelude=prelude)

    assert console.returncode == 0, console.stderr
    assert not _settled(console), console.stderr


def test_an_uncaught_interrupt_keeps_the_interpreter_status(tmp_path: Path) -> None:
    interrupted = """
    def _interrupted():
        raise KeyboardInterrupt
    """
    console = _run(
        tmp_path,
        ("--version",),
        prelude=interrupted,
        run="bootstrap.main = _interrupted\nbootstrap.console_main()",
    )
    bare = _run(tmp_path, ("--version",), prelude=interrupted, run="_interrupted()")

    assert console.returncode == bare.returncode != 0
    assert "KeyboardInterrupt" in console.stderr
    assert not _settled(console), console.stderr


def test_a_non_integer_exit_code_is_reported_by_the_interpreter(tmp_path: Path) -> None:
    console = _run(
        tmp_path,
        ("--version",),
        run=(
            "from cadrumo_runtime.host.frontend.cli.console_exit import exit_settled_console_process\n"
            "exit_settled_console_process('stopped with a message')"
        ),
    )

    assert console.returncode == 1
    assert "stopped with a message" in console.stderr
    assert not _settled(console), console.stderr


def test_the_composable_main_returns_control_to_an_in_process_caller(tmp_path: Path) -> None:
    console = _run(
        tmp_path,
        ("--version",),
        run="try:\n    bootstrap.main()\nexcept SystemExit as stop:\n    print('caller-continues', stop.code)",
    )

    assert console.returncode == 0, console.stderr
    assert console.stdout.splitlines()[-1] == "caller-continues 0"
    assert not _settled(console), console.stderr
