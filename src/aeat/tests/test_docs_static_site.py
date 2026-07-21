"""Real-behaviour tests for the Cadrumo documentation deployment helper."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from dev.deploy.docs_static_site import (
    _REQUIRED_ARTIFACTS,
    CANONICAL_DOCS_BASE_URL,
    _repo_root,
    _run,
    _site_build_environment,
    _validate_site_artifacts,
)

pytestmark = [pytest.mark.hex_core, pytest.mark.unit]


def _write_site_artifacts(root: Path, *, sitemap_locations: list[str], include_index: bool) -> None:
    """Write a minimal rendered-site artifact set for deployment validation."""
    for artifact in _REQUIRED_ARTIFACTS:
        path = root / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact\n", encoding="utf-8")
    locations = "".join(f"<url><loc>{location}</loc></url>" for location in sitemap_locations)
    (root / "sitemap.xml").write_text(
        "<?xml version='1.0' encoding='utf-8'?><urlset>" + locations + "</urlset>",
        encoding="utf-8",
    )
    if include_index:
        index = root / "pagefind" / "index" / "en_abc.pf_index"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_bytes(b"generated-pagefind-index-data")


def test_deployment_build_environment_uses_pages_only_pagefind_index() -> None:
    """Public docs search rendered pages without the local custom record pass."""
    environment = _site_build_environment()

    assert environment["AEAT_DOCS_BASE_URL"] == CANONICAL_DOCS_BASE_URL
    assert environment["AEAT_DOCS_JOBS"] == "1"
    assert environment["AEAT_DOCS_PAGEFIND_MODE"] == "pages"


def test_streaming_run_exposes_child_stdout_and_stderr_live(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    """A strict build command exposes both child streams while it runs."""
    completed = _run(
        [
            sys.executable,
            "-c",
            "import sys; print('build-progress', flush=True); print('pagefind-progress', file=sys.stderr, flush=True)",
        ],
        cwd=tmp_path,
        stream_output=True,
    )

    captured = capfd.readouterr()

    assert completed.returncode == 0
    assert "build-progress" in captured.out
    assert "pagefind-progress" in captured.err


def test_validation_accepts_canonical_root_and_generated_pagefind_index(tmp_path: Path) -> None:
    """A deployable site has the canonical root and generated search chunks."""
    _write_site_artifacts(
        tmp_path,
        sitemap_locations=[f"{CANONICAL_DOCS_BASE_URL}/", f"{CANONICAL_DOCS_BASE_URL}/guide.html"],
        include_index=True,
    )

    _validate_site_artifacts(tmp_path)


def test_validation_rejects_sitemap_without_canonical_docs_root(tmp_path: Path) -> None:
    """A sitemap that omits the root cannot become the canonical deployment."""
    _write_site_artifacts(
        tmp_path,
        sitemap_locations=[f"{CANONICAL_DOCS_BASE_URL}/guide.html"],
        include_index=True,
    )

    with pytest.raises(SystemExit, match="canonical docs root"):
        _validate_site_artifacts(tmp_path)


def test_validation_rejects_pagefind_bundle_without_generated_index(tmp_path: Path) -> None:
    """A Pagefind runtime bundle alone is not an indexed documentation site."""
    _write_site_artifacts(
        tmp_path,
        sitemap_locations=[f"{CANONICAL_DOCS_BASE_URL}/"],
        include_index=False,
    )

    with pytest.raises(SystemExit, match="substantive generated index data"):
        _validate_site_artifacts(tmp_path)


@pytest.mark.parametrize("marker", ("CI", "GITHUB_ACTIONS"))
def test_publish_refuses_each_continuous_integration_marker(marker: str) -> None:
    """The publish command refuses a real child process marked as continuous integration."""
    environment = {name: value for name, value in os.environ.items() if name not in {"CI", "GITHUB_ACTIONS"}}
    environment[marker] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.deploy.docs_static_site",
            "publish",
            "--confirm",
            "publish-cadrumo-docs",
        ],
        cwd=_repo_root(),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == f"Refusing Cadrumo documentation publish from CI: {marker}\n"
