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
    length_hits,
    measure_population,
    source_population,
)
from ..report import Status

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_length_limits_include_nested_decorated_callables() -> None:
    source = "@decorate\ndef outer():\n    def inner():\n" + "        pass\n" * 150
    findings = length_hits("dev/tool.py", source)
    assert [(hit.name, hit.lines, hit.limit) for hit in findings] == [("outer", 153, 150), ("outer.inner", 151, 150)]
    assert length_hits("src/package/module.py", "# line\n" * 1250) == []
    oversized = length_hits("src/package/module.py", "# line\n" * 1251)
    assert [(hit.name, hit.lines, hit.limit) for hit in oversized] == [("", 1251, 1250)]


def test_async_callable_limit_includes_decorators_and_nested_definitions() -> None:
    source = "@decorate\nasync def exact():\n" + "    pass\n" * 148
    assert length_hits("dev/async.py", source) == []
    source = "async def outer():\n    @decorate\n    async def inner():\n" + "        pass\n" * 149
    assert [(hit.name, hit.lines) for hit in length_hits("dev/async.py", source)] == [
        ("outer", 152),
        ("outer.inner", 151),
    ]


@pytest.mark.parametrize("threshold", [19, 21, 999])
def test_gate_refuses_a_nonstandard_cognitive_threshold(
    threshold: int, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["complexity", "--gate", "--threshold", str(threshold)])
    with pytest.raises(SystemExit) as caught:
        complexity.main()
    assert caught.value.code == 2
    assert "fixed cognitive complexity threshold of 20" in capsys.readouterr().err


@pytest.mark.parametrize("root_name", ["src", "dev"])
def test_gate_detects_length_in_each_root_then_accepts_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], root_name: str
) -> None:
    roots = tuple(tmp_path / name for name in ("src", "dev"))
    for root in roots:
        root.mkdir()
        (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    oversized = tmp_path / root_name / "module.py"
    oversized.write_text("# line\n" * 1251, encoding="utf-8")
    monkeypatch.setattr(complexity, "FIRST_PARTY_ROOTS", tuple(root.as_posix() for root in roots))
    monkeypatch.setattr("sys.argv", ["complexity", "--gate"])
    assert complexity.main() == 1
    assert f"1251 lines (limit 1250)  {oversized.as_posix()}" in capsys.readouterr().out
    oversized.write_text("VALUE = 1\n", encoding="utf-8")
    assert complexity.main() == 0
    assert "0 current hotspot(s)" in capsys.readouterr().out


def test_gate_refuses_an_unmeasurable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "broken.py").write_text("def broken(:", encoding="utf-8")
    monkeypatch.setattr(complexity, "FIRST_PARTY_ROOTS", (tmp_path.as_posix(),))
    monkeypatch.setattr("sys.argv", ["complexity", "--gate"])
    assert complexity.main() == 7


def test_gate_refuses_test_only_scope(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["complexity", "--gate", "--tests"])
    with pytest.raises(SystemExit) as caught:
        complexity.main()
    assert caught.value.code == 2
    assert "full first-party production scope" in capsys.readouterr().err


@pytest.mark.parametrize("detector", ["radon_visitors", "radon_complexity", "radon_metrics", "code_complexity"])
def test_gate_reports_each_unavailable_detector(
    detector: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "module.py").write_text("def sample():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(complexity, "FIRST_PARTY_ROOTS", (tmp_path.as_posix(),))
    monkeypatch.setattr(complexity, detector, None)
    monkeypatch.setattr("sys.argv", ["complexity", "--gate"])
    assert complexity.main() == 7
    assert "scan is incomplete and not clean" in capsys.readouterr().err


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


def test_empty_explicit_population_never_reads_as_clean() -> None:
    with pytest.raises(FileNotFoundError, match="scan of nothing"):
        complexity.scan_complexity(roots=())
    with pytest.raises(IncompleteScanError, match="scan of nothing"):
        measure_population((), cognitive_threshold=20)


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
