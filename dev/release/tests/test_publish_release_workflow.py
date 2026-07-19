"""Structural proof that the real publication authority stays fail-closed.

``publish-release.yml`` is the sole upload authority (unlike the retained
diagnostic ``publish.yml``). These tests pin its safety contract: it is inert
until the operator opts in, it never builds or regenerates an artifact, OIDC
minting is confined to the environment-protected publish job, and every external
channel push refuses instructively when its credential is absent.
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
    }
    assert document["permissions"] == {"contents": "read"}
    assert set(document["jobs"]) == {"operator-preflight", "validate", "publish"}


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
    assert "cadrumo-distribution-evidence-" in surface
    # No publish verb in the read-only validate gate.
    assert "uv publish" not in surface
    assert "gh release create" not in surface


def test_validate_aggregates_all_twelve_rows_from_authoritative_sources() -> None:
    """Gate 2 pulls every channel's rows from its own run and re-checks 12/12, no weakening."""
    validate = _document()["jobs"]["validate"]
    surface = _run_surface(validate)

    # Each channel's rows come from its authoritative run/release.
    assert 'gh run download "$PACKAGING_RUN_ID"' in surface
    assert 'gh run download "$SCOOP_RUN_ID"' in surface
    assert 'gh run download "$HOMEBREW_RUN_ID"' in surface
    assert 'gh release download "$CLAUDE_EVIDENCE_RELEASE"' in surface

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
    # It re-downloads the stored cohort rather than rebuilding.
    assert "gh run download" in surface
