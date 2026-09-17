"""Browser-build provisioning: revision-exact probe and idempotent install.

The probe runs against controlled manifest and cache directories on disk. The
installer runner is the one injected seam: it stands in for the vendor download
by writing the cache layout the real installer produces, so the application's
own re-probe decides success.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

from ...core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ..operator_actions.catalogue import lookup_action
from ..provisioning import DependencyStatus
from ..provisioning_browser import (
    BROWSER_PROVISION_ACTION_ID,
    PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S,
    install_playwright_browser,
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


def test_browsers_root_honours_the_vendor_override(tmp_path: Path) -> None:
    vendor_root = tmp_path / "vendor-playwright-cache"

    assert playwright_browsers_root(env={"PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}) == vendor_root
    assert playwright_browsers_root(env={}) != vendor_root
    assert playwright_browsers_root(tmp_path, env={"PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}) == tmp_path


class _Installer:
    """Records runs and lays down the cache the vendor installer would write."""

    def __init__(
        self,
        cache: Path,
        *,
        exit_code: int = 0,
        writes: tuple[str, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.cache = cache
        self.exit_code = exit_code
        self.writes = writes
        self.error = error
        self.timeouts: list[float] = []

    def __call__(self, timeout_s: float) -> int:
        self.timeouts.append(timeout_s)
        if self.error is not None:
            raise self.error
        for directory in self.writes:
            _install_build(self.cache, directory)
        return self.exit_code


def _probe(tmp_path: Path) -> tuple[Path, Callable[[], DependencyStatus]]:
    cache = tmp_path / "cache"
    return cache, partial(probe_playwright_browser, cache, manifest_path=_manifest(tmp_path))


_BOTH = ("chromium-1243", "chromium_headless_shell-1243")


def test_install_downloads_missing_builds_and_confirms_them(tmp_path: Path) -> None:
    cache, probe = _probe(tmp_path)
    run = _Installer(cache, writes=_BOTH)

    outcome = install_playwright_browser(run=run, probe=probe)

    assert run.timeouts == [PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S]
    assert outcome.installed is True
    assert outcome.already_installed is False
    assert outcome.installer_exit_code == 0
    assert outcome.precondition_verdict is None
    assert probe_playwright_browser(cache, manifest_path=tmp_path / "browsers.json").available is True


def test_install_is_idempotent_when_builds_are_present(tmp_path: Path) -> None:
    cache, probe = _probe(tmp_path)
    for directory in _BOTH:
        _install_build(cache, directory)
    run = _Installer(cache)

    outcome = install_playwright_browser(run=run, probe=probe)

    assert run.timeouts == []
    assert outcome.installed is True
    assert outcome.already_installed is True


@pytest.mark.parametrize(
    ("installer", "expected_facts"),
    (
        (partial(_Installer, exit_code=1), {"installer_ran": True, "installer_exit_code": 1}),
        # A zero exit that leaves a build missing is still a failed install.
        (partial(_Installer, writes=("chromium-1243",)), {"installer_ran": True, "installer_exit_code": 0}),
        (
            partial(_Installer, error=TimeoutError("slow")),
            {"installer_ran": False, "install_error_type": "TimeoutError"},
        ),
        (
            partial(_Installer, error=OSError("no network")),
            {"installer_ran": False, "install_error_type": "OSError"},
        ),
    ),
)
def test_failed_install_is_a_typed_refusal(
    tmp_path: Path, installer: Callable[[Path], _Installer], expected_facts: dict[str, object]
) -> None:
    cache, probe = _probe(tmp_path)

    outcome = install_playwright_browser(run=installer(cache), probe=probe)

    assert outcome.installed is False
    assert expected_facts.items() <= dict(outcome.facts).items()
    verdict = outcome.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALL_SUCCEEDED.value


def test_install_does_not_run_when_the_manifest_is_unreadable(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    run = _Installer(cache)

    outcome = install_playwright_browser(
        run=run, probe=partial(probe_playwright_browser, cache, manifest_path=tmp_path / "absent.json")
    )

    assert run.timeouts == []
    assert outcome.installed is False
    assert outcome.precondition_verdict is not None
    assert (
        outcome.precondition_verdict.failed_condition_id
        == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE.value
    )
