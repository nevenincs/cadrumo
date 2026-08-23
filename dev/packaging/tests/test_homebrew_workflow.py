"""Structural gate for the complete Homebrew acquisition matrix."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "packaging-homebrew.yml"


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def test_homebrew_workflow_declares_every_generated_target_row() -> None:
    """The matrix carries exactly the rows the self-hosted fleet can mint.

    Operator ruling 2026-07-21: no hosted/cloud runners, ever. macOS Intel was
    dropped the same day: Intel is no longer a supported platform (ARM-only
    macOS), so no macos-intel row may reappear.
    """
    document = _workflow()
    assert document["name"] == "Cadrumo Homebrew Acquisition"
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    rows = job["strategy"]["matrix"]["include"]

    def _runner(value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    assert {(row["id"], _runner(row["runner"]), row["expected_os"], row["expected_arch"]) for row in rows} == {
        ("macos-arm64", ("self-hosted", "macOS", "ARM64"), "Darwin", "arm64"),
        ("linux-x86_64", ("self-hosted", "Linux", "X64"), "Linux", "x86_64"),
        ("linux-arm64", ("self-hosted", "Linux", "ARM64"), "Linux", "aarch64"),
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
        step for step in steps if step["name"] == "Download the tested cohorts from the verified source run"
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
    # The cohorts come from the source run's own artifacts, which bind them to
    # that run by construction; the source-identity gate above is the whole
    # provenance check. Every leg consumes the LINUX-built python cohort
    # (wheels are py3-none-any) plus the sealed full release cohort.
    assert "gh run download" in download["run"]
    assert "--name cadrumo-python-cohort-linux" in download["run"]
    assert "--name cadrumo-release-cohort" in download["run"]
    # Least privilege: workflow-level stays read; only the uploader jobs hold
    # contents:write for the draft-release transport.
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert job["permissions"] == {"actions": "read", "contents": "read"}
    assert "uv build" not in commands


def test_homebrew_workflow_mints_every_row_from_the_immutable_cohort() -> None:
    """Each matrix row downloads THE cohort and emits its homebrew-<os>-<arch> record."""
    document = _workflow()
    job = document["jobs"]["cadrumo-homebrew-acquisition"]
    rows = job["strategy"]["matrix"]["include"]
    # All three homebrew rows run on the self-hosted fleet: the macOS
    # Linux-ARM container host carries linux-arm64. Zero hosted runners, per
    # the absolute spend mandate. macOS Intel is not a supported platform
    # (ARM-only macOS, dropped 2026-07-21).
    assert {row["row_id"] for row in rows} == {
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
    assert '--tax-evidence "$tax"' in emit["run"]
    assert 'if [[ -z "$tax" ]]' in emit["run"]
    # All three legs publish their rows (distinct {row_id}-{evidence_id}.json
    # basenames) and per-leg bundles as their OWN artifacts. Draft tags raced
    # on creation and needed a dedicated single-creator job; artifacts do not
    # race but DO clobber on name, so the per-leg matrix suffix is what keeps
    # the three concurrent legs independent — and the matrix needs no gating
    # job at all.
    publish = next(step for step in steps if step.get("name") == "Stage the Homebrew evidence bundle")
    assert "gh release" not in publish["run"]
    assert "cadrumo-homebrew-acquisition-${MATRIX_ID}.tar.gz" in publish["run"]

    artifact_names = [
        str((step.get("with") or {}).get("name")) for step in steps if "upload-artifact" in str(step.get("uses", ""))
    ]
    assert artifact_names, "the matrix leg uploads no artifact"
    assert all("${{ matrix.id }}" in name for name in artifact_names), artifact_names
    assert "needs" not in job

    # Failure diagnostics survive the ephemeral runner as debug-* artifacts,
    # never under a .json row-namespace name.
    diagnostics = next(step for step in steps if step.get("name") == "Stage build-failure diagnostics")
    assert diagnostics["if"] == "failure() && steps.initialize.outputs.ready == 'true'"
    assert "brew-install.log" in diagnostics["run"]
    assert "debug-brew-install-${MATRIX_ID}-${GITHUB_RUN_ID}.log" in diagnostics["run"]
    assert "debug-homebrew-diagnostics-${MATRIX_ID}-${GITHUB_RUN_ID}.tar.gz" in diagnostics["run"]
    assert "gh release" not in diagnostics["run"]
    assert steps.index(diagnostics) < steps.index(
        next(step for step in steps if step.get("name") == "Clean up the retained Homebrew install"),
    )


def test_homebrew_workflow_runs_the_real_source_install_and_oracles() -> None:
    """The matrix generates channel metadata then invokes the real lifecycle harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-homebrew-acquisition"]["steps"]
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    generate = next(step for step in steps if step["name"] == "Verify and generate the cohort-bound tap snapshot")
    smoke = next(step for step in steps if step["name"] == "Audit install and exercise Cadrumo through Homebrew")
    publish = next(step for step in steps if step["name"] == "Stage the Homebrew evidence bundle")

    assert initialize["id"] == "initialize"
    assert "GITHUB_RUN_ATTEMPT" in initialize["run"]
    assert "run-context.json" in initialize["run"]
    assert "dev.packaging.python_cohort verify" in generate["run"]
    assert "packaging/homebrew/generate.py" in generate["run"]
    assert "dev/packaging/smoke_homebrew.py" in smoke["run"]
    assert '--tap-name "cadrumo-smoke/${MATRIX_ID}"' in smoke["run"]
    assert publish["if"] == "always() && steps.initialize.outputs.ready == 'true'"
