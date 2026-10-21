"""The browser item's checks composed with the real adapters, against the provisioned test cache.

The repository bootstrap pins ``CADRUMO_PLAYWRIGHT_BROWSERS_DIR`` to the
provisioned browser cache the other real-browser tests launch from. These
tests only read it: the full check launches the headless build once, headless,
and nothing is installed or removed there.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.dependency_contracts import (
    DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S,
    DependencyCheckMode,
    DependencyProbeOutcome,
)
from .....application.provisioning_browser import (
    BrowserLaunchFailureCause,
    PlaywrightBrowserItem,
    browser_executable,
    browser_host_platform,
)
from .....application.provisioning_browser import required_browser_builds as pinned_builds
from ..installer import remove_browser_builds, run_browser_install
from ..launch_check import launch_headless_browser

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _provisioned_root() -> Path:
    return Path(os.environ["CADRUMO_PLAYWRIGHT_BROWSERS_DIR"])


def _item(root: Path) -> PlaywrightBrowserItem:
    return PlaywrightBrowserItem(
        install=run_browser_install,
        launch=launch_headless_browser,
        remove_builds=remove_browser_builds,
        browsers_root=lambda: root,
    )


def test_the_full_check_launches_the_provisioned_headless_build_within_budget() -> None:
    started = time.monotonic()

    reading = asyncio.run(_item(_provisioned_root()).check(DependencyCheckMode.FULL))

    assert reading.outcome is DependencyProbeOutcome.PRESENT, reading.facts
    builds = pinned_builds()
    assert builds is not None
    assert reading.facts["launched_version"] == builds[1].browser_version
    assert time.monotonic() - started < DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S


def test_a_build_whose_executable_cannot_start_fails_the_full_check(tmp_path: Path) -> None:
    builds = pinned_builds()
    host = browser_host_platform()
    assert builds is not None
    assert host is not None
    root = tmp_path / "browsers"
    for build in builds:
        executable = browser_executable(root, build, host)
        assert executable is not None
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"not a program")
        (root / build.directory_name / "INSTALLATION_COMPLETE").write_bytes(b"")

    reading = asyncio.run(_item(root).check(DependencyCheckMode.FULL))

    assert reading.outcome is DependencyProbeOutcome.FAILED
    assert reading.failure_category in {
        DependencyFailureCategory.DAMAGED_DOWNLOAD,
        DependencyFailureCategory.UNEXPECTED,
    }
    assert reading.facts["launched"] is False
    assert reading.facts["launch_failure_cause"] in {cause.value for cause in BrowserLaunchFailureCause}


def test_the_quick_check_reads_the_provisioned_cache_without_launching(tmp_path: Path) -> None:
    copy = tmp_path / "browsers"
    copy.mkdir()
    builds = pinned_builds()
    assert builds is not None
    for build in builds:
        source = _provisioned_root() / build.directory_name
        (copy / build.directory_name).mkdir()
        shutil.copy2(source / "INSTALLATION_COMPLETE", copy / build.directory_name)

    # Markers copied without the executables: a marker alone is not presence.
    reading = asyncio.run(_item(copy).check(DependencyCheckMode.QUICK))

    assert reading.outcome is DependencyProbeOutcome.ABSENT
