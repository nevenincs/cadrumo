"""Configured Chromium working roots preserve isolation and bounded lifetime."""

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from playwright.async_api import Playwright

import psutil
import pytest

from ......core.config import Settings, load_settings, override_settings
from ......core.errors.hierarchy import CoreValidationError
from ......core.storage_taxonomy import StorageCategory
from ......core.storage_taxonomy_locations import storage_location, storage_path
from ..errors import BrowserError
from ..factory import create_browser_session
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_root_follows_storage_policy_independently_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "application-storage"
    expected = root / storage_location(StorageCategory.CHROMIUM_DATA).relative_path()
    assert storage_path(StorageCategory.CHROMIUM_DATA, settings=Settings(cadrumo_storage_root=root)) == expected
    # A root named relative to the cwd is refused, never anchored there.
    with pytest.raises(CoreValidationError, match="must be an absolute directory") as refused:
        Settings(cadrumo_storage_root=root.name)
    assert refused.value.context is not None
    assert refused.value.context["storage_root_refusal"] == "relative_override_installed"
    monkeypatch.chdir(tmp_path.parent)
    assert storage_path(StorageCategory.CHROMIUM_DATA, settings=Settings(cadrumo_storage_root=root)) == expected


def test_changing_storage_root_rederives_chromium_data(tmp_path):
    chromium_data = storage_location(StorageCategory.CHROMIUM_DATA).relative_path()
    with override_settings(cadrumo_storage_root=tmp_path / "first") as first:
        assert storage_path(StorageCategory.CHROMIUM_DATA, settings=first) == tmp_path / "first" / chromium_data
        with override_settings(cadrumo_storage_root=tmp_path / "second") as second:
            assert storage_path(StorageCategory.CHROMIUM_DATA, settings=second) == tmp_path / "second" / chromium_data
        assert storage_path(StorageCategory.CHROMIUM_DATA) == tmp_path / "first" / chromium_data


