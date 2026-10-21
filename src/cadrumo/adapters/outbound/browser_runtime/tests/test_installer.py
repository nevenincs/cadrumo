"""The installer run: its environment, bounded output reading, progress, failure cause and cancel.

The runs below start a real child process that prints the vendor installer's
own output format, so the pipe reading, the progress parser, the failure
classification and the process-tree stop all run for real. Only the argv is
replaced; the environment is the one the product builds.
"""

from __future__ import annotations

import io
import os
import sys
import textwrap
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright._impl._driver import compute_driver_executable

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.dependency_network import DependencyProxy
from .....application.provisioning_browser import BrowserInstallerRequest
from .....core.child_console import WINDOWS_CREATE_NO_WINDOW, ChildConsole, child_console_binding
from .....core.config import override_settings
from .. import installer
from ..installer import (
    browser_installer_environment,
    measure_browser_downloads,
    remove_browser_builds,
    run_browser_install,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_MIB = 1024 * 1024
_PROXY_WORD = "p@ss"


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

_TWO_ARCHIVES = """
say("Downloading Chrome for Testing 156.0.8078.4 (playwright chromium v1248) from https://cdn.playwright.dev/a.zip")
say("pw:install -- total bytes: 200000000 +0ms")
say("|" + "\\u25a0" * 8 + " " * 72 + "|  10% of 190.7 MiB")
say("|" + "\\u25a0" * 80 + "| 100% of 190.7 MiB")
say("Chrome for Testing 156.0.8078.4 (playwright chromium v1248) downloaded to C:\\\\x\\\\chromium-1248")
say("Downloading FFmpeg (playwright ffmpeg v1013) from https://cdn.playwright.dev/f.zip")
say("|" + "\\u25a0" * 40 + " " * 40 + "|  50% of 1.6 MiB")
"""


def _script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "driver.py"
    path.write_text(_PRELUDE + textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, "-I", str(path)]


def _request(
    tmp_path: Path, *, timeout_s: float = 30.0, proxy: DependencyProxy | None = None
) -> BrowserInstallerRequest:
    return BrowserInstallerRequest(browsers_root=tmp_path / "browsers", timeout_s=timeout_s, proxy=proxy)


@pytest.fixture
def _storage(tmp_path: Path) -> Iterator[None]:
    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage", cadrumo_temp_dir=tmp_path / "storage" / "tmp"
    ):
        yield


@pytest.mark.usefixtures("_storage")
def test_the_environment_carries_the_roots_and_only_cadrumos_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://inherited.example:1")
    monkeypatch.setenv("no_proxy", "inherited.example")
    monkeypatch.setenv("CADRUMO_PROXY_URL", f"http://ana:{_PROXY_WORD}@proxy.example:8080")
    monkeypatch.setenv("CADRUMO_PROXY_PASSWORD_SECRET", _PROXY_WORD)
    proxy = DependencyProxy(
        host="proxy.example", port=8080, username="ana maria", password=_PROXY_WORD, bypass=("intranet.example",)
    )

    environment = browser_installer_environment(_request(tmp_path, proxy=proxy))

    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "browsers")
    assert (
        environment["TEMP"]
        == environment["TMP"]
        == environment["TMPDIR"]
        == str((tmp_path / "storage" / "tmp").resolve())
    )
    assert environment["HTTPS_PROXY"] == environment["HTTP_PROXY"] == "http://ana%20maria:p%40ss@proxy.example:8080"
    assert environment["NO_PROXY"] == "intranet.example"
    assert environment["no_proxy"] == "intranet.example"
    assert environment["DEBUG"] == "pw:install"
    # Cadrumo's own settings reach the installer only as the standard proxy variables.
    assert not any(name.upper().startswith("CADRUMO_PROXY_") for name in environment)


@pytest.mark.usefixtures("_storage")
def test_without_a_cadrumo_proxy_inherited_proxy_settings_are_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://inherited.example:1")

    environment = browser_installer_environment(_request(tmp_path))

    assert not {name.lower() for name in environment} & {"https_proxy", "http_proxy", "no_proxy", "all_proxy"}


