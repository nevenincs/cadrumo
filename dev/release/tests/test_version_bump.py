"""Real-behavior tests for the automated release version-bump executor.

Every case runs `apply_version` against real files on a real `tmp_path` tree,
mirroring the fixture shape `test_readiness.py` already established for the
same seven declaration surfaces, since the bump and the readiness gate that
checks its output must agree on what those surfaces are.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

from .. import readiness, version_bump

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


def _write_stub_uv(bin_dir: Path, *, fail_on: str | None = None) -> Path:
    """Write a real executable `uv` script that no-ops `lock`/`lock --check`.

    Mirrors the `_write_probe_gh` pattern `test_readiness.py` already uses for
    a real, explicit-path stub executable exercised via real subprocess calls
    (no PATH/PATHEXT resolution games, no Python-level mock standing in for
    the process boundary under test). ``fail_on`` names a subcommand
    (``"lock"`` or ``"check"``) that exits non-zero; every other invocation
    exits 0.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    lock_exit = 1 if fail_on == "lock" else 0
    check_exit = 1 if fail_on == "check" else 0
    if sys.platform.startswith("win"):
        script = bin_dir / "uv.bat"
        script.write_text(
            "@echo off\r\n"
            'if "%2"=="--check" (\r\n'
            f"  exit /b {check_exit}\r\n"
            ") else (\r\n"
            f"  exit /b {lock_exit}\r\n"
            ")\r\n",
            encoding="utf-8",
        )
    else:
        script = bin_dir / "uv"
        script.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$2" = "--check" ]; then\n'
            f"  exit {check_exit}\n"
            "else\n"
            f"  exit {lock_exit}\n"
            "fi\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_regenerate_and_verify_lock_runs_both_real_legs(tmp_path: Path) -> None:
    """A clean stub `uv` satisfies both `lock` and `lock --check` legs."""
    root = tmp_path / "repo"
    root.mkdir()
    stub = _write_stub_uv(tmp_path / "bin")

    version_bump.regenerate_and_verify_lock(root, uv_executable=str(stub))


def test_regenerate_and_verify_lock_refuses_when_lock_generation_fails(tmp_path: Path) -> None:
    """A real non-zero `uv lock` exit refuses with its captured output."""
    root = tmp_path / "repo"
    root.mkdir()
    stub = _write_stub_uv(tmp_path / "bin", fail_on="lock")

    with pytest.raises(version_bump.VersionBumpError, match="lock"):
        version_bump.regenerate_and_verify_lock(root, uv_executable=str(stub))


def test_regenerate_and_verify_lock_refuses_when_the_lock_check_fails(tmp_path: Path) -> None:
    """A real non-zero `uv lock --check` exit refuses -- a drifted lock is caught."""
    root = tmp_path / "repo"
    root.mkdir()
    stub = _write_stub_uv(tmp_path / "bin", fail_on="check")

    with pytest.raises(version_bump.VersionBumpError, match="check"):
        version_bump.regenerate_and_verify_lock(root, uv_executable=str(stub))


def test_regenerate_and_verify_lock_refuses_when_uv_is_unresolvable(tmp_path: Path) -> None:
    """A real environment with no resolvable `uv` binary refuses instructively."""
    root = tmp_path / "repo"
    root.mkdir()
    missing = tmp_path / "definitely-not-uv"

    with pytest.raises(version_bump.VersionBumpError, match="uv is not on PATH"):
        version_bump.regenerate_and_verify_lock(root, uv_executable=str(missing))


def test_verify_bump_passes_when_every_surface_agrees(tmp_path: Path) -> None:
    """A repo already bumped correctly on every surface passes the re-check."""
    root = _make_repo_root(tmp_path, version="2.0.0")

    version_bump.verify_bump(root)  # must not raise


def test_verify_bump_refuses_a_stale_surface(tmp_path: Path) -> None:
    """One surface left at the old version -- the transcription-error class -- refuses.

    Built directly against `check_version_surfaces_agree`'s own fixture shape
    (not through `apply_version`), so this proves the re-check catches a
    stale surface regardless of what produced it: a future `apply_version`
    defect, an interrupted partial write, or a hand edit.
    """
    root = _make_repo_root(tmp_path, version="2.0.0")
    # Corrupt exactly one of the seven surfaces back to the old version.
    stale = (root / "packaging" / "cadrumo_data_official" / "pyproject.toml").read_text(encoding="utf-8")
    (root / "packaging" / "cadrumo_data_official" / "pyproject.toml").write_text(
        stale.replace('version = "2.0.0"', 'version = "1.9.0"'),
        encoding="utf-8",
    )

    with pytest.raises(version_bump.VersionBumpError, match="post-bump readiness re-check failed"):
        version_bump.verify_bump(root)

    # Same fact, read straight from the readiness module this delegates to.
    check = readiness.check_version_surfaces_agree(root)
    assert check.passed is False


def test_stage_bump_composes_apply_lock_and_reverify(tmp_path: Path) -> None:
    """A clean stage_bump call updates every surface and leaves the lock verified."""
    root = _make_repo_root(tmp_path, version="1.2.3")
    stub = _write_stub_uv(tmp_path / "bin")

    updates = version_bump.stage_bump(
        root,
        "2.0.0",
        changelog_block=_CHANGELOG_BLOCK,
        release_date="2026-08-02",
        uv_executable=str(stub),
    )

    assert len(updates) == 7
    check = readiness.check_version_surfaces_agree(root)
    assert check.passed is True


def test_stage_bump_refuses_before_any_commit_when_the_lock_check_fails(tmp_path: Path) -> None:
    """A lock-check failure refuses `stage_bump` outright -- nothing downstream ever runs.

    `stage_bump` never touches git, so a raise here is itself the proof that
    no commit stage can follow: the caller's commit/tag/push code, which only
    runs after `stage_bump` RETURNS, never executes.
    """
    root = _make_repo_root(tmp_path, version="1.2.3")
    stub = _write_stub_uv(tmp_path / "bin", fail_on="check")

    with pytest.raises(version_bump.VersionBumpError, match="check"):
        version_bump.stage_bump(
            root,
            "2.0.0",
            changelog_block=_CHANGELOG_BLOCK,
            release_date="2026-08-02",
            uv_executable=str(stub),
        )
