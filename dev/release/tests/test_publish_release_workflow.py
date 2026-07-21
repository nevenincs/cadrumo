"""Structural proof that the real publication authority stays fail-closed.

``publish-release.yml`` is the sole upload authority (the former validate-only
``publish.yml`` diagnostic stub was retired; its ``dry_run`` mode now lives on
this authority). These tests pin its safety contract: it is inert until the
operator opts in, it never builds or regenerates an artifact, OIDC minting is
confined to the environment-protected publish job, and every external channel
push refuses instructively when its credential is absent.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-release.yml"

# A build/regenerate invocation is forbidden in EVERY job: publication promotes
# stored bytes and must never rebuild. Publishing/upload verbs are deliberately
# excluded here because the environment-protected publish job legitimately runs
# them; their confinement is asserted separately.
_BUILD_RUN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\buv\s+build\b", re.IGNORECASE),
    re.compile(r"\bpython[0-9.]*\s+-m\s+build\b", re.IGNORECASE),
    re.compile(r"\bpip[0-9.]*\s+wheel\b", re.IGNORECASE),
    re.compile(r"\b(?:poetry|flit|hatch|pdm)\s+build\b", re.IGNORECASE),
    re.compile(r"\bsetup\.py\b[^\n]*\b(?:sdist|bdist_wheel|bdist|build)\b", re.IGNORECASE),
    re.compile(r"\bpackaging/\S*generate\.py\b", re.IGNORECASE),
    re.compile(r"\brelease_cohort\b", re.IGNORECASE),
)


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_surface(job: Mapping[str, object]) -> str:
    steps = job["steps"]
    assert isinstance(steps, list)
    return "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, Mapping) and "run" in step)


def test_workflow_shape_and_least_privilege_top_level() -> None:
    """One run-bound input, least-privilege top-level perms, the three staged jobs."""
    document = _document()
    dispatch = document[True]["workflow_dispatch"]
    assert set(dispatch["inputs"]) == {
        "packaging_run_id",
        "scoop_run_id",
        "homebrew_run_id",
        "claude_evidence_release",
        "dry_run",
    }
    assert document["permissions"] == {"contents": "read"}
    assert set(document["jobs"]) == {"operator-preflight", "validate", "publish"}


def test_dry_run_validates_everything_and_skips_publish() -> None:
    """A dry_run dispatch runs Gate 1+2 fully but gates the publish job off."""
    document = _document()
    dry_run = document[True]["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is False
    assert dry_run["required"] is False
    # Only the publish job is conditioned on dry_run; operator-preflight and
    # validate always run so the validate-everything-publish-nothing mode is real.
    publish = document["jobs"]["publish"]
    assert publish["if"] == "${{ inputs.dry_run != true }}"
    assert "if" not in document["jobs"]["operator-preflight"]
    assert "if" not in document["jobs"]["validate"]


def test_inert_until_operator_opt_in() -> None:
    """The first gate refuses unless the operator sets CADRUMO_PUBLISH_ENABLED=true."""
    preflight = _document()["jobs"]["operator-preflight"]
    surface = _run_surface(preflight)
    assert "vars.CADRUMO_PUBLISH_ENABLED" in _WORKFLOW.read_text(encoding="utf-8")
    assert 'PUBLISH_ENABLED}" != "true"' in surface
    assert "REFUSED: Cadrumo publication is not enabled" in surface


def test_oidc_and_write_are_confined_to_the_protected_publish_job() -> None:
    """id-token/contents:write live only on the environment-protected publish job."""
    document = _document()
    publish = document["jobs"]["publish"]
    assert publish["environment"] == "release"
    assert publish["permissions"] == {"id-token": "write", "contents": "write"}
    assert publish["needs"] == "validate"

    for name in ("operator-preflight", "validate"):
        perms = document["jobs"][name].get("permissions", {})
        assert perms.get("id-token") != "write", f"{name} must not mint an OIDC token"


def test_validate_promotes_without_rebuild() -> None:
    """The validate gate re-verifies retained bytes; it never builds or publishes."""
    validate = _document()["jobs"]["validate"]
    surface = _run_surface(validate)
    assert "dev.release.promote_python_cohort" in surface
    assert "dev.release.readiness" in surface
    assert "cadrumo-release-cohort" in surface
    # The per-OS smoke build artifact never enters the publication chain; the
    # promotion guard is re-pointed at the sealed cohort's python bytes, and the
    # sealed cohort's installed behaviour is proven by the DistributionEvidence
    # rows the readiness gate reads.
    assert "--name cadrumo-python-cohort" not in surface
    assert "--check-pypi-only" in surface
    # Every channel's rows arrive hash-verified from its evidence draft.
    assert "dev.packaging.evidence_release verify" in surface
    # No publish verb in the read-only validate gate.
    assert "uv publish" not in surface
    assert "gh release create" not in surface


def test_validate_aggregates_all_twelve_rows_from_authoritative_sources() -> None:
    """Gate 2 pulls every channel's rows from its own run and re-checks 12/12, no weakening."""
    validate = _document()["jobs"]["validate"]
    surface = _run_surface(validate)

    # Each channel's rows come verified from its authoritative run's evidence
    # draft; the tags are DERIVED from the run-id inputs (no free-form evidence
    # tag input except the operator's claude release, which has no backing run).
    assert 'verify "evidence-smoke-$PACKAGING_RUN_ID"    "$PACKAGING_RUN_ID"' in surface
    assert 'verify "evidence-scoop-$SCOOP_RUN_ID"        "$SCOOP_RUN_ID"' in surface
    assert 'verify "evidence-homebrew-$HOMEBREW_RUN_ID"  "$HOMEBREW_RUN_ID"' in surface
    assert 'gh release download "$CLAUDE_EVIDENCE_RELEASE"' in surface

    # Trusted-source predicate on the smoke run (ci-speed redesign): a
    # dispatch-event campaign run is accepted only when its commit is verified
    # on main history via the compare API; push stays accepted for historical
    # campaign runs.
    assert '"$event" = "workflow_dispatch"' in surface
    assert "/compare/main..." in surface
    assert 'test "$ancestry" = "identical" -o "$ancestry" = "behind"' in surface

    # Per-source identity checks on the acquisition runs (parity with the smoke gate).
    assert ".github/workflows/packaging-scoop.yml" in surface
    assert ".github/workflows/packaging-homebrew.yml" in surface
    assert 'event <<<"$run_json")" = "workflow_dispatch"' in surface
    assert 'head_repository.full_name <<<"$run_json")" = "$GITHUB_REPOSITORY"' in surface

    # The readiness gate still enforces the complete bound row set (no weakening).
    assert "dev.release.readiness" in surface
    assert "--evidence-dir" in surface