@pytest.mark.asyncio
async def test_working_profiles_are_isolated_and_removed():
    # The installed browser build lives beneath the effective storage root, so a real launch runs there.
    settings = load_settings()
    root = storage_path(StorageCategory.CHROMIUM_DATA, settings=settings).resolve()
    browsers_root = storage_path(StorageCategory.PLAYWRIGHT_BROWSERS, settings=settings).resolve()
    existing = set(root.iterdir()) if root.exists() else set()
    first = await create_browser_session(settings, Profile(name="first"))
    second = await create_browser_session(settings, Profile(name="second"))
    try:
        first_context = await first.create_context()
        second_context = await second.create_context()
        directories = set(root.iterdir()) - existing
        assert len(directories) == 2
        for context in (first_context, second_context):
            assert context.browser is not None
            cdp = await context.browser.new_browser_cdp_session()
            processes = await cdp.send("SystemInfo.getProcessInfo")
            await cdp.detach()
            browser_pid = next(process["id"] for process in processes["processInfo"] if process["type"] == "browser")
            assert Path(psutil.Process(browser_pid).exe()).resolve().is_relative_to(browsers_root)
            profile_arg = next(
                arg for arg in psutil.Process(browser_pid).cmdline() if arg.startswith("--user-data-dir=")
            )
            profile_path = Path(profile_arg.split("=", 1)[1])
            assert profile_path.parent in directories
            assert profile_path.is_dir()
        await first_context.add_cookies([{"name": "synthetic", "value": "first-only", "url": "https://example.test"}])
        assert await first_context.cookies()
        assert await second_context.cookies() == []
        await first.close()
        assert len(set(root.iterdir()) - existing) == 1
        await second.close()
        assert set(root.iterdir()) == existing
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_chromium_child_data_paths_are_scoped_to_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(cadrumo_storage_root=tmp_path / "storage")
    managed_root = storage_path(StorageCategory.CHROMIUM_DATA, settings=settings)
    temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=settings)
    hostile_root = tmp_path / "hostile"
    path_variables = (
        "HOME",
        "USERPROFILE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "APPDATA",
        "LOCALAPPDATA",
    )
    for variable in (*path_variables, "TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(variable, str(hostile_root / variable.lower()))
    monkeypatch.setenv("PATH", "controlled-test-path")

    captured: dict[str, object] = {}

    class FakeBrowser:
        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch_persistent_context(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(browser=FakeBrowser())

    session = BrowserSession(
        playwright=cast("Playwright", SimpleNamespace(chromium=FakeChromium())),
        settings=settings,
        profile=Profile(name="isolated-environment"),
    )
    try:
        await session._launch_chromium(None)
        environment = captured["env"]
        assert isinstance(environment, dict)
        downloads_path = captured["downloads_path"]
        assert isinstance(downloads_path, Path)
        working_path = downloads_path.parent
        assert working_path.is_dir()
        for variable in path_variables:
            value = environment[variable]
            assert isinstance(value, str)
            path = Path(value)
            assert path.is_absolute()
            assert path.is_relative_to(working_path)
            assert path.is_dir()
            assert path != hostile_root / variable.lower()
        assert environment["PATH"] == "controlled-test-path"
        assert {environment[name] for name in ("TEMP", "TMP", "TMPDIR")} == {str(temporary_root.resolve())}
        assert temporary_root.is_dir()
        assert not hostile_root.exists()
    finally:
        await session.close()
    assert list(managed_root.iterdir()) == []


@pytest.mark.asyncio
async def test_unusable_root_refuses_browser_launch(tmp_path: Path):
    storage_root = tmp_path / "storage"
    root = storage_root / storage_location(StorageCategory.CHROMIUM_DATA).relative_path()
    root.parent.mkdir(parents=True)
    root.write_text("synthetic", encoding="utf-8")
    session = await create_browser_session(Settings(cadrumo_storage_root=storage_root), Profile(name="invalid-root"))
    try:
        with pytest.raises(BrowserError) as error:
            await session.create_context()
        assert error.value.failure_mode == "browser_launch_failed"
        assert root.read_text(encoding="utf-8") == "synthetic"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_a_disposed_runtime_does_not_poison_the_next_driver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A later independent driver must not inherit an earlier storage root."""
    import os
    from tempfile import TemporaryDirectory

    from playwright.async_api import async_playwright

    ambient = tmp_path / "ambient"
    ambient.mkdir()
    for variable in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(variable, str(ambient))
    browser_cache = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
    with TemporaryDirectory(prefix="owned-runtime-", dir=tmp_path) as prior_root:
        session = await create_browser_session(Settings(cadrumo_storage_root=Path(prior_root)), Profile(name="prior"))
        await session.close()
    assert os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == browser_cache
    independent = await async_playwright().start()
    try:
        browser = await independent.chromium.launch(headless=True)
        await browser.close()
    finally:
        await independent.stop()
    assert all(os.environ.get(variable) == str(ambient) for variable in ("TEMP", "TMP", "TMPDIR"))


@pytest.mark.asyncio
async def test_concurrent_drivers_get_their_own_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import asyncio
    import os

    from ...tests.process_support import playwright_driver_pid

    variables = ("PLAYWRIGHT_BROWSERS_PATH", "TEMP", "TMP", "TMPDIR")
    monkeypatch.setenv("TEMP", "ambient-temp")
    monkeypatch.delenv("TMP", raising=False)
    before = {variable: os.environ.get(variable) for variable in variables}
    settings = [Settings(cadrumo_storage_root=tmp_path / name) for name in ("first", "second")]
    first, second = await asyncio.gather(
        *(
            create_browser_session(item, Profile(name=name))
            for item, name in zip(settings, ("first", "second"), strict=True)
        )
    )
    try:
        for session, item in zip((first, second), settings, strict=True):
            environment = cast("Any", psutil.Process(playwright_driver_pid(session.session.playwright))).environ()
            assert Path(environment["PLAYWRIGHT_BROWSERS_PATH"]) == storage_path(
                StorageCategory.PLAYWRIGHT_BROWSERS, settings=item
            )
            for variable in ("TEMP", "TMP", "TMPDIR"):
                assert Path(environment[variable]) == storage_path(StorageCategory.TEMPORARY_FILES, settings=item)
        assert {variable: os.environ.get(variable) for variable in variables} == before
    finally:
        await asyncio.gather(first.close(), second.close())


@pytest.mark.asyncio
async def test_driver_start_failure_preserves_ambient_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import os

    from playwright._impl import _transport

    variables = ("PLAYWRIGHT_BROWSERS_PATH", "TEMP", "TMP", "TMPDIR")
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    before = {variable: os.environ.get(variable) for variable in variables}

    def missing_driver():
        raise OSError("synthetic driver failure")

    monkeypatch.setattr(_transport, "compute_driver_executable", missing_driver)
    with pytest.raises(BrowserError):
        await create_browser_session(Settings(cadrumo_storage_root=tmp_path / "failed"), Profile(name="failed"))
    assert {variable: os.environ.get(variable) for variable in variables} == before
