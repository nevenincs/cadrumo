"""Regression coverage for ASSETS-01 installed-TUI process supervision."""

from __future__ import annotations

import secrets
import sys
from pathlib import Path
from typing import Literal

import pytest

from dev.acceptance.assets.installed_journey import (
    InstalledTuiProcessError,
    read_receipt_progress,
    required_installed_tui_stages,
    run_installed_tui_probe,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _run_fixture(
    *,
    tmp_path: Path,
    module: str,
    timeout_seconds: float,
    profile_bootstrap: Literal["register", "existing"] = "register",
) -> InstalledTuiProcessError:
    """Exercise the real owned-process wrapper with one controlled child module."""
    storage_root = tmp_path / "storage"
    if profile_bootstrap == "existing":
        storage_root.mkdir()
        (storage_root / "profile-exists").touch()
    with pytest.raises(InstalledTuiProcessError) as raised:
        run_installed_tui_probe(
            python_executable=Path(sys.executable),
            workspace_root=Path.cwd(),
            storage_root=storage_root,
            receipt_path=tmp_path / "child-receipt.json",
            profile_label="assets-supervisor-fixture",
            passphrase=f"assets-{secrets.token_urlsafe(24)}",
            profile_bootstrap=profile_bootstrap,
            timeout_seconds=timeout_seconds,
            child_module=module,
        )
    return raised.value


def test_supervisor_rejects_a_zero_exit_without_a_terminal_child_receipt(tmp_path: Path) -> None:
    error = _run_fixture(
        tmp_path=tmp_path,
        module="dev.acceptance.assets.tests.installed_tui_fixture_running",
        timeout_seconds=5.0,
    )

    assert error.receipt.status == "failed"
    assert error.receipt.return_code == 0
    assert error.receipt.child_status == "running"
    assert error.receipt.last_stage == "fixture_running"
    assert error.receipt.timed_out is False
    assert error.receipt.cleanup == "not_needed"


def test_supervisor_rejects_a_proven_child_that_omits_required_journey_stages(tmp_path: Path) -> None:
    error = _run_fixture(
        tmp_path=tmp_path,
        module="dev.acceptance.assets.tests.installed_tui_fixture_false_success",
        timeout_seconds=5.0,
    )

    assert error.receipt.status == "failed"
    assert error.receipt.return_code == 0
    assert error.receipt.child_status == "proven"
    assert error.receipt.required_stage_missing == "launcher_autopilot"
    assert error.receipt.failure_identity == "missing_required_stage:launcher_autopilot"


def test_supervisor_marks_timeout_cleanup_as_failure_evidence(tmp_path: Path) -> None:
    error = _run_fixture(
        tmp_path=tmp_path,
        module="dev.acceptance.assets.tests.installed_tui_fixture_sleep",
        # Long enough for interpreter start-up to write the stage on a loaded
        # host, far short of the fixture's 30-second sleep.
        timeout_seconds=5.0,
    )

    assert error.receipt.status == "failed"
    assert error.receipt.last_stage == "fixture_sleep"
    assert error.receipt.timed_out is True
    assert error.receipt.cleanup == "terminated"


def test_supervisor_allows_only_explicit_existing_profile_continuation(tmp_path: Path) -> None:
    error = _run_fixture(
        tmp_path=tmp_path,
        module="dev.acceptance.assets.tests.installed_tui_fixture_running",
        timeout_seconds=5.0,
        profile_bootstrap="existing",
    )

    assert error.receipt.return_code == 0
    assert error.receipt.last_stage == "fixture_running"


def test_full_asset_lifecycle_requires_public_correction_and_filing_stages() -> None:
    """A clean child exit cannot omit the newly supported public asset actions."""
    assert required_installed_tui_stages(
        journey="asset_method_lifecycle",
        profile_bootstrap="existing",
    ) == (
        "installed_origin",
        "existing_profile",
        "session_admitted",
        "launcher_autopilot",
        "home_ready",
        "ledger_ready",
        "asset_screen_ready",
        "asset_created",
        "asset_inspected",
        "asset_corrected",
        "asset_forecast",
        "asset_claim",
        "asset_claim_replay",
        "asset_filing_handoff",
        "launcher_exit",
    )


def test_an_unreadable_receipt_is_no_progress_rather_than_a_supervisor_crash(tmp_path: Path) -> None:
    """A receipt the child is rewriting can refuse a read; the poll must not crash."""
    unreadable = tmp_path / "receipt.json"
    unreadable.mkdir()

    assert read_receipt_progress(unreadable) == (None, None, ())
    assert read_receipt_progress(tmp_path / "absent.json") == (None, None, ())
