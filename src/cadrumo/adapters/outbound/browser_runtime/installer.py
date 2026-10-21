"""Operating-system process control for installing the Playwright Chromium build.

:func:`run_browser_install` runs the installed Playwright package's own driver
installer over a fixed argv, so the downloaded revisions are exactly the ones
that package launches. Its output is read line by line within fixed bounds for
byte progress and for the failure cause, Cadrumo's proxy settings replace any
inherited ones, and a cancel stops the installer with every process it started.

:func:`measure_browser_downloads` asks the same installer which archives it
would fetch, without fetching them, and asks each source for its size.
:func:`remove_browser_builds` deletes named build directories under the
browser root and nothing else.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Final
from urllib.parse import urlsplit

import httpx

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.dependency_network import (
    DependencyProxy,
    dependency_proxy_environment,
)
from ....application.provisioning_browser import (
    BrowserArchive,
    BrowserDownloadMeasurement,
    BrowserInstallerExit,
    BrowserInstallerRequest,
    BrowserInstallObserver,
)
from ....core.child_console import WINDOWS_CREATE_NO_WINDOW
from ....core.config import Settings, load_settings
from ....core.errors.hierarchy import InternalInvariantError
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from .installer_output import InstallerProgressParser, classify_installer_output
from .process_tree import InstallerProcessTree

__all__ = [
    "browser_installer_environment",
    "measure_browser_downloads",
    "remove_browser_builds",
    "run_browser_install",
]

#: Longest line read at once; a longer line is read in pieces and never buffered whole.
_MAX_LINE_BYTES: Final = 4096
#: Lines kept for classifying a failure; earlier output is dropped as it is read.
_TAIL_LINES: Final = 80
_POLL_S: Final = 0.2
_READER_JOIN_S: Final = 5.0
_DRY_RUN_TIMEOUT_S: Final = 20.0
_DRY_RUN_MAX_BYTES: Final = 64 * 1024
_SIZE_REQUEST_TIMEOUT_S: Final = 5.0
#: The installer never opens a window, whatever console its parent has. Its children run in the
#: windowless console it is given, so the whole tree stays hidden.
_NO_WINDOW: Final = WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0

_PROXY_VARIABLES: Final = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
_NPM_PROXY_VARIABLES: Final = ("npm_config_proxy", "npm_config_https_proxy", "npm_config_no_proxy")
_BUILD_DIRECTORY: Final = re.compile(r"^[a-z][a-z0-9_]*-\d+$")
_DRY_RUN_LOCATION: Final = re.compile(r"^\s*Install location:\s+(.+?)\s*$")
_DRY_RUN_URL: Final = re.compile(r"^\s*Download url:\s+(https://\S+)\s*$")


def _driver_command(*arguments: str) -> list[str]:
    # The package's Node driver runs directly, as ``python -m playwright`` does: a
    # packaged interpreter child admits only declared environment names and would
    # drop the browser location.
    from playwright._impl._driver import compute_driver_executable

    node, cli = compute_driver_executable()
    return [node, cli, *arguments]


def browser_installer_environment(request: BrowserInstallerRequest) -> dict[str, str]:
    """Return the installer's environment: browser root, temporary root, and only Cadrumo's proxy.

    Inherited proxy variables are dropped so the download follows Cadrumo's
    settings and nothing else; Cadrumo's own proxy settings reach it only as the
    standard proxy variables. ``DEBUG=pw:install`` makes the installer print
    each archive's size and the network error behind a failure.
    """
    from playwright._impl._driver import get_driver_env

    settings = load_settings()
    temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=settings)
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    withheld = Settings.proxy_env_var_names()
    environment: dict[str, str] = {
        str(name): str(value)
        for name, value in get_driver_env().items()
        if name.lower() not in _PROXY_VARIABLES
        and name.lower() not in _NPM_PROXY_VARIABLES
        and name.upper() not in withheld
    }
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(request.browsers_root)
    for variable in ("TEMP", "TMP", "TMPDIR"):
        environment[variable] = str(temporary_root)
    environment["DEBUG"] = "pw:install"
    environment.update(dependency_proxy_environment(request.proxy))
    return environment


def _read_lines(
    stream: IO[bytes], parser: InstallerProgressParser, observer: BrowserInstallObserver, tail: deque[str]
) -> None:
    while True:
        raw = stream.readline(_MAX_LINE_BYTES)
        if not raw:
            return
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        tail.append(line)
        completed = parser.feed(line)
        if completed is not None:
            observer.transferred(completed)


def run_browser_install(
    request: BrowserInstallerRequest,
    observer: BrowserInstallObserver,
    *,
    command: Sequence[str] | None = None,
) -> BrowserInstallerExit:
    """Run ``playwright install chromium`` once and report how it ended.

    ``command`` replaces the driver argv; the environment is always the one
    :func:`browser_installer_environment` builds.
    """
    request.browsers_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment = browser_installer_environment(request)
    argv = list(command) if command is not None else _driver_command("install", "chromium")
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
    reader = threading.Thread(
        target=_read_lines,
        args=(output, InstallerProgressParser(), observer, tail),
        name="browser-installer-output",
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + request.timeout_s
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


def _parse_dry_run(text: str) -> list[tuple[str, str]]:
    """Return ``(build directory, primary URL)`` for each block of a dry-run listing."""
    archives: list[tuple[str, str]] = []
    location: str | None = None
    for line in text.splitlines():
        found = _DRY_RUN_LOCATION.match(line)
        if found is not None:
            location = Path(found.group(1)).name
            continue
        url = _DRY_RUN_URL.match(line)
        if url is not None and location is not None:
            if _BUILD_DIRECTORY.match(location):
                archives.append((location, url.group(1)))
            location = None
    return archives


def _measure_archive(directory: str, url: str, proxy: DependencyProxy | None) -> BrowserArchive:
    host = (urlsplit(url).hostname or "").lower()
    try:
        with httpx.Client(
            proxy=proxy.url(with_credentials=True) if proxy is not None and not proxy.bypasses(host) else None,
            trust_env=False,
            follow_redirects=True,
            timeout=_SIZE_REQUEST_TIMEOUT_S,
        ) as client:
            response = client.head(url)
    except httpx.HTTPError:
        return BrowserArchive(directory_name=directory, url=url, hosts=(host,) if host else ())
    hops = [*(step.url.host for step in response.history), response.url.host]
    hosts = tuple(dict.fromkeys(hop.lower() for hop in hops if hop))
    length = response.headers.get("content-length")
    size = int(length) if response.status_code == 200 and length is not None and length.isdigit() else None
    return BrowserArchive(directory_name=directory, url=url, download_bytes=size, hosts=hosts)


def measure_browser_downloads(
    request: BrowserInstallerRequest,
    *,
    command: Sequence[str] | None = None,
) -> BrowserDownloadMeasurement | None:
    """List the archives the installer would fetch and ask each source for its size.

    Nothing is downloaded: the installer runs with ``--dry-run`` and each
    source receives one ``HEAD`` request. ``None`` when the listing could not
    be read.
    """
    environment = browser_installer_environment(request)
    argv = list(command) if command is not None else _driver_command("install", "--dry-run", "chromium")
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_DRY_RUN_TIMEOUT_S,
            check=False,
            env=environment,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    listing = completed.stdout[:_DRY_RUN_MAX_BYTES].decode("utf-8", errors="replace")
    archives = _parse_dry_run(listing)
    if not archives:
        return None
    return BrowserDownloadMeasurement(
        archives=tuple(_measure_archive(directory, url, request.proxy) for directory, url in archives)
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
