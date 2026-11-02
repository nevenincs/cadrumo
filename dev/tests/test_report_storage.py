"""CI reports obey shared storage and an explicit category refinement."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.ci_reports import _ci_report_path
from dev.report_storage import report_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_relative_report_destinations_follow_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "storage"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(root))
    monkeypatch.setenv("CADRUMO_CI_REPORTS_DIR", "reports")
    path = _ci_report_path(["tests"])
    assert path is not None
    assert Path(path).parent == root / "reports"
    assert Path(path).parent.is_dir()


def test_a_caller_destination_overrides_the_report_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_CI_REPORTS_DIR", str(tmp_path / "configured"))
    assert report_directory() == tmp_path / "configured"
    assert report_directory(tmp_path / "caller") == tmp_path / "caller"


def test_blank_report_controls_do_not_enable_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_CI_REPORTS_DIR", "")
    assert _ci_report_path(["tests"]) is None
