"""Settled process exit for the one-shot ``aeat`` console script.

A one-shot ``aeat`` process has emitted its result by the time its command
returns, yet full interpreter finalization then spends a further 0.1-0.2 s
deallocating every module and object it imported. That teardown has no
observable effect once three things hold: the exit hooks have run, the
standard streams are flushed, and no resource whose release is itself an
effect is still open. This module ends the process at that point and, when
any of them cannot be shown, leaves the exit to the interpreter unchanged.
"""

from __future__ import annotations

import atexit
import gc
import os
import sys
import threading
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    import io
    import sqlite3
    import subprocess

# ``os._exit`` takes a C ``int``. A status outside it is left to the
# interpreter, which reports it in its own documented way.
_C_INT_MIN = -(2**31)
_C_INT_MAX = 2**31 - 1


def exit_settled_console_process(code: object) -> NoReturn:
    """End the console process with the status ``SystemExit(code)`` would give.

    Raises ``SystemExit(code)`` instead whenever the process cannot be shown to
    be settled, so the interpreter's ordinary finalization then decides the
    exit exactly as it would have without this function.

    Args:
        code: The ``SystemExit.code`` the command ended with, ``None`` for a
            command that returned normally.
    """
    status = _integer_exit_status(code)
    # Development mode exists to surface the warnings that finalization emits
    # for leaked resources, so it keeps the interpreter's exit.
    if status is None or sys.flags.dev_mode or _foreground_thread_running():
        raise SystemExit(code)
    # Finalization joins foreground threads and then runs the exit hooks; with
    # no foreground thread left, running the hooks here is the same sequence.
    # They seal key material, release lockfiles, stop KDF workers, close the
    # log handlers and run every ``weakref.finalize`` callback. The interpreter
    # does not run a hook twice: the call empties the registry it drains.
    atexit._run_exitfuncs()
    if not _standard_streams_flushed() or _unsettled_resource_open():
        raise SystemExit(code)
    os._exit(status)


def _integer_exit_status(code: object) -> int | None:
    """Return the process status for ``code``, or ``None`` when the interpreter must report it."""
    if code is None:
        return 0
    # A string or other object is printed to stderr by the interpreter before
    # it exits with 1; that report stays the interpreter's.
    if isinstance(code, int) and _C_INT_MIN <= code <= _C_INT_MAX:
        return int(code)
    return None


def _foreground_thread_running() -> bool:
    """Report a live non-daemon thread, which ordinary finalization would wait for."""
    main_thread = threading.main_thread()
    return any(
        thread is not main_thread and not thread.daemon and thread.is_alive() for thread in threading.enumerate()
    )


def _standard_streams_flushed() -> bool:
    """Flush every standard output stream, reporting whether all of them accepted it.

    A failed flush is left to the interpreter, which retries it, reports it and
    exits with its own status for that failure.
    """
    streams = {id(stream): stream for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__)}
    for stream in streams.values():
        if stream is None or stream.closed:
            continue
        try:
            stream.flush()
        except (OSError, ValueError):
            return False
    return True


def _unsettled_resource_open() -> bool:
    """Report an open resource whose release at finalization would still change something.

    The operating system closes descriptors, handles, sockets and pipes when
    the process ends exactly as their deallocation would. What it cannot do is
    flush a userspace write buffer, close a writable SQLite connection (which
    checkpoints its write-ahead log when it is the last one) or wait for a
    child process. Those types are only reachable when their modules are
    loaded, so an unloaded module contributes nothing to look for.
    """
    standard_ids = _standard_stream_ids()
    connection_type = _loaded_sqlite_connection_type()
    popen_type = _loaded_popen_type()
    return any(
        _candidate_unsettled(
            candidate,
            standard_ids=standard_ids,
            connection_type=connection_type,
            popen_type=popen_type,
        )
        for candidate in gc.get_objects()
    )


def _candidate_unsettled(
    # Typed as the garbage collector reports it: any live object at all.
    candidate: Any,
    *,
    standard_ids: frozenset[int],
    connection_type: type[sqlite3.Connection] | None,
    popen_type: type[subprocess.Popen[bytes]] | None,
) -> bool:
    """Report whether one live object is a resource whose release would still change something."""
    import io

    if isinstance(candidate, io.TextIOWrapper | io.BufferedWriter | io.BufferedRandom):
        return id(candidate) not in standard_ids and _stream_writable(candidate)
    if connection_type is not None and isinstance(candidate, connection_type):
        return _sqlite_connection_writable(candidate)
    return popen_type is not None and isinstance(candidate, popen_type) and candidate.poll() is None


def _loaded_sqlite_connection_type() -> type[sqlite3.Connection] | None:
    """Return the SQLite connection type when the process has loaded the module."""
    if "sqlite3" not in sys.modules:
        return None
    import sqlite3

    return sqlite3.Connection


def _loaded_popen_type() -> type[subprocess.Popen[bytes]] | None:
    """Return the child-process type when the process has loaded the module."""
    if "subprocess" not in sys.modules:
        return None
    import subprocess

    return subprocess.Popen


def _standard_stream_ids() -> frozenset[int]:
    """Return the identities of the standard streams and the buffers beneath them."""
    identities: set[int] = set()
    for stream in (sys.stdin, sys.stdout, sys.stderr, sys.__stdin__, sys.__stdout__, sys.__stderr__):
        layer: object = stream
        while layer is not None:
            identities.add(id(layer))
            layer = getattr(layer, "buffer", None) or getattr(layer, "raw", None)
    return frozenset(identities)


def _stream_writable(stream: io.TextIOWrapper | io.BufferedWriter | io.BufferedRandom) -> bool:
    """Report an open writable stream; a detached wrapper holds no buffer of its own."""
    try:
        return not stream.closed and stream.writable()
    except ValueError:
        return False


def _sqlite_connection_writable(connection: sqlite3.Connection) -> bool:
    """Report an open connection that is not provably read-only.

    A closed connection, or a ``query_only`` one outside a transaction, has
    nothing to commit, roll back or checkpoint. A connection this thread may
    not query counts as writable.
    """
    import sqlite3

    try:
        if connection.in_transaction:
            return True
    except sqlite3.ProgrammingError:
        # The property raises only for a closed connection.
        return False
    try:
        row: object = connection.execute("PRAGMA query_only").fetchone()
    except sqlite3.Error:
        return True
    return row != (1,)


__all__ = ["exit_settled_console_process"]
