"""Tests for the MCP stdio client-lifetime watchdog.

Every test drives real processes and real pipes: children are spawned with
``sys.executable``, stdin pipes are genuine OS pipes, and liveness is observed
through the same Win32 process-handle semantics the watchdog relies on. No
mocks, stubs, or skips: on non-Windows platforms the same tests assert the
module's genuine POSIX contract (no pipe-creator resolution, reparent-poll
arming) instead of being deselected.

Coverage spans the layered anchors: the client-PID primary (resolution directly
and through wrapper depth, instant reap of a dead client), the ancestor-chain
fallback (non-pipe launches, grace-window pruning of transient spawners), the
operator kill switch, the pre-exit hook that compensates for ``os._exit``
bypassing :mod:`atexit`, and the structured stderr events.

The load-bearing regression is the unanchored case. Both sibling
implementations shipped a defect where losing every anchor disarmed the backstop
permanently and left the server relying on stdin EOF - the exact thing that does
not arrive on Windows - stranding servers for 20+ hours. The corrected design
re-acquires instead of standing down, and self-reaps only on confirmed
orphanhood; ``test_unanchored_worker_reaps_itself_when_all_ancestry_is_gone``
and its event sibling are what hold that fix in place.
"""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import pytest

from .._settings import reset_mcp_settings_cache
from .._stdio_lifetime import (
    _GRACE_SECONDS,
    PARENT_PID_ENV,
    STDIO_WATCHDOG_ENV,
    arm_stdio_lifetime_watchdog,
    disarm_stdio_lifetime_watchdog,
    register_pre_exit_hook,
    resolve_stdin_client_pid,
    watchdog_disabled,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

if TYPE_CHECKING:
    from pathlib import Path

_MODULE = "cadrumo_harness.mcp._stdio_lifetime"
_RESOLVER_SNIPPET = f"from {_MODULE} import resolve_stdin_client_pid;print(resolve_stdin_client_pid(), flush=True)"


def _wait_for_pid_exit(pid: int, timeout: float) -> bool:
    """Wait until *pid* exits (Windows only).

    Uses ``OpenProcess``/``WaitForSingleObject`` rather than ``os.kill``, which
    on Windows terminates the target instead of probing it.
    """
    if sys.platform != "win32":  # pragma: no cover - callers gate on the platform
        # Narrowed here as well as at the call sites: the ctypes Windows API below
        # is absent from the POSIX stubs, so a checker running on Linux reports
        # every reference unresolved unless the platform is established in-body.
        raise RuntimeError("the Windows process-wait probe is not available on this platform")

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x0010_0000, False, ctypes.c_ulong(pid))
    if not handle:
        return True
    try:
        return bool(kernel32.WaitForSingleObject(ctypes.c_void_p(handle), int(timeout * 1000)) == 0)
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def _kill_pid(pid: int) -> None:
    """Force-kill *pid* on either platform, ignoring an already-dead target."""
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"] if sys.platform == "win32" else ["kill", "-9", str(pid)],
        capture_output=True,
        check=False,
    )


