"""Run the shared agent specs against the packaged desktop, on a fresh marked storage root.

The lane drives a built package the way a person does, through its own
programs, and the desktop window through its WebView2 DevTools endpoint:

1. creates a fresh empty storage root under ``build/acceptance`` and marks it;
2. creates a synthetic profile through the package's ``aeat`` command line and
   sets its language to English, the language the shared specs read;
3. starts the remote-debugging desktop test host in a kill-on-close Job, with
   ``CADRUMO_LOCAL_STORAGE_ROOT`` and exactly one
   ``--remote-debugging-port=<port>`` in ``WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS``,
   and requires the DevTools endpoint to listen on loopback only;
4. signs the profile in through the command line, the password on its standard
   input only, and requires the sign-in to be stored so the desktop resumes it;
5. requires a provider key stored for the profile by the person;
6. runs the live Playwright project, which attaches to the window;
7. signs out, closes the window and requires every process the run started to
   have ended;
8. scans the started processes' command lines, the run's files and logs, and the
   Playwright traces and screenshots for the provider key prefix.

Exit 0 means every step held and every spec passed. Exit 1 names what failed.
Exit 3 means a prerequisite is absent: the test host, the package, an
interactive desktop, a credential store that keeps the sign-in, or the
person's stored provider key. ``--attach-only`` runs only the attachment check
and always ends incomplete. ``--served`` loads the shell from the development
server (``just dev``) for iterating on it; the host, launcher and agent stay
real.

Provider keys are entered by the person and never by this lane. It never takes
a key on its command line, in a file or in its environment.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import httpx
import psutil

from ..packaging.command_execution import run_command
from ..runtime_lifecycle.caller_owned_root import (
    AcceptanceError,
    Programs,
    consumer_environment,
    error_code,
    require,
    run_cli,
)
from .scans import (
    ProcessRecord,
    ScanResult,
    descendants,
    merge,
    process_table,
    scan_command_lines,
    scan_tree,
    survivors,
)

_REPOSITORY: Final = Path(__file__).resolve().parents[2]
_FRONTEND: Final = _REPOSITORY / "native" / "desktop" / "frontend"
_BUILD: Final = _REPOSITORY / "build" / "windows-x64"
_PACKAGE: Final = _BUILD / "stage" / "Release" / "app"
_PROFILE: Final = "desktop-agent-live"
_PACKAGED_ENTRY: Final = "http://tauri.localhost/index.html"
_DEVTOOLS_SECONDS: Final = 120.0
_RUNTIME_SECONDS: Final = 120.0
_CLOSE_SECONDS: Final = 60.0
_SETTLE_SECONDS: Final = 10.0
_WATCH_SECONDS: Final = 1.0
_DESKTOP_UNAVAILABLE: Final = 69
"""The desktop host's exit when the logon has no interactive desktop for its window."""

STORE_KEY_COMMAND: Final[str | None] = None
"""The package command a person runs to store a provider key for a profile, once the package has one."""


class UnavailableError(Exception):
    """A prerequisite of the lane is absent; the run cannot say pass or fail."""


@dataclass(frozen=True, slots=True)
class TestHost:
    """The recorded remote-debugging desktop host and the shell it loads."""

    executable: Path
    entry: str


