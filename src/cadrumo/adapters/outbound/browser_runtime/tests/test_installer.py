"""The installer run: verified downloads first, then the vendor installer on a loopback host.

The fetch refusals run the real downloader over an ``httpx.MockTransport``
playing a hostile source, and prove the installer never starts. The end-to-end
run drives the real bundled Playwright driver against the loopback host with
synthetic archives pinned for this computer's platform, so the environment,
the download-host override, the serving and the vendor's own extraction all
run for real without the network. The remaining runs start a child that prints
the vendor installer's output format, so the pipe reading, the failure
classification and the process-tree stop run for real.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import textwrap
import time
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import override

import httpx
import pytest
from playwright._impl._driver import compute_driver_executable

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.browser_archive_pins import BrowserArchivePin, load_browser_archive_pins
from .....application.dependency_network import DependencyProxy, dependency_hosts
from .....application.provisioning_browser import (
    BrowserBuild,
    BrowserInstallerRequest,
    browser_executable,
    browser_host_platform,
)
from .....core.child_console import WINDOWS_CREATE_NO_WINDOW, ChildConsole, child_console_binding
from .....core.config import override_settings
from .. import installer
from ..installer import browser_installer_environment, remove_browser_builds, run_browser_install

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROXY_WORD = "p@ss"
_ORIGIN = "http://127.0.0.1:9"


class _Observer:
    def __init__(self, *, cancel_at_bytes: int | None = None) -> None:
        self.figures: list[int] = []
        self._cancel_at = cancel_at_bytes

    def transferred(self, completed_bytes: int) -> None:
        self.figures.append(completed_bytes)

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel_at is not None and any(figure >= self._cancel_at for figure in self.figures)


_PRELUDE = """
import subprocess, sys, time
# The vendor driver writes UTF-8 whatever the console code page is.
sys.stdout.reconfigure(encoding="utf-8")
def say(line):
    print(line, flush=True)