def test_resolver_identifies_pipe_creating_process() -> None:
    """A child resolving its stdin pipe reports the pipe creator's PID.

    ``subprocess.PIPE`` creates the stdin pipe inside this test process, so the
    child's resolver must return this process's PID on Windows and the fail-open
    ``None`` elsewhere.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _RESOLVER_SNIPPET],
        stdin=subprocess.PIPE,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    expected = str(os.getpid()) if sys.platform == "win32" else "None"
    assert proc.stdout.strip() == expected


def test_resolver_sees_through_wrapper_processes() -> None:
    """Wrapper depth does not change the resolved client PID.

    This is the property the MCPB bundle depends on: its launch chain interposes
    two ``uv`` processes, two venv trampolines, and the resident bootstrap
    between the client and the server, and the watchdog must still anchor to the
    client rather than to any of them.
    """
    intermediary = (
        "import subprocess, sys;"
        f"sys.exit(subprocess.run([sys.executable, '-c', {_RESOLVER_SNIPPET!r}], stdin=sys.stdin).returncode)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", intermediary],
        stdin=subprocess.PIPE,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    expected = str(os.getpid()) if sys.platform == "win32" else "None"
    assert proc.stdout.strip() == expected


def test_non_pipe_stdin_arms_ancestor_fallback(tmp_path: Path) -> None:
    """A file-backed stdin declines resolution but still arms a backstop."""
    snippet = (
        f"from {_MODULE} import arm_stdio_lifetime_watchdog, resolve_stdin_client_pid;"
        "print(resolve_stdin_client_pid(), arm_stdio_lifetime_watchdog(), flush=True)"
    )
    stdin_file = tmp_path / "stdin.txt"
    stdin_file.write_text("not a pipe\n", encoding="utf-8")
    with stdin_file.open("rb") as handle:
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            stdin=handle,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "None True"


def test_kill_switch_disables_arming_in_process() -> None:
    """The settings kill switch declines arming before any anchor is touched.

    Drives the real ``CADRUMO_MCP_STDIO_WATCHDOG`` environment variable through
    the settings facade, proving the documented operator knob is the one the
    watchdog actually reads rather than a second, drifting env lookup.
    """
    previous = os.environ.get(STDIO_WATCHDOG_ENV)
    os.environ[STDIO_WATCHDOG_ENV] = "false"
    # `_constructed_settings` is lru_cached, so settings built earlier in this
    # process would answer from before the assignment above and the env var
    # would look inert. Dropping the cache keeps this driving the REAL
    # environment variable through the real settings facade - the point of the
    # test - instead of substituting `override_settings`, which would prove the
    # override mechanism rather than the operator's knob.
    reset_mcp_settings_cache()
    try:
        assert watchdog_disabled() is True
        assert arm_stdio_lifetime_watchdog() is False
        os.environ[STDIO_WATCHDOG_ENV] = "true"
        reset_mcp_settings_cache()
        assert watchdog_disabled() is False
    finally:
        if previous is None:
            del os.environ[STDIO_WATCHDOG_ENV]
        else:
            os.environ[STDIO_WATCHDOG_ENV] = previous
        reset_mcp_settings_cache()


def test_disarm_prevents_an_armed_watchdog_from_killing_later_work(tmp_path: Path) -> None:
    """Normal completion cancels the generation before its client dies."""
    victim = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog, disarm_stdio_lifetime_watchdog
        print(f"armed={{arm_stdio_lifetime_watchdog(client_pid={victim.pid}, parent_pid={victim.pid}, rearm_seconds=0.1)}}", flush=True)
        print(f"disarmed={{disarm_stdio_lifetime_watchdog()}}", flush=True)
        time.sleep(3)
        print("later-work-complete", flush=True)
        """
    )
    worker = subprocess.Popen([sys.executable, "-c", worker_code], stdout=subprocess.PIPE, text=True)
    try:
        assert worker.stdout is not None
        assert worker.stdout.readline().strip() == "armed=True"
        assert worker.stdout.readline().strip() == "disarmed=True"
        victim.kill()
        victim.wait(timeout=30)
        assert worker.stdout.readline().strip() == "later-work-complete"
        assert worker.wait(timeout=30) == 0
    finally:
        if worker.poll() is None:
            worker.kill()
        if victim.poll() is None:
            victim.kill()


def test_disarm_is_idempotent_without_an_active_generation() -> None:
    """Repeated normal cleanup cannot affect a later watchdog generation."""
    disarm_stdio_lifetime_watchdog()
    assert disarm_stdio_lifetime_watchdog() is False


