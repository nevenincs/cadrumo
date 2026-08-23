"""Regression gates for the base-product/external-client release boundary."""

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_BASE_RELEASE_SURFACES = (
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("justfile"),
    Path("dev/packaging/python_cohort.py"),
    Path("dev/packaging/release_cohort.py"),
    Path("dev/packaging/cohort_manifest.py"),
    Path("dev/packaging/oracle_emit_cohort.py"),
    Path("dev/packaging/acquire_pypi.py"),
    Path("dev/packaging/publication_inputs.py"),
    Path("dev/release/readiness.py"),
    Path("dev/release/version_bump.py"),
    Path("dev/release/release_candidate.py"),
    Path("dev/release/seal_candidate.py"),
    Path("dev/release/soak_promoter.py"),
    Path(".github/workflows/packaging-smoke.yml"),
    Path(".github/workflows/release-orchestrator.yml"),
    Path(".github/workflows/publish-release.yml"),
    Path(".github/workflows/ci-full.yml"),
    Path("RELEASING.md"),
)

_EXTERNAL_CLIENT_MARKERS = (
    "cadrumo-harness",
    "cadrumo_harness",
    "cadrumo-mcp",
    "mcpb",
    "claude-plugin",
    "claude_marketplace",
    "claude-marketplace",
    "marketplace",
    "packaging-claude",
    "claude_evidence",
    "smoke_desktop_client",
)


@pytest.mark.parametrize("relative", _BASE_RELEASE_SURFACES)
def test_base_release_surface_cannot_name_the_external_client(relative: Path) -> None:
    """The product release graph has no build, evidence, or publication knowledge of its clients."""
    text = (REPO_ROOT / relative).read_text(encoding="utf-8").lower()
    present = tuple(marker for marker in _EXTERNAL_CLIENT_MARKERS if marker in text)
    assert not present, f"{relative} crosses the external-client boundary: {present!r}"


def test_external_client_workflows_are_not_product_workflows() -> None:
    """Client-owned CI entry points cannot survive in the base repository."""
    assert not (REPO_ROOT / ".github/workflows/packaging-claude.yml").exists()
    assert not (REPO_ROOT / ".github/workflows/agent-harness-eval.yml").exists()
