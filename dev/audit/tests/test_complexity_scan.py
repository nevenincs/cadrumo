"""Detector-teeth tests for the baseline-free complexity projection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import complexity, report
from ..complexity import CcHit, CogHit, ComplexityScan, MiHit, collect_cog
from ..report import Status

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_scan_projects_every_live_hit_without_a_disposition() -> None:
    scan = ComplexityScan(
        cyclomatic=(CcHit("src/cadrumo/a.py", "branch", "C", 22),),
        maintainability=(MiHit("src/cadrumo/b.py", "B", 14.0),),
        cognitive=(CogHit("src/cadrumo/c.py", "nested", 30),),
    )

    assert scan.finding_count == 3
    assert scan.rendered_findings() == [
        "cyclomatic: C (22)  src/cadrumo/a.py::branch",
        "maintainability: B ( 14.0)  src/cadrumo/b.py",
        "cognitive:   30  src/cadrumo/c.py::nested",
    ]


def test_cognitive_detector_turns_the_same_planted_function_red_then_green(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "module.py"
    source.write_text("def planted():\n    return 1\n", encoding="utf-8")

    monkeypatch.setattr(
        complexity,
        "file_complexity",
        lambda _path: SimpleNamespace(functions=[SimpleNamespace(name="planted", complexity=21)]),
    )
    assert collect_cog(tmp_path, is_test_run=False, threshold=20) == [
        CogHit(path=str(source).replace("\\", "/"), name="planted", score=21),
    ]

    monkeypatch.setattr(
        complexity,
        "file_complexity",
        lambda _path: SimpleNamespace(functions=[SimpleNamespace(name="planted", complexity=20)]),
    )
    assert collect_cog(tmp_path, is_test_run=False, threshold=20) == []


def test_cognitive_scan_refuses_an_empty_source_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="scan of nothing"):
        collect_cog(tmp_path, is_test_run=False, threshold=20)


def test_cognitive_scan_refuses_an_unavailable_file_analyzer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file-analysis failure must not be reduced to a false clean result."""
    (tmp_path / "module.py").write_text("def planted():\n    return 1\n", encoding="utf-8")

    def fail(_path: str) -> None:
        raise ValueError("unsupported syntax")

    monkeypatch.setattr(complexity, "file_complexity", fail)

    with pytest.raises(RuntimeError, match="could not analyze"):
        collect_cog(tmp_path, is_test_run=False, threshold=20)


def test_monthly_report_projects_the_same_live_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    red_scan = ComplexityScan(
        cyclomatic=(CcHit("src/cadrumo/a.py", "branch", "C", 22),),
        maintainability=(),
        cognitive=(),
    )
    monkeypatch.setattr(report, "scan_complexity", lambda: red_scan)

    red = report.audit_complexity()
    assert red.status is Status.RED
    assert red.headline == "1 current complexity hotspot(s)"
    assert red.details == ["cyclomatic: C (22)  src/cadrumo/a.py::branch"]

    monkeypatch.setattr(report, "scan_complexity", lambda: ComplexityScan((), (), ()))
    green = report.audit_complexity()
    assert green.status is Status.GREEN
    assert green.headline == "no complexity hotspots"
