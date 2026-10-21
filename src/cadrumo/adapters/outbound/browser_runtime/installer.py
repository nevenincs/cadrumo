"""Operating-system process control for installing the Playwright Chromium build.

:func:`run_browser_install` runs the installed Playwright package's own driver
installer over a fixed argv, so the extracted revisions are exactly the ones
that package launches, with its download host pointed at a loopback server
(:mod:`.archive_server`). That server answers only the pinned archives the run
needs, and downloads each itself the first time it is asked for
(:mod:`.archive_fetch`): from the approved hosts only, refusing any byte that
differs from its pin. The installer itself therefore never reaches the network,
and builds still complete one at a time, so an interruption keeps every build
already finished. Its environment carries
none of the inherited Playwright, Node, npm or proxy variables that could move
its download or weaken its checks; its output is read within fixed bounds for
the failure cause, and a cancel stops it with every process it started.

:func:`remove_browser_builds` deletes named build directories under the
browser root and nothing else.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Final

import httpx

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.browser_archive_pins import BrowserArchivePin
from ....application.provisioning_browser import (
    BrowserInstallerExit,
    BrowserInstallerRequest,
    BrowserInstallObserver,
)
from ....core.child_console import WINDOWS_CREATE_NO_WINDOW
from ....core.config import Settings, load_settings
from ....core.errors.hierarchy import InternalInvariantError
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from .archive_fetch import fetch_pinned_archive
from .archive_server import VerifiedArchiveServer
from .installer_output import classify_installer_output
from .process_tree import InstallerProcessTree

__all__ = [
    "browser_installer_environment",
    "remove_browser_builds",
    "run_browser_install",
]

#: Longest line read at once; a longer line is read in pieces and never buffered whole.
_MAX_LINE_BYTES: Final = 4096
#: Lines kept for classifying a failure; earlier output is dropped as it is read.
_TAIL_LINES: Final = 80
_POLL_S: Final = 0.2
_READER_JOIN_S: Final = 5.0
#: The installer never opens a window, whatever console its parent has. Its children run in the
#: windowless console it is given, so the whole tree stays hidden.
_NO_WINDOW: Final = WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0

_PROXY_VARIABLES: Final = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
#: Inherited variables that could move the installer's download, its platform, its Node runtime or
#: its TLS checks. Every one is withheld; the driver's own language markers are set again below.
_WITHHELD_PREFIXES: Final = ("PLAYWRIGHT_", "PW_", "NODE_", "NPM_CONFIG_")
_DRIVER_MARKERS: Final = frozenset({"PW_LANG_NAME", "PW_LANG_NAME_VERSION", "PW_CLI_DISPLAY_VERSION"})
_BUILD_DIRECTORY: Final = re.compile(r"^[a-z][a-z0-9_]*-\d+$")


def _driver_command(*arguments: str) -> list[str]:
    # The package's Node driver runs directly, as ``python -m playwright`` does: a
    # packaged interpreter child admits only declared environment names and would
    # drop the browser location.
    from playwright._impl._driver import compute_driver_executable

    node, cli = compute_driver_executable()
    return [node, cli, *arguments]


def _withheld(name: str, cadrumo_proxy_names: frozenset[str]) -> bool:
    upper = name.upper()
    return (
        name.lower() in _PROXY_VARIABLES
        or upper in cadrumo_proxy_names
        or (upper.startswith(_WITHHELD_PREFIXES) and upper not in _DRIVER_MARKERS)
    )


def browser_installer_environment(request: BrowserInstallerRequest, *, download_origin: str) -> dict[str, str]:
    """Return the installer's environment: browser root, temporary root and the verified download host.

    Inherited proxy, Playwright, Node and npm variables are dropped, so nothing
    outside Cadrumo can redirect the download, change the platform it selects
    or weaken its connection checks. The installer downloads only from
    ``download_origin``, the loopback host serving verified archives, so it is
    given no proxy at all. ``DEBUG=pw:install`` makes it print the error
    behind a failure.
    """
    from playwright._impl._driver import get_driver_env

    settings = load_settings()
    temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=settings)
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    withheld = frozenset(Settings.proxy_env_var_names())
    environment: dict[str, str] = {
        str(name): str(value) for name, value in get_driver_env().items() if not _withheld(str(name), withheld)
    }
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(request.browsers_root)
    environment["PLAYWRIGHT_DOWNLOAD_HOST"] = download_origin
    for variable in ("TEMP", "TMP", "TMPDIR"):
        environment[variable] = str(temporary_root)
    environment["DEBUG"] = "pw:install"
    return environment


def _read_lines(stream: IO[bytes], tail: deque[str]) -> None:
    while True:
        raw = stream.readline(_MAX_LINE_BYTES)
        if not raw:
            return
        tail.append(raw.decode("utf-8", errors="replace").rstrip("\r\n"))


def run_browser_install(
    request: BrowserInstallerRequest,
    observer: BrowserInstallObserver,
    *,
    command: Sequence[str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> BrowserInstallerExit:
    """Run ``playwright install chromium`` with only the request's pinned archives to download.

    The installer asks the loopback host for each archive in turn; the first
    request fetches and verifies that archive, and the observer sees the bytes
    fetched as the run's progress. Anything else it asks for is refused, and a
    staged file that changed after verification is cut short. A failed fetch
    ends the run with that fetch's category, so a refused or damaged download
    is reported as such rather than as the installer's own complaint.

    ``command`` replaces the driver argv and ``transport`` the network the
    archives are fetched over; the environment is always the one
    :func:`browser_installer_environment` builds.
    """
    request.browsers_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + request.timeout_s
    temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=load_settings())
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix="browser-archives-", dir=temporary_root))
    try:
        fetch = _StagingFetcher(request, observer, staging, deadline, transport)
        with VerifiedArchiveServer(request.archives, fetch) as server:
            environment = browser_installer_environment(request, download_origin=server.origin)
            argv = list(command) if command is not None else _driver_command("install", "chromium")
            ended = _run_installer(argv, environment, observer, deadline)
        failure = server.failure
        if ended.cancelled or (failure is not None and failure.category is DependencyFailureCategory.CANCELLED):
            return BrowserInstallerExit(exit_code=None, cancelled=True)
        if failure is not None:
            return BrowserInstallerExit(
                exit_code=ended.exit_code,
                timed_out=failure.facts.get("timed_out") is True,
                failure_category=failure.category,
                transient=failure.transient,
            )
        if server.mismatched:
            return BrowserInstallerExit(
                exit_code=ended.exit_code, failure_category=DependencyFailureCategory.DAMAGED_DOWNLOAD
            )
        return ended
    finally:
        shutil.rmtree(staging, ignore_errors=True)


class _StagingFetcher:
    """Fetches each pinned archive into the run's staging directory, reporting bytes across the whole run."""

    def __init__(
        self,
        request: BrowserInstallerRequest,
        observer: BrowserInstallObserver,
        staging: Path,
        deadline: float,
        transport: httpx.BaseTransport | None,
    ) -> None:
        self._request = request
        self._observer = observer
        self._staging = staging
        self._deadline = deadline
        self._transport = transport
        self._lock = threading.Lock()
        self._received: dict[str, int] = {}

    def __call__(self, pin: BrowserArchivePin) -> Path:
        # Each build directory is pinned once per platform, so it names its archive uniquely.
        target = self._staging / f"{pin.directory_name}.zip"
        fetch_pinned_archive(
            pin,
            target,
            allowed_hosts=self._request.allowed_hosts,
            proxy=self._request.proxy,
            progress=lambda received: self._progress(pin, received),
            cancelled=lambda: self._observer.cancellation_requested,
            deadline=self._deadline,
            transport=self._transport,
        )
        return target

    def _progress(self, pin: BrowserArchivePin, received: int) -> None:
        with self._lock:
            self._received[pin.path] = received
            total = sum(self._received.values())
        self._observer.transferred(total)


