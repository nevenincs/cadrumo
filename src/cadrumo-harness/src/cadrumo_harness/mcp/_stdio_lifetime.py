"""Client-lifetime watchdog for the ``cadrumo-mcp`` stdio server.

The stdio transport's protocol-blessed exit path is stdin EOF, but on Windows an
inherited pipe handle can keep stdin open after the spawning client is gone, so
EOF never arrives and the server outlives its client indefinitely. The blocked
anyio stdin reader is a non-daemon thread that cannot be cancelled in-process,
so the only reliable backstop is to notice that the process chain above us broke
and hard-exit. This module anchors the server's lifetime to its client through
layered anchors:

- **Primary (Windows):** resolve the process that created the stdin pipe, hold a
  ``SYNCHRONIZE`` handle to it, and hard-exit the moment it terminates - exact
  client semantics regardless of wrapper depth. This matters especially for the
  MCPB bundle, whose launch chain interposes two ``uv`` processes, two venv
  trampolines, and a resident bootstrap between the client and this server; the
  pipe creator is the real client, none of those intermediates.
- **Fallback (Windows):** when stdin is not a client-created pipe, watch the
  discovered ancestor chain instead (handles taken at startup so PID reuse
  cannot retarget the wait, creation-time monotonicity ending the walk at a
  reused PID, and a grace window dropping transient spawn helpers).
- **POSIX:** the same layered idea without the pipe-creator primary, which has
  no portable equivalent. Reparenting is the definitive orphan signal and costs
  nothing to observe; beyond it the ancestor chain is re-read each round
  (``/proc`` on Linux, ``ps`` on macOS and the BSDs) and the process self-reaps
  once repeated rounds agree no ancestor is alive. Both platforms therefore
  re-discover rather than latch, and both treat an unreadable observation as
  ambiguous rather than as evidence of orphanhood.

stdin EOF stays the primary exit path everywhere; this module is only the
backstop for when EOF does not arrive.

Failing open is bounded on Windows. Losing every anchor - discovery finding
nothing watchable, the grace window pruning the whole chain, or the wait itself
failing - does not disarm the backstop for the process's lifetime; it enters a
re-acquisition poll that re-arms as soon as a live ancestor is discoverable
again. Only after repeated polls positively show no live ancestor does the
server reap itself, because a stdio server no live process can reach is an
orphan and the EOF path is exactly what cannot recover it there. Two rules keep
that poll safe: it never queries the stdin handle (a named-pipe query blocks
behind the transport's pending read forever, turning a recoverable disarm into a
silent permanent hang), and it decides liveness by process enumeration rather
than ``OpenProcess``, which is refused for higher-integrity clients that are
perfectly alive.

The operator kill switch is the ``cadrumo_mcp_stdio_watchdog`` setting
(environment variable ``CADRUMO_MCP_STDIO_WATCHDOG``); every failure path fails
open, because a watchdog that cannot arm must never prevent the server from
serving. Before every hard exit one structured JSON event line is flushed to
stderr, matching the companion vaultspec-core and vaultspec-rag servers' event
shape so host-side tooling can consume all three from one reader.

See Also:
    :func:`~cadrumo_harness.mcp._server.serve`
        The entry point that arms this watchdog before the transport starts.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from collections.abc import Callable

from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8

logger = logging.getLogger(__name__)

#: Operator kill switch. Declared as the ``cadrumo_mcp_stdio_watchdog`` field on
#: :class:`~core.config.Settings`; this name is the environment variable that
#: field reads, quoted here only for the log line that names it.
STDIO_WATCHDOG_ENV = "CADRUMO_MCP_STDIO_WATCHDOG"

#: Explicit client PID override, watched in addition to the discovered client.
#: Read directly from the environment alongside ``CADRUMO_MCP_PERSONA`` and
#: ``CADRUMO_MCP_SURFACE``: a PID is per-launch wiring, not a deployment
#: setting, so it does not belong on the settings facade.
PARENT_PID_ENV = "CADRUMO_MCP_PARENT_PID"

#: Ancestors beyond this depth are noise (session managers, init); the spawning
#: client is always within a few hops. The MCPB chain is the deep case at
#: client -> uv -> uv -> venv trampoline -> bootstrap -> venv trampoline -> server.
_MAX_ANCESTOR_DEPTH = 8

#: Seconds before the fallback watchdog arms. Transient spawn helpers (``cmd /c``
#: wrappers) exit within moments of spawning the chain; discovered ancestors that
#: die during the grace window are dropped instead of treated as termination
#: intent. The precise anchors (resolved client, explicit override) are never
#: grace-pruned.
_GRACE_SECONDS = 10.0

#: Coarse POSIX reparent-poll interval; the backstop does not need to be fast,
#: only eventual.
_POSIX_POLL_SECONDS = 15.0

#: Interval between anchor re-acquisition attempts once every anchor has been
#: lost. The unanchored state is rare, so the poll is coarse.
_REARM_POLL_SECONDS = 30.0

#: Consecutive unanchored polls before the process concludes it is orphaned and
#: reaps itself. A stdio server that can resolve neither a stdin pipe creator nor
#: a single live ancestor for this long has no process left that could be
#: speaking to it.
_ORPHAN_CONFIRMATIONS = 4

_SYNCHRONIZE = 0x0010_0000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x0000_1000
_INFINITE = 0xFFFF_FFFF
_WAIT_OBJECT_0 = 0x0000_0000
_WAIT_TIMEOUT = 0x0000_0102
_TH32CS_SNAPPROCESS = 0x0000_0002

#: Wall-clock bound on the pre-exit hook. The hook is a courtesy, not a
#: guarantee: a hook that hangs must never prevent the reap this module exists
#: to perform, so it runs on its own thread and is abandoned at this deadline.
_PRE_EXIT_HOOK_TIMEOUT_S = 3.0

_pre_exit_hooks: list[Callable[[], None]] = []
_pre_exit_lock = threading.Lock()
_watchdog_lock = threading.Lock()
_active_watchdog: threading.Event | None = None


def disarm_stdio_lifetime_watchdog() -> bool:
    """Disarm the currently active watchdog, if any.

    Normal stdio completion and startup failure both end the lifetime the
    watchdog protects.  Cancelling that generation prevents its daemon thread
    from observing an ancestor death later and terminating unrelated work in a
    host process that invoked the server in-process.
    """
    global _active_watchdog
    with _watchdog_lock:
        stop = _active_watchdog
        _active_watchdog = None
    if stop is None:
        return False
    stop.set()
    return True


def _new_watchdog_control() -> threading.Event:
    """Install and return the sole active watchdog generation."""
    global _active_watchdog
    stop = threading.Event()
    with _watchdog_lock:
        previous = _active_watchdog
        _active_watchdog = stop
    if previous is not None:
        previous.set()
    return stop


def register_pre_exit_hook(hook: Callable[[], None]) -> None:
    """Register a callable to run, best effort, before a watchdog hard exit.

    :func:`os._exit` bypasses :mod:`atexit`, so a watchdog reap skips every
    interpreter-shutdown hook the process registered. This gives the server a
    bounded window to release what it can before that happens.

    The contract is deliberately weak, and callers must not over-read it. Hooks
    run on a dedicated thread with a hard :data:`_PRE_EXIT_HOOK_TIMEOUT_S`
    deadline and every exception swallowed; a hook that hangs or raises is
    abandoned and the exit proceeds.

    A hook runs on the watchdog's own thread, so it observes NO
    :class:`~contextvars.ContextVar` state bound by other threads. A hook that
    must act on state another thread owns has to reach it through a
    process-wide registry rather than a context lookup - which is why the
    server's key-zeroisation hook sweeps the live bucket-session registry
    instead of calling the context-scoped close, and why a hook doing the
    latter would silently no-op while appearing to work.

    Args:
        hook: Zero-argument callable run before the hard exit.
    """
    with _pre_exit_lock:
        _pre_exit_hooks.append(hook)


def _run_pre_exit_hooks() -> None:
    """Run registered pre-exit hooks on a bounded, isolated thread."""
    with _pre_exit_lock:
        hooks = list(_pre_exit_hooks)
    if not hooks:
        return

    def _drain() -> None:
        for hook in hooks:
            try:
                hook()
            except Exception:
                logger.debug("watchdog: pre-exit hook failed", exc_info=True)

    worker = threading.Thread(target=_drain, name="cadrumo-mcp-pre-exit", daemon=True)
    worker.start()
    worker.join(_PRE_EXIT_HOOK_TIMEOUT_S)


def watchdog_disabled() -> bool:
    """Return whether the operator kill switch disables the watchdog.

    Reads the ``cadrumo_mcp_stdio_watchdog`` setting so the environment variable
    and the settings facade cannot drift apart. A settings load that refuses (a
    machine carrying retired former-product state, an unreadable dotenv) must
    not silently strip the server's only lifetime anchor, so an unreadable
    setting leaves the watchdog ENABLED.
    """
    try:
        from ._settings import load_mcp_settings

        return not load_mcp_settings().cadrumo_mcp_stdio_watchdog
    except Exception:
        logger.debug("watchdog: settings unreadable; keeping the watchdog enabled", exc_info=True)
        return False


def _resolved_parent_pid_override() -> int | None:
    """Return the explicit client PID from the environment, or ``None``.

    A malformed value is ignored rather than fatal: the override is an operator
    convenience and must never take down a server that would otherwise serve.
    """
    raw = os.environ.get(PARENT_PID_ENV, "").strip()
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        logger.warning("watchdog: ignoring malformed %s=%r", PARENT_PID_ENV, raw)
        return None
    return pid if pid > 0 else None


class _WatchedProcess:
    """A process the watchdog holds a ``SYNCHRONIZE`` handle on."""

    __slots__ = ("exe", "grace_prunable", "handle", "pid")

    def __init__(self, pid: int, exe: str, handle: int, *, grace_prunable: bool) -> None:
        self.pid = pid
        self.exe = exe
        self.handle = handle
        self.grace_prunable = grace_prunable


def _emit_event(event: str, **fields: object) -> None:
    """Flush one structured JSON event line to stderr.

    The envelope (``event`` plus ``shim_pid``) matches the companion
    vaultspec-core and vaultspec-rag servers' event shape so host tooling parses
    all three from one reader, and stderr is used because stdout carries
    JSON-RPC.
    """
    sys.stderr.write(json.dumps({"event": event, "shim_pid": os.getpid(), **fields}) + "\n")
    sys.stderr.flush()


def _exit_on_watched_death(pid: int, exe: str, reason: str = "watched_process_exit") -> None:
    """Run pre-exit hooks, flush one structured event line, and hard-exit.

    :func:`os._exit` is deliberate: shutdown must not depend on the event loop
    cooperating mid-teardown, and the blocked stdio reader cannot be cancelled
    in-process. Exit code 0 because self-reaping after the client died is the
    intended outcome, not a crash a supervisor should retry.

    Args:
        pid: The watched process whose death triggered the exit, or ``0`` when no
            anchor was ever identified.
        exe: That process's image name.
        reason: Discriminator for hosts consuming the event stream;
            ``watched_process_exit`` for an anchor's death, ``unanchored_orphan``
            for a confirmed-orphan self-reap.
    """
    _run_pre_exit_hooks()
    _emit_event(
        "stdio_watchdog_exit",
        dead_ancestor_pid=pid,
        dead_ancestor_exe=exe,
        reason=reason,
    )
    os._exit(0)


def _walk_ancestor_pids(
    start_pid: int,
    parents: dict[int, int],
    max_depth: int = _MAX_ANCESTOR_DEPTH,
) -> list[int]:
    """Ancestor PIDs of ``start_pid``, nearest first, bounded and cycle-safe.

    ``parents`` maps pid to parent pid as observed in one snapshot. The walk
    stops at the depth bound, at a missing entry, at pid 0/self-parenting, and at
    any pid already seen (snapshot cycles happen when PIDs were reused between
    rows).
    """
    chain: list[int] = []
    seen: set[int] = {start_pid}
    pid = start_pid
    for _ in range(max_depth):
        ppid = parents.get(pid)
        if ppid is None or ppid == 0 or ppid == pid or ppid in seen:
            break
        chain.append(ppid)
        seen.add(ppid)
        pid = ppid
    return chain


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _PROCESSENTRY32(ctypes.Structure):
        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        )

    class _FILETIME(ctypes.Structure):
        _fields_ = (
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        )

    # Undeclared ctypes signatures marshal through default int inference and fail
    # silently when they drift, so every binding declares argtypes and restype
    # (OpenProcess in particular truncates 64-bit handles without a pointer-sized
    # restype).
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.GetNamedPipeServerProcessId.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.WaitForMultipleObjects.argtypes = (
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.BOOL,
        wintypes.DWORD,
    )
    _kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
    _kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32))
    _kernel32.Process32First.restype = wintypes.BOOL
    _kernel32.Process32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32))
    _kernel32.Process32Next.restype = wintypes.BOOL
    _kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
    )
    _kernel32.GetProcessTimes.restype = wintypes.BOOL

    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    def _snapshot_processes() -> tuple[dict[int, int], dict[int, str]]:
        """One Toolhelp32 pass: pid to ppid and pid to exe name."""
        snap = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if snap is None or snap == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        parents: dict[int, int] = {}
        names: dict[int, str] = {}
        try:
            entry = _PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
            ok = bool(_kernel32.Process32First(snap, ctypes.byref(entry)))
            while ok:
                pid = int(entry.th32ProcessID)
                parents[pid] = int(entry.th32ParentProcessID)
                names[pid] = entry.szExeFile.decode(errors="replace")
                ok = bool(_kernel32.Process32Next(snap, ctypes.byref(entry)))
        finally:
            _kernel32.CloseHandle(snap)
        return parents, names

    def _creation_time(handle: int) -> int:
        """Process creation time as a FILETIME integer; 0 when unreadable."""
        created = _FILETIME()
        exited = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        ok = _kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not ok:
            return 0
        return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)

    def _open_process(pid: int) -> int | None:
        handle = _kernel32.OpenProcess(_SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        return int(handle) if handle else None

    def _self_creation_time() -> int:
        """This process's creation time as a FILETIME integer; 0 if unreadable."""
        handle = _open_process(os.getpid())
        if handle is None:
            return 0
        try:
            return _creation_time(handle)
        finally:
            _kernel32.CloseHandle(handle)

    def _predates(handle: int, reference_ctime: int) -> bool:
        """Whether the handle's process is old enough to be a genuine anchor.

        A real ancestor - and the process that created this process's stdin pipe -
        necessarily existed first, so a candidate younger than the reference is a
        reused PID wearing a dead process's number. An unreadable reference fails
        open and accepts the candidate.
        """
        if not reference_ctime:
            return True
        candidate_ctime = _creation_time(handle)
        return candidate_ctime != 0 and candidate_ctime <= reference_ctime

    def _close_targets(targets: list[_WatchedProcess]) -> None:
        """Release every held process handle in *targets*."""
        for target in targets:
            _kernel32.CloseHandle(target.handle)

    def resolve_stdin_client_pid() -> int | None:
        """Resolve the PID of the process that created this process's stdin pipe.

        Anonymous pipes are named pipes under the hood on Windows, so
        ``GetNamedPipeServerProcessId`` on the inherited stdin handle yields the
        pipe-creating process: the MCP client, regardless of how many wrapper
        processes (``uv``, venv trampolines, the MCPB bootstrap) sit in between.

        MUST be called on the main thread before the transport starts. Once the
        stdio reader has a ``ReadFile`` pending on that handle, this query blocks
        behind it for the life of the process.

        Returns:
            The client PID, or ``None`` when stdin is not a pipe (console or
            redirected-file stdin), the handle is unavailable, or the resolved
            PID is this process itself. Fails open on anything unexpected.
        """
        try:
            import msvcrt

            try:
                handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            except OSError:
                logger.debug("watchdog: no stdin OS handle")
                return None

            server_pid = ctypes.c_ulong(0)
            ok = _kernel32.GetNamedPipeServerProcessId(handle, ctypes.byref(server_pid))
            if not ok:
                logger.debug("watchdog: stdin is not a pipe (error %d)", ctypes.get_last_error())
                return None

            pid = int(server_pid.value)
            if pid == 0 or pid == os.getpid():
                logger.debug("watchdog: pipe creator is self or unresolved (%d)", pid)
                return None
            return pid
        except Exception:
            logger.debug("watchdog: client resolution failed", exc_info=True)
            return None

    def _open_ancestor_chain() -> list[_WatchedProcess]:
        """SYNCHRONIZE handles on the live ancestor chain, PID-reuse safe.

        Walks the snapshot parent chain from this process, opening each
        ancestor's handle immediately and enforcing creation-time monotonicity: a
        genuine ancestor existed before its child, so a "parent" younger than the
        child is a reused PID and ends the walk.
        """
        watched: list[_WatchedProcess] = []
        parents, names = _snapshot_processes()
        child_ctime = _self_creation_time()
        for pid in _walk_ancestor_pids(os.getpid(), parents):
            handle = _open_process(pid)
            if handle is None:
                break
            ancestor_ctime = _creation_time(handle)
            if child_ctime and (ancestor_ctime == 0 or ancestor_ctime > child_ctime):
                _kernel32.CloseHandle(handle)
                break
            watched.append(_WatchedProcess(pid, names.get(pid, "?"), handle, grace_prunable=True))
            child_ctime = ancestor_ctime
        return watched

    def _open_watched(pid: int, *, grace_prunable: bool) -> _WatchedProcess | None:
        """Open one explicit PID as a watched process; ``None`` when refused."""
        handle = _open_process(pid)
        if handle is None:
            logger.debug("watchdog: cannot open process %d (error %d)", pid, ctypes.get_last_error())
            return None
        try:
            _, names = _snapshot_processes()
            exe = names.get(pid, "?")
        except Exception:
            exe = "?"
        return _WatchedProcess(pid, exe, handle, grace_prunable=grace_prunable)

    def _grace_prune(watched: list[_WatchedProcess], grace_seconds: float) -> list[_WatchedProcess]:
        """Sleep the grace window and drop discovered ancestors already gone.

        Only discovered-chain targets are grace prunable; the resolved client and
        an explicit override are returned untouched, preserving the instant reap
        of an already-dead client.
        """
        if any(w.grace_prunable for w in watched):
            time.sleep(grace_seconds)
        survivors: list[_WatchedProcess] = []
        for target in watched:
            # A precise anchor is never pruned; a discovered one survives only
            # if it is still running when the grace window closes.
            still_running = _kernel32.WaitForSingleObject(target.handle, 0) == _WAIT_TIMEOUT
            if not target.grace_prunable or still_running:
                survivors.append(target)
            else:
                _kernel32.CloseHandle(target.handle)
                logger.info(
                    "watchdog: dropping ancestor %d (%s) gone during grace",
                    target.pid,
                    target.exe,
                )
        return survivors

    def _wait_any(targets: list[_WatchedProcess], timeout_ms: int) -> tuple[_WatchedProcess | None, bool]:
        """Wait boundedly for one target; return ``(dead, failed)``."""
        handles = (wintypes.HANDLE * len(targets))(*[target.handle for target in targets])
        result = int(_kernel32.WaitForMultipleObjects(len(targets), handles, False, timeout_ms))
        if result == _WAIT_TIMEOUT:
            return None, False
        index = result - _WAIT_OBJECT_0
        if not 0 <= index < len(targets):
            logger.warning(
                "watchdog: wait failed (result 0x%x, error %d)",
                result,
                ctypes.get_last_error(),
            )
            return None, True
        return targets[index], False

    def _reacquire_targets() -> list[_WatchedProcess] | None:
        """Anchors visible right now; ``None`` when the observation is ambiguous.

        Two constraints shape this probe, both settled by the companion servers'
        fix for the permanent-disarm defect (vaultspec-rag#288):

        It must never touch stdin. :func:`resolve_stdin_client_pid` is safe only
        on the main thread before the transport starts; once the reader has a
        ``ReadFile`` pending on that handle, a named-pipe query blocks behind it
        for the life of the process, turning a recoverable disarm into a silent
        permanent hang.

        Enumeration, not ``OpenProcess``, decides liveness. A Toolhelp snapshot
        lists processes without needing rights on them, while ``OpenProcess`` is
        refused for a higher-integrity target - so a live-but-privileged client
        appears in the snapshot and nowhere else, and reaping on the handle walk
        alone would kill servers whose clients are alive.

        Nothing returned is grace prunable: a process still alive this far past
        startup is a genuine anchor, not a transient spawn helper.

        Returns:
            Freshly opened anchors to wait on; an empty list when enumeration
            positively shows no live ancestor; ``None`` when the observation
            cannot be trusted - a failed snapshot, or live ancestors that refuse
            inspection - which must never count toward declaring the process
            orphaned.
        """
        try:
            parents, names = _snapshot_processes()
        except Exception:
            logger.debug("watchdog: process snapshot failed", exc_info=True)
            return None
        # A pid present as a snapshot key is a running process; the walk's chain
        # may end on a recorded ppid whose process is already gone.
        live = [pid for pid in _walk_ancestor_pids(os.getpid(), parents) if pid in parents]
        if not live:
            return []
        self_ctime = _self_creation_time()
        targets: list[_WatchedProcess] = []
        for pid in live:
            handle = _open_process(pid)
            if handle is None:
                continue
            if not _predates(handle, self_ctime):
                # A PID that outlived its process and got reused is not an
                # ancestor; waiting on it would reap this server when an
                # unrelated process exits.
                _kernel32.CloseHandle(handle)
                continue
            targets.append(_WatchedProcess(pid, names.get(pid, "?"), handle, grace_prunable=False))
        if not targets:
            # Live ancestors exist but none can be watched. Ambiguous, so keep
            # polling rather than reaping a server that still has a client;
            # races may only ever extend protection.
            logger.debug("watchdog: %d live ancestor(s) visible but none watchable", len(live))
            return None
        return targets

    def _windows_wait(
        watched: list[_WatchedProcess],
        grace_seconds: float,
        rearm_seconds: float = _REARM_POLL_SECONDS,
        orphan_confirmations: int = _ORPHAN_CONFIRMATIONS,
        stop: threading.Event | None = None,
    ) -> None:
        """Wait on the anchors, re-acquiring rather than disarming for good.

        Runs on a daemon thread. Discovered ancestors are grace pruned first,
        then the survivors are waited on and any death hard-exits the process.
        Losing every anchor - arming with nothing watchable, the grace window
        pruning the whole chain, or the wait API failing - does not end the
        watchdog: it falls into a re-acquisition poll that re-arms the moment an
        anchor resolves again, and reaps the process only once
        ``orphan_confirmations`` consecutive polls agree that neither a stdin
        pipe creator nor one live ancestor exists. That state is the orphan stdin
        EOF cannot recover from on Windows.
        """
        stop = stop or threading.Event()
        targets = _grace_prune(watched, grace_seconds)
        if stop.is_set():
            _close_targets(targets)
            return
        if not targets:
            _emit_event("stdio_watchdog_disarmed", reason="no_anchor_after_grace")
        unanchored_polls = 0
        while True:
            if stop.is_set():
                _close_targets(targets)
                return
            if targets:
                dead, failed = _wait_any(targets, 250)
                if dead is not None:
                    if stop.is_set():
                        _close_targets(targets)
                        return
                    _exit_on_watched_death(dead.pid, dead.exe)
                if not failed:
                    continue
                # The wait failed on live targets: release the handles and
                # rebuild from discovery instead of leaving the process
                # unanchored for the rest of its life.
                _close_targets(targets)
                targets = []
                unanchored_polls = 0
                _emit_event("stdio_watchdog_disarmed", reason="wait_failed")
            if stop.wait(rearm_seconds):
                return
            reacquired = _reacquire_targets()
            if reacquired is None:
                # Ambiguous observation: reset rather than accumulate, so a race
                # can only ever extend protection.
                unanchored_polls = 0
                continue
            if reacquired:
                targets = reacquired
                unanchored_polls = 0
                logger.info(
                    "watchdog: re-armed on %s",
                    ", ".join(f"{t.pid}({t.exe})" for t in targets),
                )
                continue
            unanchored_polls += 1
            logger.warning(
                "watchdog: no anchor resolvable (%d/%d confirmations)",
                unanchored_polls,
                orphan_confirmations,
            )
            if unanchored_polls >= orphan_confirmations:
                _exit_on_watched_death(0, "<unanchored>", reason="unanchored_orphan")

    def _anchor_on_client(watched: list[_WatchedProcess], resolved: int | None) -> bool:
        """Add the client anchor to ``watched``; report whether one is held.

        A pid already present counts as held without opening a second handle:
        an explicit parent override naming the same process is the anchor, and
        re-opening it would leak a duplicate handle for no added liveness.
        """
        if resolved is None:
            return False
        if any(target.pid == resolved for target in watched):
            return True
        client = _open_watched(resolved, grace_prunable=False)
        if client is None:
            return False
        watched.append(client)
        return True

    def _extend_with_ancestor_chain(watched: list[_WatchedProcess]) -> None:
        """Add discovered ancestors, skipping any already watched.

        A duplicate arrives holding its own freshly-opened handle, so it must be
        closed rather than merely dropped or the handle leaks for the process
        lifetime.
        """
        known = {target.pid for target in watched}
        for target in _open_ancestor_chain():
            if target.pid in known:
                _kernel32.CloseHandle(target.handle)
            else:
                watched.append(target)

    def _windows_watch_targets(
        client_pid: int | None,
        parent_pid: int | None,
    ) -> list[_WatchedProcess]:
        """Return the processes whose exit means this server lost its client.

        Ordered by how much authority each anchor carries: an explicit parent
        override first, then the stdin pipe creator, and only when neither
        yields a client anchor does the discovered ancestor chain stand in.

        An empty list is a legitimate result, not a failure - it is the orphan
        signature itself, and the caller arms on it so the watchdog thread can
        poll for an anchor and reap on confirmed orphanhood.
        """
        watched: list[_WatchedProcess] = []
        if parent_pid is not None:
            explicit = _open_watched(parent_pid, grace_prunable=False)
            if explicit is None:
                logger.warning("watchdog: explicit parent pid %d not watchable", parent_pid)
            else:
                watched.append(explicit)
        if _anchor_on_client(watched, client_pid or resolve_stdin_client_pid()):
            return watched
        _extend_with_ancestor_chain(watched)
        return watched

    def _arm_windows_watchdog(
        *,
        client_pid: int | None,
        parent_pid: int | None,
        grace_seconds: float,
        rearm_seconds: float,
        orphan_confirmations: int,
        stop: threading.Event,
    ) -> bool:
        """Start the Windows watchdog thread over the resolved anchor set."""
        watched = _windows_watch_targets(client_pid, parent_pid)
        if not watched:
            # Nothing watchable is the orphan signature itself, not a reason
            # to stand down: arm on an empty set so the thread polls for an
            # anchor and reaps on confirmed orphanhood.
            logger.debug("watchdog: no watchable targets; arming the unanchored re-acquisition poll")
        thread = threading.Thread(
            target=_windows_wait,
            args=(watched, grace_seconds, rearm_seconds, orphan_confirmations, stop),
            name="cadrumo-mcp-client-watchdog",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            _close_targets(watched)
            raise
        logger.debug(
            "watchdog: armed on %s",
            ", ".join(f"{target.pid}({target.exe})" for target in watched) or "no anchor yet",
        )
        return True

else:

    def resolve_stdin_client_pid() -> int | None:
        """POSIX has no pipe-creator resolution; the ancestor poll covers it.

        ``GetNamedPipeServerProcessId`` has no portable equivalent: a POSIX
        anonymous pipe carries no record of which process created it. The
        ancestor chain plus reparent detection is the portable substitute, and it
        is materially safer here than on Windows because a POSIX orphan is
        reparented to init immediately and observably.
        """
        return None


def _pid_alive(pid: int) -> bool:
    """POSIX liveness probe (never use ``os.kill(pid, 0)`` on Windows).

    ``PermissionError`` means the process exists but belongs to another user,
    which is liveness, not absence - the same distinction the Windows path draws
    between enumeration and ``OpenProcess``.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        logger.debug("watchdog: liveness probe failed for pid %d", pid, exc_info=True)
        return True
    return True


def _posix_parent_map() -> dict[int, int] | None:
    """A pid-to-ppid snapshot, or ``None`` when the platform declines.

    Linux exposes this through ``/proc`` with no subprocess at all; macOS and the
    BSDs have no ``/proc``, so ``ps`` is the portable fallback. Reading ``/proc``
    first keeps the common Linux container case free of a per-poll fork.

    Returns ``None`` rather than an empty map when the observation fails, so an
    unreadable snapshot can never be mistaken for "no ancestors are alive" and
    trigger a false orphan reap - the same ambiguity rule the Windows
    re-acquisition poll follows.
    """
    proc_root = "/proc"
    if os.path.isdir(proc_root):
        return _proc_parent_map(proc_root)
    return _ps_parent_map()


def _proc_parent_map(proc_root: str) -> dict[int, int] | None:
    """Snapshot pid-to-ppid from ``/proc``, or ``None`` when the directory walk fails."""
    parents: dict[int, int] = {}
    try:
        for name in os.listdir(proc_root):
            if not name.isdigit():
                continue
            try:
                with open(f"{proc_root}/{name}/stat", encoding=_UTF_8) as handle:
                    fields = handle.read().rsplit(")", 1)[-1].split()
                # After the comm field, fields are: state, ppid, ...
                parents[int(name)] = int(fields[1])
            except (OSError, IndexError, ValueError):
                # The process exited between listdir and read; skip it.
                continue
    except OSError:
        logger.debug("watchdog: /proc snapshot failed", exc_info=True)
        return None
    return parents or None


def _ps_parent_map() -> dict[int, int] | None:
    """Snapshot pid-to-ppid through ``ps`` on a POSIX platform that has no ``/proc``."""
    # Imported lazily: this branch is only reached on a POSIX platform without
    # /proc (macOS, the BSDs), and the module must stay import-cheap on the
    # startup path.
    import subprocess

    try:
        completed = subprocess.run(
            ["ps", "-Ao", "pid=,ppid="],  # noqa: S607 - fixed argv; ps is resolved from PATH by design
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug("watchdog: ps snapshot failed", exc_info=True)
        return None
    if completed.returncode != 0:
        return None
    parents = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                parents[int(parts[0])] = int(parts[1])
            except ValueError:
                continue
    return parents or None


#: PIDs that are never a lifetime anchor. init/launchd adopts every orphan, so
#: counting it as a live ancestor would make the orphan-confirmation poll
#: unreachable: the chain of an abandoned process always ends at it. Reparenting
#: TO this pid is the orphan signal, not evidence of a client.
_POSIX_NON_ANCHOR_PIDS = frozenset({0, 1})


def _posix_ancestor_pids() -> list[int] | None:
    """Candidate anchor ancestors, nearest first.

    Mirrors the Windows :func:`_reacquire_targets` contract exactly, and the
    three-way return is the whole point: ``None`` means the observation failed
    and must never count toward a reap, ``[]`` means the walk positively found
    nothing above us but init, and a non-empty list is the live anchor set.
    Collapsing the first two into one empty list is what would make the
    orphan-confirmation poll either unreachable or trigger-happy.

    init/launchd is filtered out deliberately - see
    :data:`_POSIX_NON_ANCHOR_PIDS`.
    """
    parents = _posix_parent_map()
    if parents is None:
        return None
    return [pid for pid in _walk_ancestor_pids(os.getpid(), parents) if pid not in _POSIX_NON_ANCHOR_PIDS]


def _posix_round_is_anchored() -> bool | None:
    """Whether any discovered ancestor is alive, or ``None`` when the snapshot is unreadable.

    The tri-state is load-bearing: an unreadable snapshot must stay
    distinguishable from a confirmed absence of live ancestors, so it can never
    be mistaken for orphanhood.
    """
    ancestors = _posix_ancestor_pids()
    if ancestors is None:
        return None
    return bool(ancestors) and any(_pid_alive(pid) for pid in ancestors)


def _posix_watchdog(
    initial_ppid: int,
    extra_pids: tuple[int, ...],
    poll_seconds: float = _POSIX_POLL_SECONDS,
    orphan_confirmations: int = _ORPHAN_CONFIRMATIONS,
    stop: threading.Event | None = None,
) -> None:
    """Ancestor-chain poll mirroring the Windows anchors on POSIX.

    Three signals, cheapest first. Reparenting (``getppid`` changed, typically to
    init) is the definitive POSIX orphan signal and needs no snapshot at all. An
    explicitly named client dying is watched directly. Otherwise the discovered
    ancestor chain is polled, and the process reaps itself once
    ``orphan_confirmations`` consecutive rounds agree that not one ancestor is
    alive.

    A chain captured at arm time is deliberately NOT held forever: like the
    Windows re-acquisition poll, the chain is re-read each round so a wrapper
    exiting during startup does not permanently strand the watchdog, and an
    unresolvable snapshot resets the counter rather than counting toward
    orphanhood.
    """
    stop = stop or threading.Event()
    unanchored_polls = 0
    while True:
        if stop.wait(poll_seconds):
            return
        if os.getppid() != initial_ppid:
            _exit_on_watched_death(initial_ppid, "parent")
        for pid in extra_pids:
            if not _pid_alive(pid):
                _exit_on_watched_death(pid, "explicit-client")
        anchored = _posix_round_is_anchored()
        if anchored is None or anchored:
            # Either an ancestor is alive, or the snapshot failed and the answer
            # is ambiguous. Never count an unreadable observation toward a reap,
            # so a race can only ever extend protection.
            unanchored_polls = 0
            continue
        unanchored_polls += 1
        logger.warning(
            "watchdog: no live ancestor (%d/%d confirmations)",
            unanchored_polls,
            orphan_confirmations,
        )
        if unanchored_polls == 1:
            _emit_event("stdio_watchdog_disarmed", reason="no_live_ancestor")
        if unanchored_polls >= orphan_confirmations:
            _exit_on_watched_death(0, "<unanchored>", reason="unanchored_orphan")


def _arm_posix_watchdog(
    *,
    parent_pid: int | None,
    rearm_seconds: float,
    orphan_confirmations: int,
    stop: threading.Event,
) -> bool:
    """Start the POSIX reparent-plus-ancestor poll thread."""
    extra = (parent_pid,) if parent_pid is not None else ()
    # The POSIX poll cadence is derived from the same knobs the Windows path
    # takes, so a test can compress both platforms through the real
    # parameters instead of patching either.
    thread = threading.Thread(
        target=_posix_watchdog,
        args=(os.getppid(), extra, min(_POSIX_POLL_SECONDS, rearm_seconds), orphan_confirmations, stop),
        name="cadrumo-mcp-client-watchdog",
        daemon=True,
    )
    thread.start()
    logger.debug("watchdog: armed POSIX ancestor poll")
    return True


def arm_stdio_lifetime_watchdog(
    client_pid: int | None = None,
    parent_pid: int | None = None,
    grace_seconds: float = _GRACE_SECONDS,
    rearm_seconds: float = _REARM_POLL_SECONDS,
    orphan_confirmations: int = _ORPHAN_CONFIRMATIONS,
) -> bool:
    """Arm the lifetime backstop; return whether a watchdog thread started.

    On Windows the primary anchor is the stdin pipe creator resolved by
    :func:`resolve_stdin_client_pid` (or the injected ``client_pid``); when
    resolution declines, the discovered ancestor chain is watched instead,
    grace-pruned so transient spawn helpers do not count as termination intent.
    An explicit ``parent_pid`` (or ``CADRUMO_MCP_PARENT_PID``) is watched ahead
    of discovery in either mode. Finding nothing watchable still arms: the thread
    polls for an anchor and self-reaps only on confirmed orphanhood. On POSIX the
    same contract holds through reparent detection plus an ancestor-chain poll,
    with the identical orphan-confirmation rule; only the pipe-creator primary is
    Windows-specific, having no portable counterpart.

    MUST be called on the main thread before the stdio transport starts, because
    pipe-creator resolution is only safe there.

    Arming failures fail open, and the ``cadrumo_mcp_stdio_watchdog`` kill switch
    skips arming entirely.

    Args:
        client_pid: Explicit client PID for the primary anchor. Defaults to the
            stdin pipe creator.
        parent_pid: Additional process to watch ahead of discovery. Defaults to
            ``CADRUMO_MCP_PARENT_PID``.
        grace_seconds: Fallback grace window before discovered ancestors count as
            termination intent.
        rearm_seconds: Windows only; interval between anchor re-acquisition
            attempts while no anchor is held.
        orphan_confirmations: Windows only; consecutive unanchored polls required
            before the process reaps itself as an orphan.

    Returns:
        ``True`` when a watchdog thread armed, ``False`` when arming was disabled
        or failed open and the server retains EOF-only shutdown.
    """
    if watchdog_disabled():
        logger.info(
            "watchdog: disabled via %s; stdin EOF is the only exit path",
            STDIO_WATCHDOG_ENV,
        )
        return False

    stop = _new_watchdog_control()

    if parent_pid is None:
        parent_pid = _resolved_parent_pid_override()

    try:
        if sys.platform == "win32":
            return _arm_windows_watchdog(
                client_pid=client_pid,
                parent_pid=parent_pid,
                grace_seconds=grace_seconds,
                rearm_seconds=rearm_seconds,
                orphan_confirmations=orphan_confirmations,
                stop=stop,
            )
        return _arm_posix_watchdog(
            parent_pid=parent_pid,
            rearm_seconds=rearm_seconds,
            orphan_confirmations=orphan_confirmations,
            stop=stop,
        )
    except Exception:
        disarm_stdio_lifetime_watchdog()
        logger.debug("watchdog: arming failed; not arming", exc_info=True)
        return False


__all__ = [
    "PARENT_PID_ENV",
    "STDIO_WATCHDOG_ENV",
    "arm_stdio_lifetime_watchdog",
    "disarm_stdio_lifetime_watchdog",
    "register_pre_exit_hook",
    "resolve_stdin_client_pid",
    "watchdog_disabled",
]
