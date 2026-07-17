"""Structural gate for the complete Homebrew acquisition matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "packaging-homebrew.yml"


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def test_homebrew_workflow_declares_every_generated_target_row() -> None:
    """The matrix covers both architectures on macOS and Linux."""
    document = _workflow()
    assert document["name"] == "Cadrumo Homebrew Acquisition"
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    rows = job["strategy"]["matrix"]["include"]
    assert {(row["runner"], row["expected_os"], row["expected_arch"]) for row in rows} == {
        ("macos-15-intel", "Darwin", "x86_64"),
        ("macos-15", "Darwin", "arm64"),
        ("ubuntu-24.04", "Linux", "x86_64"),
        ("ubuntu-24.04-arm", "Linux", "aarch64"),
    }
    assert job["strategy"]["fail-fast"] is False
    preflight = next(step for step in job["steps"] if step["name"] == "Verify declared Homebrew release row")
    assert 'test "$(uname -s)" = "$EXPECTED_OS"' in preflight["run"]
    assert 'test "$(uname -m)" = "$EXPECTED_ARCH"' in preflight["run"]
    assert 'test -x "$BREW_PATH"' in preflight["run"]


def test_homebrew_workflow_consumes_one_successful_commit_bound_cohort() -> None:
    """Every row downloads the same stored bytes from one trusted source run."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-homebrew-acquisition"]["steps"]
    source_gate = next(step for step in steps if step["name"] == "Verify source workflow identity")
    checkout = next(step for step in steps if step["name"] == "Checkout tested source commit")
    download = next(step for step in steps if step["name"] == "Download tested Cadrumo Python cohort")
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert 'test "$(jq -r .name <<<"$run_json")" = "Cadrumo Packaging Smoke"' in source_gate["run"]
    assert ".github/workflows/packaging-smoke.yml" in source_gate["run"]
    assert 'test "$(jq -r .conclusion <<<"$run_json")" = "success"' in source_gate["run"]
    assert 'test "$(jq -r .event <<<"$run_json")" = "push"' in source_gate["run"]
    assert 'test "$(jq -r .head_branch <<<"$run_json")" = "main"' in source_gate["run"]
    assert checkout["with"]["ref"] == "${{ inputs.source_commit }}"
    assert checkout["with"]["persist-credentials"] is False
    assert download["with"]["name"] == "cadrumo-python-cohort"
    assert download["with"]["run-id"] == "${{ inputs.source_run_id }}"
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert "uv build" not in commands


def test_homebrew_workflow_runs_the_real_source_install_and_oracles() -> None:
    """The matrix generates channel metadata then invokes the real lifecycle harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-homebrew-acquisition"]["steps"]
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    generate = next(step for step in steps if step["name"] == "Verify and generate the cohort-bound tap snapshot")
    smoke = next(step for step in steps if step["name"] == "Audit install and exercise Cadrumo through Homebrew")
    upload = next(step for step in steps if step["name"] == "Upload Cadrumo Homebrew acquisition evidence")

    assert initialize["id"] == "initialize"
    assert "GITHUB_RUN_ATTEMPT" in initialize["run"]
    assert "run-context.json" in initialize["run"]
    assert "dev.packaging.python_cohort verify" in generate["run"]
    assert "packaging/homebrew/generate.py" in generate["run"]
    assert "dev/packaging/smoke_homebrew.py" in smoke["run"]
    assert '--tap-name "cadrumo-smoke/${MATRIX_ID}"' in smoke["run"]
    assert upload["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["name"] == ("cadrumo-homebrew-acquisition-${{ matrix.id }}-${{ github.run_attempt }}")