def _run_installer(
    argv: list[str], environment: dict[str, str], observer: BrowserInstallObserver, deadline: float
) -> BrowserInstallerExit:
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
        creationflags=_NO_WINDOW,
        start_new_session=sys.platform != "win32",
    )
    tree = InstallerProcessTree(process)
    tail: deque[str] = deque(maxlen=_TAIL_LINES)
    output = process.stdout
    if output is None:
        raise InternalInvariantError("installer output pipe was not opened")
    reader = threading.Thread(target=_read_lines, args=(output, tail), name="browser-installer-output", daemon=True)
    reader.start()
    cancelled = False
    timed_out = False
    try:
        while process.poll() is None:
            if observer.cancellation_requested:
                cancelled = True
                tree.stop()
                break
            if time.monotonic() >= deadline:
                timed_out = True
                tree.stop()
                break
            reader.join(_POLL_S)
        exit_code = process.wait()
    finally:
        tree.close()
        reader.join(_READER_JOIN_S)
        output.close()
    if cancelled:
        return BrowserInstallerExit(exit_code=None, cancelled=True)
    if timed_out:
        return BrowserInstallerExit(
            exit_code=None,
            timed_out=True,
            failure_category=DependencyFailureCategory.HOST_UNREACHABLE,
            transient=True,
        )
    if exit_code == 0:
        return BrowserInstallerExit(exit_code=0)
    category, transient = classify_installer_output(tail)
    return BrowserInstallerExit(
        exit_code=exit_code,
        failure_category=category or DependencyFailureCategory.UNEXPECTED,
        transient=transient,
    )


def remove_browser_builds(root: Path, directory_names: Sequence[str]) -> tuple[str, ...]:
    """Delete the named build directories directly under ``root`` and return the names removed.

    A name that is not a build directory, or that resolves outside ``root``, is
    refused; a link is unlinked rather than followed.

    Raises:
        ValueError: When a name is not a build directory under ``root``.
        OSError: When a directory cannot be deleted.
    """
    resolved_root = root.resolve()
    removed: list[str] = []
    for name in directory_names:
        if not _BUILD_DIRECTORY.match(name):
            raise ValueError(f"{name!r} is not a browser build directory")
        path = root / name
        if path.is_symlink():
            path.unlink()
            removed.append(name)
            continue
        if not path.exists():
            continue
        if path.resolve().parent != resolved_root:
            raise ValueError(f"{name!r} does not resolve inside the browser root")
        shutil.rmtree(path)
        removed.append(name)
    return tuple(removed)
