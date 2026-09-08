"""Detector controls for the monthly report's live shadowing projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.audit import report
from dev.quality.import_hygiene_scan import MultiSourcedSymbol

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _symbol(*, confidence: str = "high", facades: list[str] | None = None) -> MultiSourcedSymbol:
    return MultiSourcedSymbol(
        symbol="SharedName",
        facades=facades or ["cadrumo.first", "cadrumo.second"],
        private_sources=[],
        consumed_from_facade_by=[],
        consumed_from_private_by=[],
        confidence=confidence,
    )


def _replace_scan(monkeypatch, findings: list[MultiSourcedSymbol]) -> None:
    monkeypatch.setattr(report, "scan_directory", lambda *args, **kwargs: ())
    monkeypatch.setattr(report, "discover_facades", lambda: {})
    monkeypatch.setattr(report, "find_multi_sourced_symbols", lambda facades, sites: findings)


def test_current_high_confidence_multi_facade_symbol_is_red(monkeypatch) -> None:
    _replace_scan(monkeypatch, [_symbol()])

    finding = report.audit_shadowing()

    assert finding.status is report.Status.RED
    assert finding.details == ["SharedName (facades=['cadrumo.first', 'cadrumo.second'])"]


def test_non_structural_candidates_do_not_manufacture_debt_state(monkeypatch) -> None:
    _replace_scan(
        monkeypatch,
        [
            _symbol(confidence="name_collision"),
            _symbol(facades=["cadrumo.first"]),
        ],
    )

    finding = report.audit_shadowing()

    assert finding.status is report.Status.GREEN
    assert finding.details == []


def test_persisted_health_report_identifies_its_command(tmp_path: Path) -> None:
    health = report.HealthReport(
        dimensions=(report.DimensionReport(name="layering", status=report.Status.GREEN, headline="kept"),)
    )
    command = ("python", "-m", "dev.audit.report", "--full")

    run_dir = report.persist_report(tmp_path, health, command)

    assert run_dir.parent.parent.parent == tmp_path / ".logs"
    payload = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["command"] == list(command)
    assert payload["report"]["overall"] == "green"
    assert "command: python -m dev.audit.report --full" in (run_dir / "report.md").read_text(encoding="utf-8")