def test_armed_worker_exits_when_dead_client_pid_signals() -> None:
    """Arming against an already-exited client exits the worker immediately.

    The test holds the victim's ``Popen`` handle so the kernel keeps the process
    object alive after exit: ``OpenProcess`` then succeeds and the wait fires at
    once. On POSIX the override path declines and the worker reports it stayed
    up.
    """
    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)

    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        armed = arm_stdio_lifetime_watchdog(client_pid={victim.pid})
        print(f"armed={{armed}}", flush=True)
        time.sleep(20)
        print("still-alive", flush=True)
        """
    )
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    elapsed = time.monotonic() - started
    if sys.platform == "win32":
        # The wait fires the instant it arms, so os._exit races (and usually
        # beats) the worker's own print: assert on the exit, not the output.
        assert proc.returncode == 0
        assert "still-alive" not in proc.stdout
        assert elapsed < 15, f"worker outlived a dead client by {elapsed:.1f}s"
    else:
        assert "armed=False" in proc.stdout
        assert "still-alive" in proc.stdout


def test_dead_client_exit_emits_the_structured_event() -> None:
    """The reap is observable on stderr in the shared sibling event shape."""
    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)

    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        arm_stdio_lifetime_watchdog(client_pid={victim.pid}, parent_pid={victim.pid})
        time.sleep(20)
        print("still-alive", flush=True)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if sys.platform != "win32":
        assert "still-alive" in proc.stdout
        return
    assert proc.returncode == 0
    assert "still-alive" not in proc.stdout
    events = [json.loads(line) for line in proc.stderr.splitlines() if line.startswith("{")]
    assert events, f"no exit event on stderr: {proc.stderr!r}"
    event = events[-1]
    assert event["event"] == "stdio_watchdog_exit"
    assert event["dead_ancestor_pid"] == victim.pid
    assert event["reason"] == "watched_process_exit"
    assert event["shim_pid"] != os.getpid()


def test_parent_pid_env_override_is_honoured() -> None:
    """``CADRUMO_MCP_PARENT_PID`` reaches the watchdog without an explicit argument.

    The bundle and any wrapper launcher configure the override through the
    environment, so the env path - not just the keyword argument - must anchor.
    """
    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)

    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        arm_stdio_lifetime_watchdog()
        time.sleep(20)
        print("still-alive", flush=True)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        env={**os.environ, PARENT_PID_ENV: str(victim.pid)},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if sys.platform != "win32":
        assert "still-alive" in proc.stdout
        return
    assert "still-alive" not in proc.stdout, "the env override never anchored the watchdog"
    events = [json.loads(line) for line in proc.stderr.splitlines() if line.startswith("{")]
    assert events and events[-1]["dead_ancestor_pid"] == victim.pid, proc.stderr


def test_malformed_parent_pid_env_does_not_prevent_serving() -> None:
    """A garbage override is ignored rather than taking the server down."""
    worker_code = textwrap.dedent(
        f"""
        from {_MODULE} import arm_stdio_lifetime_watchdog
        print(f"armed={{arm_stdio_lifetime_watchdog(grace_seconds=0.2)}}", flush=True)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        env={**os.environ, PARENT_PID_ENV: "not-a-pid"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "armed=True" in proc.stdout


def test_pre_exit_hook_runs_before_the_hard_exit(tmp_path: Path) -> None:
    """Registered hooks run before ``os._exit`` skips every atexit hook.

    This is what keeps a watchdog reap from stranding process-global state (the
    bucket lockfiles that would otherwise block the operator's next session).
    The hook writes to a file rather than a pipe because the exit is immediate.
    """
    if sys.platform != "win32":
        # The hook mechanism is platform-independent; assert it directly rather
        # than driving the POSIX reparent poll's 15s cadence.
        marker: list[str] = []
        register_pre_exit_hook(lambda: marker.append("ran"))
        from .._stdio_lifetime import _run_pre_exit_hooks

        _run_pre_exit_hooks()
        assert marker == ["ran"]
        return

    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)
    receipt = tmp_path / "pre-exit.txt"
    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog, register_pre_exit_hook
        register_pre_exit_hook(
            lambda: open({str(receipt)!r}, "w", encoding="utf-8").write("ran")
        )
        arm_stdio_lifetime_watchdog(client_pid={victim.pid})
        time.sleep(20)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert receipt.exists(), "the pre-exit hook did not run before os._exit"
    assert receipt.read_text(encoding="utf-8") == "ran"