def test_pypi_ships_the_sealed_cohort_not_the_per_os_smoke_build() -> None:
    """Every PyPI upload path resolves under the sealed release cohort's python dir."""
    publish = _document()["jobs"]["publish"]
    surface = _run_surface(publish)
    # The per-OS smoke build (cadrumo-python-cohort) is out of the publish chain.
    assert "--name cadrumo-python-cohort" not in surface
    # Each of the six wheels/sdists is uploaded from RELEASE_COHORT_DIR/python.
    for artifact in (
        'cadrumo-"$VERSION"-py3-none-any.whl',
        'cadrumo-"$VERSION".tar.gz',
        'cadrumo_data_manuals-"$VERSION"-py3-none-any.whl',
        'cadrumo_data_manuals-"$VERSION".tar.gz',
        'cadrumo_data_official-"$VERSION"-py3-none-any.whl',
        'cadrumo_data_official-"$VERSION".tar.gz',
    ):
        assert f'"$RELEASE_COHORT_DIR"/python/{artifact}' in surface


def test_no_job_ever_builds_or_regenerates_an_artifact() -> None:
    """Promotion moves stored bytes; a build/regenerate invocation is forbidden anywhere."""
    document = _document()
    offenders: dict[str, list[str]] = {}
    for job_name, job in document["jobs"].items():
        surface = _run_surface(job)
        hits = [" ".join(m.group(0).split()) for pattern in _BUILD_RUN_PATTERNS for m in pattern.finditer(surface)]
        if hits:
            offenders[job_name] = hits
    assert offenders == {}, f"publication must never build/regenerate: {offenders}"


def test_external_channel_pushes_refuse_instructively_when_unconfigured() -> None:
    """Scoop and Homebrew pushes fail closed with instructions when credentials are absent."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "REFUSED: Scoop bucket not configured" in surface
    assert "REFUSED: Homebrew tap not configured" in surface
    assert "CADRUMO_SCOOP_BUCKET_TOKEN" in surface
    assert "CADRUMO_HOMEBREW_TAP_TOKEN" in surface


def test_publish_uploads_the_stored_cohort_via_trusted_publishing() -> None:
    """The publish job promotes stored wheels via OIDC Trusted Publishing and a GH release."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "uv publish --trusted-publishing always" in surface
    assert "gh release create" in surface
    # It re-downloads and re-verifies the stored cohort rather than rebuilding.
    assert "dev.packaging.evidence_release verify" in surface
    assert '--pattern "cadrumo-release-cohort.tar.gz"' in surface
    # D8: the published release also carries the verified rows and the three
    # per-lane manifests, so draft GC can never orphan a shipped audit trail.
    assert "evidence-manifest-$4.json" in surface
    assert '"$EVIDENCE_FINAL_DIR/attach"' in surface


def test_github_release_refuses_colliding_asset_basenames() -> None:
    """Gh flattens assets to basename, so a collision guard runs before the release create."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "uniq -d" in surface
    assert "colliding asset basenames" in surface
    # The hard guard precedes the actual release invocation, so a clobbered asset
    # cannot ship. Anchor on the versioned invocation, not the explanatory comment.
    assert surface.index("colliding asset basenames") < surface.index('gh release create "v$VERSION"')


def test_no_workflow_consumes_per_os_cohort_for_publication() -> None:
    """The retired stub is gone and the sole publication authority never pulls a per-OS cohort."""
    workflows = _REPO_ROOT / ".github" / "workflows"
    # publish.yml (the validate-only stub that downloaded the per-OS cohort and
    # carried that publication defect class) is retired outright.
    assert not (workflows / "publish.yml").exists()

    # The sole publication authority downloads ONLY the sealed cohort: no step in
    # any job names a per-OS smoke cohort artifact, via gh run download or the
    # download-artifact action.
    document = _document()
    for job_name, job in document["jobs"].items():
        steps = job["steps"] if isinstance(job.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            run = str(step.get("run", ""))
            assert "--name cadrumo-python-cohort" not in run, job_name
            uses = str(step.get("uses", ""))
            with_block = step.get("with", {})
            if "download-artifact" in uses and isinstance(with_block, Mapping):
                name = str(with_block.get("name", ""))
                assert not name.startswith("cadrumo-python-cohort"), job_name
