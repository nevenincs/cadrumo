"""Real-behaviour tests for the Cadrumo frontend deployment helper."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dev.deploy.frontend_static_site import (
    _INVALIDATION_PATHS,
    _PROTECTED_PREFIX_EXCLUDES,
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_URL,
    _build_site,
    _repo_root,
    _validate_site_artifacts,
)

pytestmark = [pytest.mark.hex_core, pytest.mark.unit]


def _run_publish_command(*, confirmation: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the actual publisher CLI without allowing it to reach AWS."""
    return subprocess.run(  # noqa: S603 -- fixed Python module and parametrized literal confirmations.
        [
            sys.executable,
            "-m",
            "dev.deploy.frontend_static_site",
            "publish",
            "--confirm",
            confirmation,
        ],
        cwd=_repo_root(),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("confirmation", ("publish-cadrumo-docs", "publish-cadrumo-frontend-now"))
def test_publish_command_requires_the_literal_frontend_confirmation(confirmation: str) -> None:
    """The CLI rejects every near-match before it can inspect local deploy tools."""
    completed = _run_publish_command(confirmation=confirmation, environment=os.environ.copy())

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "invalid choice" in completed.stderr
    assert "publish-cadrumo-frontend" in completed.stderr


@pytest.mark.parametrize("marker", ("CI", "GITHUB_ACTIONS"))
def test_publish_refuses_each_continuous_integration_marker_before_aws(marker: str) -> None:
    """The real CLI exits at the human gate without producing AWS command output."""
    environment = {name: value for name, value in os.environ.items() if name not in {"CI", "GITHUB_ACTIONS"}}
    environment[marker] = "1"

    completed = _run_publish_command(
        confirmation="publish-cadrumo-frontend",
        environment=environment,
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == f"Refusing Cadrumo documentation publish from CI: {marker}\n"


@pytest.fixture(scope="module")
def built_frontend_dist() -> Path:
    """Build the real Vite frontend once for deployment-artifact checks."""
    dist_root = _build_site(_repo_root())
    _validate_site_artifacts(dist_root)
    return dist_root


def test_vite_build_produces_a_deployable_landing_page(built_frontend_dist: Path) -> None:
    """The actual Vite build emits the root document and bundled runtime assets."""
    index_html = (built_frontend_dist / "index.html").read_text(encoding="utf-8")

    assert '<div id="root"></div>' in index_html
    assert "/assets/" in index_html


def test_validation_rejects_a_real_build_missing_a_required_artifact(
    built_frontend_dist: Path,
    tmp_path: Path,
) -> None:
    """Artifact validation rejects a damaged copy of genuine Vite output."""
    damaged_dist = tmp_path / "dist"
    shutil.copytree(built_frontend_dist, damaged_dist)
    (damaged_dist / "favicon.png").unlink()

    with pytest.raises(SystemExit, match=r"favicon\.png"):
        _validate_site_artifacts(damaged_dist)


def test_root_deployment_reserves_the_documentation_prefix() -> None:
    """The root publisher owns the site root and leaves the docs publisher its prefix."""
    assert f"{CANONICAL_SITE_URL}/docs" == CANONICAL_DOCS_BASE_URL
    assert _PROTECTED_PREFIX_EXCLUDES == ("docs/*",)
    assert "/" in _INVALIDATION_PATHS
    assert all(not path.startswith("/docs/") for path in _INVALIDATION_PATHS)
