"""Isolated-environment acquisition lane: a vanilla-machine stand-in for real setup downloads.

The lane runs the real browser acquisition end to end inside one throwaway root
under the configured build tree's ``testing`` directory. Every Cadrumo storage
location, the user profile directories and the temporary directory of the
acquisition child point into that root, so nothing reaches the real profile,
the installation storage or ``var/storage``; a before-and-after fingerprint of
the real acquisition destinations proves it.

Disk use is bounded three ways: the run refuses to start unless the volume has
the plan's required free space plus a 10 GiB margin, a watchdog aborts the
child as soon as the root grows past the run's byte budget, and the root is
removed in a ``finally`` and at exit, on success, failure and Ctrl-C alike, with
the removal verified.

Scenarios, in order, against one root: the network refusal through an
unreachable proxy, an install whose first attempt meets a transient fault and is
retried, an interruption after the first build completes, a rerun that moves
only the remainder, the full check, and a second run that moves nothing. All
traffic passes through a local counting ``CONNECT`` proxy, so the bytes each run
moved are measured on the wire rather than taken from the installer's word.

The local AI -- its program and its models -- is opt-in by name and is refused
here until its isolated variant is wired; no model is ever loaded or run.

Usage::

    .venv/Scripts/python.exe -m dev.smoke.acquisition_lane run --items browser

Not a pytest module: a run downloads hundreds of megabytes. Its guards are
proved without any download by ``dev/smoke/tests/test_acquisition_lane.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import base64
import ctypes
import json
import os
import shutil
import signal
import socket
import struct
import sys
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final
from urllib.parse import quote

GIB: Final = 1024**3
MIB: Final = 1024**2
DISK_MARGIN_BYTES: Final = 10 * GIB
"""Free space kept on the volume beyond what the plan itself requires."""

ITEM_BYTE_BUDGETS: Final[Mapping[str, int]] = {"browser": 2 * GIB}
"""Largest size the scratch root may reach for each wired item; the watchdog aborts past it."""

OPT_IN_ITEMS: Final = ("local_ai",)
"""Items a run may name only explicitly; none is wired into the isolated lane yet."""

WINDOWS_CREATE_NO_WINDOW: Final = 0x08000000
_SAMPLE_INTERVAL_S: Final = 0.5
_INTERRUPT_AFTER_BYTES: Final = 5 * MIB
_NO_TRANSFER_ALLOWANCE: Final = 1 * MIB
"""What a run that downloads nothing may still move beyond plan sizing: the preflight's TLS handshakes.

Sizing and the preflight are kilobytes; the smallest browser archive is tens of megabytes, so a run
under this allowance re-downloaded nothing.
"""
_REMOVAL_ATTEMPTS: Final = 10
_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
_BUILD_DIRECTORY: Final = _REPOSITORY_ROOT / "build" / "windows-x64"
_LANE_DIRECTORY: Final = "acquisition"
_BROWSER_BUILDS: Final = ("chromium", "chromium_headless_shell")
_COMPLETE_MARKER: Final = "INSTALLATION_COMPLETE"
_STRIPPED_PREFIXES: Final = ("CADRUMO_", "PLAYWRIGHT_", "OLLAMA_", "WEBVIEW2_")
_STRIPPED_PROXY_NAMES: Final = frozenset({"http_proxy", "https_proxy", "all_proxy", "no_proxy"})


class LaneRefusalError(RuntimeError):
    """The lane cannot run safely and started nothing."""


# --------------------------------------------------------------------------
# Disk, budget and isolation guards
# --------------------------------------------------------------------------


def required_free_bytes(download_bytes: int) -> int:
    """Return the setup plan's own free-space rule; the lane adds its margin on top."""
    from cadrumo.application.dependency_contracts import required_free_bytes as plan_rule

    return plan_rule(download_bytes)


def free_space_refusal(*, free_bytes: int, download_bytes: int | None) -> str | None:
    """Return why the volume is too full for the run, or ``None`` when it may start.

    A plan whose size is unknown is refused: the margin cannot be computed
    against a size nobody stated.
    """
    if download_bytes is None:
        return "the plan does not state its download size, so the free-space floor cannot be computed"
    needed = required_free_bytes(download_bytes) + DISK_MARGIN_BYTES
    if free_bytes < needed:
        return f"the volume has {free_bytes} bytes free; the run needs {needed} ({download_bytes} to download)"
    return None


def tree_bytes(root: Path) -> int:
    """Return the bytes of every regular file under ``root``, without following links.

    Each file is stat'ed by path: on Windows a directory listing carries a
    cached size that lags a file still open for writing, which is exactly the
    download the budget has to catch.
    """
    total = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += os.stat(entry.path, follow_symlinks=False).st_size
            except (FileNotFoundError, PermissionError):
                continue
    return total


def lane_parent(build_directory: Path = _BUILD_DIRECTORY) -> Path:
    """Return the managed directory the lane's roots live in: the build tree's declared ``testing`` path."""
    manifest = build_directory / "build-paths.json"
    if not manifest.is_file():
        raise LaneRefusalError(f"{manifest} is missing; configure the windows-x64 build before running the lane")
    paths = json.loads(manifest.read_text(encoding="utf-8")).get("paths", {})
    testing = paths.get("testing")
    if not isinstance(testing, str) or not testing:
        raise LaneRefusalError(f"{manifest} declares no testing directory")
    return build_directory / testing / _LANE_DIRECTORY


