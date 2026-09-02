"""Structural gates for the dedicated rolling Python compatibility workflow.

The workflow is a separate evidence surface.  It must derive its rows from the
validated inventory, build one exact release cohort, and run source and binary
probes as distinct verdicts for every stable and prerelease row.  These tests
read the live YAML and deliberately inspect executable fields rather than
comments, so a prose-only workflow cannot satisfy the contract.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "python-runtime-compatibility.yml"
_GUARD: Final = (
    "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
)
_MATRIX_JOBS: Final = ("compatibility-source", "compatibility-binary")
_REQUIRED_PATHS: Final = frozenset(
    {
        ".github/workflows/python-runtime-compatibility.yml",
        ".python-version",
        "pyproject.toml",
        "uv.lock",
        "dev/**",
        "src/**",
        "packaging/**",
    },
)


def _document() -> dict[str, Any]:
    """Load the checked-in workflow using the repository's YAML convention."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    """Return the trigger mapping across YAML 1.1 and 1.2 loaders."""
    triggers = document[True] if True in document else document["on"]
    assert isinstance(triggers, dict)
    return triggers


def _run_lines(job: dict[str, Any]) -> list[str]:
    """Return executable run lines, excluding comments and blank lines."""
    lines: list[str] = []
    for step in job.get("steps", []):
        if not isinstance(step, dict) or "run" not in step:
            continue
        for line in str(step["run"]).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
    return lines


def _run_surface(job: dict[str, Any]) -> str:
    """Return the executable surface of a job as one searchable string."""
    return "\n".join(_run_lines(job))


