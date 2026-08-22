"""Real-behavior tests for the automated release version-bump executor.

Every case runs `apply_version` against real files on a real `tmp_path` tree,
mirroring the fixture shape `test_readiness.py` already established for the
same seven declaration surfaces, since the bump and the readiness gate that
checks its output must agree on what those surfaces are.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var

from .. import readiness, version_bump, version_identity

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
        f"# Changelog\n\n## [Unreleased]\n\n## [{prior_version}] - {prior_date}\n\n### Features\n- thing\n",
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


def _write_probe_uv(bin_dir: Path, *, fail_on: str | None = None) -> Path:
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
            f'#!/usr/bin/env bash\nif [ "$2" = "--check" ]; then\n  exit {check_exit}\nelse\n  exit {lock_exit}\nfi\n',
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_regenerate_and_verify_lock_runs_both_real_legs(tmp_path: Path) -> None:
    """A clean stub `uv` satisfies both `lock` and `lock --check` legs."""
    root = tmp_path / "repo"
    root.mkdir()
    probe_uv = _write_probe_uv(tmp_path / "bin")

    version_bump.regenerate_and_verify_lock(root, uv_executable=str(probe_uv))


def test_regenerate_and_verify_lock_refuses_when_lock_generation_fails(tmp_path: Path) -> None:
    """A real non-zero `uv lock` exit refuses with its captured output."""
    root = tmp_path / "repo"
    root.mkdir()
    probe_uv = _write_probe_uv(tmp_path / "bin", fail_on="lock")

    with pytest.raises(version_bump.VersionBumpError, match="lock"):
        version_bump.regenerate_and_verify_lock(root, uv_executable=str(probe_uv))


def test_regenerate_and_verify_lock_refuses_when_the_lock_check_fails(tmp_path: Path) -> None:
    """A real non-zero `uv lock --check` exit refuses -- a drifted lock is caught."""
    root = tmp_path / "repo"
    root.mkdir()
    probe_uv = _write_probe_uv(tmp_path / "bin", fail_on="check")

    with pytest.raises(version_bump.VersionBumpError, match="check"):
        version_bump.regenerate_and_verify_lock(root, uv_executable=str(probe_uv))


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
    probe_uv = _write_probe_uv(tmp_path / "bin")

    updates = version_bump.stage_bump(
        root,
        "2.0.0",
        changelog_block=_CHANGELOG_BLOCK,
        release_date="2026-08-02",
        uv_executable=str(probe_uv),
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
    probe_uv = _write_probe_uv(tmp_path / "bin", fail_on="check")

    with pytest.raises(version_bump.VersionBumpError, match="check"):
        version_bump.stage_bump(
            root,
            "2.0.0",
            changelog_block=_CHANGELOG_BLOCK,
            release_date="2026-08-02",
            uv_executable=str(probe_uv),
        )


def _git(root: Path, *args: str) -> str:
    """Run git in *root*, failing loudly with its stderr.

    Mirrors `dev/audit/tests/test_checkout_drift.py`'s `_git` helper: a real
    subprocess call against a real repository, with `core.autocrlf` pinned
    off so the fixture's checkout semantics do not depend on the
    contributor's global git config.
    """
    executable = shutil.which("git")
    assert executable is not None, "git must be on PATH for these cases to mean anything"
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only.
        [executable, "-c", "core.autocrlf=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _make_git_repo_root(tmp_path: Path, *, version: str = "1.2.3", manifest_floor: str | None = None) -> Path:
    """A real git repository, initialised and committed, at the given version.

    `manifest_floor` overrides the manifest's recorded version independent of
    the declared surfaces, so a below-floor case can be built without also
    building an inconsistent (and thus readiness-refused) surface set.
    """
    root = _make_repo_root(tmp_path, version=version)
    if manifest_floor is not None:
        (root / ".release-please-manifest.json").write_text(json.dumps({".": manifest_floor}), encoding="utf-8")
    # `commit_tag_and_push` stages `uv.lock` (retired manual bump checklist
    # step 9); in real orchestration `stage_bump` has already regenerated it
    # by the time this stage runs, so the fixture seeds a placeholder.
    (root / "uv.lock").write_text("# stub lock\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=bump@example.invalid", "-c", "user.name=bump", "commit", "-q", "-m", "seed")
    return root


def test_commit_tag_and_push_creates_a_local_commit_and_tag_without_pushing(tmp_path: Path) -> None:
    """Commit and annotated tag creation need no ambient Git identity."""
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="1.0.0")
    # A real diff to commit -- in real orchestration `stage_bump` has
    # already run and produced exactly this kind of change by the time this
    # stage runs.
    version_bump.apply_version(root, "2.0.0", changelog_block=_CHANGELOG_BLOCK, release_date="2026-08-02")

    empty_config_home = tmp_path / "empty-git-config"
    empty_config_home.mkdir()
    environment = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "HOME": str(empty_config_home),
        "USERPROFILE": str(empty_config_home),
        "XDG_CONFIG_HOME": str(empty_config_home),
    }
    invocation = subprocess.run(  # noqa: S603 - fixed interpreter and argument vector, no shell.
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from dev.release.version_bump import commit_tag_and_push; "
                "print(commit_tag_and_push(Path(__import__('sys').argv[1]), '2.0.0', "
                "repository='nevenincs/cadrumo', skip_network=True))"
            ),
            str(root),
        ],
        cwd=Path(__file__).resolve().parents[3],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert invocation.returncode == 0, invocation.stderr
    commit_sha = invocation.stdout.strip()

    assert commit_sha == _git(root, "rev-parse", "HEAD").strip()
    tags = _git(root, "tag", "-l").split()
    assert "v2.0.0" in tags
    log = _git(root, "log", "-1", "--format=%s")
    assert log.strip() == "chore(release): v2.0.0"
    author = _git(root, "log", "-1", "--format=%an <%ae>").strip()
    assert author == "cadrumo-release <release@cadrumo.invalid>"
    assert _git(root, "cat-file", "-t", "v2.0.0").strip() == "tag"
    tagger = _git(root, "for-each-ref", "refs/tags/v2.0.0", "--format=%(taggername) <%(taggeremail)>").strip()
    assert tagger == "cadrumo-release <<release@cadrumo.invalid>>"


def test_commit_tag_and_push_refuses_a_burned_version_before_any_commit(tmp_path: Path) -> None:
    """A version on the shipped burned ledger refuses -- no commit, no tag created."""
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="0.1.0")
    before_head = _git(root, "rev-parse", "HEAD").strip()

    with pytest.raises(version_identity.VersionIdentityError, match="burned"):
        version_bump.commit_tag_and_push(
            root,
            "0.2.0",
            repository="nevenincs/cadrumo",
            skip_network=True,
        )

    assert _git(root, "rev-parse", "HEAD").strip() == before_head
    assert "v0.2.0" not in _git(root, "tag", "-l").split()


def test_commit_tag_and_push_refuses_a_version_at_or_below_the_manifest_floor(tmp_path: Path) -> None:
    """A version at or below the recorded manifest floor refuses -- no commit, no tag created."""
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="3.0.0")
    before_head = _git(root, "rev-parse", "HEAD").strip()

    with pytest.raises(version_identity.VersionIdentityError, match="floor"):
        version_bump.commit_tag_and_push(
            root,
            "2.5.0",
            repository="nevenincs/cadrumo",
            skip_network=True,
        )

    assert _git(root, "rev-parse", "HEAD").strip() == before_head
    assert "v2.5.0" not in _git(root, "tag", "-l").split()


def test_commit_tag_and_push_refuses_when_git_is_unresolvable(tmp_path: Path) -> None:
    """A real environment with no resolvable `git` binary refuses instructively."""
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="1.0.0")
    missing = tmp_path / "definitely-not-git"

    with pytest.raises(version_bump.VersionBumpError, match="is not on PATH"):
        version_bump.commit_tag_and_push(
            root,
            "2.0.0",
            repository="nevenincs/cadrumo",
            git_executable=str(missing),
            skip_network=True,
        )


def test_run_release_please_dry_run_refuses_instructively_when_node_is_absent(tmp_path: Path) -> None:
    """OP-11: a real environment with no resolvable `node` refuses before touching npx.

    Blanks `PATH` (mirroring `test_readiness.py`'s `gh`-unresolvable case) so
    `shutil.which("node")` genuinely returns `None`, rather than mocking the
    resolver -- the refusal must fire from a real absence, not a stand-in for
    one.
    """
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    root = tmp_path / "repo"
    root.mkdir()

    with scoped_env_var("PATH", str(empty_path)), pytest.raises(version_bump.VersionBumpError) as excinfo:
        version_bump.run_release_please_dry_run(root, token="x", repository="nevenincs/cadrumo")  # noqa: S106

    message = str(excinfo.value)
    assert "node is not on PATH" in message
    # Names the provisioning action, not just the bare fact of absence.
    assert "OP-11" in message
    assert "provision" in message


def _write_probe_npx(bin_dir: Path, argv_path: Path) -> Path:
    """Write a real executable `npx` script that records its argv and exits 0.

    Mirrors `_write_probe_uv`/`test_readiness.py`'s `_write_probe_gh`
    pattern: a real, explicit-path stub exercised via a real subprocess call,
    not a mock standing in for the process boundary under test.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "npx.bat"
        script.write_text(f'@echo off\r\necho %* > "{argv_path}"\r\nexit /b 0\r\n', encoding="utf-8")
    else:
        script = bin_dir / "npx"
        script.write_text(f'#!/usr/bin/env bash\necho "$@" > "{argv_path}"\nexit 0\n', encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_release_please_dry_run_passes_repo_relative_config_and_manifest_paths(tmp_path: Path) -> None:
    """`--config-file`/`--manifest-file` must be repo-relative, never absolute local paths.

    `--repo-url` puts release-please into its GitHub-API remote-fetch
    manifest mode, where these flags are repo-relative STRINGS used to fetch
    the named files from `target_branch` via the API, not local filesystem
    paths. A live dispatch failed with "Missing required manifest config:
    <absolute path>" because an earlier version of this function joined
    `repo_root` onto them, producing a path that can never match anything in
    the fetched tree. `node` is required and genuinely present on the
    machine running this test (not mocked); only `npx` is a real, explicit-
    path stub, per the established probe pattern.
    """
    root = tmp_path / "repo"
    root.mkdir()
    argv_path = tmp_path / "npx-argv.txt"
    npx = _write_probe_npx(tmp_path / "bin", argv_path)

    version_bump.run_release_please_dry_run(
        root,
        token="x",  # noqa: S106
        repository="nevenincs/cadrumo",
        npx_executable=str(npx),
    )

    captured = argv_path.read_text(encoding="utf-8")
    assert "--config-file release-please-config.json" in captured
    assert "--manifest-file .release-please-manifest.json" in captured
    # The bug this proves fixed: the absolute repo_root must never appear.
    assert str(root) not in captured


def test_parse_computed_version_extracts_a_json_version_field() -> None:
    """A `"version": "X.Y.Z"` announcement in the debug log is extracted."""
    log = 'some debug noise\n{\n  "version": "2.4.0",\n  "notes": "..."\n}\nmore noise'

    assert version_bump.parse_computed_version(log) == "2.4.0"


def test_parse_computed_version_extracts_a_conventional_release_commit_line() -> None:
    """A `chore(main): release X.Y.Z` announcement in the debug log is extracted."""
    log = "√ Building pull requests\nWould create: chore(main): release 3.1.0\n"

    assert version_bump.parse_computed_version(log) == "3.1.0"


def test_parse_computed_version_refuses_on_an_unrecognised_log_shape() -> None:
    """A log carrying neither known announcement shape refuses rather than guessing."""
    log = "this log carries no version announcement release-please pattern recognises"

    with pytest.raises(version_bump.VersionBumpError, match="could not determine the computed version"):
        version_bump.parse_computed_version(log)


#: An excerpt of the REAL output from a live `release-please@16 release-pr
#: --dry-run --debug` run against `nevenincs/cadrumo` @ `ac6305809d`
#: (2026-08-02), trimmed to the summary/changelog-heading region. Captured
#: while verifying the `bootstrap-sha` addition; this is the log shape
#: `_VERSION_ANNOUNCEMENT_PATTERNS`'s first two entries are grounded against.
_REAL_DRY_RUN_LOG_EXCERPT = """\
Would open 1 pull requests
fork: false
title: chore: release main
branch: release-please--branches--main
draft: false
body: :robot: I have created a release *beep* *boop*
---


<details><summary>0.2.0</summary>

## [0.2.0](https://github.com/nevenincs/cadrumo/compare/v0.1.0...v0.2.0) (2026-08-02)


### Features

* **adapters:** extend external integration boundaries ([f547b5c](https://github.com/nevenincs/cadrumo/commit/f547b5c6ca6d593ea02e3ea748fcde35e1e41462))
"""


def test_parse_computed_version_extracts_from_a_real_captured_dry_run_log() -> None:
    """The parser correctly reads a real release-please success-path log.

    Unlike the synthetic-fixture cases above, this is not a guess at the
    output shape -- it is the shape a real live run actually produced. The
    pull-request title itself carries no version in this repo's current
    config (`pullRequestTitlePattern miss the part of '${version}'`, present
    verbatim in the real log though not asserted here), which is why the
    `<summary>`/changelog-heading patterns, not a title pattern, are what
    make this real log parseable at all.
    """
    assert version_bump.parse_computed_version(_REAL_DRY_RUN_LOG_EXCERPT) == "0.2.0"


def test_rehearse_bump_refuses_a_burned_version_and_leaves_the_real_root_untouched(tmp_path: Path) -> None:
    """A rehearsal proves what it claims: it catches a burned version before any real dispatch.

    Exercises the real seven-surface mutation, lock regeneration, parity
    re-check, and identity guard against a discarded COPY -- not a return
    immediately after computing the version, which could never surface this
    class of refusal at all.
    """
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="0.1.0")
    before_manifest = (root / ".release-please-manifest.json").read_text(encoding="utf-8")
    before_head = _git(root, "rev-parse", "HEAD").strip()
    probe_uv = _write_probe_uv(tmp_path / "bin")

    with pytest.raises(version_identity.VersionIdentityError, match="burned"):
        version_bump.rehearse_bump(
            root,
            "0.2.0",
            changelog_block=_CHANGELOG_BLOCK,
            release_date="2026-08-02",
            repository="nevenincs/cadrumo",
            uv_executable=str(probe_uv),
            skip_network=True,
        )

    # The real root: no surface written, no ref created, HEAD unmoved.
    assert (root / ".release-please-manifest.json").read_text(encoding="utf-8") == before_manifest
    assert _git(root, "rev-parse", "HEAD").strip() == before_head
    assert "v0.2.0" not in _git(root, "tag", "-l").split()


def test_rehearse_bump_succeeds_for_a_clean_version_and_still_leaves_the_real_root_untouched(
    tmp_path: Path,
) -> None:
    """A clean rehearsal runs the full chain without raising, and mutates nothing real.

    The positive control for the case above: proves the rehearsal genuinely
    exercises `stage_bump` and `commit_tag_and_push` (not a no-op that would
    trivially "pass" any version), while the real repository root is
    provably unaffected either way.
    """
    root = _make_git_repo_root(tmp_path, version="1.2.3", manifest_floor="1.0.0")
    before_manifest = (root / ".release-please-manifest.json").read_text(encoding="utf-8")
    before_head = _git(root, "rev-parse", "HEAD").strip()
    probe_uv = _write_probe_uv(tmp_path / "bin")

    version_bump.rehearse_bump(
        root,
        "2.0.0",
        changelog_block=_CHANGELOG_BLOCK,
        release_date="2026-08-02",
        repository="nevenincs/cadrumo",
        uv_executable=str(probe_uv),
        skip_network=True,
    )  # must not raise

    assert (root / ".release-please-manifest.json").read_text(encoding="utf-8") == before_manifest
    assert _git(root, "rev-parse", "HEAD").strip() == before_head
    assert "v2.0.0" not in _git(root, "tag", "-l").split()