def isolated_environment(scratch: Path, base: Mapping[str, str], *, proxy_url: str) -> dict[str, str]:
    """Return the acquisition child's environment: nothing inherited from Cadrumo, every location in ``scratch``."""
    environment = {
        name: value
        for name, value in base.items()
        if not name.upper().startswith(_STRIPPED_PREFIXES) and name.lower() not in _STRIPPED_PROXY_NAMES
    }
    storage = scratch / "storage"
    home = scratch / "home"
    temporary = scratch / "tmp"
    environment |= {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(storage),
        "CADRUMO_PLAYWRIGHT_BROWSERS_DIR": str(storage / "components" / "playwright"),
        "CADRUMO_OLLAMA_HOME_DIR": str(storage / "components" / "ollama" / "home"),
        "CADRUMO_OLLAMA_MODELS_DIR": str(storage / "models" / "ollama"),
        "CADRUMO_TEMP_DIR": str(storage / "tmp"),
        "CADRUMO_SECRET_STORE_DIR": str(scratch / "secret-store"),
        "CADRUMO_RUNTIME_SOCKET_DIR": str(scratch / "runtime"),
        "CADRUMO_LOG_LEVEL": "WARNING",
        "CADRUMO_PROXY_URL": proxy_url,
        "LOCALAPPDATA": str(home / "local"),
        "APPDATA": str(home / "roaming"),
        "TEMP": str(temporary),
        "TMP": str(temporary),
        "TMPDIR": str(temporary),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return environment


def prepare_scratch(scratch: Path) -> None:
    """Create the root and every directory the isolated environment names.

    Settings refuse an explicitly overridden directory that does not exist, so
    each override is created here rather than left for its owner to make.
    """
    for directory in (
        scratch / "storage",
        scratch / "storage" / "tmp",
        scratch / "storage" / "components" / "playwright",
        scratch / "storage" / "components" / "ollama" / "home",
        scratch / "storage" / "models" / "ollama",
        scratch / "secret-store",
        scratch / "runtime",
        scratch / "home" / "local",
        scratch / "home" / "roaming",
        scratch / "tmp",
    ):
        directory.mkdir(parents=True, exist_ok=True)


type Fingerprint = dict[str, tuple[int, int]]


def fingerprint(roots: Iterable[Path]) -> Fingerprint:
    """Return every file and directory under ``roots`` with its size and modification time."""
    found: Fingerprint = {}
    for root in roots:
        if not root.exists():
            found[f"{root}|absent"] = (0, 0)
            continue
        for path in [root, *root.rglob("*")]:
            with suppress(FileNotFoundError):
                stat = path.lstat()
                found[str(path)] = (0 if path.is_dir() else stat.st_size, stat.st_mtime_ns)
    return found


BROWSER_RUNTIME_LOG: Final = "debug.log"
"""The log a running Chromium appends to beside its own executable."""


def fingerprint_changes(before: Fingerprint, after: Fingerprint) -> list[str]:
    """Name every path added, removed or changed between two fingerprints.

    A change to an existing browser's own runtime log is left out: any browser
    already running from that install appends to it, so it shows activity of
    another process rather than an acquisition. Its appearance or removal still
    counts.
    """
    changes = [f"added {path}" for path in sorted(after.keys() - before.keys())]
    changes += [f"removed {path}" for path in sorted(before.keys() - after.keys())]
    changes += [
        f"changed {path}"
        for path in sorted(before.keys() & after.keys())
        if before[path] != after[path] and Path(path).name != BROWSER_RUNTIME_LOG
    ]
    return changes


def runtime_log_changes(before: Fingerprint, after: Fingerprint) -> list[str]:
    """Name the existing browser runtime logs that changed, reported apart from real-storage changes."""
    return [
        f"changed {path}"
        for path in sorted(before.keys() & after.keys())
        if before[path] != after[path] and Path(path).name == BROWSER_RUNTIME_LOG
    ]


def real_acquisition_destinations(repository: Path = _REPOSITORY_ROOT) -> tuple[Path, ...]:
    """Return the real places a browser or model acquisition would write to on this computer.

    These are watched whole; the busy remainder of ``var/storage`` (logs,
    temporary files of other sessions) is outside what an acquisition writes.
    """
    from cadrumo.core.config_state_root import live_state_root_inputs
    from cadrumo.core.storage_environment import host_installed_default_root

    inputs = live_state_root_inputs()
    installed = host_installed_default_root(inputs.environ, sys_platform=inputs.platform)
    storage_roots = [repository / "var" / "storage", repository / "var" / "storage" / "development", installed]
    destinations = [root / part for root in storage_roots for part in ("components", "models")]
    # Playwright owns its legacy browser cache separately from Cadrumo's root.
    if inputs.platform == "win32":
        browser_cache = installed.parent / "ms-playwright"
    elif inputs.platform == "darwin":
        browser_cache = inputs.home / "Library" / "Caches" / "ms-playwright"
    else:
        browser_cache = Path(inputs.environ.get("XDG_CACHE_HOME") or inputs.home / ".cache") / "ms-playwright"
    destinations.append(browser_cache)
    return tuple(destinations)


def remove_scratch(scratch: Path, *, parent: Path) -> bool:
    """Remove ``scratch``, which must sit directly inside ``parent``, and return whether it is gone."""
    resolved, owner = scratch.resolve(), parent.resolve()
    if resolved.parent != owner:
        raise LaneRefusalError(f"refusing to remove {resolved}: it is not a lane root inside {owner}")

    def clear_read_only(function: Callable[..., object], path: str, _error: BaseException) -> None:
        with suppress(OSError):
            os.chmod(path, 0o700)
            function(path)

    for _ in range(_REMOVAL_ATTEMPTS):
        if not resolved.exists():
            return True
        with suppress(OSError):
            shutil.rmtree(resolved, onexc=clear_read_only)
        if resolved.exists():
            time.sleep(0.5)
    return not resolved.exists()


def credential_targets() -> frozenset[tuple[str, int]]:
    """Return the Cadrumo entries in the Windows credential store as (target, type); empty elsewhere."""
    if sys.platform != "win32":
        return frozenset[tuple[str, int]]()
    count = ctypes.c_uint32(0)
    entries = ctypes.POINTER(ctypes.POINTER(_Credential))()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    if not advapi.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(entries)):
        return frozenset[tuple[str, int]]()
    try:
        found = {
            (str(entries[index].contents.TargetName), int(entries[index].contents.Type)) for index in range(count.value)
        }
    finally:
        advapi.CredFree(entries)
    return frozenset(entry for entry in found if "cadrumo" in entry[0].lower())


def delete_credentials(targets: Iterable[tuple[str, int]]) -> list[str]:
    """Delete the named credential entries and return the targets still present afterwards."""
    wanted = set(targets)
    if sys.platform == "win32" and wanted:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        for target, kind in wanted:
            advapi.CredDeleteW(target, kind, 0)
    return sorted(target for target, _kind in wanted & credential_targets())


if sys.platform == "win32":

    class _Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_uint64),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]


# --------------------------------------------------------------------------
# Counting CONNECT proxy
# --------------------------------------------------------------------------