"""


def _script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "driver.py"
    path.write_text(_PRELUDE + textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, "-I", str(path)]


def _request(
    tmp_path: Path,
    *,
    timeout_s: float = 30.0,
    proxy: DependencyProxy | None = None,
    archives: tuple[BrowserArchivePin, ...] = (),
) -> BrowserInstallerRequest:
    return BrowserInstallerRequest(
        browsers_root=tmp_path / "browsers",
        timeout_s=timeout_s,
        proxy=proxy,
        archives=archives,
        allowed_hosts=dependency_hosts("browser"),
    )


@pytest.fixture
def _storage(tmp_path: Path) -> Iterator[None]:
    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage", cadrumo_temp_dir=tmp_path / "storage" / "tmp"
    ):
        yield


# -- environment ---------------------------------------------------------------


@pytest.mark.usefixtures("_storage")
def test_the_environment_offers_only_the_verified_host_and_withholds_every_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inherited = {
        "HTTPS_PROXY": "http://inherited.example:1",
        "no_proxy": "inherited.example",
        "npm_config_https_proxy": "http://inherited.example:1",
        "CADRUMO_PROXY_URL": f"http://ana:{_PROXY_WORD}@proxy.example:8080",
        "CADRUMO_PROXY_PASSWORD_SECRET": _PROXY_WORD,
        "PLAYWRIGHT_DOWNLOAD_HOST": "https://downloads.attacker.example",
        "PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST": "https://downloads.attacker.example",
        "PLAYWRIGHT_HOST_PLATFORM_OVERRIDE": "ubuntu24.04-x64",
        "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1",
        "PW_TEST_CDN_THAT_SHOULD_WORK": "https://downloads.attacker.example",
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        "NODE_EXTRA_CA_CERTS": str(tmp_path / "attacker-ca.pem"),
        "NODE_OPTIONS": "--require ./hook.js",
    }
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)

    environment = browser_installer_environment(_request(tmp_path), download_origin=_ORIGIN)

    assert environment["PLAYWRIGHT_DOWNLOAD_HOST"] == _ORIGIN
    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "browsers")
    assert (
        environment["TEMP"]
        == environment["TMP"]
        == environment["TMPDIR"]
        == str((tmp_path / "storage" / "tmp").resolve())
    )
    assert environment["DEBUG"] == "pw:install"
    # The driver's own language markers survive; nothing inherited that could steer it does.
    assert environment["PW_LANG_NAME"] == "python"
    withheld = {name.upper() for name in inherited} - {"PLAYWRIGHT_DOWNLOAD_HOST"}
    assert not withheld & {name.upper() for name in environment}
    assert not {name.lower() for name in environment} & {"https_proxy", "http_proxy", "no_proxy", "all_proxy"}


# -- verified downloads ----------------------------------------------------------


#: Where each vendor build keeps the executable the installer marks runnable, by platform.
_TOOL_EXECUTABLES = {
    "ffmpeg": {
        "win-x64": "ffmpeg-win64.exe",
        "linux-x64": "ffmpeg-linux",
        "linux-arm64": "ffmpeg-linux",
        "mac-x64": "ffmpeg-mac",
        "mac-arm64": "ffmpeg-mac",
    },
    "winldd": {"win-x64": "PrintDeps.exe"},
}


def _executable(directory_name: str, platform: str) -> str:
    name, _, revision = directory_name.rpartition("-")
    if name in _TOOL_EXECUTABLES:
        return _TOOL_EXECUTABLES[name][platform]
    build = BrowserBuild(name=name.replace("_", "-"), revision=revision)
    path = browser_executable(Path(), build, platform)
    assert path is not None
    return path.relative_to(build.directory_name).as_posix()


def _synthetic_archive(pin: BrowserArchivePin, executable: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(executable, f"synthetic {pin.directory_name}".encode())
    return buffer.getvalue()


def _synthetic_pins(platform: str) -> tuple[tuple[BrowserArchivePin, ...], dict[str, bytes]]:
    """Return this platform's pins rebound to small synthetic archives, and each primary source's bytes."""
    table = load_browser_archive_pins()
    assert table is not None
    served: dict[str, bytes] = {}
    pins: list[BrowserArchivePin] = []
    for pin in table.for_platform(platform):
        body = _synthetic_archive(pin, _executable(pin.directory_name, platform))
        served[pin.urls[0]] = body
        pins.append(pin.model_copy(update={"download_bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}))
    return tuple(pins), served


@pytest.mark.usefixtures("_storage")
@pytest.mark.parametrize(
    ("hostile", "category"),
    (
        (
            lambda _body: httpx.Response(307, headers={"location": "https://downloads.attacker.example/chrome.zip"}),
            DependencyFailureCategory.BLOCKED_BY_NETWORK,
        ),
        (
            lambda body: httpx.Response(200, stream=httpx.ByteStream(body[:-4] + b"evil")),
            DependencyFailureCategory.DAMAGED_DOWNLOAD,
        ),
    ),
    ids=("redirect-off-plan", "substituted-bytes"),
)
def test_a_download_that_is_not_the_pinned_archive_is_never_extracted(
    tmp_path: Path, hostile: Callable[[bytes], httpx.Response], category: DependencyFailureCategory
) -> None:
    platform = browser_host_platform()
    assert platform is not None
    pins, served = _synthetic_pins(platform)
    requested: list[str] = []

    def network(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return hostile(served[str(request.url)])

    ended = run_browser_install(
        _request(tmp_path, timeout_s=120.0, archives=pins), _Observer(), transport=httpx.MockTransport(network)
    )

    assert ended.failure_category is category
    assert ended.transient is False
    # The first archive the installer asked for was refused once and never fetched again.
    assert len(requested) == 1
    root = tmp_path / "browsers"
    assert not any((root / pin.directory_name).exists() for pin in pins)
    assert not any((tmp_path / "storage" / "tmp").glob("browser-archives-*"))


@pytest.mark.usefixtures("_storage")
def test_the_vendor_installer_extracts_exactly_the_verified_archives(tmp_path: Path) -> None:
    platform = browser_host_platform()
    assert platform is not None
    pins, served = _synthetic_pins(platform)
    observer = _Observer()

    ended = run_browser_install(
        _request(tmp_path, timeout_s=120.0, archives=tuple(pins)),
        observer,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=httpx.ByteStream(served[str(request.url)]))
        ),
    )

    assert ended.exit_code == 0
    assert ended.failure_category is None
    assert observer.figures[-1] == sum(len(body) for body in served.values())
    root = tmp_path / "browsers"
    for pin in pins:
        assert (root / pin.directory_name / "INSTALLATION_COMPLETE").is_file()
        extracted = root / pin.directory_name / _executable(pin.directory_name, platform)
        assert extracted.read_bytes() == f"synthetic {pin.directory_name}".encode()


# -- installer process -------------------------------------------------------------


@pytest.mark.usefixtures("_storage")
@pytest.mark.parametrize(
    ("error", "category", "transient"),
    (
        ("Error: getaddrinfo EAI_AGAIN cdn.playwright.dev", DependencyFailureCategory.HOST_UNREACHABLE, True),
        (
            "Download failed: server returned code 503 body ''. URL: https://x",
            DependencyFailureCategory.HOST_UNREACHABLE,
            True,
        ),
        (
            "Download failed: server returned code 407 body ''. URL: https://x",
            DependencyFailureCategory.BLOCKED_BY_NETWORK,
            False,
        ),
        ("Error: ENOSPC: no space left on device, write", DependencyFailureCategory.DISK_FULL, False),
        ("Error: unable to get local issuer certificate", DependencyFailureCategory.SECURE_CONNECTION_FAILED, False),
        ("Error: something nobody expected", DependencyFailureCategory.UNEXPECTED, False),
    ),
)
def test_a_failed_run_names_its_category(
    tmp_path: Path, error: str, category: DependencyFailureCategory, transient: bool
) -> None:
    body = f"say({error!r})\nsys.exit(1)\n"

    ended = run_browser_install(_request(tmp_path), _Observer(), command=_script(tmp_path, body))

    assert ended.exit_code == 1
    assert ended.failure_category is category
    assert ended.transient is transient


_HEARTBEAT_CHILD = """
import pathlib, sys, time
beat = pathlib.Path(sys.argv[1])
while True:
    beat.write_text(str(time.monotonic()))
    time.sleep(0.05)
