"""Detector controls for the monthly report's live shadowing projection."""

from __future__ import annotations

import pytest

from dev.audit import report
from dev.quality.import_hygiene_scan import MultiSourcedSymbol

pytestmark = pytest.mark.unit


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
