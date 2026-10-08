"""Detector-teeth tests for the baseline-free complexity projection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import complexity, report
from ..complexity import (
    CcHit,
    CogHit,
    ComplexityScan,
    IncompleteScanError,
    MiHit,
    cognitive_hits,
    measure_population,
    source_population,
)
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


def test_cognitive_detector_turns_the_same_planted_function_red_then_green(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "def planted():\n    return 1\n"

    monkeypatch.setattr(
        complexity,
        "code_complexity",
        lambda _source: SimpleNamespace(functions=[SimpleNamespace(name="planted", complexity=21)]),
    )
    assert cognitive_hits("pkg/module.py", source, 20) == [CogHit(path="pkg/module.py", name="planted", score=21)]

    monkeypatch.setattr(
        complexity,
        "code_complexity",
        lambda _source: SimpleNamespace(functions=[SimpleNamespace(name="planted", complexity=20)]),
    )
    assert cognitive_hits("pkg/module.py", source, 20) == []


def test_population_refuses_an_empty_source_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="scan of nothing"):
        source_population((tmp_path.as_posix(),))


def test_population_refuses_a_root_holding_only_test_files(tmp_path: Path) -> None:
    (tmp_path / "test_module.py").write_text("def planted():\n    return 1\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="scan of nothing"):
        source_population((tmp_path.as_posix(),))


def test_test_scope_enumerates_the_nested_test_surface(tmp_path: Path) -> None:
    """The test scope reads the authority's test surface at every depth, never production or data."""
    test_files = ("tests/unit/check.py", "pkg/test_mod.py", "pkg/deep/_test_mod.py", "pkg/conftest.py")
    other_files = ("pkg/mod.py", "_data/tests/test_bundled.py", "pkg/test_notes.txt")
    for relative in (*test_files, *other_files):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")

    population = source_population((tmp_path.as_posix(),), tests=True)

    assert {path.relative_to(tmp_path).as_posix() for path in population} == set(test_files)


def test_a_failing_analyzer_makes_the_scan_incomplete_naming_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file-analysis failure must not be reduced to a false clean result."""
    module = tmp_path / "module.py"
    module.write_text("def planted():\n    return 1\n", encoding="utf-8")

    def fail(_source: str) -> None:
        raise ValueError("unsupported syntax")

    monkeypatch.setattr(complexity, "code_complexity", fail)

    with pytest.raises(IncompleteScanError, match="complexipy cognitive: ValueError: unsupported syntax") as caught:
        measure_population((module,), cognitive_threshold=20)
    assert module.as_posix() in str(caught.value)


def test_production_scan_refuses_a_missing_root(tmp_path: Path) -> None:
    """A dropped or renamed root must fail the scan, never silently shrink it."""
    present = tmp_path / "present"
    present.mkdir()
    (present / "module.py").write_text("def planted():\n    return 1\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="scan of nothing"):
        complexity.scan_complexity(roots=(present.as_posix(), (tmp_path / "absent").as_posix()))


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


def test_monthly_report_reads_an_incomplete_scan_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def incomplete() -> ComplexityScan:
        raise IncompleteScanError("1 measurement(s) failed: pkg/broken.py (radon cyclomatic: SyntaxError)")

    monkeypatch.setattr(report, "scan_complexity", incomplete)

    unavailable = report.audit_complexity()
    assert unavailable.status is Status.AMBER
    assert unavailable.available is False
    assert "pkg/broken.py" in unavailable.headline
