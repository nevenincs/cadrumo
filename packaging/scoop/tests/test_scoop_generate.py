"""Real-artifact tests for the generated Cadrumo Scoop manifest."""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from dev.packaging._hashing import sha256_path
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_sdist,
    build_wheel,
    commit_defined_build_root,
    run_checked,
)
from dev.packaging.python_cohort import attest_command_specs
from dev.packaging.uv_constraints import export_runtime_constraints

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATOR = _REPO_ROOT / "packaging" / "scoop" / "generate.py"


@dataclass(frozen=True)
class BuiltCohort:
    """One real closed-world cohort shared by Scoop generator tests."""

    directory: Path
    root: Path
    manuals: Path
    official: Path
    version: str


def _generator_command(cohort: BuiltCohort, *, cohort_dir: Path | None = None) -> list[str]:
    return [
        sys.executable,
        str(_GENERATOR),
        "--cohort-dir",
        str(cohort.directory if cohort_dir is None else cohort_dir),
        "--version",
        cohort.version,
    ]


def _copy_cohort(
    artifacts: tuple[Path, Path, Path],
    destination: Path,
) -> tuple[Path, Path, Path]:
    destination.mkdir()
    copied: list[Path] = []
    for artifact in artifacts:
        target = destination / artifact.name
        shutil.copy2(artifact, target)
        copied.append(target)
    return copied[0], copied[1], copied[2]


def _conditional_companion_pin_wheel(
    source: Path,
    destination: Path,
    *,
    version: str,
) -> None:
    with zipfile.ZipFile(source) as source_archive:
        members = tuple(source_archive.infolist())
        metadata_members = tuple(member for member in members if member.filename.endswith(".dist-info/METADATA"))
        assert len(metadata_members) == 1
        metadata_name = metadata_members[0].filename
        original = f"Requires-Dist: cadrumo-data-manuals=={version}"
        replacement = f'{original}; sys_platform != "win32"'
        metadata = source_archive.read(metadata_name).decode("utf-8")
        assert metadata.count(original) == 1
        rewritten = metadata.replace(original, replacement)
        with zipfile.ZipFile(destination, "w") as destination_archive:
            for member in members:
                payload = (
                    rewritten.encode("utf-8")
                    if member.filename == metadata_name
                    else source_archive.read(member.filename)
                )
                destination_archive.writestr(member, payload)


