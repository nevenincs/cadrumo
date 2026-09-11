from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ..command import run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_command_run_streams_and_persists_identity(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    command = (sys.executable, "-c", "print('observable signal')")

    status = run(command, repository=tmp_path, family="audit-runs", label="audit-probe")

    assert status == 0
    assert "observable signal" in capsys.readouterr().out
    run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["command"] == list(command)
    assert metadata["exit_status"] == 0
    assert "COMMAND " in (run_dir / "run.log").read_text(encoding="utf-8")


def test_command_run_preserves_failure_status(tmp_path: Path) -> None:
    status = run(
        (sys.executable, "-c", "raise SystemExit(7)"),
        repository=tmp_path,
        family="audit-runs",
        label="audit-probe",
    )

    assert status == 7


def test_command_run_confines_child_temp_and_cache_paths(tmp_path: Path) -> None:
    probe = (
        "import json, os, pathlib, tempfile; "
        "pathlib.Path(os.environ['CADRUMO_DEV_ARTIFACTS_DIR']).joinpath('paths.json').write_text("
        "json.dumps({'temp': tempfile.gettempdir(), 'cache': os.environ['XDG_CACHE_HOME']}))"
    )
    status = run((sys.executable, "-c", probe), repository=tmp_path, family="audit-runs", label="path-probe")

    assert status == 0
    run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
    paths = json.loads((run_dir / "artifacts" / "paths.json").read_text(encoding="utf-8"))
    assert Path(paths["temp"]).resolve() == (run_dir / "scratch").resolve()
    assert Path(paths["cache"]).resolve() == (run_dir / "cache").resolve()


def test_import_boundaries_signal_deduces_contract_and_diagnostic_hotspots(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = "\n".join(
        (
            "Analyzed 4 files, 5 dependencies.",
            "Application has no concrete outer dependency BROKEN",
            "cadrumo.application is not allowed to import cadrumo.adapters:",
            "-   cadrumo.application.service -> ",
            "cadrumo.adapters.persistence.repository (l.4)",
            "cadrumo is not allowed to import cadrumo.adapters:",
            "-   cadrumo.application.service -> ",
            "cadrumo.adapters.persistence.repository (l.4)",
            "[SUBORDINATE_CHECKER] exit 1",
            "[CANONICAL_TARGET_MISSING] src/cadrumo/application/service.py:4: "
            "'cadrumo.core.old_home' does not define imported symbol 'Thing'",
            "[PACKAGE_FACADE] src/cadrumo/application/service.py:4: "
            "symbol 'Other' is consumed from package facade 'cadrumo.core.facade'",
            "[PRIVATE_CROSS_PACKAGE] dev/tests/test_probe.py:9: "
            "'dev.tests.test_probe' reaches private module 'dev.tooling._private'",
        )
    )
    script = f"print({transcript!r}); raise SystemExit(1)"

    status = run(
        (sys.executable, "-c", script),
        repository=tmp_path,
        family="test-runs",
        label="check-import-boundaries",
        signal="import-boundaries",
    )

    assert status == 1
    envelope = json.loads(capsys.readouterr().out)
    deductions = envelope["deductions"]
    assert deductions["schema_version"] == 1
    assert deductions["contract_paths"] == {
        "by_forbidden_edge": {
            "cadrumo -> cadrumo.adapters": {
                "direct_paths": 1,
                "non_test_scoped_paths": 1,
                "reported_paths": 1,
                "test_scoped_paths": 0,
                "top_bridge_modules": [],
                "top_source_modules": [],
                "top_terminal_modules": [],
                "transitive_paths": 0,
                "unique_source_modules": 1,
                "unique_terminal_modules": 1,
            },
            "cadrumo.application -> cadrumo.adapters": {
                "direct_paths": 1,
                "non_test_scoped_paths": 1,
                "reported_paths": 1,
                "test_scoped_paths": 0,
                "top_bridge_modules": [],
                "top_source_modules": [],
                "top_terminal_modules": [],
                "transitive_paths": 0,
                "unique_source_modules": 1,
                "unique_terminal_modules": 1,
            },
        },
        "classification": "test_scoped uses module naming conventions; non_test_scoped is its complement",
        "maximum_contract_multiplicity": 2,
        "overlapping_unique_paths": 1,
        "reported_paths": 2,
        "reports_for_overlapping_paths": 2,
        "unique_dependency_paths": 1,
    }
    assert deductions["diagnostic_signal"]["amplification"] == {
        "files": 2,
        "findings": 3,
        "findings_at_multi_finding_locations": 2,
        "locations": 2,
        "locations_with_multiple_findings": 1,
        "maximum_findings_at_one_location": 2,
    }
    assert deductions["diagnostic_signal"]["by_code"]["CANONICAL_TARGET_MISSING"]["top_targets"] == [
        {"count": 1, "value": "cadrumo.core.old_home"}
    ]
    assert deductions["remediation_lanes"]["canonical_import_surface"]["findings"] == 2
    assert deductions["remediation_lanes"]["private_encapsulation"]["test_scoped_findings"] == 1


def test_pytest_summary_signal_aggregates_lanes_without_streaming_details(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = "\n".join(
        (
            '{"event":"lane_started","lane":"calculations-parallel"}',
            "FAILED tests/test_probe.py::test_one",
            "E   ImportError: cannot import name 'Thing' from 'package'",
            "======= 12 passed, 1 failed, 3 deselected in 2.50s (0:00:02) =======",
            '{"event":"lane_finished","exit_status":1,"lane":"calculations-parallel","seconds":3}',
            '{"event":"lane_started","lane":"registry-conformance"}',
            "collection detail that must remain in the log",
            "ERROR tests/test_registry.py",
            "E   ImportError: cannot import name 'Thing' from 'package'",
            "INTERNALERROR> AssertionError: ('tests/test_registry.py::test_one', <WorkerController gw0>)",
            "============ 4 passed, 2 errors, 1 warning in 1.25s (0:00:01) ============",
            '{"event":"lane_finished","exit_status":1,"lane":"registry-conformance","seconds":2}',
        )
    )

    status = run(
        (sys.executable, "-c", f"print({transcript!r}); raise SystemExit(1)"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("calculations-parallel", "registry-conformance"),
    )

    assert status == 1
    output = capsys.readouterr().out
    envelopes = [json.loads(line) for line in output.splitlines()]
    assert len(envelopes) == 6
    assert "test_probe.py" not in output
    finished = envelopes[-1]
    assert finished["classification"] == "blocking_findings"
    assert finished["summary"] == {
        "deselected": 3,
        "error": 2,
        "failed": 1,
        "complete": True,
        "lanes_completed": 2,
        "lanes_expected": 2,
        "lanes_failed": 2,
        "lanes_not_run": 0,
        "lanes_tool_failed": 1,
        "passed": 16,
        "pytest_invocations": 2,
        "skipped": 0,
        "total_selected": 19,
        "warning": 1,
        "xfailed": 0,
        "xpassed": 0,
    }
    assert [lane["name"] for lane in finished["lanes"]] == [
        "calculations-parallel",
        "registry-conformance",
    ]
    assert finished["lanes"][0]["top_affected_files"] == [{"count": 1, "value": "tests/test_probe.py"}]
    assert finished["lanes"][0]["classification"] == "blocking_findings"
    assert finished["lanes"][1]["classification"] == "tool_failure"
    assert finished["lanes"][1]["root_causes"][0] == {
        "count": 1,
        "exception": "AssertionError",
        "message": "('tests/test_registry.py::test_one', <WorkerController gw0>)",
        "phase": "tool",
    }
    assert finished["lanes"][0]["root_causes"] == [
        {
            "count": 1,
            "exception": "ImportError",
            "message": "cannot import name 'Thing' from 'package'",
            "phase": "execution",
        }
    ]
    run_dir = next((tmp_path / ".logs" / "test-runs").glob("*/*"))
    assert "collection detail" in (run_dir / "run.log").read_text(encoding="utf-8")
