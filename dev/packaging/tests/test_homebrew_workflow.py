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
    """The matrix covers both architectures on macOS and Linux.

    Self-hosting: the two rows that genuinely map to the free fleet run on it
    (linux-x86_64 -> the WSL X64 runner, macos-arm64 -> the MacBook), while
    macos-intel and linux-arm64 (aarch64) have no self-hosted home and honestly
    stay hosted rather than run on a mismatched architecture.
    """
    document = _workflow()
    assert document["name"] == "Cadrumo Homebrew Acquisition"
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    rows = job["strategy"]["matrix"]["include"]

    def _runner(value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    assert {(row["id"], _runner(row["runner"]), row["expected_os"], row["expected_arch"]) for row in rows} == {
        ("macos-intel", "macos-15-intel", "Darwin", "x86_64"),
        ("macos-arm64", ("self-hosted", "macOS", "ARM64"), "Darwin", "arm64"),
        ("linux-x86_64", ("self-hosted", "Linux", "X64"), "Linux", "x86_64"),
        ("linux-arm64", "ubuntu-24.04-arm", "Linux", "aarch64"),
    }
    assert job["strategy"]["fail-fast"] is False
    preflight = next(step for step in job["steps"] if step["name"] == "Verify declared Homebrew release row")
    assert 'test "$(uname -s)" = "$EXPECTED_OS"' in preflight["run"]
    assert 'test "$(uname -m)" = "$EXPECTED_ARCH"' in preflight["run"]
    assert 'test -x "$BREW_PATH"' in preflight["run"]


def test_homebrew_workflow_consumes_one_successful_commit_bound_cohort() -> None:
    """Every row downloads the same stored bytes from one trusted source run."""
    document = _workflow()
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    steps = job["steps"]
    source_gate = next(step for step in steps if step["name"] == "Verify source workflow identity")
    checkout = next(step for step in steps if step["name"] == "Checkout tested source commit")
    download = next(
        step for step in steps if step["name"] == "Download and verify the tested cohorts from the smoke evidence draft"
    )
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert 'test "$(jq -r .name <<<"$run_json")" = "Cadrumo Packaging Smoke"' in source_gate["run"]
    assert ".github/workflows/packaging-smoke.yml" in source_gate["run"]
    assert 'test "$(jq -r .conclusion <<<"$run_json")" = "success"' in source_gate["run"]
    # Trusted-source predicate (ci-speed redesign): main-branch runs, either
    # push (historical) or dispatch verified on main history via compare API.
    assert 'test "$(jq -r .head_branch <<<"$run_json")" = "main"' in source_gate["run"]
    assert '"$event" = "workflow_dispatch"' in source_gate["run"]
    assert "/compare/main..." in source_gate["run"]
    assert 'test "$ancestry" = "identical" -o "$ancestry" = "behind"' in source_gate["run"]
    assert 'test "$event" = "push"' in source_gate["run"]
    assert checkout["with"]["ref"] == "${{ inputs.source_commit }}"
    assert checkout["with"]["persist-credentials"] is False
    # The cohorts come hash-verified from the smoke run's evidence draft, with
    # the tag DERIVED from the run-id input; every leg consumes the LINUX-built
    # python cohort (wheels are py3-none-any; parity with the pre-transport
    # unsuffixed artifact) plus the sealed full release cohort.
    assert "dev.packaging.evidence_release verify" in download["run"]
    assert '--tag "evidence-smoke-${SOURCE_RUN_ID}"' in download["run"]
    assert '--expect-workflow ".github/workflows/packaging-smoke.yml"' in download["run"]
    assert '--pattern "cadrumo-python-cohort-linux.tar.gz"' in download["run"]
    assert '--pattern "cadrumo-release-cohort.tar.gz"' in download["run"]
    # Least privilege: workflow-level stays read; only the uploader jobs hold
    # contents:write for the draft-release transport.
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert job["permissions"] == {"actions": "read", "contents": "write"}
    assert "uv build" not in commands


def test_homebrew_workflow_mints_every_row_from_the_immutable_cohort() -> None:
    """Each matrix row downloads THE cohort and emits its homebrew-<os>-<arch> record."""
    document = _workflow()
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    rows = job["strategy"]["matrix"]["include"]
    assert {row["row_id"] for row in rows} == {
        "homebrew-macos-x86-64",
        "homebrew-macos-arm64",
        "homebrew-linux-x86-64",
        "homebrew-linux-arm64",
    }

    steps = job["steps"]
    emit = next(
        step for step in steps if step.get("name") == "Emit the sanctioned Homebrew distribution-evidence record"
    )
    assert "dev.packaging.distribution_evidence_emit" in emit["run"]
    assert '--row-id "$ROW_ID"' in emit["run"]
    assert "--release-cohort-dir " in emit["run"]

    # All four legs publish their rows (distinct {row_id}-{evidence_id}.json
    # basenames) and per-leg bundles to the ONE run draft created by the
    # dedicated create-evidence-draft job (single-creator topology: concurrent
    # matrix creates would mint duplicate drafts); the terminal seal job mints
    # the manifest only on full matrix success.
    publish = next(
        step for step in steps if step.get("name") == "Publish Homebrew evidence to the run's evidence draft"
    )
    assert publish["env"]["EVIDENCE_TAG"] == "evidence-homebrew-${{ github.run_id }}"
    assert "gh release create" not in publish["run"]  # upload-only leg
    assert "cadrumo-homebrew-acquisition-${MATRIX_ID}.tar.gz" in publish["run"]

    creator = document["jobs"]["create-evidence-draft"]
    creator_surface = "\n".join(str(step.get("run", "")) for step in creator["steps"])
    assert "gh release create" in creator_surface
    assert "--draft" in creator_surface
    assert "gh release view" in creator_surface  # create-if-absent probe
    assert job["needs"] == "create-evidence-draft"

    seal = document["jobs"]["seal-evidence-manifest"]
    assert seal["needs"] == "cadrumo-homebrew-acquisition"
    assert "if" not in seal  # manifest only on full success
    seal_surface = "\n".join(str(step.get("run", "")) for step in seal["steps"] if "run" in step)
    assert "dev.packaging.evidence_release emit-manifest" in seal_surface
    assert 'gh release upload "$EVIDENCE_TAG" evidence-manifest.json --clobber' in seal_surface


def test_homebrew_workflow_runs_the_real_source_install_and_oracles() -> None:
    """The matrix generates channel metadata then invokes the real lifecycle harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-homebrew-acquisition"]["steps"]
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    generate = next(step for step in steps if step["name"] == "Verify and generate the cohort-bound tap snapshot")
    smoke = next(step for step in steps if step["name"] == "Audit install and exercise Cadrumo through Homebrew")
    publish = next(step for step in steps if step["name"] == "Publish Homebrew evidence to the run's evidence draft")

    assert initialize["id"] == "initialize"
    assert "GITHUB_RUN_ATTEMPT" in initialize["run"]
    assert "run-context.json" in initialize["run"]
    assert "dev.packaging.python_cohort verify" in generate["run"]
    assert "packaging/homebrew/generate.py" in generate["run"]
    assert "dev/packaging/smoke_homebrew.py" in smoke["run"]
    assert '--tap-name "cadrumo-smoke/${MATRIX_ID}"' in smoke["run"]
    assert publish["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    assert "gh release upload" in publish["run"]
