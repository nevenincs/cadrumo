"""Browser-build provisioning: the revision-exact probe and the managed browser root.

The probe runs against controlled manifest and cache directories on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...core.config import Settings
from ...core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ..operator_actions.catalogue import lookup_action
from ..provisioning_browser import (
    BROWSER_PROVISION_ACTION_ID,
    playwright_browsers_root,
    probe_playwright_browser,
    required_browser_builds,
)
from ..provisioning_contracts import ProvisioningPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _manifest(tmp_path: Path, *, revision: str = "1243", overrides: bool = False) -> Path:
    path = tmp_path / "browsers.json"
    shell: dict[str, object] = {"name": "chromium-headless-shell", "revision": revision}
    if overrides:
        shell["revisionOverrides"] = {"mac14": "1200"}
    document = {
        "browsers": [
            {"name": "chromium", "revision": revision},
            shell,
            {"name": "firefox", "revision": "1543"},
        ]
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _install_build(cache: Path, directory: str, *, complete: bool = True) -> None:
    build = cache / directory
    build.mkdir(parents=True)
    if complete:
        (build / "INSTALLATION_COMPLETE").write_bytes(b"")


def test_installed_playwright_manifest_pins_both_chromium_builds() -> None:
    builds = required_browser_builds()

    assert builds is not None
    assert [build.name for build in builds] == ["chromium", "chromium-headless-shell"]
    assert all(build.revision.isdigit() for build in builds)
    assert builds[1].directory_name == f"chromium_headless_shell-{builds[1].revision}"


def test_empty_cache_is_refused_with_the_provisioning_action(tmp_path: Path) -> None:
    status = probe_playwright_browser(tmp_path / "cache", manifest_path=_manifest(tmp_path))

    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.facts["chromium_installed"] is False
    assert status.facts["missing_builds"] == "chromium-1243,chromium_headless_shell-1243"
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict.action is not None
    assert verdict.action.action_id == BROWSER_PROVISION_ACTION_ID
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert lookup_action(BROWSER_PROVISION_ACTION_ID).target_command_key == "config.provision.browser"


def test_complete_pinned_builds_are_available(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_build(cache, "chromium-1243")
    _install_build(cache, "chromium_headless_shell-1243")

    status = probe_playwright_browser(cache, manifest_path=_manifest(tmp_path))

    assert status.available is True
    assert status.precondition_verdict is None
    assert "missing_builds" not in status.facts


@pytest.mark.parametrize(
    ("directories", "missing"),
    (
        # Builds of an earlier Playwright are not the ones this version launches.
        (("chromium-1228", "chromium_headless_shell-1228"), "chromium-1243,chromium_headless_shell-1243"),
        (("chromium-1243",), "chromium_headless_shell-1243"),
    ),
)
def test_stale_or_partial_builds_are_not_installed(tmp_path: Path, directories: tuple[str, ...], missing: str) -> None:
    cache = tmp_path / "cache"
    for directory in directories:
        _install_build(cache, directory)

    status = probe_playwright_browser(cache, manifest_path=_manifest(tmp_path))

    assert status.available is False
    assert status.facts["missing_builds"] == missing


def test_build_without_completion_marker_is_not_installed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_build(cache, "chromium-1243")
    _install_build(cache, "chromium_headless_shell-1243", complete=False)

    status = probe_playwright_browser(cache, manifest_path=_manifest(tmp_path))

    assert status.available is False
    assert status.facts["missing_builds"] == "chromium_headless_shell-1243"


@pytest.mark.parametrize("manifest", ("missing", "malformed", "overrides"))
def test_unreadable_manifest_is_refused_without_a_recovery_action(tmp_path: Path, manifest: str) -> None:
    if manifest == "missing":
        path = tmp_path / "absent.json"
    elif manifest == "malformed":
        path = tmp_path / "browsers.json"
        path.write_text("{not json", encoding="utf-8")
    else:
        path = _manifest(tmp_path, overrides=True)

    status = probe_playwright_browser(tmp_path / "cache", manifest_path=path)

    assert status.available is False
    assert status.facts["browser_manifest_readable"] is False
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_browsers_root_ignores_uncontrolled_vendor_override(tmp_path: Path) -> None:
    storage_root = tmp_path / "configured-storage"
    vendor_root = tmp_path / "vendor-playwright-cache"

    assert (
        playwright_browsers_root(
            env={"CADRUMO_STORAGE_ROOT": str(storage_root), "PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}
        )
        == (storage_root / "components/playwright").resolve()
    )
    assert playwright_browsers_root(tmp_path, env={"PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}) == tmp_path


def test_browsers_root_defaults_under_the_configured_storage_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", raising=False)
    settings = Settings(cadrumo_local_storage_root=tmp_path)

    assert playwright_browsers_root(settings=settings) == (tmp_path / "components" / "playwright").resolve()


def test_cadrumo_browser_root_override_wins_over_vendor_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(storage_root))
    monkeypatch.delenv("CADRUMO_LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "browser-cache")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "vendor-cache"))

    assert playwright_browsers_root() == (storage_root / "browser-cache").resolve()
