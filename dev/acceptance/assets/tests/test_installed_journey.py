"""Regression coverage for ASSETS-01 installed-TUI process supervision."""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

import pytest
from dev.acceptance.assets.installed_journey import InstalledTuiProcessError, run_installed_tui_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _run_fixture(*, tmp_path: Path, module: str, timeout_seconds: float) -> InstalledTuiProcessError:
    """Exercise the real owned-process wrapper with one controlled child module."""
    with pytest.raises(InstalledTuiProcessError) as raised:
        run_installed_tui_probe(
            python_executable=Path(sys.executable),
            workspace_root=Path.cwd(),
            storage_root=tmp_path / "storage",
            receipt_path=tmp_path / "child-receipt.json",
            profile_label="assets-supervisor-fixture",
            passphrase=f"assets-{secrets.token_urlsafe(24)}",
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


def test_supervisor_marks_timeout_cleanup_as_failure_evidence(tmp_path: Path) -> None:
    error = _run_fixture(
        tmp_path=tmp_path,
        module="dev.acceptance.assets.tests.installed_tui_fixture_sleep",
        timeout_seconds=0.2,
    )

    assert error.receipt.status == "failed"
    assert error.receipt.last_stage == "fixture_sleep"
    assert error.receipt.timed_out is True
    assert error.receipt.cleanup == "terminated"