class ProxyMode(StrEnum):
    """What the proxy does with a new tunnel."""

    FORWARD = "forward"
    RESET = "reset"


@dataclass(slots=True)
class CountingProxy:
    """A loopback ``CONNECT`` proxy that counts tunnelled bytes and can reset new tunnels.

    ``connect`` replaces the outbound connection, so tests can tunnel to a local
    server; a run tunnels to the publisher. With ``credentials`` (``user:password``)
    set, a tunnel opens only for a request carrying them as ``Proxy-Authorization``
    and any other answers 407, which proves the client used the configured proxy's
    credentials rather than another route.
    """

    connect: Callable[[str, int], socket.socket] = lambda host, port: socket.create_connection((host, port), 15)
    mode: ProxyMode = ProxyMode.FORWARD
    credentials: str | None = None
    unauthenticated: int = 0
    downstream_bytes: int = 0
    upstream_bytes: int = 0
    tunnels: int = 0
    resets: int = 0
    hosts: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _listener: socket.socket | None = None
    _stopping: threading.Event = field(default_factory=threading.Event)

    @property
    def port(self) -> int:
        """The loopback port the proxy listens on."""
        if self._listener is None:
            raise RuntimeError("the proxy is not started")
        return int(self._listener.getsockname()[1])

    def counters(self) -> tuple[int, int]:
        """Return the downstream and upstream byte totals so far."""
        with self._lock:
            return self.downstream_bytes, self.upstream_bytes

    def start(self) -> CountingProxy:
        """Listen on an ephemeral loopback port and serve tunnels on daemon threads."""
        listener = socket.create_server(("127.0.0.1", 0))
        listener.settimeout(0.2)
        self._listener = listener
        threading.Thread(target=self._accept, name="lane-proxy", daemon=True).start()
        return self

    def stop(self) -> None:
        """Stop accepting tunnels; open tunnels close with their peers."""
        self._stopping.set()
        if self._listener is not None:
            self._listener.close()

    def _accept(self) -> None:
        listener = self._listener
        while listener is not None and not self._stopping.is_set():
            try:
                client, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self._tunnel, args=(client,), daemon=True).start()

    def _tunnel(self, client: socket.socket) -> None:
        with client:
            head = _read_request_head(client)
            if head is None:
                return
            request_line, *header_lines = head.split("\r\n")
            method, _, target = request_line.partition(" ")
            authority = target.partition(" ")[0]
            host, _, port = authority.rpartition(":")
            if method != "CONNECT" or not port.isdigit():
                client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
                return
            if self.credentials is not None and not _authorized(header_lines, self.credentials):
                with self._lock:
                    self.unauthenticated += 1
                client.sendall(
                    b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                    b'Proxy-Authenticate: Basic realm="lane"\r\nContent-Length: 0\r\n\r\n'
                )
                return
            with self._lock:
                self.tunnels += 1
                self.hosts.add(host)
                resetting = self.mode is ProxyMode.RESET
                self.resets += int(resetting)
            if resetting:
                client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                return
            try:
                upstream = self.connect(host, int(port))
            except OSError:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                return
            with upstream:
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                pump = threading.Thread(target=self._pump, args=(client, upstream, False), daemon=True)
                pump.start()
                self._pump(upstream, client, True)
                pump.join(5)

    def _pump(self, source: socket.socket, sink: socket.socket, downstream: bool) -> None:
        try:
            while chunk := source.recv(65536):
                sink.sendall(chunk)
                with self._lock:
                    if downstream:
                        self.downstream_bytes += len(chunk)
                    else:
                        self.upstream_bytes += len(chunk)
        except OSError:
            pass
        finally:
            with suppress(OSError):
                sink.shutdown(socket.SHUT_WR)


def _read_request_head(client: socket.socket) -> str | None:
    received = b""
    client.settimeout(15)
    while b"\r\n\r\n" not in received:
        try:
            chunk = client.recv(4096)
        except OSError:
            return None
        if not chunk or len(received) > 16384:
            return None
        received += chunk
    return received.split(b"\r\n\r\n", 1)[0].decode("latin-1")


def _authorized(header_lines: Iterable[str], credentials: str) -> bool:
    expected = "Basic " + base64.b64encode(credentials.encode()).decode()
    for line in header_lines:
        name, _, value = line.partition(":")
        if name.strip().lower() == "proxy-authorization":
            return value.strip() == expected
    return False


def proxy_credential_forms(credentials: str) -> tuple[str, ...]:
    """Return every spelling of ``credentials`` a careless log line could carry: plain, encoded and in a header."""
    user, _, password = credentials.partition(":")
    return (password, quote(password, safe=""), base64.b64encode(credentials.encode()).decode(), f"{user}:{password}@")


def logged_errors(root: Path, *, limit: int = 30) -> list[str]:
    """Return the last error and warning lines every log under ``root`` holds, for a failed run's report."""
    lines: list[str] = []
    for log in sorted(root.rglob("*.log")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines += [line[:600] for line in text.splitlines() if "[ERROR]" in line or "[WARNING]" in line]
    return lines[-limit:]


def credential_leaks(root: Path, forms: Sequence[str], *, skip: Iterable[Path] = ()) -> list[str]:
    """Return the files under ``root`` holding any of ``forms``, outside the ``skip`` trees.

    The scratch root holds every log, journal, receipt and store the run wrote,
    so a credential that reached any of them is found here.
    """
    needles = [form.encode() for form in forms if form]
    skipped = [path.resolve() for path in skip]
    leaks: list[str] = []
    for directory, _directories, files in os.walk(root):
        if any(Path(directory).resolve().is_relative_to(path) for path in skipped):
            continue
        for name in files:
            path = Path(directory) / name
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if any(needle in content for needle in needles):
                leaks.append(str(path.relative_to(root)))
    return sorted(leaks)


# --------------------------------------------------------------------------
# One supervised child run
# --------------------------------------------------------------------------


@dataclass(slots=True)
class ChildRun:
    """What one acquisition child did, as the parent observed it."""

    command: str
    exit_code: int | None = None
    result: dict[str, object] | None = None
    events: list[dict[str, object]] = field(default_factory=list)
    peak_scratch_bytes: int = 0
    downstream_bytes: int = 0
    aborted: str | None = None
    elapsed_s: float = 0.0
    stdout: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)