@pytest.mark.usefixtures("_storage")
def test_a_run_reports_running_bytes_across_archives(tmp_path: Path) -> None:
    observer = _Observer()

    ended = run_browser_install(_request(tmp_path), observer, command=_script(tmp_path, _TWO_ARCHIVES))

    assert ended.exit_code == 0
    assert ended.failure_category is None
    assert observer.figures == [20_000_000, 200_000_000, 200_000_000, 200_000_000 + round(1.6 * _MIB) // 2]


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


@pytest.mark.usefixtures("_storage")
def test_cancel_stops_the_installer_and_the_children_it_started(tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child.write_text(_HEARTBEAT_CHILD, encoding="utf-8")
    beat = tmp_path / "beat.txt"
    flags = "0x08000000" if sys.platform == "win32" else "0"
    body = f"""
    subprocess.Popen([sys.executable, "-I", {str(child)!r}, {str(beat)!r}], creationflags={flags})
    while not __import__("pathlib").Path({str(beat)!r}).exists():
        time.sleep(0.02)
    say("Downloading Chrome for Testing 1 (playwright chromium v1248) from https://cdn.playwright.dev/a.zip")
    say("|" + "x" * 8 + "|  10% of 100 MiB")
    time.sleep(60)
    """

    started = time.monotonic()
    ended = run_browser_install(_request(tmp_path), _Observer(cancel_at_bytes=1), command=_script(tmp_path, body))

    assert ended.cancelled is True
    assert time.monotonic() - started < 30
    settled = beat.read_text(encoding="utf-8")
    time.sleep(0.5)
    assert beat.read_text(encoding="utf-8") == settled


@pytest.mark.usefixtures("_storage")
def test_a_run_past_its_deadline_is_stopped_as_a_transient_failure(tmp_path: Path) -> None:
    ended = run_browser_install(
        _request(tmp_path, timeout_s=0.5), _Observer(), command=_script(tmp_path, "time.sleep(60)\n")
    )

    assert ended.timed_out is True
    assert ended.transient is True


_DRY_RUN = r"""
say("Chrome for Testing 156.0.8078.4 (playwright chromium v1248)")
say("  Install location:    C:\\pw\\chromium-1248")
say("  Download url:        https://cdn.playwright.dev/builds/cft/156.0.8078.4/win64/chrome-win64.zip")
say("")
say("FFmpeg (playwright ffmpeg v1013)")
say("  Install location:    /pw/ffmpeg-1013")
say("  Download url:        https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1013/ffmpeg-win64.zip")
say("  Download fallback 1: https://playwright.download.prss.microsoft.com/x.zip")
say("")
say("Something (playwright odd v1)")
say("  Install location:    <system>")
"""


@pytest.mark.usefixtures("_storage")
def test_the_dry_run_listing_names_each_archive_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    measured: list[tuple[str, str]] = []

    def record(directory: str, url: str, proxy: object) -> object:
        del proxy
        measured.append((directory, url))
        return installer.BrowserArchive(directory_name=directory, url=url, download_bytes=10)

    # The sizes come from the network; here only the listing is under test.
    monkeypatch.setattr(installer, "_measure_archive", record)

    measurement = measure_browser_downloads(_request(tmp_path), command=_script(tmp_path, _DRY_RUN))

    assert measurement is not None
    assert [archive.directory_name for archive in measurement.archives] == ["chromium-1248", "ffmpeg-1013"]
    assert measured[1][1].endswith("/ffmpeg/1013/ffmpeg-win64.zip")


@pytest.mark.usefixtures("_storage")
def test_an_unreadable_listing_measures_nothing(tmp_path: Path) -> None:
    assert measure_browser_downloads(_request(tmp_path), command=_script(tmp_path, "sys.exit(2)\n")) is None


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
    listed: list[dict[str, object]] = []

    def popen(argv: list[str], **kwargs: object) -> _FinishedProcess:
        process = _FinishedProcess(argv, **kwargs)
        started.append(process)
        return process

    def run(argv: list[str], **kwargs: object) -> object:
        listed.append(kwargs)
        return type("Completed", (), {"returncode": 1, "stdout": b""})()

    monkeypatch.setattr(installer.subprocess, "Popen", popen)
    monkeypatch.setattr(installer.subprocess, "run", run)

    with child_console_binding.override(console):
        ended = run_browser_install(_request(tmp_path), _Observer())
        measure_browser_downloads(_request(tmp_path))

    no_window = WINDOWS_CREATE_NO_WINDOW if sys.platform == "win32" else 0
    assert ended.exit_code == 0
    # The driver runs directly: an interpreter child would filter the browser location out.
    assert started[0].argv == [*compute_driver_executable(), "install", "chromium"]
    assert started[0].kwargs["creationflags"] == no_window
    assert listed[0]["creationflags"] == no_window
