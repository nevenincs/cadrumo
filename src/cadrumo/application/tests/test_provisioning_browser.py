"""Browser location: the probe that locates the engine-recorded browser, and the managed browser root.

The probe runs against a controlled driver package and the record the engine writes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...core.config import Settings
from ...core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ...tests.component_record_support import write_engine_browser_record
from ..operator_actions.catalogue import lookup_action
from ..provisioning import DependencyStatus
from ..provisioning_browser import (
    BROWSER_PROVISION_ACTION_ID,
    playwright_browsers_root,
    probe_playwright_browser,
    required_browser_builds,
)
from ..provisioning_contracts import ProvisioningPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DRIVER = "1.64.0-beta-1791568591000"


def _manifest(tmp_path: Path, *, overrides: bool = False) -> Path:
    """A driver package as the bundled one lays it out: its build list and its version."""
    path = tmp_path / "browsers.json"
    shell: dict[str, object] = {"name": "chromium-headless-shell", "revision": "1243"}
    if overrides:
        shell["revisionOverrides"] = {"mac14": "1200"}
    document = {
        "browsers": [
            {"name": "chromium", "revision": "1243"},
            shell,
            {"name": "firefox", "revision": "1543"},
        ]
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    (tmp_path / "package.json").write_text(json.dumps({"version": _DRIVER}), encoding="utf-8")
    return path


def _probe(tmp_path: Path) -> DependencyStatus:
    return probe_playwright_browser(
        tmp_path / "cache", manifest_path=_manifest(tmp_path), records_root=tmp_path / "receipts"
    )


def _no_folder_published(status: DependencyStatus, tmp_path: Path) -> None:
    # The verdict is published with every refusal, so no fact names a folder or a path.
    assert not [value for value in status.facts.values() if str(tmp_path) in str(value)]


def test_installed_playwright_manifest_pins_both_chromium_builds() -> None:
    builds = required_browser_builds()

    assert builds is not None
    assert [build.name for build in builds] == ["chromium", "chromium-headless-shell"]
    assert all(build.revision.isdigit() for build in builds)
    assert builds[1].directory_name == f"chromium_headless_shell-{builds[1].revision}"


def test_a_browser_without_an_engine_record_is_refused_with_the_provisioning_action(tmp_path: Path) -> None:
    # Builds an installer left, markers and all, are not ones the engine checked and recorded.
    for directory in ("chromium-1243", "chromium_headless_shell-1243"):
        (tmp_path / "cache" / directory).mkdir(parents=True)
        (tmp_path / "cache" / directory / "INSTALLATION_COMPLETE").write_bytes(b"")

    status = _probe(tmp_path)

    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.facts["chromium_installed"] is False
    assert status.facts["browser_record"] == "no_record"
    assert status.facts["required_builds"] == "chromium-1243,chromium_headless_shell-1243"
    _no_folder_published(status, tmp_path)
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict.action is not None
    assert verdict.action.action_id == BROWSER_PROVISION_ACTION_ID
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert lookup_action(BROWSER_PROVISION_ACTION_ID).target_command_key == "config.provision.browser"


def test_the_engine_recorded_browser_is_located_where_playwright_looks(tmp_path: Path) -> None:
    write_engine_browser_record(
        records_root=tmp_path / "receipts", browsers_root=tmp_path / "cache", driver_version=_DRIVER
    )

    status = _probe(tmp_path)

    assert status.available is True
    assert status.precondition_verdict is None
    assert status.facts["browser_record"] == "located"
    assert status.facts["browser_version"] == "156.0.8078.4"
    assert "missing_builds" not in status.facts
    _no_folder_published(status, tmp_path)


@pytest.mark.parametrize(
    ("placement", "outcome"),
    (
        # A record of an earlier driver describes builds this driver does not launch.
        ("other driver", "other_identity"),
        # A record of another folder describes builds Playwright is not given.
        ("other folder", "other_folder"),
        ("executable gone", "path_missing"),
        ("unreadable", "record_unreadable"),
    ),
)
def test_a_record_that_does_not_describe_what_playwright_launches_is_refused(
    tmp_path: Path, placement: str, outcome: str
) -> None:
    records = tmp_path / "receipts"
    paths = write_engine_browser_record(
        records_root=records,
        browsers_root=tmp_path / ("elsewhere" if placement == "other folder" else "cache"),
        driver_version="1.63.0" if placement == "other driver" else _DRIVER,
    )
    if placement == "executable gone":
        paths["chromium-headless-shell"].unlink()
    if placement == "unreadable":
        (records / "browser.json").write_text("{", encoding="utf-8")

    status = _probe(tmp_path)

    assert status.available is False
    assert status.facts["browser_record"] == outcome
    if placement == "executable gone":
        assert status.facts["missing_builds"] == "chromium-headless-shell"
    _no_folder_published(status, tmp_path)
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == BROWSER_PROVISION_ACTION_ID


@pytest.mark.parametrize("manifest", ("missing", "malformed", "overrides", "no driver version"))
def test_an_unreadable_driver_is_refused_without_a_recovery_action(tmp_path: Path, manifest: str) -> None:
    write_engine_browser_record(
        records_root=tmp_path / "receipts", browsers_root=tmp_path / "cache", driver_version=_DRIVER
    )
    path = _manifest(tmp_path, overrides=manifest == "overrides")
    if manifest == "missing":
        path = tmp_path / "absent.json"
    elif manifest == "malformed":
        path.write_text("{not json", encoding="utf-8")
    elif manifest == "no driver version":
        (tmp_path / "package.json").write_text("{not json", encoding="utf-8")

    status = probe_playwright_browser(tmp_path / "cache", manifest_path=path, records_root=tmp_path / "receipts")

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
