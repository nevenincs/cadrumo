"""Configured Chromium working roots preserve isolation and bounded lifetime."""

from pathlib import Path

import psutil
import pytest

from ......core.config import Settings, override_settings
from ......core.paths import resolve_project_path
from ..errors import BrowserError
from ..factory import create_browser_session
from ..profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("override", [None, "", "custom-browser-data", "absolute"])
def test_root_follows_storage_policy_independently_of_cwd(tmp_path, monkeypatch, override):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CADRUMO_CHROMIUM_DATA_ROOT", raising=False)
    if override == "absolute":
        override = str(tmp_path / "custom-browser-data")
    if override is not None:
        monkeypatch.setenv("CADRUMO_CHROMIUM_DATA_ROOT", override)
    root = tmp_path / "application-storage"
    expected = resolve_project_path(override) if override else root / "chromium-data"
    settings = Settings(cadrumo_local_storage_root=root)
    assert settings.cadrumo_chromium_data_root == expected
    monkeypatch.chdir(tmp_path.parent)
    assert Settings(cadrumo_local_storage_root=root).cadrumo_chromium_data_root == expected


def test_changing_storage_root_rederives_chromium_default(tmp_path):
    with override_settings(cadrumo_local_storage_root=tmp_path / "first") as first:
        assert first.cadrumo_chromium_data_root == tmp_path / "first" / "chromium-data"
        with override_settings(cadrumo_local_storage_root=tmp_path / "second") as second:
            assert second.cadrumo_chromium_data_root == tmp_path / "second" / "chromium-data"
        with (
            override_settings(cadrumo_chromium_data_root=tmp_path / "explicit"),
            override_settings(cadrumo_local_storage_root=tmp_path / "third") as third,
        ):
            assert third.cadrumo_chromium_data_root == tmp_path / "explicit"


@pytest.mark.asyncio
async def test_working_profiles_are_isolated_and_removed(tmp_path: Path):
    root = tmp_path / "chromium"
    settings = Settings(cadrumo_chromium_data_root=root)
    first = await create_browser_session(settings, Profile(name="first"))
    second = await create_browser_session(settings, Profile(name="second"))
    try:
        first_context = await first.create_context()
        second_context = await second.create_context()
        directories = list(root.iterdir())
        assert len(directories) == 2
        for context in (first_context, second_context):
            assert context.browser is not None
            cdp = await context.browser.new_browser_cdp_session()
            processes = await cdp.send("SystemInfo.getProcessInfo")
            await cdp.detach()
            browser_pid = next(process["id"] for process in processes["processInfo"] if process["type"] == "browser")
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
        assert len(list(root.iterdir())) == 1
        await second.close()
        assert list(root.iterdir()) == []
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_unusable_root_refuses_browser_launch(tmp_path: Path):
    root = tmp_path / "file"
    root.write_text("synthetic", encoding="utf-8")
    session = await create_browser_session(Settings(cadrumo_chromium_data_root=root), Profile(name="invalid-root"))
    try:
        with pytest.raises(BrowserError) as error:
            await session.create_context()
        assert error.value.failure_mode == "browser_launch_failed"
        assert root.read_text(encoding="utf-8") == "synthetic"
    finally:
        await session.close()
