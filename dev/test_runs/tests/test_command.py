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


def test_command_run_finalizes_metadata_when_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InterruptingOutput:
        def __iter__(self) -> InterruptingOutput:
            return self

        def __next__(self) -> str:
            run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
            seeded = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            assert seeded["exit_status"] == 130
            assert seeded["finished_at"]
            raise KeyboardInterrupt

    class InterruptingProcess:
        stdout = InterruptingOutput()
        terminated = False

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float | None = None) -> int:
            assert timeout == 5.0
            return 130

    process = InterruptingProcess()
    monkeypatch.setattr("dev.test_runs.command.subprocess.Popen", lambda *args, **kwargs: process)

    status = run(
        (sys.executable, "-c", "print('never reached')"),
        repository=tmp_path,
        family="audit-runs",
        label="audit-probe",
    )

    assert status == 130
    assert process.terminated is True
    run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["exit_status"] == 130
    assert metadata["finished_at"]
    transcript = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "INTERRUPTED exit=130" in transcript
    assert "FINISH " in transcript


def test_locale_signal_persists_backlog_and_keeps_stdout_bounded(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "outcome": "backlog",
        "headline": "Translate 1 locale cell for 1 unique key: es 1.",
        "summary": {
            "inventory": {"closed": True, "required_keys": 1},
            "translation_backlog": {
                "exact": True,
                "unique_keys_to_translate": 1,
                "cells_to_translate": 1,
            },
            "cells": {"required": 1, "ready": 0, "missing": 1},
            "locales": [{"locale": "es", "to_translate": 1}],
            "domains": [{"domain": "cli", "state": "translate", "to_translate": 1}],
            "catalogue_only": {"keys": 0, "cells": 0},
            "next_action": {"action": "create_missing_catalogue_leaves", "command": "just locales-scaffold"},
        },
        "details": {
            "backlog": [{"domain": "cli", "key": "cli.save", "locale": "es", "state": "missing"}],
            "findings": [{"kind": "translation_missing", "key": "cli.save", "locale": "es"}],
        },
    }
    script = f"import json; print(json.dumps({payload!r}))"

    status = run(
        (sys.executable, "-c", script),
        repository=tmp_path,
        family="test-runs",
        label="locales-status",
        signal="locales-status",
    )

    assert status == 0
    envelopes = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [item["event"] for item in envelopes] == ["run_started", "run_finished"]
    finished = envelopes[-1]
    assert finished["translation_backlog"]["cells_to_translate"] == 1
    assert "cli.save" not in json.dumps(finished)
    run_dir = next((tmp_path / ".logs" / "test-runs").glob("*/*"))
    assert (run_dir / "artifacts" / "locale-status.json").is_file()
    assert "cli.save" in (run_dir / "artifacts" / "locale-backlog.jsonl").read_text(encoding="utf-8")
    assert "translation_missing" in (run_dir / "artifacts" / "locale-findings.jsonl").read_text(encoding="utf-8")


def test_locale_signal_fails_closed_when_child_payload_is_not_parseable(
    tmp_path: Path,
) -> None:
    status = run(
        (sys.executable, "-c", "print('not-json')"),
        repository=tmp_path,
        family="test-runs",
        label="locales-status",
        signal="locales-status",
    )

    assert status == 7
    run_dir = next((tmp_path / ".logs" / "test-runs").glob("*/*"))
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["exit_status"] == 7