def _steps_with_run(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Return run-bearing steps after asserting their expected YAML shape."""
    steps = job.get("steps")
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, dict) and "run" in step]


def _probe_step(job: dict[str, Any], mode: str) -> dict[str, Any]:
    """Find the one executable compatibility probe for a job and mode."""
    matches = [
        step
        for step in _steps_with_run(job)
        if "dev.ci.python_runtime_compatibility" in str(step["run"])
        and f"--mode {mode}" in str(step["run"])
    ]
    assert len(matches) == 1, f"expected one {mode} compatibility probe"
    return matches[0]


def _assert_probe_contract(job: dict[str, Any], *, mode: str) -> None:
    """Assert one matrix job invokes the runner with an attributable row."""
    probe = _probe_step(job, mode)
    surface = str(probe["run"])
    assert "uv run --no-sync python -m dev.ci.python_runtime_compatibility" in surface
    assert f"--mode {mode}" in surface
    assert '--python "${{ matrix.python-version }}"' in surface
    assert '--runtime-id "${{ matrix.runtime-id }}"' in surface
    assert '--stability "${{ matrix.phase }}"' in surface
    assert '"${{ matrix.blocking }}"' in surface
    assert "probe_status=$?" in surface
    assert "::error::" in surface
    assert "::warning::" in surface
    assert "if [ \"${{ matrix.blocking }}\" = \"true\" ]" in surface
    if mode == "binary":
        assert '--cohort-dir var/python-runtime-cohort' in surface
    else:
        assert "--cohort-dir" not in surface


def _assert_evidence_upload_contract(job: dict[str, Any], *, mode: str) -> None:
    """Assert that one matrix leg retains failed-run evidence and its digest."""
    uploads = [
        step
        for step in job["steps"]
        if isinstance(step, dict) and "actions/upload-artifact@" in str(step.get("uses", ""))
    ]
    assert len(uploads) == 1, mode
    upload = uploads[0]
    assert upload["if"] == "always()"
    assert upload["with"].get("if-no-files-found") == "error"
    assert mode in upload["with"]["name"]
    assert "compatibility-evidence.json*" in upload["with"]["path"]

    surface = _run_surface(job)
    assert f"Hash {mode} compatibility evidence" in "\n".join(
        str(step.get("name", "")) for step in job["steps"] if isinstance(step, dict)
    )
    assert "sha256sum \"$evidence\"" in surface


def test_workflow_has_dedicated_triggers_and_product_identity() -> None:
    """The compatibility surface runs on code changes and manual dispatch."""
    document = _document()
    assert document["name"] == "Cadrumo Python Runtime Compatibility"
    triggers = _triggers(document)
    assert set(triggers) == {"workflow_dispatch", "push", "pull_request"}
    for event in ("push", "pull_request"):
        trigger = triggers[event]
        assert trigger["branches"] == ["main"]
        assert set(trigger["paths"]) >= _REQUIRED_PATHS
    assert document["permissions"] == {"contents": "read"}
    assert "schedule" not in triggers


def test_every_job_is_self_hosted_and_fork_guarded() -> None:
    """No fork head can execute a matrix probe or its build prerequisite."""
    document = _document()
    jobs = document["jobs"]
    assert set(jobs) == {
        "runtime-inventory",
        "build-python-cohort",
        "compatibility-source",
        "compatibility-binary",
    }
    for job_name, job in jobs.items():
        assert job["if"] == _GUARD, job_name
        assert job["runs-on"] == ["self-hosted", "Linux", "X64"], job_name


def test_inventory_job_is_the_only_matrix_authority() -> None:
    """Both mode matrices consume the validated inventory output verbatim."""
    document = _document()
    inventory = document["jobs"]["runtime-inventory"]
    assert inventory["outputs"] == {"matrix": "${{ steps.emit-matrix.outputs.matrix }}"}
    inventory_surface = _run_surface(inventory)
    assert "uv sync --frozen" in inventory_surface
    assert "uv run --no-sync python -m dev.ci.python_runtime_matrix" in inventory_surface
    emit_steps = [step for step in inventory["steps"] if isinstance(step, dict) and step.get("id") == "emit-matrix"]
    assert len(emit_steps) == 1
    assert "GITHUB_OUTPUT" in str(emit_steps[0]["run"])

    source = document["jobs"]["compatibility-source"]
    binary = document["jobs"]["compatibility-binary"]
    assert source["needs"] == "runtime-inventory"
    assert set(binary["needs"]) == {"runtime-inventory", "build-python-cohort"}
    for job in (source, binary):
        matrix = job["strategy"]["matrix"]
        assert matrix == "${{ fromJSON(needs.runtime-inventory.outputs.matrix) }}"
        assert job["strategy"]["fail-fast"] is False


def test_source_and_binary_are_separate_complete_probe_jobs() -> None:
    """Every inventory row gets one source verdict and one binary verdict."""
    document = _document()
    source = document["jobs"]["compatibility-source"]
    binary = document["jobs"]["compatibility-binary"]
    _assert_probe_contract(source, mode="source")
    _assert_probe_contract(binary, mode="binary")

    source_surface = _run_surface(source)
    binary_surface = _run_surface(binary)
    assert "--mode binary" not in source_surface
    assert "--mode source" not in binary_surface
    assert "--stability" in source_surface and "--stability" in binary_surface


def test_probe_mode_gate_has_detector_teeth() -> None:
    """A source job carrying a binary probe is rejected by the structural gate."""
    document = deepcopy(_document())
    source = document["jobs"]["compatibility-source"]
    probe = next(step for step in source["steps"] if "dev.ci.python_runtime_compatibility" in str(step.get("run", "")))
    probe["run"] = str(probe["run"]).replace("--mode source", "--mode binary")
    with pytest.raises(AssertionError, match="source"):
        _assert_probe_contract(source, mode="source")


def test_advisory_and_blocking_outcomes_are_explicit_without_workflow_skips() -> None:
    """The next row is visible as evidence; stable failures still fail the job."""
    document = _document()
    for job_name in document["jobs"]:
        job = document["jobs"][job_name]
        assert "continue-on-error" not in job, job_name
        for step in job.get("steps", []):
            assert isinstance(step, dict)
            assert "continue-on-error" not in step, f"{job_name}:{step.get('name', '')}"
            if "if" in step:
                assert str(step["if"]) == "always()", f"unexpected conditional step in {job_name}"

    for mode_job in _MATRIX_JOBS:
        job = document["jobs"][mode_job]
        surface = _run_surface(job)
        assert "set +e" in surface
        assert "probe_status=$?" in surface
        assert "matrix.blocking" in surface
        assert "::warning::advisory" in surface
        assert "::error::blocking" in surface


def test_evidence_uploads_are_fail_closed_and_mode_specific() -> None:
    """Every row uploads JSON plus its digest sidecar, including failed probes."""
    document = _document()
    for mode_job, mode in (("compatibility-source", "source"), ("compatibility-binary", "binary")):
        _assert_evidence_upload_contract(document["jobs"][mode_job], mode=mode)


def test_binary_rows_download_and_verify_one_cohort() -> None:
    """Binary rows consume the one run-local archive and verify its digest."""
    document = _document()
    build = document["jobs"]["build-python-cohort"]
    build_surface = _run_surface(build)
    assert build_surface.count("python -m dev.packaging.release_cohort build") == 1
    assert "--expected-commit" in build_surface
    assert "sha256sum cadrumo-python-runtime-cohort.tar.gz >" in build_surface
    assert "python-runtime-cohort.tar.gz.sha256" in build_surface
    assert "python -m dev.packaging.release_cohort verify" in build_surface
    assert "cadrumo-python-runtime-cohort" in "\n".join(
        str(step.get("with", {}).get("name", ""))
        for step in build["steps"]
        if isinstance(step, dict)
    )

    binary = document["jobs"]["compatibility-binary"]
    download = [
        step
        for step in binary["steps"]
        if isinstance(step, dict) and "actions/download-artifact@" in str(step.get("uses", ""))
    ]
    assert len(download) == 1
    assert download[0]["with"]["name"] == "cadrumo-python-runtime-cohort"
    binary_surface = _run_surface(binary)
    assert "sha256sum --check cadrumo-python-runtime-cohort.tar.gz.sha256" in binary_surface
    assert "python -m dev.packaging.release_cohort verify" in binary_surface
    assert "python -m dev.packaging.release_cohort build" not in binary_surface


def test_cohort_builder_preserves_the_exact_pin_lane() -> None:
    """The cohort builder does not replace the repository's exact Python pin."""
    document = _document()
    build = document["jobs"]["build-python-cohort"]
    setup = [
        step
        for step in build["steps"]
        if isinstance(step, dict) and str(step.get("uses", "")).startswith("astral-sh/setup-uv@")
    ]
    assert len(setup) == 1
    assert "python-version" not in (setup[0].get("with") or {})


def test_evidence_upload_gate_has_detector_teeth() -> None:
    """A missing evidence fail-closed setting is rejected by the gate."""
    document = deepcopy(_document())
    source = document["jobs"]["compatibility-source"]
    upload = next(step for step in source["steps"] if "actions/upload-artifact@" in str(step.get("uses", "")))
    del upload["with"]["if-no-files-found"]
    with pytest.raises(AssertionError, match="error"):
        _assert_evidence_upload_contract(source, mode="source")