type Trigger = Callable[[ChildRun, int], str | None]


def run_child(
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str],
    scratch: Path,
    budget_bytes: int,
    proxy: CountingProxy | None = None,
    on_event: Callable[[dict[str, object]], None] | None = None,
    interrupt: Trigger | None = None,
    timeout_s: float = 1800.0,
    program: Sequence[str] | None = None,
) -> ChildRun:
    """Run one acquisition child windowless, watching the scratch root against ``budget_bytes``.

    The watchdog terminates the child when the root grows past the budget,
    when ``interrupt`` names a reason, or at ``timeout_s``. The browser
    installer runs inside the child's kill-on-close job, so terminating the
    child stops the download with it. ``program`` replaces the lane's own child
    command, so the guards can be proved against a small stand-in.
    """
    argv = list(program) if program is not None else [sys.executable, "-m", "dev.smoke.acquisition_lane", "child"]
    return asyncio.run(
        _supervise(
            [*argv, *arguments],
            environment=environment,
            scratch=scratch,
            budget_bytes=budget_bytes,
            proxy=proxy,
            on_event=on_event,
            interrupt=interrupt,
            timeout_s=timeout_s,
        )
    )


async def _supervise(
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    scratch: Path,
    budget_bytes: int,
    proxy: CountingProxy | None,
    on_event: Callable[[dict[str, object]], None] | None,
    interrupt: Trigger | None,
    timeout_s: float,
    stdin_bytes: bytes | None = None,
    result_line: bool = True,
) -> ChildRun:
    """Run ``argv`` windowless under the scratch-root watchdog.

    ``stdin_bytes`` is written once and the input closed, which is how secrets
    reach a command without its argument list. A child whose ``result_line``
    is false reports through its whole output, parsed as JSON, instead of one
    ``result`` event line.
    """
    started = time.monotonic()
    before = proxy.counters()[0] if proxy is not None else 0
    run = ChildRun(command=" ".join(argv[4:] if argv[1:3] == ["-m", "dev.smoke.acquisition_lane"] else argv))
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL if stdin_bytes is None else asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(environment),
        cwd=_REPOSITORY_ROOT,
        creationflags=WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        start_new_session=sys.platform != "win32",
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("child pipes were not opened")
    if stdin_bytes is not None and process.stdin is not None:
        process.stdin.write(stdin_bytes)
        await process.stdin.drain()
        process.stdin.close()
    tail = run.stderr_tail
    readers = [
        asyncio.create_task(_read_events(process.stdout, run, on_event)),
        asyncio.create_task(_read_tail(process.stderr, tail)),
    ]
    try:
        while process.returncode is None:
            size = await asyncio.to_thread(tree_bytes, scratch)
            run.peak_scratch_bytes = max(run.peak_scratch_bytes, size)
            moved = (proxy.counters()[0] - before) if proxy is not None else 0
            reason = None
            if size > budget_bytes:
                reason = f"scratch root reached {size} bytes, over the {budget_bytes}-byte budget"
            elif time.monotonic() - started > timeout_s:
                reason = f"child exceeded {timeout_s:.0f} s"
            elif interrupt is not None:
                reason = interrupt(run, moved)
            if reason is not None:
                run.aborted = reason
                process.kill()
                break
            with suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), _SAMPLE_INTERVAL_S)
        run.exit_code = await asyncio.wait_for(process.wait(), 60)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await asyncio.gather(*readers, return_exceptions=True)
        run.peak_scratch_bytes = max(run.peak_scratch_bytes, await asyncio.to_thread(tree_bytes, scratch))
        run.downstream_bytes = (proxy.counters()[0] - before) if proxy is not None else 0
        run.elapsed_s = round(time.monotonic() - started, 2)
    if not result_line and run.aborted is None:
        run.result = _parsed_output(run.stdout)
    if run.result is None and run.aborted is None:
        run.aborted = "child ended without a result: " + " | ".join(tail[-5:])
    return run


def _object_dict(value: object) -> dict[str, object] | None:
    """Return ``value`` as a string-keyed object when it is a JSON object, else ``None``."""
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _parsed_output(lines: Sequence[str]) -> dict[str, object] | None:
    """Return a command's JSON output: one document, or its last JSON line when it streams events."""
    text = "\n".join(lines).strip()
    if not text:
        return None
    try:
        whole = json.loads(text)
    except ValueError:
        whole = None
    if (document := _object_dict(whole)) is not None:
        return document
    for line in reversed(lines):
        with suppress(ValueError):
            if (document := _object_dict(json.loads(line))) is not None:
                return document
    return None


async def _read_events(
    stream: asyncio.StreamReader,
    run: ChildRun,
    on_event: Callable[[dict[str, object]], None] | None,
) -> None:
    while raw := await stream.readline():
        run.stdout.append(raw.decode("utf-8", errors="replace").rstrip())
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") == "result":
            run.result = event
        else:
            run.events.append(event)
        if on_event is not None:
            on_event(event)


async def _read_tail(stream: asyncio.StreamReader, tail: list[str]) -> None:
    while raw := await stream.readline():
        tail.append(raw.decode("utf-8", errors="replace").rstrip())
        del tail[:-40]


# --------------------------------------------------------------------------
# The lane
# --------------------------------------------------------------------------