def test_locale_signal_normalizes_nonzero_child_without_payload_to_tool_failure(tmp_path: Path) -> None:
    status = run(
        (sys.executable, "-c", "print('broken'); raise SystemExit(1)"),
        repository=tmp_path,
        family="test-runs",
        label="locales-status",
        signal="locales-status",
    )

    assert status == 7
    run_dir = next((tmp_path / ".logs" / "test-runs").glob("*/*"))
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["exit_status"] == 7


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
    envelope = json.loads(capsys.readouterr().out.splitlines()[-1])
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
        (sys.executable, "-c", f"print({transcript!r})"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("calculations-parallel", "registry-conformance"),
    )

    assert status == 7
    output = capsys.readouterr().out
    envelopes = [json.loads(line) for line in output.splitlines()]
    assert len(envelopes) == 6
    assert "FAILED tests/test_probe.py" not in output
    finished = envelopes[-1]
    assert finished["classification"] == "blocking_findings"
    assert finished["summary"] == {
        "collected": 0,
        "deselected": 3,
        "error": 2,
        "failed": 1,
        "complete": True,
        "lanes_completed": 2,
        "lanes_expected": 2,
        "lanes_failed": 2,
        "lanes_blocked": 0,
        "lanes_not_run": 0,
        "lanes_load_failed": 0,
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


def test_pytest_summary_fails_closed_when_expected_lanes_never_emit_events(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = run(
        (sys.executable, "-c", "print('child exited without lane events')"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("collect", "load"),
    )

    assert status == 7
    finished = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert finished["classification"] == "incomplete"
    assert finished["result"] == "failed"
    assert finished["summary"]["complete"] is False
    assert finished["summary"]["lanes_not_run"] == 2
    assert [lane["result"] for lane in finished["lanes"]] == ["not_run", "not_run"]


def test_pytest_summary_classifies_typed_summaryless_load_as_load_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = "\n".join(
        (
            '{"event":"lane_started","kind":"collection","lane":"collect","role":"preflight"}',
            "================ 1 passed in 0.25s ================",
            '{"event":"lane_finished","exit_status":0,"kind":"collection","lane":"collect","role":"preflight","seconds":1}',
            '{"event":"lane_started","kind":"load","lane":"load","role":"preflight"}',
            "registry-runtime-load\tstatus=failed\tloadable=false\tdetail="
            "AuthorityArtifactFormatError: published authority artifact has an invalid authority payload",
            '{"event":"lane_finished","exit_status":2,"kind":"load","lane":"load","role":"preflight","seconds":1}',
        )
    )

    status = run(
        (sys.executable, "-c", f"print({transcript!r}); raise SystemExit(2)"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("collect", "load"),
    )

    assert status == 2
    finished = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert finished["classification"] == "load_failure"
    assert finished["summary"]["lanes_load_failed"] == 1
    assert finished["summary"]["lanes_tool_failed"] == 0
    assert finished["lanes"][1]["classification"] == "load_failure"
    assert finished["lanes"][1]["kind"] == "load"
    assert finished["lanes"][1]["root_causes"] == [
        {
            "count": 1,
            "exception": "AuthorityArtifactFormatError",
            "message": "published authority artifact has an invalid authority payload",
            "phase": "load",
        }
    ]


def test_pytest_summary_classifies_summaryless_collection_preflight_as_collection_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = "\n".join(
        (
            '{"event":"lane_started","kind":"collection","lane":"collect","role":"preflight"}',
            "SyntaxError: invalid syntax in registry test module",
            '{"event":"lane_finished","exit_status":2,"kind":"collection","lane":"collect","role":"preflight","seconds":1}',
        )
    )

    status = run(
        (sys.executable, "-c", f"print({transcript!r}); raise SystemExit(2)"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("collect",),
    )

    assert status == 2
    finished = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert finished["classification"] == "collection_failure"
    assert finished["summary"]["lanes_tool_failed"] == 0
    assert finished["lanes"][0]["classification"] == "collection_failure"
    assert finished["lanes"][0]["kind"] == "collection"
    assert finished["lanes"][0]["root_causes"][0]["phase"] == "collection"


def test_pytest_summary_reports_collection_preflight_and_blocked_lanes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = "\n".join(
        (
            '{"event":"lane_started","kind":"collection","lane":"collect","role":"preflight"}',
            "================ 314 tests collected in 1.25s ================",
            '{"event":"lane_finished","exit_status":0,"kind":"collection","lane":"collect","role":"preflight","seconds":2}',
            '{"event":"lane_started","kind":"load","lane":"load","role":"preflight"}',
            "registry-runtime-load\tstatus=failed\tloadable=false\tdetail="
            "AuthorityArtifactFormatError: published authority artifact has an invalid authority payload",
            '{"event":"lane_finished","exit_status":1,"kind":"load","lane":"load","role":"preflight","seconds":1}',
            '{"blocked_by":["load"],"event":"lane_skipped","kind":"command","lane":"parallel","reason":"preflight_failed","role":"execution"}',
            '{"blocked_by":["load"],"event":"lane_skipped","kind":"command","lane":"serial","reason":"preflight_failed","role":"execution"}',
        )
    )

    status = run(
        (sys.executable, "-c", f"print({transcript!r})"),
        repository=tmp_path,
        family="test-runs",
        label="test-registry",
        signal="pytest-summary",
        expected_lanes=("collect", "load", "parallel", "serial"),
    )

    assert status == 7
    finished = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert finished["classification"] == "preflight_failure"
    assert finished["summary"]["complete"] is True
    assert finished["summary"]["collected"] == 314
    assert finished["summary"]["lanes_completed"] == 2
    assert finished["summary"]["lanes_blocked"] == 2
    assert finished["summary"]["lanes_not_run"] == 0
    assert finished["summary"]["lanes_load_failed"] == 1
    assert finished["summary"]["lanes_tool_failed"] == 0
    assert finished["lanes"][1]["classification"] == "load_failure"
    assert finished["lanes"][1]["root_causes"][0]["phase"] == "load"
    assert [lane["kind"] for lane in finished["lanes"]] == ["collection", "load", "command", "command"]
    assert [lane["result"] for lane in finished["lanes"][2:]] == ["blocked", "blocked"]