@dataclass(slots=True)
class Watch:
    """Every process the run started, recorded as it appears, and the key findings on their command lines."""

    roots: list[int]
    members: Callable[[], tuple[int, ...]] = tuple
    started: set[ProcessRecord] = field(default_factory=set)
    command_lines: list[ScanResult] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def observe(self) -> None:
        """Record the run's processes now and scan the command lines of the new ones."""
        members = self.members()
        table = process_table()
        current = descendants(table, self.roots) | {table[pid] for pid in members if pid in table}
        new = current - self.started
        if new:
            self.command_lines.append(scan_command_lines(new))
            self.started |= new

    def start(self) -> None:
        """Observe in the background until :meth:`stop`."""

        def loop() -> None:
            while not self._stop.wait(_WATCH_SECONDS):
                with suppress(Exception):
                    self.observe()

        self._thread = threading.Thread(target=loop, name="desktop-agent-live-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop observing, after one last observation."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self.observe()


def mark_lane_root(root: Path) -> None:
    """Mark the freshly created, empty storage root with the agent lane's own mark."""
    from cadrumo.application.agent_host.lane_root import write_lane_mark

    try:
        write_lane_mark(root)
    except (OSError, ValueError) as refused:
        raise AcceptanceError(f"the lane root could not be marked: {refused}") from refused


def is_lane_root(root: Path) -> bool:
    """Whether ``root`` carries the agent lane's mark for exactly that root."""
    from cadrumo.application.agent_host.lane_root import is_marked_lane_root

    return is_marked_lane_root(root)


def stored_provider_key(programs: Programs, environment: Mapping[str, str]) -> bool:
    """Whether the signed-in profile has a provider key the person stored.

    Raises:
        UnavailableError: The package has no command to read provider settings yet.
    """
    del programs, environment
    if STORE_KEY_COMMAND is None:
        raise UnavailableError("this package has no provider-settings command yet, so no key can be stored or read")
    return False


def test_host(served: bool) -> TestHost:
    """Read the remote-debugging host record the host build wrote, refusing a changed image."""
    import hashlib

    variant = "served" if served else "packaged"
    record = _BUILD / "desktop" / "testing" / variant / "host.json"
    build = (
        "node native/desktop/tests/packaged/host.mjs --served (with CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG "
        "and CADRUMO_NATIVE_CONTRACT set)"
        if served
        else "just build-native Release desktop-packaged-host"
    )
    if not record.is_file():
        raise UnavailableError(f"no remote-debugging desktop host is built; build it with: {build}")
    value = json.loads(record.read_text(encoding="utf-8"))
    executable = Path(value.get("executable", ""))
    if "webview2-remote-debugging" not in value.get("features", ()) or not executable.is_file():
        raise UnavailableError(f"the desktop host record is not a remote-debugging host; rebuild it with: {build}")
    if hashlib.sha256(executable.read_bytes()).hexdigest() != value.get("sha256"):
        raise UnavailableError(f"the desktop host changed after its build recorded it; rebuild it with: {build}")
    shell = value.get("shell")
    return TestHost(executable, f"{shell}index.html" if served and shell else _PACKAGED_ENTRY)


def require_served_shell(entry: str) -> None:
    """Require the development server to answer and to be this checkout's own."""
    port = int(entry.split(":")[2].split("/")[0])
    owners = [
        connection.pid
        for connection in psutil.net_connections(kind="tcp")
        if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == port
    ]
    if not owners:
        raise UnavailableError(f"nothing serves the shell on port {port}; start it with: just dev")
    for pid in owners:
        with suppress(psutil.Error):
            process = psutil.Process(pid)
            places = [Path(process.cwd()), *(Path(parent.cwd()) for parent in process.parents()[:2])]
            if any(place.resolve() in {_REPOSITORY, _FRONTEND} for place in places):
                return
    raise UnavailableError(f"port {port} is served by another checkout; stop it and run just dev here")


def free_port() -> int:
    """A loopback TCP port that was free a moment ago."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _exit_code(process: Any) -> int | None:
    """The desktop's exit code, or ``None`` while it runs."""
    from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

    try:
        return int(process.wait(timeout=0))
    except RuntimeRefusalError as error:
        if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
            return None
        raise


def devtools_endpoint(port: int, host: Any, deadline: float) -> str:
    """Wait for the window's DevTools endpoint, and require it to listen on loopback only."""
    endpoint = f"http://127.0.0.1:{port}"
    while True:
        with suppress(httpx.HTTPError):
            if httpx.get(f"{endpoint}/json/version", timeout=2).status_code == 200:
                break
        code = _exit_code(host)
        if code == _DESKTOP_UNAVAILABLE:
            raise UnavailableError("this logon has no interactive desktop for the window; run the lane from it")
        if code is not None:
            raise AcceptanceError(f"the desktop exited with {code} before its DevTools endpoint answered")
        if time.monotonic() > deadline:
            raise UnavailableError(
                "the desktop opened no DevTools endpoint; the window needs an interactive desktop session"
            )
        time.sleep(0.5)
    listening = {
        connection.laddr.ip
        for connection in psutil.net_connections(kind="tcp")
        if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == port
    }
    require(bool(listening) and listening <= {"127.0.0.1", "::1"}, f"DevTools listens beyond loopback: {listening}")
    return endpoint


def wait_for_runtime(programs: Programs, environment: Mapping[str, str], deadline: float) -> None:
    """Wait until the desktop's runtime serves the lane root."""
    while True:
        code, envelope = run_cli(programs, environment, "config", "sign-in-status")
        if code == 0:
            return
        if time.monotonic() > deadline:
            raise AcceptanceError(f"no runtime served the lane root: {code} {error_code(envelope)}")
        time.sleep(1)


def close_windows(pid: int) -> int:
    """Ask every top-level window of ``pid`` to close, as the title bar's close does; return how many."""
    import win32con
    import win32gui
    import win32process

    windows: list[int] = []

    def collect(handle: int, _extra: object) -> bool:
        if win32process.GetWindowThreadProcessId(handle)[1] == pid and win32gui.IsWindowVisible(handle):
            windows.append(handle)
        return True

    win32gui.EnumWindows(collect, None)
    for handle in windows:
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
    return len(windows)


def playwright(entry: str, endpoint: str, results: Path, arguments: list[str]) -> int:
    """Run the live project as a child of this lane and return its exit status."""
    environment = {
        name: value for name, value in os.environ.items() if not name.upper().startswith(("CADRUMO_", "WEBVIEW2_"))
    }
    environment |= {
        "CADRUMO_CMAKE_BINARY_DIR": str(_BUILD),
        "CADRUMO_AGENT_LIVE_ENDPOINT": endpoint,
        "CADRUMO_AGENT_LIVE_ENTRY": entry,
        "CADRUMO_AGENT_LIVE_RESULTS": str(results),
    }
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if npx is None:
        raise UnavailableError("npx is not on PATH")
    return run_command(
        [npx, "playwright", "test", "-c", "tests/live/playwright.config.ts", *arguments],
        cwd=_FRONTEND,
        environment=environment,
        inherit_output=True,
    ).returncode


@contextmanager
def lane_desktop(host: TestHost, environment: Mapping[str, str], directory: Path, port: int) -> Generator[Any]:
    """Run the desktop in a kill-on-close Job for the block; the Job is reaped however the block ends."""
    from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    try:
        process = scope.launch(
            executable=host.executable,
            arguments=("--gui",),
            directory=directory,
            environment={**environment, "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": f"--remote-debugging-port={port}"},
        )
        yield scope, process
    finally:
        scope.terminate(timeout=30)


def run(run_directory: Path, *, served: bool, attach_only: bool, arguments: list[str]) -> list[str]:
    """Run the lane in ``run_directory``; return what it could not prove."""
    if sys.platform != "win32":
        raise UnavailableError("the lane drives the Windows desktop")
    unproven: list[str] = []
    host = test_host(served)
    if served:
        require_served_shell(host.entry)
    programs = Programs.of(_PACKAGE)
    root, secret_store, results = run_directory / "storage", run_directory / "secrets", run_directory / "playwright"
    for directory in (root, secret_store, results):
        directory.mkdir(parents=True)
    mark_lane_root(root)
    environment = consumer_environment(root, secret_store)
    environment = {name: value for name, value in environment.items() if not name.upper().startswith("WEBVIEW2_")}
    environment["CADRUMO_DESKTOP_PACKAGE_ROOT"] = str(_PACKAGE)

    password = secrets.token_urlsafe(32)
    code, envelope = run_cli(
        programs,
        environment,
        *("config", "profile", "create", _PROFILE, "--quiet", "--secrets-stdin"),
        secret={"passphrase": password, "passphrase_confirmation": password},
    )
    require(code == 0, f"profile create: {code} {error_code(envelope)}")
    print(json.dumps({"step": "profile_created"}), flush=True)

    started_before = descendants(process_table(), [os.getpid()])
    require(not started_before, f"processes already run under the lane: {sorted(p.pid for p in started_before)}")
    watch = Watch(roots=[os.getpid()])
    port = free_port()
    signed_in = False
    absent: UnavailableError | None = None
    failures: list[str] = []
    with lane_desktop(host, environment, run_directory, port) as (scope, desktop):
        watch.members = scope.active_process_ids
        watch.start()
        try:
            endpoint = devtools_endpoint(port, desktop, time.monotonic() + _DEVTOOLS_SECONDS)
            print(json.dumps({"step": "desktop_attached", "endpoint": endpoint}), flush=True)
            wait_for_runtime(programs, environment, time.monotonic() + _RUNTIME_SECONDS)
            code, envelope = run_cli(
                programs,
                environment,
                *("--profile-secrets-stdin", "config", "profile", "edit", "--quiet", "--output-language", "en"),
                secret={"profile_passphrase": password},
            )
            require(code == 0, f"profile language: {code} {error_code(envelope)}")
            code, envelope = run_cli(
                programs, environment, "config", "login", _PROFILE, "--secrets-stdin", secret={"passphrase": password}
            )
            require(code == 0, f"sign-in: {code} {error_code(envelope)}")
            signed_in = True
            if envelope.get("result", {}).get("session_persisted") is not True:
                raise UnavailableError(
                    "this logon's credential store did not keep the sign-in, so the desktop cannot resume it; "
                    "run the lane from the signed-in Windows desktop"
                )
            print(json.dumps({"step": "signed_in"}), flush=True)
            if attach_only:
                unproven.append("agent specs: --attach-only ran only the attachment check")
                arguments = [*arguments, "tests/live/attach.live.ts"]
            elif not stored_provider_key(programs, environment):
                raise UnavailableError(
                    f"no provider key is stored for the profile; store it first: {STORE_KEY_COMMAND}"
                )
            status = playwright(host.entry, endpoint, results, arguments)
            print(json.dumps({"step": "playwright", "exit_code": status}), flush=True)
            if status != 0:
                failures.append(f"the live project failed with exit {status}; report: {results / 'results.json'}")
        except UnavailableError as error:
            absent = error
        except AcceptanceError as error:
            failures.append(str(error))
        finally:
            failures.extend(_settle(programs, environment, desktop, watch, signed_in=signed_in))
    _delete_stored_sign_in(root)
    scan = merge(*watch.command_lines, scan_tree([run_directory]))
    failures.extend(f"provider key prefix in the {finding.location} ({finding.encoding})" for finding in scan.findings)
    failures.extend(f"not scanned, unreadable: {place}" for place in scan.unreadable)
    if scan.clean:
        print(json.dumps({"step": "key_scan_clean", "processes": len(watch.started)}), flush=True)
    if failures:
        raise AcceptanceError("; ".join(failures))
    if absent is not None:
        raise absent
    return unproven


def _settle(
    programs: Programs, environment: Mapping[str, str], desktop: Any, watch: Watch, *, signed_in: bool
) -> list[str]:
    """Sign out, close the window, and return what the run left behind."""
    failures: list[str] = []
    with suppress(Exception):
        watch.observe()
    if signed_in:
        code, envelope = run_cli(programs, environment, "config", "logout")
        if code != 0:
            failures.append(f"sign-out: {code} {error_code(envelope)}")
    if _exit_code(desktop) is None:
        close_windows(desktop.pid)
        with suppress(Exception):
            desktop.wait(timeout=_CLOSE_SECONDS)
    if _exit_code(desktop) is None:
        failures.append(f"the desktop did not close within {_CLOSE_SECONDS:.0f}s of its close request")
    time.sleep(_SETTLE_SECONDS)
    watch.stop()
    left = survivors(watch.started, process_table())
    if left:
        failures.append("processes the run started survive it: " + ", ".join(f"{p.pid}:{p.name}" for p in left))
    else:
        print(json.dumps({"step": "no_surviving_processes", "started": len(watch.started)}), flush=True)
    return failures


def _delete_stored_sign_in(root: Path) -> None:
    """Remove the profile's stored sign-in from the credential store, if sign-out left it."""
    from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
    from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer

    with suppress(Exception):
        selected = observe_active_profile_pointer(root).bucket_id
        if selected is not None:
            delete_profile_session(storage_root=root, profile_id=UUID(selected))


def main(argv: list[str] | None = None) -> int:
    """Run the lane; exit 0 on pass, 1 on a failure, 3 when a prerequisite is absent."""
    parser = argparse.ArgumentParser(prog="desktop-agent-live", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--served", action="store_true", help="Load the shell from the development server.")
    parser.add_argument("--attach-only", action="store_true", help="Run only the attachment check.")
    parser.add_argument("--keep", action="store_true", help="Keep the run directory after a pass.")
    parser.add_argument("playwright", nargs="*", help="Arguments after -- go to Playwright, such as -g PATTERN.")
    options = parser.parse_args(argv)
    base = _REPOSITORY / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    run_directory = base / f"desktop-agent-live-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
    run_directory.mkdir()
    try:
        unproven = run(
            run_directory, served=options.served, attach_only=options.attach_only, arguments=options.playwright
        )
    except UnavailableError as absent:
        # Nothing ran that a kept root would explain, so only --keep keeps it.
        if not options.keep and is_lane_root(run_directory / "storage"):
            _remove_run(run_directory, base)
        elif not any(run_directory.iterdir()):
            run_directory.rmdir()
        print(json.dumps({"step": "unavailable", "reason": str(absent)}), flush=True)
        return 3
    except AcceptanceError as failure:
        print(json.dumps({"step": "failed", "reason": str(failure), "kept": str(run_directory)}), flush=True)
        return 1
    if unproven:
        print(json.dumps({"step": "incomplete", "unproven": unproven, "kept": str(run_directory)}), flush=True)
        return 3
    if not options.keep:
        _remove_run(run_directory, base)
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


def _remove_run(run_directory: Path, base: Path) -> None:
    """Remove a run directory this lane created and marked, and nothing else."""
    resolved = run_directory.resolve()
    if resolved.parent != base.resolve() or not resolved.name.startswith("desktop-agent-live-"):
        raise AcceptanceError(f"refusing to remove {resolved}: not a lane run directory")
    if not is_lane_root(resolved / "storage"):
        raise AcceptanceError(f"refusing to remove {resolved}: its root carries no lane mark")
    shutil.rmtree(resolved)
