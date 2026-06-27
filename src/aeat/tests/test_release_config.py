"""Tripwire tests for the release-please LOCAL-only workflow (aeat#60).

These tests validate the project-meta files that drive `just release`:

- ``release-please-config.json``
- ``.release-please-manifest.json``
- ``CHANGELOG.md``
- the three version surfaces (``pyproject.toml``,
  ``src/aeat/__init__.py``, ``.release-please-manifest.json``)
  agree.

The test lives in ``src/aeat/tests/`` rather than alongside any
``aeat.*`` runtime subpackage because it validates project-meta
files that do not belong to a runtime module.

Per the project pydantic mandate, the JSON payloads are parsed into
strict pydantic v2 models so typos in either config file are caught
as test failures rather than silent drift.
"""

from __future__ import annotations

import json
import re
import tomllib

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ._inventory import repo_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

CONFIG_PATH = repo_path("release-please-config.json")
MANIFEST_PATH = repo_path(".release-please-manifest.json")
CHANGELOG_PATH = repo_path("CHANGELOG.md")
PYPROJECT_PATH = repo_path("pyproject.toml")
INIT_PATH = repo_path("src/aeat/__init__.py")


class ChangelogSection(BaseModel):
    """One entry in ``release-please-config.json``'s changelog-sections list."""

    model_config = ConfigDict(extra="forbid")

    type: str
    section: str
    hidden: bool = False


class ReleasePleasePackage(BaseModel):
    """Per-package block under ``packages`` in the release-please config."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(alias="package-name")
    release_type: str = Field(alias="release-type")
    changelog_path: str = Field(alias="changelog-path")
    extra_files: list[str] = Field(default_factory=list, alias="extra-files")


class ReleasePleaseConfig(BaseModel):
    """Full shape of ``release-please-config.json``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    release_type: str = Field(alias="release-type")
    include_component_in_tag: bool = Field(alias="include-component-in-tag")
    separate_pull_requests: bool = Field(alias="separate-pull-requests")
    draft: bool
    prerelease: bool
    changelog_path: str = Field(alias="changelog-path")
    packages: dict[str, ReleasePleasePackage]
    changelog_sections: list[ChangelogSection] = Field(alias="changelog-sections")


class ReleasePleaseManifest(BaseModel):
    """Full shape of ``.release-please-manifest.json``."""

    model_config = ConfigDict(extra="forbid")

    root: str = Field(alias=".")


_VERSION_RE = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def _read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _read_init_version() -> str:
    match = _VERSION_RE.search(INIT_PATH.read_text(encoding="utf-8"))
    assert match, f"__version__ not found in {INIT_PATH}"
    return match.group(1)


def test_release_please_config_is_well_formed() -> None:
    """``release-please-config.json`` parses as the strict pydantic model."""
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = ReleasePleaseConfig.model_validate(payload)

    assert config.release_type == "python"
    assert config.changelog_path == "CHANGELOG.md"
    assert "." in config.packages
    root_pkg = config.packages["."]
    assert root_pkg.package_name == "aeat"
    assert root_pkg.release_type == "python"
    assert "src/aeat/__init__.py" in root_pkg.extra_files

    types = {section.type for section in config.changelog_sections}
    # The project-relevant commit types must all have a rendering decision
    # (visible or hidden), never absent.
    required_types = {
        "feat",
        "fix",
        "perf",
        "revert",
        "docs",
        "refactor",
        "chore",
        "test",
        "build",
        "ci",
        "style",
    }
    missing = required_types - types
    assert not missing, f"changelog-sections missing types: {sorted(missing)}"


def test_release_please_manifest_is_well_formed() -> None:
    """``.release-please-manifest.json`` parses as the strict model."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Single-key manifest — no extra packages allowed.
    assert list(payload.keys()) == ["."], f"manifest must have exactly one key '.', got {list(payload.keys())!r}"
    manifest = ReleasePleaseManifest.model_validate(payload)
    assert manifest.root  # non-empty


def test_changelog_exists_and_non_empty() -> None:
    """``CHANGELOG.md`` exists at the repo root and is non-empty."""
    assert CHANGELOG_PATH.is_file(), f"{CHANGELOG_PATH} is missing"
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert text.strip(), "CHANGELOG.md is empty"
    assert "# Changelog" in text


def test_version_surfaces_agree() -> None:
    """pyproject.toml, ``__init__.py``, and the manifest agree on one version."""
    pyproject_version = _read_pyproject_version()
    init_version = _read_init_version()
    manifest_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_version = manifest_payload["."]

    assert pyproject_version == init_version == manifest_version, (
        f"version drift: pyproject={pyproject_version!r}, __init__={init_version!r}, manifest={manifest_version!r}"
    )


def test_no_release_please_github_actions_workflow() -> None:
    """GitHub Actions is disabled on this repo — no release-please workflow may exist."""
    workflow = repo_path(".github/workflows/release-please.yml")
    assert not workflow.exists(), (
        f"{workflow} must not exist: release-please runs LOCALLY only on this repo "
        "(GitHub Actions is permanently disabled)."
    )