@pytest.fixture(scope="module")
def built_cohort(tmp_path_factory: pytest.TempPathFactory) -> BuiltCohort:
    """Build one real command-and-companion wheel cohort."""
    uv = shutil.which("uv")
    assert uv is not None
    root_dir = tmp_path_factory.mktemp("scoop-cohort")
    build_dir = root_dir / "build"
    # Build from a commit-defined root, not the working tree: in the shared
    # worktree a peer's uncommitted edit would otherwise ride into the wheels,
    # and the manifest this test asserts on would describe bytes matching no
    # commit. On a clean checkout this IS the tree, so CI pays nothing.
    # ``build_wheel`` still takes the real repository as well, because its
    # tracked-data queries need Git and the extract has no ``.git``.
    build_root = commit_defined_build_root(_REPO_ROOT, build_dir)
    root = build_wheel(_REPO_ROOT, build_dir, uv, build_root=build_root)
    manuals, official = build_companion_wheels(build_dir, uv, build_root=build_root)
    cohort_dir = root_dir / "cohort"
    copied_root, copied_manuals, copied_official = _copy_cohort(
        (root, manuals, official),
        cohort_dir,
    )
    root_sdist = build_sdist(build_dir, uv, build_root=build_root)
    companion_sdists = build_dir / "companion-sdists"
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=build_root / "packaging/cadrumo_data_manuals",
    )
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=build_root / "packaging/cadrumo_data_official",
    )
    copied_sdists = []
    for artifact in (root_sdist, *sorted(companion_sdists.glob("*.tar.gz"))):
        target = cohort_dir / artifact.name
        shutil.copy2(artifact, target)
        copied_sdists.append(target)
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    artifacts = {
        "cadrumo": copied_root.name,
        "cadrumo-sdist": copied_sdists[0].name,
        "cadrumo-data-manuals": copied_manuals.name,
        "cadrumo-data-manuals-sdist": next(path.name for path in copied_sdists if "manuals" in path.name),
        "cadrumo-data-official": copied_official.name,
        "cadrumo-data-official-sdist": next(path.name for path in copied_sdists if "official" in path.name),
    }
    source_archive = cohort_dir / f"cadrumo-source-{'a' * 40}.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("pyproject.toml", "[project]\nname='cadrumo'\n")
    artifacts["source-archive"] = source_archive.name
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "sha256": {name: sha256_path(cohort_dir / filename) for name, filename in artifacts.items()},
                "source_commit": "a" * 40,
                "version": version,
                "command_spec_attestation": attest_command_specs(
                    site_root=build_root / "src",
                    root_wheel=copied_root,
                    root_sdist=copied_sdists[0],
                    source_archive=source_archive,
                    source_commit="a" * 40,
                    work_root=root_dir,
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return BuiltCohort(
        directory=cohort_dir,
        root=copied_root,
        manuals=copied_manuals,
        official=copied_official,
        version=version,
    )


def test_generated_manifest_binds_exact_cohort_and_the_cli_command(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Require deterministic Scoop material for the exact real cohort."""

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = _generator_command(built_cohort)
    run_checked([*command, "--output", str(first)], cwd=_REPO_ROOT)
    run_checked([*command, "--output", str(second)], cwd=_REPO_ROOT)
    assert first.read_bytes() == second.read_bytes()

    manifest = json.loads(first.read_text(encoding="utf-8"))
    assert manifest["version"] == built_cohort.version
    assert "post_install" not in manifest
    # No download block: the manifest installs what the index serves, by name
    # and exact version. Only a source distribution has a stable address on the
    # index ahead of an upload, so a wheel URL here could only be a release
    # asset -- a surface no workflow populates.
    assert "architecture" not in manifest
    install = "\n".join(manifest["pre_install"])
    assert f"'cadrumo=={built_cohort.version}'" in install
    assert "releases/download" not in json.dumps(manifest)
    assert manifest["depends"] == ["python", "uv"]
    # The manifest exposes only the product CLI.
    assert manifest["bin"] == [["aeat.cmd", "aeat"]]
    assert manifest["persist"] == ["state"]

    hooks = manifest["pre_install"]
    assert len(hooks) == 6
    assert "Join-Path $dir 'state'" in hooks[0]
    assert "uv venv" in hooks[1]
    # The transitive dependency closure is pinned from the tested uv.lock: a
    # constraints file is written to the app dir and fed to uv pip install.
    assert "Set-Content" in hooks[2]
    assert "constraints.txt" in hooks[2]
    assert "==" in hooks[2]
    assert built_cohort.root.name in hooks[3]
    # The retired cadrumo[agent] extra is gone: the cohort wheels install
    # without any extra, and the launcher pin no longer rides the root wheel.
    assert "[agent]" not in hooks[3]
    assert "--constraint (Join-Path $dir 'constraints.txt')" in hooks[3]
    assert built_cohort.manuals.name in hooks[3]
    assert built_cohort.official.name in hooks[3]
    assert "uv pip check" in hooks[4]
    assert sum("$LASTEXITCODE -ne 0" in hook for hook in hooks) == 3
    hook = hooks[5]
    assert 'if not defined CADRUMO_LOCAL_STORAGE_ROOT set `"CADRUMO_LOCAL_STORAGE_ROOT=$state`"' in hook
    assert "venv\\Scripts\\aeat.exe" in hook
    assert "%*" in hook
    assert "Join-Path $dir 'aeat.cmd'" in hook
    assert "-NoNewline -Encoding ascii" in hook


def test_manifest_pins_transitive_closure_from_lock(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """The written constraints closure is the exact tested uv.lock export."""
    output = tmp_path / "manifest.json"
    run_checked(
        [*_generator_command(built_cohort), "--output", str(output)],
        cwd=_REPO_ROOT,
    )
    manifest = json.loads(output.read_text(encoding="utf-8"))
    write_hook = manifest["pre_install"][2]
    install_hook = manifest["pre_install"][3]

    expected = export_runtime_constraints(repo_root=_REPO_ROOT)
    assert expected
    for line in expected:
        assert "==" in line
        assert line in write_hook
    # The pinned file must actually gate the install, not merely be written.
    assert "--constraint (Join-Path $dir 'constraints.txt')" in install_hook


def test_generator_rejects_missing_and_duplicate_wheels(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Require exactly one artifact for every cohort distribution."""
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    shutil.copy2(built_cohort.root, missing_dir / built_cohort.root.name)
    shutil.copy2(built_cohort.manuals, missing_dir / built_cohort.manuals.name)
    with pytest.raises(SystemExit):
        run_checked(
            [
                *_generator_command(built_cohort, cohort_dir=missing_dir),
                "--output",
                str(tmp_path / "missing.json"),
            ],
            cwd=_REPO_ROOT,
        )

    duplicate_dir = tmp_path / "duplicate"
    _copy_cohort(
        (built_cohort.root, built_cohort.manuals, built_cohort.official),
        duplicate_dir,
    )
    shutil.copy2(
        built_cohort.manuals,
        duplicate_dir / f"cadrumo_data_manuals-{built_cohort.version}-duplicate.whl",
    )
    with pytest.raises(SystemExit):
        run_checked(
            [
                *_generator_command(built_cohort, cohort_dir=duplicate_dir),
                "--output",
                str(tmp_path / "duplicate.json"),
            ],
            cwd=_REPO_ROOT,
        )


def test_generator_rejects_distribution_and_version_mismatches(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Reject a renamed foreign companion and a requested version mismatch."""
    foreign_dir = tmp_path / "foreign"
    foreign_dir.mkdir()
    shutil.copy2(built_cohort.root, foreign_dir / built_cohort.root.name)
    shutil.copy2(
        built_cohort.official,
        foreign_dir / built_cohort.manuals.name,
    )
    shutil.copy2(built_cohort.official, foreign_dir / built_cohort.official.name)
    with pytest.raises(SystemExit):
        run_checked(
            [
                *_generator_command(built_cohort, cohort_dir=foreign_dir),
                "--output",
                str(tmp_path / "foreign.json"),
            ],
            cwd=_REPO_ROOT,
        )

    command = _generator_command(built_cohort)
    command[command.index("--version") + 1] = "999.0.0"
    with pytest.raises(SystemExit):
        run_checked([*command, "--output", str(tmp_path / "version.json")], cwd=_REPO_ROOT)


def test_generator_rejects_conditional_companion_pin(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Reject a root artifact that makes a mandatory companion conditional."""
    conditional_dir = tmp_path / "conditional"
    conditional_dir.mkdir()
    _conditional_companion_pin_wheel(
        built_cohort.root,
        conditional_dir / built_cohort.root.name,
        version=built_cohort.version,
    )
    shutil.copy2(built_cohort.manuals, conditional_dir / built_cohort.manuals.name)
    shutil.copy2(built_cohort.official, conditional_dir / built_cohort.official.name)
    with pytest.raises(SystemExit):
        run_checked(
            [
                *_generator_command(built_cohort, cohort_dir=conditional_dir),
                "--output",
                str(tmp_path / "conditional.json"),
            ],
            cwd=_REPO_ROOT,
        )