@dataclass(slots=True)
class LaneReport:
    """Everything a run reports: per-scenario evidence, bytes, peak size and cleanup."""

    scratch: str
    items: list[str]
    path: str = "direct"
    free_bytes_at_start: int = 0
    plan_download_bytes: int | None = None
    budget_bytes: int = 0
    scenarios: dict[str, dict[str, object]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    total_downstream_bytes: int = 0
    peak_scratch_bytes: int = 0
    free_bytes_at_end: int = 0
    proxy_tunnels: int = 0
    proxy_hosts: list[str] = field(default_factory=list)
    proxy_unauthenticated: int = 0
    credential_leaks: list[str] = field(default_factory=list)
    real_storage_changes: list[str] = field(default_factory=list)
    real_runtime_log_changes: list[str] = field(default_factory=list)
    refused: str | None = None
    credentials_created: list[str] = field(default_factory=list)
    credentials_left: list[str] = field(default_factory=list)
    scratch_removed: bool | None = None
    secret_forms: tuple[str, ...] = field(default=(), repr=False)
    """The proxy credentials' spellings, searched for in every output; never reported."""

    def record(self, name: str, run: ChildRun, **verdict: object) -> None:
        """Keep one scenario's evidence, fold its bytes into the totals and search its output for the credentials."""
        output = "\n".join([*run.stdout, *run.stderr_tail, json.dumps(run.result, default=str)])
        if any(form and form in output for form in self.secret_forms):
            self.credential_leaks.append(f"output of {name}")
        self.scenarios[name] = {
            "exit_code": run.exit_code,
            "aborted": run.aborted,
            "downstream_bytes": run.downstream_bytes,
            "peak_scratch_bytes": run.peak_scratch_bytes,
            "elapsed_s": run.elapsed_s,
            "result": run.result,
            **verdict,
        }
        self.total_downstream_bytes += run.downstream_bytes
        self.peak_scratch_bytes = max(self.peak_scratch_bytes, run.peak_scratch_bytes)

    def require(self, condition: bool, failure: str) -> None:
        """Record ``failure`` when ``condition`` does not hold."""
        if not condition:
            self.failures.append(failure)


def _completed_builds(browsers: Path) -> dict[str, int]:
    found: dict[str, int] = {}
    if not browsers.is_dir():
        return found
    for directory in browsers.iterdir():
        marker = directory / _COMPLETE_MARKER
        if directory.name.startswith(_BROWSER_BUILDS) and marker.is_file():
            found[directory.name] = marker.stat().st_mtime_ns
    return found


def _result_field(run: ChildRun, name: str) -> object:
    return None if run.result is None else run.result.get(name)


def run_browser_lane(report: LaneReport, *, scratch: Path, environment: dict[str, str], proxy: CountingProxy) -> None:
    """Drive the browser item through every scenario against one scratch root."""
    budget = report.budget_bytes
    browsers = scratch / "storage" / "components" / "playwright"

    guard = run_child(["guard"], environment=environment, scratch=scratch, budget_bytes=budget)
    report.record("isolation", guard)
    report.require(_result_field(guard, "outside") == [], f"locations outside the scratch root: {guard.result}")

    unreachable = dict(environment, CADRUMO_PROXY_URL=f"http://127.0.0.1:{_closed_port()}")
    offline = run_child(["reachability"], environment=unreachable, scratch=scratch, budget_bytes=budget)
    category = _result_field(offline, "failure_category")
    report.record("network_refusal", offline)
    report.require(category in {"offline", "host_unreachable"}, f"unreachable network read as {category!r}")
    report.require(tree_bytes(browsers) == 0, "the refused run wrote browser files")

    quick = run_child(["check", "quick"], environment=environment, scratch=scratch, budget_bytes=budget, proxy=proxy)
    report.record("absent_before", quick)
    report.require(_result_field(quick, "outcome") == "absent", f"a clean root read {quick.result}")
    report.require(quick.downstream_bytes == 0, "the quick check moved bytes")

    def retry_then_pass(event: Mapping[str, object]) -> None:
        if event.get("event") == "retrying":
            proxy.mode = ProxyMode.FORWARD

    def after_first_build(_run: ChildRun, moved: int) -> str | None:
        completed = _completed_builds(browsers)
        if not completed:
            return None
        mark = first_build_bytes.setdefault("moved", moved)
        if moved - mark >= _INTERRUPT_AFTER_BYTES:
            return f"interrupted {moved - mark} bytes into the next build"
        return None

    first_build_bytes: dict[str, int] = {}
    proxy.mode = ProxyMode.RESET
    first = run_child(
        ["provision"],
        environment=environment,
        scratch=scratch,
        budget_bytes=budget,
        proxy=proxy,
        on_event=retry_then_pass,
        interrupt=after_first_build,
    )
    proxy.mode = ProxyMode.FORWARD
    retried = [event for event in first.events if event.get("event") == "retrying"]
    completed_at_cut = _completed_builds(browsers)
    report.record("transient_retry_and_interrupt", first, retries=len(retried), completed_at_cut=completed_at_cut)
    report.require(bool(retried), "the transient fault was not retried")
    report.require(
        first.aborted is not None and first.aborted.startswith("interrupted"),
        f"the interruption was not exercised: {first.aborted or first.result}",
    )
    report.require(len(completed_at_cut) == 1, f"the cut left {sorted(completed_at_cut)} complete, not one build")

    remaining = run_child(["plan"], environment=environment, scratch=scratch, budget_bytes=budget)
    remainder = _result_field(remaining, "download_bytes")
    report.record("plan_after_interrupt", remaining)
    report.require(
        isinstance(remainder, int)
        and isinstance(report.plan_download_bytes, int)
        and remainder < report.plan_download_bytes,
        f"the plan after the cut still names {remainder} bytes of {report.plan_download_bytes}",
    )

    resumed = run_child(["provision"], environment=environment, scratch=scratch, budget_bytes=budget, proxy=proxy)
    report.record("resume", resumed, remainder_bytes=remainder)
    report.require(_result_field(resumed, "failure_category") is None, f"resume failed: {resumed.result}")
    if isinstance(remainder, int) and isinstance(report.plan_download_bytes, int):
        # TLS framing adds a little to the archive bytes on the wire; a restart would add the finished build.
        report.require(
            resumed.downstream_bytes < remainder * 1.05 + 2 * MIB,
            f"resume moved {resumed.downstream_bytes} bytes for a {remainder}-byte remainder",
        )
    untouched = {name: stamp for name, stamp in _completed_builds(browsers).items() if name in completed_at_cut}
    report.require(untouched == completed_at_cut, "the build finished before the cut was downloaded again")

    full = run_child(["check", "full"], environment=environment, scratch=scratch, budget_bytes=budget, proxy=proxy)
    report.record("full_check", full)
    report.require(_result_field(full, "outcome") == "present", f"the full check read {full.result}")
    facts = _result_field(full, "facts")
    report.require(
        isinstance(facts, dict) and facts.get("launched") is True, "the full check did not launch the browser"
    )

    again = run_child(["provision"], environment=environment, scratch=scratch, budget_bytes=budget, proxy=proxy)
    report.record("second_run", again)
    report.require(_result_field(again, "changed") is False, f"the second run changed something: {again.result}")
    report.require(_result_field(again, "transferred_bytes") == 0, f"the second run transferred: {again.result}")
    # Planning sizes each archive with one HEAD request; a second run may spend that, and nothing more.
    measuring = report.scenarios["plan"]["downstream_bytes"]
    ceiling = (measuring if isinstance(measuring, int) else 0) + _NO_TRANSFER_ALLOWANCE
    report.require(
        again.downstream_bytes <= ceiling,
        f"the second run moved {again.downstream_bytes} bytes; sizing the plan alone moves {measuring}",
    )


def _closed_port() -> int:
    with socket.create_server(("127.0.0.1", 0)) as probe:
        return int(probe.getsockname()[1])


# --------------------------------------------------------------------------
# The operation path: the real dependencies.setup through the runtime client
# --------------------------------------------------------------------------

_AUTHORITY_ROOT: Final = _REPOSITORY_ROOT / ".authority"
_RUNTIME_READY_S: Final = 120.0
_PROFILE_NAME: Final = "acquisition-lane"


def _console_script(name: str) -> str:
    """Return the project environment's own console script, never one found on the search path."""
    suffix = ".exe" if sys.platform == "win32" else ""
    script = Path(sys.executable).parent / f"{name}{suffix}"
    if not script.is_file():
        raise LaneRefusalError(f"{script} is missing; sync the project environment first")
    return str(script)


def _data(run: ChildRun) -> dict[str, object]:
    """Return the ``result`` object of a command's JSON envelope, or the envelope itself."""
    document = run.result or {}
    return _object_dict(document.get("result")) or document


def _browser_result(run: ChildRun) -> dict[str, object]:
    """Return the browser's entry in a setup command's ``results``, read through the CLI's published shape."""
    from cadrumo.entrypoints.cli.config.provision_payloads import ProvisionSetupItemPayload

    results = _data(run).get("results")
    if isinstance(results, list):
        for entry in results:
            result = ProvisionSetupItemPayload.model_validate(entry)
            if result.item_id == "browser":
                return _object_dict(result.model_dump(mode="json")) or {}
    return {}


def _browser_row(run: ChildRun) -> dict[str, object]:
    """Return the browser's row from a provision command's ``items``, read through the CLI's published shape."""
    from cadrumo.entrypoints.cli.config.provision_payloads import ProvisionItemPayload

    items = _data(run).get("items")
    if isinstance(items, list):
        for entry in items:
            row = ProvisionItemPayload.model_validate(entry)
            if row.item_id == "browser":
                return _object_dict(row.model_dump(mode="json")) or {}
    return {}


@dataclass(slots=True)
class _HeldRuntime:
    """A configured-root runtime kept alive by its open standard input."""

    process: asyncio.subprocess.Process
    ready: dict[str, object]
    drains: list[asyncio.Task[None]]
    stderr_tail: list[str] = field(default_factory=list)

    async def stop(self) -> int | None:
        """Close the runtime's input, which asks it to stop, and wait for it; terminate it if it lingers."""
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 60)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
        await asyncio.gather(*self.drains, return_exceptions=True)
        return self.process.returncode


