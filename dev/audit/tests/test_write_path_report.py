"""The write-path report exits distinctly for findings, an unavailable scan and a clean tree.

The report is a finding-bearing diagnostic whose callers read its exit status,
so a crashed or empty scan must never share a status with either a clean tree
or a tree that holds findings.
"""

from __future__ import annotations

import json

import pytest

from dev.audit import write_path_coverage as report
from dev.quality.write_path_coverage import WritePathFinding, WritePathResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FINDING = WritePathFinding(
    path="src/pkg/ledger.py",
    line=7,
    module="pkg.ledger",
    service="LedgerService",
    read_verbs=("latest",),
    write_verbs=("save",),
    read_callers=("pkg.cli",),
    write_labels=(),
)


def _run(result: WritePathResult, monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(report._analysis, "run_write_path_scan", lambda: result)
    return report.main(list(argv))


def test_a_finding_exits_three_and_names_the_stranded_surface(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = WritePathResult.from_findings(surfaces_examined=("pkg.ledger.LedgerService",), findings=(_FINDING,))

    assert _run(result, monkeypatch) == 3

    assert "LedgerService" in capsys.readouterr().out


def test_an_unavailable_scan_exits_one_and_never_reads_as_clean_or_as_a_finding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = WritePathResult.error("no persistence surface could be classified")

    assert _run(result, monkeypatch) == 1

    assert "unavailable" in capsys.readouterr().out


def test_a_clean_scan_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    result = WritePathResult.clean(surfaces_examined=("pkg.ledger.LedgerService",))

    assert _run(result, monkeypatch) == 0

    assert "still has a production writer" in capsys.readouterr().out


def test_the_three_outcomes_never_share_an_exit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    results = (
        WritePathResult.clean(surfaces_examined=("pkg.ledger.LedgerService",)),
        WritePathResult.from_findings(surfaces_examined=("pkg.ledger.LedgerService",), findings=(_FINDING,)),
        WritePathResult.error("scan could not run"),
    )

    assert len({_run(result, monkeypatch) for result in results}) == len(results)


def test_json_output_carries_the_outcome_that_decides_the_exit_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = WritePathResult.error("scan could not run")

    status = _run(result, monkeypatch, "--json")

    payload = json.loads(capsys.readouterr().out)
    assert (status, payload["outcome"], payload["reason"]) == (1, "error", "scan could not run")
