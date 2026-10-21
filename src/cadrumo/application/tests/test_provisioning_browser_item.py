"""The ``browser`` setup item: checks, plan and setup against real manifest and cache trees.

The manifest parser, the cache observation, the receipt comparison, the retry
schedule and the state the registry derives all run for real against files on
disk. The injected seams are the outside effects only: the installer stands in
for the vendor download by writing the cache layout the real installer
produces, the sizer returns a measurement, and the launcher reports a version.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.storage_taxonomy import StorageCategory
from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemFinisher,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencySetupStep,
    DependencyState,
)
from ..dependency_receipts import DependencyReceipt, DependencyReceiptStore, build_file_manifest
from ..dependency_registry import BROWSER_DECLARATION, derive_dependency_row
from ..dependency_transfer import DEPENDENCY_RETRY_POLICY
from ..provisioning_browser import (
    BrowserArchive,
    BrowserBuild,
    BrowserDownloadMeasurement,
    BrowserInstallerExit,
    BrowserInstallerRequest,
    BrowserInstallObserver,
    BrowserLaunchFailureCause,
    BrowserLaunchReading,
    PlaywrightBrowserItem,
    browser_executable,
    browser_host_platform,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HOST = "win-x64"
_VERSION = "156.0.8078.4"
_FULL = BrowserBuild(name="chromium", revision="1248", browser_version=_VERSION)
_SHELL = BrowserBuild(name="chromium-headless-shell", revision="1248", browser_version=_VERSION)
_BOTH = (_FULL.directory_name, _SHELL.directory_name)


def _manifest(tmp_path: Path, *, overrides: bool = False) -> Path:
    path = tmp_path / "browsers.json"
    shell: dict[str, object] = {"name": "chromium-headless-shell", "revision": "1248", "browserVersion": _VERSION}
    if overrides:
        shell["revisionOverrides"] = {"mac14": "1200"}
    document = {"browsers": [{"name": "chromium", "revision": "1248", "browserVersion": _VERSION}, shell]}
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _lay_down(root: Path, build: BrowserBuild, *, marker: bool = True, executable: bytes | None = b"exe") -> None:
    (root / build.directory_name).mkdir(parents=True, exist_ok=True)
    if marker:
        (root / build.directory_name / "INSTALLATION_COMPLETE").write_bytes(b"")
    if executable is not None:
        path = browser_executable(root, build, _HOST)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(executable)


class _Events:
    def __init__(self, *, cancel_after_transfer: bool = False) -> None:
        self.steps: list[DependencySetupStep] = []
        self.transfers: list[tuple[int, int | None]] = []
        self.retries: list[tuple[int, float]] = []
        self.irreversible_entered = 0
        self._cancel = False
        self._cancel_after_transfer = cancel_after_transfer

    async def step(self, step: DependencySetupStep) -> None:
        self.steps.append(step)

    async def transferred(self, *, completed: int, total: int | None) -> None:
        self.transfers.append((completed, total))
        if self._cancel_after_transfer:
            self._cancel = True

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        self.retries.append((attempt, delay_s))

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel

    def request_cancel(self) -> None:
        self._cancel = True

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        self.irreversible_entered += 1
        yield


class _Installer:
    """Writes the cache the vendor installer would write, reporting progress as it goes."""

    def __init__(
        self, root: Path, outcomes: Sequence[BrowserInstallerExit | None], *, cancel_wait_s: float = 0.0
    ) -> None:
        self.root = root
        self.cancel_wait_s = cancel_wait_s
        self.outcomes = list(outcomes)
        self.requests: list[BrowserInstallerRequest] = []
        self.present_at_start: list[tuple[str, ...]] = []

    def __call__(self, request: BrowserInstallerRequest, observer: BrowserInstallObserver) -> BrowserInstallerExit:
        self.requests.append(request)
        self.present_at_start.append(tuple(sorted(p.name for p in self.root.iterdir())) if self.root.exists() else ())
        outcome = self.outcomes.pop(0)
        observer.transferred(100)
        # Like the real installer, keep running while watching for a cancel.
        deadline = time.monotonic() + self.cancel_wait_s
        while not observer.cancellation_requested and time.monotonic() < deadline:
            time.sleep(0.01)
        if observer.cancellation_requested:
            return BrowserInstallerExit(exit_code=None, cancelled=True)
        if outcome is None:
            _lay_down(self.root, _FULL)
            _lay_down(self.root, _SHELL)
            observer.transferred(300)
            return BrowserInstallerExit(exit_code=0)
        # A failed attempt leaves a partial build behind, as an interrupted extraction would.
        _lay_down(self.root, _SHELL, marker=False)
        return outcome


class _Launcher:
    def __init__(self, reading: BrowserLaunchReading) -> None:
        self.reading = reading
        self.launched: list[Path] = []

    async def __call__(self, executable: Path, *, timeout_s: float) -> BrowserLaunchReading:
        assert timeout_s <= 60
        self.launched.append(executable)
        return self.reading


def _remove(root: Path, names: Sequence[str]) -> tuple[str, ...]:
    removed = []
    for name in names:
        if (root / name).exists():
            shutil.rmtree(root / name)
            removed.append(name)
    return tuple(removed)


async def _no_sleep(_seconds: float) -> None:
    return None


def _item(
    tmp_path: Path,
    *,
    installer: _Installer | None = None,
    measurement: BrowserDownloadMeasurement | None = None,
    launcher: _Launcher | None = None,
    receipts: DependencyReceiptStore | None = None,
    manifest: Path | str | None = "default",
    host: str | None = _HOST,
) -> PlaywrightBrowserItem:
    root = tmp_path / "cache"
    manifest_path = _manifest(tmp_path) if manifest == "default" else manifest
    assert not isinstance(manifest_path, str)
    return PlaywrightBrowserItem(
        install=installer or _Installer(root, []),
        measure=lambda _request: measurement,
        launch=launcher or _Launcher(BrowserLaunchReading(version=_VERSION)),
        remove_builds=_remove,
        receipts=receipts,
        browsers_root=lambda: root,
        manifest_path=lambda: manifest_path,
        host_platform=lambda: host,
        sleep=_no_sleep,
        jitter=lambda: 0.5,
    )


def _check(item: PlaywrightBrowserItem, mode: DependencyCheckMode = DependencyCheckMode.QUICK):
    return asyncio.run(item.check(mode))


def _store(tmp_path: Path) -> DependencyReceiptStore:
    return DependencyReceiptStore(tmp_path / "receipts")


def _record(tmp_path: Path) -> DependencyReceiptStore:
    """Write the receipt a verified setup of the current cache would have written."""
    root = tmp_path / "cache"
    store = _store(tmp_path)
    store.write(
        DependencyReceipt(
            item_id="browser",
            version=_VERSION,
            files=build_file_manifest(root),
            verified_at=datetime(2026, 10, 18, tzinfo=UTC),
        )
    )
    return store


# -- quick check -------------------------------------------------------------


def test_an_empty_cache_reads_absent_and_derives_set_up(tmp_path: Path) -> None:
    reading = _check(_item(tmp_path))

    assert reading.outcome is DependencyProbeOutcome.ABSENT
    assert reading.facts["missing_builds"] == ",".join(_BOTH)
    row = derive_dependency_row(BROWSER_DECLARATION, reading)
    assert row.state is DependencyState.ABSENT


def test_a_marker_without_its_executable_is_not_present(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL, executable=None)

    reading = _check(_item(tmp_path))

    assert reading.outcome is DependencyProbeOutcome.ABSENT
    assert reading.facts["missing_builds"] == _SHELL.directory_name


def test_complete_builds_are_present_with_the_pinned_version(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    _lay_down(root, BrowserBuild(name="chromium", revision="1200"))

    reading = _check(_item(tmp_path))

    assert reading.outcome is DependencyProbeOutcome.PRESENT
    assert reading.version == _VERSION
    assert reading.facts["superseded_builds"] == "chromium-1200"
    assert reading.facts["receipt_matches_builds"] is False


def test_a_receipt_alone_never_makes_the_browser_present(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    store = _record(tmp_path)
    shutil.rmtree(root)

    reading = _check(_item(tmp_path, receipts=store))

    assert reading.outcome is DependencyProbeOutcome.ABSENT


def test_a_size_that_differs_from_the_receipt_is_a_damaged_download(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    store = _record(tmp_path)
    _lay_down(root, _SHELL, executable=b"truncated-or-grown")

    reading = _check(_item(tmp_path, receipts=store))

    assert reading.outcome is DependencyProbeOutcome.FAILED
    assert reading.failure_category is DependencyFailureCategory.DAMAGED_DOWNLOAD
    assert reading.facts["damaged_files"] == 1


def test_without_the_playwright_package_the_browser_is_not_in_this_build(tmp_path: Path) -> None:
    reading = _check(_item(tmp_path, manifest=None))

    assert reading.outcome is DependencyProbeOutcome.BLOCKED
    assert reading.blocked_reason is DependencyBlockedReason.NOT_IN_THIS_BUILD


@pytest.mark.parametrize("cause", ("overrides", "malformed", "platform"))
def test_an_unreadable_manifest_or_platform_reads_unreadable(tmp_path: Path, cause: str) -> None:
    if cause == "overrides":
        item = _item(tmp_path, manifest=_manifest(tmp_path, overrides=True))
    elif cause == "malformed":
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        item = _item(tmp_path, manifest=broken)
    else:
        item = _item(tmp_path, host=None)

    reading = _check(item)

    assert reading.outcome is DependencyProbeOutcome.UNREADABLE
    assert derive_dependency_row(BROWSER_DECLARATION, reading).state is DependencyState.UNKNOWN


def test_the_quick_check_never_launches(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    launcher = _Launcher(BrowserLaunchReading(version=_VERSION))

    _check(_item(tmp_path, launcher=launcher))

    assert launcher.launched == []


# -- full check --------------------------------------------------------------


def test_the_full_check_launches_the_headless_build_once(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    launcher = _Launcher(BrowserLaunchReading(version=_VERSION))

    reading = _check(_item(tmp_path, launcher=launcher, receipts=_record(tmp_path)), DependencyCheckMode.FULL)

    assert reading.outcome is DependencyProbeOutcome.PRESENT
    assert reading.mode is DependencyCheckMode.FULL
    assert reading.facts["launched_version"] == _VERSION
    assert launcher.launched == [browser_executable(root, _SHELL, _HOST)]


def test_a_launched_version_other_than_the_manifest_is_a_damaged_download(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)

    reading = _check(
        _item(tmp_path, launcher=_Launcher(BrowserLaunchReading(version="150.0.0.1"))), DependencyCheckMode.FULL
    )

    assert reading.failure_category is DependencyFailureCategory.DAMAGED_DOWNLOAD


def test_a_browser_that_does_not_start_fails_the_full_check(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    failing = _Launcher(
        BrowserLaunchReading(
            failure_category=DependencyFailureCategory.UNEXPECTED, failure_cause=BrowserLaunchFailureCause.TIMED_OUT
        )
    )

    reading = _check(_item(tmp_path, launcher=failing), DependencyCheckMode.FULL)

    assert reading.outcome is DependencyProbeOutcome.FAILED
    assert reading.failure_category is DependencyFailureCategory.UNEXPECTED
    # The failure explains itself in closed words a report may carry.
    assert reading.facts["launched"] is False
    assert reading.facts["launch_failure_cause"] == "timed_out"
    assert derive_dependency_row(BROWSER_DECLARATION, reading).state is DependencyState.FAILED


def test_a_launch_cause_stands_only_beside_a_failure() -> None:
    with pytest.raises(ValidationError):
        BrowserLaunchReading(version=_VERSION, failure_cause=BrowserLaunchFailureCause.TIMED_OUT)


def test_the_full_check_compares_every_recorded_file_where_the_quick_check_compares_executables(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    (root / _FULL.directory_name / "chrome-win64" / "chrome.dll").write_bytes(b"aaaa")
    store = _record(tmp_path)
    (root / _FULL.directory_name / "chrome-win64" / "chrome.dll").write_bytes(b"bbbb")
    launcher = _Launcher(BrowserLaunchReading(version=_VERSION))
    item = _item(tmp_path, launcher=launcher, receipts=store)

    assert _check(item).outcome is DependencyProbeOutcome.PRESENT
    full = _check(item, DependencyCheckMode.FULL)

    assert full.failure_category is DependencyFailureCategory.DAMAGED_DOWNLOAD
    assert launcher.launched == []


# -- plan --------------------------------------------------------------------


def _archive(directory: str, size: int | None, *hosts: str) -> BrowserArchive:
    return BrowserArchive(
        directory_name=directory, url=f"https://cdn.playwright.dev/{directory}.zip", download_bytes=size, hosts=hosts
    )


def test_the_plan_sums_the_archives_still_to_download(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, BrowserBuild(name="ffmpeg", revision="1013"), executable=None)
    measurement = BrowserDownloadMeasurement(
        archives=(
            _archive(_FULL.directory_name, 200, "cdn.playwright.dev", "storage.googleapis.com"),
            _archive("ffmpeg-1013", 7, "cdn.playwright.dev"),
            _archive(_SHELL.directory_name, 120, "cdn.playwright.dev", "storage.googleapis.com"),
        )
    )

    entry = asyncio.run(_item(tmp_path, measurement=measurement).plan(model_name=None))

    assert entry.download_bytes == 320
    assert entry.destination is StorageCategory.PLAYWRIGHT_BROWSERS
    assert entry.target_version == _VERSION
    assert entry.source_hosts[-1] == "storage.googleapis.com"
    assert "cdn.playwright.dev" in entry.source_hosts


@pytest.mark.parametrize(
    "measurement",
    (None, BrowserDownloadMeasurement(archives=(_archive("chromium-1248", None, "cdn.playwright.dev"),))),
)
def test_an_unmeasured_plan_leaves_the_size_unknown(
    tmp_path: Path, measurement: BrowserDownloadMeasurement | None
) -> None:
    entry = asyncio.run(_item(tmp_path, measurement=measurement).plan(model_name=None))

    assert entry.download_bytes is None
    assert entry.source_hosts


# -- setup -------------------------------------------------------------------


def _entry(size: int | None = 300, version: str = _VERSION) -> DependencyPlanEntry:
    return DependencyPlanEntry(
        item_id="browser",
        download_bytes=size,
        source_hosts=("cdn.playwright.dev",),
        destination=StorageCategory.PLAYWRIGHT_BROWSERS,
        target_version=version,
    )


def _with_superseded_revisions(root: Path) -> None:
    _lay_down(root, BrowserBuild(name="chromium", revision="1200"))
    _lay_down(root, BrowserBuild(name="chromium-headless-shell", revision="1200"))
    _lay_down(root, BrowserBuild(name="ffmpeg", revision="1013"), executable=None)


def test_setup_installs_without_recording_or_removing_anything_before_verification(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _with_superseded_revisions(root)
    receipts = _store(tmp_path)
    events = _Events()

    result = asyncio.run(
        _item(tmp_path, installer=_Installer(root, [None]), receipts=receipts).provision(_entry(), events)
    )

    assert result.failure_category is None
    assert result.changed is True
    assert result.transferred_bytes == 300
    assert events.steps == [DependencySetupStep.DOWNLOAD]
    assert events.transfers == [(100, 300), (300, 300)]
    assert receipts.read("browser").receipt is None
    assert {"chromium-1200", "chromium_headless_shell-1200"} <= {p.name for p in root.iterdir()}


def test_after_verification_the_receipt_is_written_and_superseded_revisions_go(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _with_superseded_revisions(root)
    receipts = _store(tmp_path)
    item = _item(tmp_path, installer=_Installer(root, [None]), receipts=receipts)
    asyncio.run(item.provision(_entry(), _Events()))

    assert isinstance(item, DependencyItemFinisher)
    assert _check(item, DependencyCheckMode.FULL).outcome is DependencyProbeOutcome.PRESENT
    asyncio.run(item.after_verified(_entry()))

    assert sorted(p.name for p in root.iterdir()) == ["chromium-1248", "chromium_headless_shell-1248", "ffmpeg-1013"]
    written = receipts.read("browser").receipt
    assert written is not None
    assert written.version == _VERSION
    assert [file.path for file in written.files] == [
        "chromium-1248/INSTALLATION_COMPLETE",
        "chromium-1248/chrome-win64/chrome.exe",
        "chromium_headless_shell-1248/INSTALLATION_COMPLETE",
        "chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe",
    ]
    assert _check(_item(tmp_path, receipts=receipts)).outcome is DependencyProbeOutcome.PRESENT


def test_an_install_that_fails_verification_leaves_no_receipt(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _with_superseded_revisions(root)
    receipts = _store(tmp_path)
    failing = _Launcher(BrowserLaunchReading(failure_category=DependencyFailureCategory.UNEXPECTED))
    item = _item(tmp_path, installer=_Installer(root, [None]), launcher=failing, receipts=receipts)

    asyncio.run(item.provision(_entry(), _Events()))
    verified = _check(item, DependencyCheckMode.FULL)

    # The setup finishes an item only after this check passes, so nothing is recorded or removed.
    assert verified.outcome is DependencyProbeOutcome.FAILED
    assert receipts.read("browser").receipt is None
    assert "chromium-1200" in {p.name for p in root.iterdir()}


def test_a_reinstall_drops_the_receipt_of_the_files_it_replaces(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    store = _record(tmp_path)
    _lay_down(root, _FULL, executable=b"exf")

    asyncio.run(_item(tmp_path, installer=_Installer(root, [None]), receipts=store).provision(_entry(), _Events()))

    assert store.read("browser").receipt is None


def test_a_transient_failure_is_retried_after_the_partial_build_is_deleted(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    reset = BrowserInstallerExit(
        exit_code=1, failure_category=DependencyFailureCategory.HOST_UNREACHABLE, transient=True
    )
    installer = _Installer(root, [reset, None])
    events = _Events()

    result = asyncio.run(_item(tmp_path, installer=installer).provision(_entry(), events))

    assert result.failure_category is None
    assert result.facts["attempts"] == 2
    assert events.retries == [(2, DEPENDENCY_RETRY_POLICY.delay_s(1, jitter=0.5))]
    # The partial headless build the first attempt left was gone before the second began.
    assert installer.present_at_start == [(), ()]


def test_a_failure_that_will_not_pass_is_not_retried(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    full_disk = BrowserInstallerExit(exit_code=1, failure_category=DependencyFailureCategory.DISK_FULL)
    events = _Events()

    result = asyncio.run(_item(tmp_path, installer=_Installer(root, [full_disk])).provision(_entry(), events))

    assert result.failure_category is DependencyFailureCategory.DISK_FULL
    assert result.changed is True
    assert events.retries == []


def test_retries_stop_at_the_attempt_budget(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    reset = BrowserInstallerExit(
        exit_code=1, failure_category=DependencyFailureCategory.HOST_UNREACHABLE, transient=True
    )
    installer = _Installer(root, [reset] * DEPENDENCY_RETRY_POLICY.max_attempts)
    events = _Events()

    result = asyncio.run(_item(tmp_path, installer=installer).provision(_entry(), events))

    assert result.failure_category is DependencyFailureCategory.HOST_UNREACHABLE
    assert len(installer.requests) == DEPENDENCY_RETRY_POLICY.max_attempts
    assert [attempt for attempt, _delay in events.retries] == list(range(2, DEPENDENCY_RETRY_POLICY.max_attempts + 1))
    assert all(delay <= 60 for _attempt, delay in events.retries)


def test_cancel_during_the_download_stops_the_install(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    events = _Events(cancel_after_transfer=True)

    result = asyncio.run(
        _item(tmp_path, installer=_Installer(root, [None], cancel_wait_s=5.0)).provision(_entry(), events)
    )

    assert result.failure_category is DependencyFailureCategory.CANCELLED
    assert DependencySetupStep.CLEANUP not in events.steps


def test_a_plan_for_other_builds_is_refused_before_anything_runs(tmp_path: Path) -> None:
    installer = _Installer(tmp_path / "cache", [None])

    result = asyncio.run(_item(tmp_path, installer=installer).provision(_entry(version="150.0.0.1"), _Events()))

    assert result.failure_category is DependencyFailureCategory.UNEXPECTED
    assert result.changed is False
    assert installer.requests == []


def test_a_damaged_build_is_reinstalled(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    _lay_down(root, _FULL)
    _lay_down(root, _SHELL)
    store = _record(tmp_path)
    _lay_down(root, _FULL, executable=b"exf")
    installer = _Installer(root, [None])

    result = asyncio.run(_item(tmp_path, installer=installer, receipts=store).provision(_entry(), _Events()))

    assert result.failure_category is None
    assert installer.present_at_start == [()]


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    (
        ("win32", "AMD64", "win-x64"),
        ("linux", "aarch64", "linux-arm64"),
        ("darwin", "arm64", "mac-arm64"),
        ("linux", "riscv64", None),
        ("freebsd14", "amd64", None),
    ),
)
def test_host_platform_keys(system: str, machine: str, expected: str | None) -> None:
    assert browser_host_platform(system=system, machine=machine) == expected