async def _drain(stream: asyncio.StreamReader, tail: list[str] | None = None) -> None:
    while raw := await stream.readline():
        if tail is not None:
            tail.append(raw.decode("utf-8", errors="replace").rstrip())
            del tail[:-40]


async def _start_runtime(environment: Mapping[str, str]) -> _HeldRuntime:
    process = await asyncio.create_subprocess_exec(
        _console_script("cadrumo-runtime"),
        "--configured-root",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(environment),
        cwd=_REPOSITORY_ROOT,
        creationflags=WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        start_new_session=sys.platform != "win32",
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("runtime pipes were not opened")
    stderr_tail: list[str] = []
    stderr_drain = asyncio.create_task(_drain(process.stderr, stderr_tail))
    deadline = time.monotonic() + _RUNTIME_READY_S
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(process.stdout.readline(), max(0.1, deadline - time.monotonic()))
        except TimeoutError:
            break
        if not raw:
            break
        with suppress(ValueError):
            line = json.loads(raw)
            if isinstance(line, dict) and line.get("kind") == "runtime_ready":
                drains = [stderr_drain, asyncio.create_task(_drain(process.stdout))]
                return _HeldRuntime(process, line, drains, stderr_tail)
    process.kill()
    await process.wait()
    stderr_drain.cancel()
    raise LaneRefusalError("the isolated runtime did not report ready")


async def _operation_path(
    report: LaneReport, *, scratch: Path, environment: dict[str, str], proxy: CountingProxy
) -> None:
    """Drive the browser through the registered setup operations of a runtime held on the scratch root."""
    budget = report.budget_bytes
    aeat = _console_script("aeat")
    passphrase = os.urandom(24).hex()
    secrets_json = json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase}).encode()
    login_json = json.dumps({"passphrase": passphrase}).encode()

    async def cli(name: str, *arguments: str, secrets: bytes | None = None, timeout_s: float = 300.0) -> ChildRun:
        run = await _supervise(
            [aeat, "--format", "json", *arguments],
            environment=environment,
            scratch=scratch,
            budget_bytes=budget,
            proxy=proxy,
            on_event=None,
            interrupt=None,
            timeout_s=timeout_s,
            stdin_bytes=secrets,
            result_line=False,
        )
        report.record(name, run)
        return run

    runtime = await _start_runtime(environment)
    report.scenarios["runtime"] = {"ready": runtime.ready}
    try:
        created = await cli(
            "profile_create",
            "config",
            "profile",
            "create",
            "--quiet",
            "--secrets-stdin",
            "--",
            _PROFILE_NAME,
            secrets=secrets_json,
        )
        report.require(created.exit_code == 0, f"the isolated profile was not created: {created.stderr_tail[-3:]}")
        login = await cli("login", "config", "login", "--secrets-stdin", secrets=login_json)
        signed_in = login.exit_code == 0
        report.require(signed_in, f"the isolated profile did not sign in: {login.stderr_tail[-3:]}")
        if not signed_in:
            return

        status = await cli("operation_status_before", "config", "provision", "status")
        report.require(
            _browser_row(status).get("state") == "absent", f"status before setup read {_browser_row(status)}"
        )
        report.require(status.downstream_bytes == 0, "the status read moved bytes")

        unapproved = await cli("operation_setup_without_approval", "config", "provision", "browser")
        report.require(unapproved.exit_code not in {0, None}, "a setup without approval did not refuse")
        report.require(
            tree_bytes(scratch / "storage" / "components" / "playwright") == 0,
            "an unapproved setup wrote browser files",
        )
        report.require(
            unapproved.downstream_bytes <= 2 * MIB,
            f"an unapproved setup moved {unapproved.downstream_bytes} bytes; only plan sizing may run",
        )

        setup = await cli("operation_setup", "config", "provision", "browser", "--yes", timeout_s=1800.0)
        report.require(setup.exit_code == 0, f"the approved setup failed: {setup.stderr_tail[-3:]}")
        planned = report.plan_download_bytes
        if isinstance(planned, int):
            report.require(
                planned <= setup.downstream_bytes < planned * 1.05 + 4 * MIB,
                f"the setup moved {setup.downstream_bytes} bytes for a {planned}-byte plan",
            )

        verify = await cli("operation_verify", "config", "provision", "verify", "--item", "browser", timeout_s=300.0)
        row = _browser_row(verify)
        report.require(verify.exit_code == 0 and row.get("state") == "ready", f"the full check after setup read {row}")

        again = await cli("operation_second_setup", "config", "provision", "browser", "--yes")
        measuring = report.scenarios["plan"]["downstream_bytes"]
        ceiling = (measuring if isinstance(measuring, int) else 0) + _NO_TRANSFER_ALLOWANCE
        report.require(again.exit_code == 0, f"the second setup failed: {again.stderr_tail[-3:]}")
        repeated = _browser_result(again)
        report.require(
            repeated.get("changed") is False and repeated.get("transferred_bytes") == 0,
            f"the second setup changed or transferred something: {repeated}",
        )
        report.require(
            again.downstream_bytes <= ceiling,
            f"the second setup moved {again.downstream_bytes} bytes; sizing the plan alone moves {measuring}",
        )
    finally:
        # Signing out removes the session keys sign-in placed in the credential store.
        logout = await cli("logout", "config", "logout", "--secrets-stdin", secrets=login_json)
        login_record = report.scenarios.get("login", {})
        if login_record.get("exit_code") == 0:
            report.require(logout.exit_code == 0, f"the isolated profile did not sign out: {logout.stderr_tail[-3:]}")
        report.scenarios["runtime"]["exit_code"] = await runtime.stop()
        if report.failures:
            # A failed run explains itself: the runtime's last words and the error lines its processes logged.
            report.scenarios["runtime"]["stderr_tail"] = runtime.stderr_tail[-20:]
            report.scenarios["runtime"]["logged_errors"] = logged_errors(scratch)