def test_a_hanging_pre_exit_hook_cannot_block_the_reap(tmp_path: Path) -> None:
    """A wedged hook is abandoned; the reap still happens promptly.

    The hook is a courtesy and must never become a way for a stuck resource to
    keep an orphaned server alive - the failure this whole module exists to
    prevent.
    """
    if sys.platform != "win32":
        from .._stdio_lifetime import _run_pre_exit_hooks

        register_pre_exit_hook(lambda: time.sleep(30))
        started = time.monotonic()
        _run_pre_exit_hooks()
        assert time.monotonic() - started < 10
        return

    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)
    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog, register_pre_exit_hook
        register_pre_exit_hook(lambda: time.sleep(300))
        arm_stdio_lifetime_watchdog(client_pid={victim.pid})
        time.sleep(60)
        """
    )
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 0
    assert elapsed < 30, f"a hung pre-exit hook delayed the reap by {elapsed:.1f}s"


def test_fallback_grace_window_prunes_transient_ancestor(tmp_path: Path) -> None:
    """An ancestor dying inside the grace window is not termination intent.

    The intermediary exits right after spawning the worker (a transient spawn
    helper, exactly what ``uv`` is in the real chain); the worker's fallback must
    prune it during the grace window and keep serving on the surviving
    ancestors. The worker reports through a result file, never through a pipe its
    dead parent owned, so a broken pipe cannot fake the outcome.
    """
    result_file = tmp_path / "worker-result.txt"
    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        armed = arm_stdio_lifetime_watchdog(grace_seconds=4.0)
        with open({str(result_file)!r}, "a", encoding="utf-8") as fh:
            fh.write(f"armed={{armed}}\\n")
            fh.flush()
            time.sleep(8)
            fh.write("still-alive\\n")
        """
    )
    intermediary_code = textwrap.dedent(
        f"""
        import subprocess, sys, time
        worker = subprocess.Popen(
            [sys.executable, "-c", {worker_code!r}],
            stdin=subprocess.DEVNULL,
        )
        print(worker.pid, flush=True)
        time.sleep(1)
        """
    )
    worker_pid = 0
    intermediary = subprocess.Popen(
        [sys.executable, "-c", intermediary_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert intermediary.stdout is not None
        worker_pid = int(intermediary.stdout.readline())
        intermediary.wait(timeout=60)

        deadline = time.monotonic() + 40
        content = ""
        while time.monotonic() < deadline:
            content = result_file.read_text(encoding="utf-8") if result_file.exists() else ""
            if "still-alive" in content or "armed=False" in content:
                break
            time.sleep(0.5)
        assert "armed=True" in content, content
        assert "still-alive" in content, "worker was reaped by a grace-window death instead of pruning it"
    finally:
        if intermediary.poll() is None:
            intermediary.kill()
        if worker_pid:
            _kill_pid(worker_pid)


def _pid_is_openable(pid: int) -> bool:
    """Whether ``OpenProcess`` still resolves *pid* (Windows only).

    A fully released process object refuses ``OpenProcess`` even by a PID the
    caller remembers, which is exactly the state the watchdog's ancestor walk
    sees for a dead, unreferenced ancestor.
    """
    if sys.platform != "win32":  # pragma: no cover - the caller gates on the platform
        raise RuntimeError("the Windows handle probe is not available on this platform")

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x0010_0000, False, ctypes.c_ulong(pid))
    if not handle:
        return False
    kernel32.CloseHandle(ctypes.c_void_p(handle))
    return True


def _orphanable_spawn() -> tuple[str, dict[str, str]]:
    """Interpreter and environment for a process that can genuinely orphan.

    Spawning through the venv's ``python.exe`` is useless for orphan tests: under
    uv it is a trampoline that stays resident as its child's parent for the
    child's entire life, so no orphan can form beneath it and the ancestor walk
    always finds a live anchor. The base interpreter carries no such shim, but it
    also resolves none of the venv's imports, hence the explicit source root and
    purelib on ``PYTHONPATH``.
    """
    import sysconfig
    from pathlib import Path as _Path

    base_candidate: object = getattr(sys, "_base_executable", None)
    base = base_candidate if isinstance(base_candidate, str) and base_candidate else sys.executable
    # Derived from this test module's own location (three parents up: tests ->
    # mcp -> cadrumo_harness -> src) rather than an absolute `import
    # cadrumo`, so the relative-imports gate stays satisfied.
    src_root = _Path(__file__).resolve().parents[3]
    application_src_root = _Path(__file__).resolve().parents[3]
    roots = [str(src_root), str(application_src_root), sysconfig.get_paths()["purelib"]]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        roots.append(existing)
    return base, {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(roots),
        STDIO_WATCHDOG_ENV: "true",
    }


def _spawn_unanchored_worker(tmp_path: Path, *, stderr_path: Path, confirmations: int = 2) -> int:
    """Spawn a worker whose entire discovered ancestry is gone before arming.

    Reproduces the field orphan. An intermediary spawns the worker with a
    non-pipe stdin (so no client PID can resolve) and exits; the worker blocks on
    a release file until this test has confirmed the dead intermediary is no
    longer openable, so the ancestor walk provably breaks at it and never reaches
    this live test process. The watchdog therefore arms with no anchor
    whatsoever. Timings are compressed through the real arming knobs rather than
    patched.
    """
    release_file = tmp_path / "release.txt"
    worker_code = textwrap.dedent(
        f"""
        import os, sys, time
        deadline = time.monotonic() + 60
        while not os.path.exists({str(release_file)!r}):
            if time.monotonic() > deadline:
                raise SystemExit("release file never appeared")
            time.sleep(0.1)
        sys.stderr = open({str(stderr_path)!r}, "w", encoding="utf-8", buffering=1)
        from {_MODULE} import arm_stdio_lifetime_watchdog
        arm_stdio_lifetime_watchdog(
            grace_seconds=0.5,
            rearm_seconds=0.5,
            orphan_confirmations={confirmations},
        )
        time.sleep(120)
        """
    )
    base, env = _orphanable_spawn()
    intermediary_code = textwrap.dedent(
        f"""
        import os, subprocess
        worker = subprocess.Popen(
            [{base!r}, "-c", {worker_code!r}],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(os.getpid(), flush=True)
        print(worker.pid, flush=True)
        """
    )
    # subprocess.run drops its Popen on return, releasing the last handle to the
    # exited intermediary; a retained Popen would keep the process object alive
    # and OpenProcess would still resolve its PID.
    completed = subprocess.run(
        [base, "-c", intermediary_code],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    intermediary_pid, worker_pid = (int(line) for line in completed.stdout.split())

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        gc.collect()
        if not _pid_is_openable(intermediary_pid):
            break
        time.sleep(0.2)
    assert not _pid_is_openable(intermediary_pid), "the intermediary is still openable; the worker would find an anchor"
    release_file.write_text("go", encoding="utf-8")
    return worker_pid


def _wait_for_posix_pid_exit(pid: int, timeout: float) -> bool:
    """Poll POSIX liveness until *pid* exits or the deadline passes.

    ``os.kill(pid, 0)`` is the correct probe on POSIX only; on Windows it
    terminates the target, hence the separate handle-based helper above.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.5)
    return False


def test_posix_parent_map_resolves_this_process_ancestry() -> None:
    """The portable ancestry snapshot agrees with ``os.getppid()``.

    The POSIX anchor is only as good as this snapshot, and it has two very
    different backends (``/proc`` on Linux, ``ps`` elsewhere). Asserting it
    against the kernel's own answer for THIS process proves the parser on
    whichever backend the platform actually took.
    """
    if sys.platform == "win32":
        from .._stdio_lifetime import _snapshot_processes

        parents, _ = _snapshot_processes()
        assert parents[os.getpid()] == os.getppid()
        return

    from .._stdio_lifetime import _posix_ancestor_pids, _posix_parent_map

    parents = _posix_parent_map()
    assert parents is not None, "no portable ancestry backend resolved on this platform"
    assert parents[os.getpid()] == os.getppid()
    ancestors = _posix_ancestor_pids()
    assert ancestors is not None, "the ancestry backend resolved a parent map but no ancestor list"
    assert ancestors[0] == os.getppid()


def test_posix_worker_reaps_itself_when_reparented(tmp_path: Path) -> None:
    """Killing the parent reaps the worker through the POSIX reparent signal.

    An intermediary spawns the worker and is then killed, so the worker is
    reparented to init and must exit rather than serve on with no client.

    This scenario is POSIX-only by design, and Windows is not deselected but
    asserted: there the discovered-ancestor fallback grace-prunes any ancestor
    that dies inside the grace window, treating it as a transient spawn helper
    rather than termination intent. This test kills the intermediary the
    instant the worker arms, which is squarely inside that window, so the
    documented Windows behaviour is to keep serving. Asserting a reap there
    would contradict :func:`test_fallback_grace_window_prunes_transient_ancestor`,
    which pins exactly that survival. The Windows branch therefore asserts the
    grace window is real, which is the property that makes the scenario
    inapplicable, rather than skipping or asserting a falsehood.
    """
    if sys.platform == "win32":
        assert _GRACE_SECONDS > 0, (
            "the discovered-ancestor fallback prunes an ancestor that dies inside the grace "
            "window, so this reparent scenario cannot reap on Windows; a zero grace window "
            "would make it applicable and this test would need a real Windows arm"
        )
        return

    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        arm_stdio_lifetime_watchdog(rearm_seconds=1.0, orphan_confirmations=2)
        print("armed", flush=True)
        time.sleep(120)
        """
    )
    intermediary_code = textwrap.dedent(
        f"""
        import subprocess, sys, time
        worker = subprocess.Popen(
            [sys.executable, "-c", {worker_code!r}],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            text=True,
        )
        print(worker.pid, flush=True)
        print(worker.stdout.readline().strip(), flush=True)
        time.sleep(3600)
        """
    )
    worker_pid = 0
    intermediary = subprocess.Popen(
        [sys.executable, "-c", intermediary_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert intermediary.stdout is not None
        worker_pid = int(intermediary.stdout.readline())
        assert intermediary.stdout.readline().strip() == "armed"
        intermediary.kill()
        intermediary.wait(timeout=60)
        assert _wait_for_posix_pid_exit(worker_pid, timeout=60), (
            "reparented worker survived; the POSIX anchor did not fire"
        )
    finally:
        if intermediary.poll() is None:
            intermediary.kill()
        if worker_pid:
            _kill_pid(worker_pid)


def test_unanchored_worker_reaps_itself_when_all_ancestry_is_gone(tmp_path: Path) -> None:
    """A worker with no resolvable anchor reaps itself instead of leaking.

    This is the sibling repos' reported defect (vaultspec-core#281,
    vaultspec-rag#288) that cadrumo must not inherit: pipe resolution declines,
    every discovered ancestor is already gone, and the process would otherwise be
    left with stdin EOF - documented as unreliable on Windows - as its only exit
    path. The watchdog must confirm orphanhood across polls and then exit, rather
    than standing down for the process's lifetime.

    The POSIX equivalent of this scenario is covered by the reparent test above:
    a POSIX orphan is reparented to init immediately, which is a stronger and
    cheaper signal than the confirmation poll.
    """
    if sys.platform != "win32":
        assert resolve_stdin_client_pid() is None
        return

    stderr_path = tmp_path / "worker-stderr.txt"
    worker_pid = _spawn_unanchored_worker(tmp_path, stderr_path=stderr_path)
    try:
        assert _wait_for_pid_exit(worker_pid, timeout=60), (
            "unanchored worker survived; it would have leaked indefinitely"
        )
    finally:
        _kill_pid(worker_pid)


def test_unanchored_worker_emits_disarm_and_reasoned_exit_events(tmp_path: Path) -> None:
    """The unanchored path is observable on stderr, not just in the logs.

    Losing every anchor emits ``stdio_watchdog_disarmed`` so host tooling can
    detect an unanchored server immediately, and the eventual self-reap carries
    ``reason=unanchored_orphan`` to distinguish it from an anchor's death.
    Without this assertion a worker that merely died with its launcher would pass
    the liveness test above.
    """
    if sys.platform != "win32":
        assert resolve_stdin_client_pid() is None
        return

    stderr_path = tmp_path / "worker-stderr.txt"
    worker_pid = _spawn_unanchored_worker(tmp_path, stderr_path=stderr_path)
    try:
        assert _wait_for_pid_exit(worker_pid, timeout=60), "worker was never reaped"
        stderr_text = stderr_path.read_text(encoding="utf-8")
        events = [json.loads(line) for line in stderr_text.splitlines() if line.startswith("{")]
        names = [event["event"] for event in events]
        assert "stdio_watchdog_disarmed" in names, stderr_text
        disarmed = next(e for e in events if e["event"] == "stdio_watchdog_disarmed")
        assert disarmed["reason"] == "no_anchor_after_grace", disarmed
        assert disarmed["shim_pid"] == worker_pid

        exits = [e for e in events if e["event"] == "stdio_watchdog_exit"]
        assert exits, events
        assert exits[-1]["reason"] == "unanchored_orphan", exits[-1]
        assert exits[-1]["shim_pid"] == worker_pid
    finally:
        _kill_pid(worker_pid)


def test_real_server_exits_when_client_dies_despite_a_leaked_stdin_pipe() -> None:
    """End-to-end reproduction of the reported leak, resolved by the watchdog.

    This is the only test that proves the *wiring* rather than the module: it
    spawns the real ``cadrumo-mcp`` executable, so it fails if ``_run_server``
    stops arming the watchdog, if arming moves after the transport starts (where
    pipe resolution deadlocks), or if the kill switch defaults to off.

    A client process creates the server's stdin pipe with an inheritable write
    end, spawns the server on the read end, and leaks the write end into a
    sibling sleeper. Killing the client therefore leaves the pipe open - the
    sibling holds it - so stdin EOF can never arrive and only the client
    watchdog can reap the server. That is exactly the Windows condition issue
    #621 describes; on POSIX the reparent anchor covers the same abandonment and
    is proven by the reparent test above.
    """
    if sys.platform != "win32":
        # The leaked-pipe reproduction depends on Windows named-pipe
        # creator resolution (GetNamedPipeServerProcessId); POSIX has no
        # portable equivalent (see resolve_stdin_client_pid's own contract),
        # and the reparent test above proves the POSIX abandonment case for
        # real instead.
        assert resolve_stdin_client_pid() is None
        return

    client_code = textwrap.dedent(
        """
        import json, os, subprocess, sys, time
        r, w = os.pipe()
        os.set_inheritable(w, True)
        server = subprocess.Popen(
            ["cadrumo-mcp"],
            stdin=r,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        os.close(r)
        # The sleeper inherits the pipe write end (close_fds=False), so the pipe
        # stays open after this client dies: the leak scenario.
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            close_fds=False,
        )
        print(server.pid, flush=True)
        print(sleeper.pid, flush=True)

        def send(obj):
            os.write(w, (json.dumps(obj) + "\\n").encode("utf-8"))

        def recv(expect_id):
            for _ in range(40):
                line = server.stdout.readline()
                if not line:
                    return None
                message = json.loads(line)
                if message.get("id") == expect_id:
                    return message.get("result")
            return None

        send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "leak-client", "version": "0"},
            },
        })
        init_result = recv(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_result = recv(2)
        name = (init_result or {}).get("serverInfo", {}).get("name")
        count = len((tools_result or {}).get("tools", []))
        print("SERVING name=" + str(name) + " tools=" + str(count), flush=True)
        time.sleep(3600)
        """
    )
    sleeper_pid = 0
    client = subprocess.Popen(
        [sys.executable, "-c", client_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert client.stdout is not None
        server_pid = int(client.stdout.readline())
        sleeper_pid = int(client.stdout.readline())

        # Functional floor: the server must prove it actually serves MCP over
        # this exact pipe, otherwise "it exited" would pass for a server that
        # simply crashed at startup.
        serving_line = client.stdout.readline().strip()
        assert serving_line.startswith("SERVING name=cadrumo "), serving_line
        assert int(serving_line.split("tools=", 1)[1]) > 0, serving_line

        client.kill()
        client.wait(timeout=60)

        assert _wait_for_pid_exit(server_pid, timeout=90), (
            "the real server survived its client despite the watchdog; this is the 17-hour leak from issue #621"
        )
    finally:
        if client.poll() is None:
            client.kill()
        # The sleeper is reaped on every exit path, including a failed serving
        # assertion, so no failure mode leaks the 300s pipe holder.
        if sleeper_pid:
            _kill_pid(sleeper_pid)


def test_anchored_worker_is_not_reaped_by_the_orphan_poll(tmp_path: Path) -> None:
    """A live ancestor keeps the worker up well past the confirmation window.

    The orphan reap must fire only on genuine anchorlessness. This worker has a
    non-pipe stdin (so it takes the ancestor fallback) and a parent that stays
    alive, and it must still be serving long after an unanchored sibling would
    have been reaped. Without this the previous test could be satisfied by a
    watchdog that simply always exits.
    """
    result_file = tmp_path / "anchored-result.txt"
    worker_code = textwrap.dedent(
        f"""
        import time
        from {_MODULE} import arm_stdio_lifetime_watchdog
        armed = arm_stdio_lifetime_watchdog(
            grace_seconds=0.5, rearm_seconds=0.5, orphan_confirmations=2
        )
        with open({str(result_file)!r}, "a", encoding="utf-8") as fh:
            fh.write(f"armed={{armed}}\\n")
            fh.flush()
            time.sleep(10)
            fh.write("still-alive\\n")
        """
    )
    worker = subprocess.Popen(
        [sys.executable, "-c", worker_code],
        stdin=subprocess.DEVNULL,
        cwd=tmp_path,
    )
    try:
        worker.wait(timeout=120)
        content = result_file.read_text(encoding="utf-8")
        assert "armed=True" in content, content
        assert "still-alive" in content, "an anchored worker was reaped by the orphan confirmation poll"
    finally:
        if worker.poll() is None:
            worker.kill()
