"""Real-behavior tests for the automated release version-bump executor.

Every case runs `apply_version` against real files on a real `tmp_path` tree,
mirroring the fixture shape `test_readiness.py` already established for the
same seven declaration surfaces, since the bump and the readiness gate that
checks its output must agree on what those surfaces are.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import version_bump

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CHANGELOG_BLOCK = "### Features\n\n* **thing:** did the thing ([abc1234](https://example.invalid/abc1234))\n"


def _write_project(project_file: Path, *, name: str, version: str, extra: str = "") -> None:
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n{extra}', encoding="utf-8")


def _write_pyprojects(root: Path, version: str) -> None:
    _write_project(
        root / "pyproject.toml",
        name="cadrumo",
        version=version,
        extra=f'dependencies = [\n  "cadrumo-data-manuals=={version}",\n  "cadrumo-data-official=={version}",\n]\n',
    )
    _write_project(
        root / "packaging" / "cadrumo_data_manuals" / "pyproject.toml",
        name="cadrumo-data-manuals",
        version=version,
    )
    _write_project(
        root / "packaging" / "cadrumo_data_official" / "pyproject.toml",
        name="cadrumo-data-official",
        version=version,
    )


def _write_init(root: Path, version: str) -> None:
    init_dir = root / "src" / "cadrumo"
    init_dir.mkdir(parents=True, exist_ok=True)
    (init_dir / "__init__.py").write_text(
        f'"""Docstring."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )


def _write_manifest(root: Path, version: str) -> None:
    (root / ".release-please-manifest.json").write_text(json.dumps({".": version}), encoding="utf-8")


def _write_mcpb_manifest(root: Path, version: str = "0.0.0") -> None:
    manifest_dir = root / "packaging" / "mcpb"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")


def _write_changelog(root: Path, *, prior_version: str = "1.2.3", prior_date: str = "2026-07-04") -> None:
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n"
        f"## [{prior_version}] - {prior_date}\n\n### Features\n- thing\n",
        encoding="utf-8",
    )


def _make_repo_root(tmp_path: Path, *, version: str = "1.2.3") -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _write_pyprojects(root, version)
    _write_init(root, version)
    _write_manifest(root, version)
    _write_mcpb_manifest(root)
    _write_changelog(root, prior_version=version)
    return root


def test_apply_version_updates_all_seven_surfaces_individually(tmp_path: Path) -> None:
    """Every one of the seven surfaces carries the new version after the bump."""
    root = _make_repo_root(tmp_path, version="1.2.3")

    updates = version_bump.apply_version(
        root,
        "2.0.0",
        changelog_block=_CHANGELOG_BLOCK,
        release_date="2026-08-02",
    )

    assert len(updates) == 7
    relative_paths = [update.relative_path for update in updates]
    assert relative_paths == [
        version_bump.MANIFEST_RELATIVE,
        version_bump.ROOT_PYPROJECT_RELATIVE,
        version_bump.DATA_MANUALS_PYPROJECT_RELATIVE,
        version_bump.DATA_OFFICIAL_PYPROJECT_RELATIVE,
        version_bump.INIT_RELATIVE,
        version_bump.ROOT_PYPROJECT_RELATIVE,
        version_bump.CHANGELOG_RELATIVE,
    ]

    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))
    assert manifest["."] == "2.0.0"

    root_pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in root_pyproject
    assert '"cadrumo-data-manuals==2.0.0"' in root_pyproject
    assert '"cadrumo-data-official==2.0.0"' in root_pyproject

    manuals_pyproject = (root / "packaging" / "cadrumo_data_manuals" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in manuals_pyproject
    official_pyproject = (root / "packaging" / "cadrumo_data_official" / "pyproject.toml").read_text(
        encoding="utf-8",
    )
    assert 'version = "2.0.0"' in official_pyproject

    init_text = (root / "src" / "cadrumo" / "__init__.py").read_text(encoding="utf-8")
    assert '__version__ = "2.0.0"' in init_text

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.0.0] - 2026-08-02" in changelog
    assert _CHANGELOG_BLOCK.strip() in changelog
    # New section lands directly after Unreleased and before the prior release.
    assert changelog.index("## [2.0.0]") < changelog.index("## [1.2.3]")


def test_apply_version_leaves_the_mcpb_manifest_sentinel_untouched(tmp_path: Path) -> None:
    """The build-stamped `.mcpb` manifest is never one of the bumped surfaces."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    before = (root / "packaging" / "mcpb" / "manifest.json").read_text(encoding="utf-8")

    version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")

    after = (root / "packaging" / "mcpb" / "manifest.json").read_text(encoding="utf-8")
    assert after == before
    assert json.loads(after)["version"] == "0.0.0"


def test_apply_version_refuses_when_a_pyproject_carries_no_version_literal(tmp_path: Path) -> None:
    """A surface missing its expected literal refuses rather than silently skipping."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    (root / "packaging" / "cadrumo_data_manuals" / "pyproject.toml").write_text(
        '[project]\nname = "cadrumo-data-manuals"\n',
        encoding="utf-8",
    )

    with pytest.raises(version_bump.VersionBumpError, match="cadrumo_data_manuals"):
        version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")


def test_apply_version_refuses_when_a_pyproject_carries_two_version_literals(tmp_path: Path) -> None:
    """A surface with an ambiguous second match refuses rather than guessing which one."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    (root / "packaging" / "cadrumo_data_official" / "pyproject.toml").write_text(
        '[project]\nname = "cadrumo-data-official"\nversion = "1.2.3"\n\n[tool.other]\nversion = "1.2.3"\n',
        encoding="utf-8",
    )

    with pytest.raises(version_bump.VersionBumpError, match="cadrumo_data_official"):
        version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")


def test_apply_version_refuses_a_manifest_with_no_root_entry(tmp_path: Path) -> None:
    """A manifest missing the root '.' key refuses rather than inventing one."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    (root / ".release-please-manifest.json").write_text(json.dumps({"packages/other": "1.0.0"}), encoding="utf-8")

    with pytest.raises(version_bump.VersionBumpError, match="release-please-manifest"):
        version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")


def test_apply_version_refuses_a_changelog_with_no_unreleased_anchor(tmp_path: Path) -> None:
    """A changelog missing the Unreleased anchor refuses rather than appending blindly."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## [1.2.3] - 2026-07-04\n", encoding="utf-8")

    with pytest.raises(version_bump.VersionBumpError, match="Unreleased"):
        version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")


def test_apply_version_refuses_a_duplicate_changelog_section(tmp_path: Path) -> None:
    """Bumping to a version the changelog already documents refuses rather than duplicating it."""
    root = _make_repo_root(tmp_path, version="1.2.3")

    with pytest.raises(version_bump.VersionBumpError, match="already carries a section"):
        version_bump.apply_version(root, "1.2.3", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")