@contextmanager
def _cleanup_guard(scratch: Path, parent: Path, report: LaneReport) -> Generator[None]:
    """Remove the scratch root however the run ends, including Ctrl-C and interpreter exit."""
    removed = threading.Event()

    def remove() -> None:
        if removed.is_set():
            return
        removed.set()
        report.scratch_removed = remove_scratch(scratch, parent=parent)

    def interrupted(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    atexit.register(remove)
    previous = {
        number: signal.signal(number, interrupted)
        for number in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", signal.SIGINT))
    }
    try:
        yield
    finally:
        remove()
        atexit.unregister(remove)
        for number, handler in previous.items():
            signal.signal(number, handler)


def run_lane(items: Sequence[str], *, accept_size: bool = False, path: str = "direct") -> LaneReport:
    """Run the isolated acquisition lane for ``items`` and return its report."""
    refused = [item for item in items if item in OPT_IN_ITEMS]
    if refused:
        raise LaneRefusalError(f"{refused}: the local AI is opt-in and not wired into the isolated lane yet")
    unknown = [item for item in items if item not in ITEM_BYTE_BUDGETS]
    if unknown:
        raise LaneRefusalError(f"not a lane item: {unknown}")
    parent = lane_parent()
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    scratch = parent / f"run-{stamp}-{os.getpid()}"
    report = LaneReport(
        scratch=str(scratch), items=list(items), path=path, budget_bytes=sum(ITEM_BYTE_BUDGETS[i] for i in items)
    )
    destinations = (*real_acquisition_destinations(), _AUTHORITY_ROOT)
    real_before = fingerprint(destinations)
    credentials_before = credential_targets()
    # The proxy demands synthetic credentials carried in its address, so every download
    # proves it took the configured route and the credentials can be searched for afterwards.
    proxy_credentials = f"lane:{os.urandom(12).hex()}"
    proxy = CountingProxy(credentials=proxy_credentials).start()
    report.secret_forms = proxy_credential_forms(proxy_credentials)
    with _cleanup_guard(scratch, parent, report):
        try:
            prepare_scratch(scratch)
            proxy_url = f"http://{proxy_credentials}@127.0.0.1:{proxy.port}"
            environment = isolated_environment(scratch, os.environ, proxy_url=proxy_url)
            plan = run_child(
                ["plan"], environment=environment, scratch=scratch, budget_bytes=report.budget_bytes, proxy=proxy
            )
            report.record("plan", plan)
            planned = _result_field(plan, "download_bytes")
            report.plan_download_bytes = planned if isinstance(planned, int) else None
            report.free_bytes_at_start = shutil.disk_usage(parent).free
            refusal = free_space_refusal(
                free_bytes=report.free_bytes_at_start, download_bytes=report.plan_download_bytes
            )
            if refusal is None and not accept_size:
                refusal = (
                    f"the run downloads {report.plan_download_bytes} bytes from {_result_field(plan, 'source_hosts')}; "
                    "pass --accept-size to proceed"
                )
            if refusal is not None:
                report.refused = refusal
            elif path == "operation":
                operation_environment = dict(environment, CADRUMO_AUTHORITY_ROOT=str(_AUTHORITY_ROOT))
                asyncio.run(_operation_path(report, scratch=scratch, environment=operation_environment, proxy=proxy))
            else:
                run_browser_lane(report, scratch=scratch, environment=environment, proxy=proxy)
        finally:
            proxy.stop()
            report.proxy_tunnels = proxy.tunnels
            report.proxy_hosts = sorted(proxy.hosts)
            report.proxy_unauthenticated = proxy.unauthenticated
            forms = proxy_credential_forms(proxy_credentials)
            browsers = scratch / "storage" / "components" / "playwright"
            report.credential_leaks += credential_leaks(scratch, forms, skip=(browsers,))
            created = sorted(credential_targets() - credentials_before)
            report.credentials_created = [target for target, _kind in created]
            report.credentials_left = delete_credentials(created)
            real_after = fingerprint(destinations)
            report.real_storage_changes = fingerprint_changes(real_before, real_after)
            report.real_runtime_log_changes = runtime_log_changes(real_before, real_after)
    report.free_bytes_at_end = shutil.disk_usage(parent).free
    report.require(not report.real_storage_changes, "real storage changed during the run")
    report.require(not report.credential_leaks, f"the proxy credentials were written to {report.credential_leaks}")
    report.require(not report.credentials_left, "credential entries the run created are still present")
    report.require(report.scratch_removed is True, "the scratch root was not removed")
    return report


# --------------------------------------------------------------------------
# The acquisition child: composes the real browser item inside the isolated environment
# --------------------------------------------------------------------------


def _emit(event: str, **fields: object) -> None:
    sys.stdout.write(json.dumps({"event": event, **fields}, default=str) + "\n")
    sys.stdout.flush()


class _LaneEvents:
    """The setup operation's event port, as the lane stands in for it until the operation path lands."""

    def __init__(self) -> None:
        self._reported = -1

    async def step(self, step: object) -> None:
        _emit("step", step=str(step))

    async def transferred(self, *, completed: int, total: int | None) -> None:
        if completed - self._reported >= 8 * MIB or (total is not None and completed >= total):
            self._reported = completed
            _emit("transferred", completed=completed, total=total)

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        _emit("retrying", attempt=attempt, delay_s=delay_s)

    @property
    def cancellation_requested(self) -> bool:
        return False

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        yield


def _browser_item() -> object:
    from cadrumo.adapters.outbound.browser_runtime.installer import (
        measure_browser_downloads,
        remove_browser_builds,
        run_browser_install,
    )
    from cadrumo.adapters.outbound.browser_runtime.launch_check import launch_headless_browser
    from cadrumo.application.dependency_receipts import DependencyReceiptStore
    from cadrumo.application.provisioning_browser import PlaywrightBrowserItem
    from cadrumo.core.storage_taxonomy import StorageCategory
    from cadrumo.core.storage_taxonomy_locations import storage_path

    return PlaywrightBrowserItem(
        install=run_browser_install,
        measure=measure_browser_downloads,
        launch=launch_headless_browser,
        remove_builds=remove_browser_builds,
        receipts=DependencyReceiptStore(storage_path(StorageCategory.DEPENDENCY_RECEIPTS)),
    )


def _outside_scratch() -> list[str]:
    from cadrumo.application.provisioning_browser import playwright_browsers_root
    from cadrumo.core.storage_taxonomy_locations import ROOT_DERIVED_STORAGE_LOCATIONS, storage_path

    root = Path(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"]).resolve().parent
    resolved = {location.category.value: storage_path(location.category) for location in ROOT_DERIVED_STORAGE_LOCATIONS}
    resolved["playwright_browsers_root"] = playwright_browsers_root()
    resolved["temporary"] = Path(os.environ["TEMP"])
    return sorted(f"{name}={path}" for name, path in resolved.items() if not path.resolve().is_relative_to(root))


async def _child(command: str, mode: str | None) -> None:
    from cadrumo.application.dependency_contracts import DependencyCheckMode
    from cadrumo.application.dependency_network import dependency_host_reachability, dependency_hosts
    from cadrumo.application.provisioning_browser import PlaywrightBrowserItem
    from cadrumo.core.child_console import isolate_child_consoles

    isolate_child_consoles()
    if command == "guard":
        _emit("result", outside=_outside_scratch())
        return
    if command == "reachability":
        category = await dependency_host_reachability(dependency_hosts("browser"))
        _emit("result", failure_category=None if category is None else category.value)
        return
    item = _browser_item()
    if not isinstance(item, PlaywrightBrowserItem):
        raise TypeError("the browser item did not compose")
    if command == "check":
        reading = await item.check(DependencyCheckMode(mode or "quick"))
        _emit("result", **reading.model_dump(mode="json"))
        return
    entry = await item.plan(model_name=None)
    if command == "plan":
        _emit("result", **entry.model_dump(mode="json"))
        return
    outcome = await item.provision(entry, _LaneEvents())
    _emit("result", **outcome.model_dump(mode="json"))


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Run the lane, or one acquisition child, and return the process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m dev.smoke.acquisition_lane",
        description="Isolated-environment acquisition lane for real setup downloads.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the isolated acquisition lane")
    run.add_argument("--items", nargs="+", default=["browser"], help="setup items; the browser alone is the default")
    run.add_argument("--accept-size", action="store_true", help="proceed after the planned download size is named")
    run.add_argument(
        "--path",
        choices=("direct", "operation"),
        default="direct",
        help="drive the item directly, or the registered setup operation through an isolated runtime",
    )
    child = commands.add_parser("child", help="internal: one acquisition step inside the isolated environment")
    child.add_argument("step", choices=("guard", "reachability", "check", "plan", "provision"))
    child.add_argument("mode", nargs="?", choices=("quick", "full"))
    arguments = parser.parse_args(argv)
    if arguments.command == "child":
        asyncio.run(_child(arguments.step, arguments.mode))
        return 0
    try:
        report = run_lane(arguments.items, accept_size=arguments.accept_size, path=arguments.path)
    except LaneRefusalError as refusal:
        sys.stderr.write(f"acquisition-lane: refused: {refusal}\n")
        return 2
    sys.stdout.write(json.dumps(_report_dict(report), indent=2, default=str) + "\n")
    if report.refused is not None:
        sys.stderr.write(f"acquisition-lane: refused: {report.refused}\n")
        return 1 if report.failures else 2
    return 1 if report.failures else 0


def _report_dict(report: LaneReport) -> dict[str, object]:
    return {name: getattr(report, name) for name in LaneReport.__dataclass_fields__ if name != "secret_forms"}


if __name__ == "__main__":
    sys.exit(main())