"""


class _CancelWhenStarted(_Observer):
    """Asks to cancel once the installer's child has proved it is running."""

    def __init__(self, beat: Path) -> None:
        super().__init__()
        self._beat = beat

    @property
    @override
    def cancellation_requested(self) -> bool:
        return self._beat.exists()


@pytest.mark.usefixtures("_storage")
def test_cancel_stops_the_installer_and_the_children_it_started(tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child.write_text(_HEARTBEAT_CHILD, encoding="utf-8")
    beat = tmp_path / "beat.txt"
    flags = "0x08000000" if sys.platform == "win32" else "0"
    body = f"""
    subprocess.Popen([sys.executable, "-I", {str(child)!r}, {str(beat)!r}], creationflags={flags})
    time.sleep(60)
    """

    started = time.monotonic()
    ended = run_browser_install(_request(tmp_path), _CancelWhenStarted(beat), command=_script(tmp_path, body))

    assert ended.cancelled is True
    assert time.monotonic() - started < 30
    # Terminating the tree completes asynchronously, so a write already under way may still land;
    # a child that kept running would keep changing the beat and never settle.
    settled = beat.read_text(encoding="utf-8")
    settle_by = time.monotonic() + 5
    while time.monotonic() < settle_by:
        time.sleep(0.3)
        current = beat.read_text(encoding="utf-8")
        if current == settled:
            break
        settled = current
    time.sleep(0.5)
    assert beat.read_text(encoding="utf-8") == settled


@pytest.mark.usefixtures("_storage")
def test_a_run_past_its_deadline_is_stopped_as_a_transient_failure(tmp_path: Path) -> None:
    ended = run_browser_install(
        _request(tmp_path, timeout_s=0.5), _Observer(), command=_script(tmp_path, "time.sleep(60)\n")
    )

    assert ended.timed_out is True
    assert ended.transient is True


def test_build_removal_stays_inside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "browsers"
    (root / "chromium-1200" / "chrome-win64").mkdir(parents=True)
    (root / "chromium-1200" / "chrome-win64" / "chrome.exe").write_bytes(b"x")
    outside = tmp_path / "keep"
    outside.mkdir()

    assert remove_browser_builds(root, ["chromium-1200", "chromium-1100"]) == ("chromium-1200",)
    assert not (root / "chromium-1200").exists()
    for refused in ("..", "../keep", "chromium-1200/../../keep", "notabuild"):
        with pytest.raises(ValueError):
            remove_browser_builds(root, [refused])
    assert outside.is_dir()


class _FinishedProcess:
    def __init__(self, argv: list[str], **kwargs: object) -> None:
        self.argv = argv
        self.kwargs = kwargs
        self.stdout = io.BytesIO(b"")
        self.pid = os.getpid()
        self._handle = 0

    def poll(self) -> int:
        return 0

    def wait(self) -> int:
        return 0

    def kill(self) -> None:
        return None


@pytest.mark.usefixtures("_storage")
@pytest.mark.parametrize("console", [ChildConsole.SHARED, ChildConsole.OWN])
def test_the_driver_runs_directly_and_never_opens_a_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, console: ChildConsole
) -> None:
    started: list[_FinishedProcess] = []

    def popen(argv: list[str], **kwargs: object) -> _FinishedProcess:
        process = _FinishedProcess(argv, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(installer.subprocess, "Popen", popen)

    with child_console_binding.override(console):
        ended = run_browser_install(_request(tmp_path), _Observer())

    no_window = WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0
    assert ended.exit_code == 0
    # The driver runs directly: an interpreter child would filter the browser location out.
    assert started[0].argv == [*compute_driver_executable(), "install", "chromium"]
    assert started[0].kwargs["creationflags"] == no_window
