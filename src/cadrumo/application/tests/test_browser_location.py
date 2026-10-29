"""Browser location: the probe that locates the installed browser builds, and the managed browser root.

The probe runs against a controlled driver package and the completion markers Playwright writes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...core.config import Settings
from ...core.operator_action_enums import NoRecoveryOutcome
from ..browser_location import (
    playwright_browsers_root,
    probe_playwright_browser,
    required_browser_builds,
)
from ..probe_outcomes import ProbePreconditionCondition
from ..workstation_probes import DependencyStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUILD_DIRECTORIES = ("chromium-1243", "chromium_headless_shell-1243")


def _manifest(tmp_path: Path, *, overrides: bool = False) -> Path:
    """A driver package as the bundled one lays it out: its build list."""
    path = tmp_path / "browsers.json"
    shell: dict[str, object] = {"name": "chromium-headless-shell", "revision": "1243"}
    if overrides:
        shell["revisionOverrides"] = {"mac14": "1200"}
    document = {
        "browsers": [
            {"name": "chromium", "revision": "1243", "browserVersion": "156.0.8078.4"},
            shell,
            {"name": "firefox", "revision": "1543"},
        ]
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _install(cache: Path, *directories: str) -> None:
    for directory in directories:
        (cache / directory).mkdir(parents=True)
        (cache / directory / "INSTALLATION_COMPLETE").write_bytes(b"")


def _probe(tmp_path: Path) -> DependencyStatus:
    return probe_playwright_browser(tmp_path / "cache", manifest_path=_manifest(tmp_path))


def _no_folder_published(status: DependencyStatus, tmp_path: Path) -> None:
    # The verdict is published with every refusal, so no fact names a folder or a path.
    assert not [value for value in status.facts.values() if str(tmp_path) in str(value)]


def test_installed_playwright_manifest_pins_both_chromium_builds() -> None:
    builds = required_browser_builds()

    assert builds is not None
    assert [build.name for build in builds] == ["chromium", "chromium-headless-shell"]
    assert all(build.revision.isdigit() for build in builds)
    assert builds[1].directory_name == f"chromium_headless_shell-{builds[1].revision}"


def test_a_browser_that_is_not_there_is_refused_without_a_recovery_action(tmp_path: Path) -> None:
    status = _probe(tmp_path)

    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.facts["chromium_installed"] is False
    assert status.facts["required_builds"] == "chromium-1243,chromium_headless_shell-1243"
    _no_folder_published(status, tmp_path)
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProbePreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_build_without_its_completion_marker_is_not_present(tmp_path: Path) -> None:
    _install(tmp_path / "cache", *_BUILD_DIRECTORIES)
    (tmp_path / "cache" / "chromium_headless_shell-1243" / "INSTALLATION_COMPLETE").unlink()

    status = _probe(tmp_path)

    assert status.available is False
    assert status.facts["missing_builds"] == "chromium_headless_shell-1243"
    _no_folder_published(status, tmp_path)


def test_builds_of_another_revision_are_not_the_ones_the_driver_launches(tmp_path: Path) -> None:
    _install(tmp_path / "cache", "chromium-1200", "chromium_headless_shell-1200")

    status = _probe(tmp_path)

    assert status.available is False
    assert status.facts["missing_builds"] == "chromium-1243,chromium_headless_shell-1243"


def test_both_builds_with_their_markers_are_located_where_playwright_looks(tmp_path: Path) -> None:
    _install(tmp_path / "cache", *_BUILD_DIRECTORIES)

    status = _probe(tmp_path)

    assert status.available is True
    assert status.precondition_verdict is None
    assert status.facts["chromium_installed"] is True
    assert status.facts["browser_version"] == "156.0.8078.4"
    assert "missing_builds" not in status.facts
    _no_folder_published(status, tmp_path)


@pytest.mark.parametrize("manifest", ("missing", "malformed", "overrides"))
def test_an_unreadable_driver_is_refused_without_a_recovery_action(tmp_path: Path, manifest: str) -> None:
    _install(tmp_path / "cache", *_BUILD_DIRECTORIES)
    path = _manifest(tmp_path, overrides=manifest == "overrides")
    if manifest == "missing":
        path = tmp_path / "absent.json"
    elif manifest == "malformed":
        path.write_text("{not json", encoding="utf-8")

    status = probe_playwright_browser(tmp_path / "cache", manifest_path=path)

    assert status.available is False
    assert status.facts["browser_manifest_readable"] is False
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProbePreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE.value
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
