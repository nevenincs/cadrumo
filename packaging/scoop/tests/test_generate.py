"""Real-artifact tests for the generated Cadrumo Scoop manifest."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from dev.packaging.smoke_core import _build_companion_wheels, _build_wheel, _run

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATOR = _REPO_ROOT / "packaging" / "scoop" / "generate.py"


@dataclass(frozen=True)
class BuiltCohort:
    """One real three-wheel cohort shared by Scoop generator tests."""

    directory: Path
    root: Path
    manuals: Path
    official: Path
    version: str
    release_base: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generator_command(cohort: BuiltCohort, *, cohort_dir: Path | None = None) -> list[str]:
    return [
        sys.executable,
        str(_GENERATOR),
        "--cohort-dir",
        str(cohort.directory if cohort_dir is None else cohort_dir),
        "--version",
        cohort.version,
        "--release-base-url",
        cohort.release_base,
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
    root = _build_wheel(_REPO_ROOT, build_dir, uv)
    manuals, official = _build_companion_wheels(_REPO_ROOT, build_dir, uv)
    cohort_dir = root_dir / "cohort"
    copied_root, copied_manuals, copied_official = _copy_cohort(
        (root, manuals, official),
        cohort_dir,
    )
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    release_base = f"https://github.com/nevenincs/cadrumo/releases/download/v{version}"
    return BuiltCohort(
        directory=cohort_dir,
        root=copied_root,
        manuals=copied_manuals,
        official=copied_official,
        version=version,
        release_base=release_base,
    )


def test_generated_manifest_binds_exact_cohort_and_both_commands(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Require deterministic Scoop material for the exact real cohort."""
    artifacts = (built_cohort.root, built_cohort.manuals, built_cohort.official)

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = _generator_command(built_cohort)
    _run([*command, "--output", str(first)], cwd=_REPO_ROOT)
    _run([*command, "--output", str(second)], cwd=_REPO_ROOT)
    assert first.read_bytes() == second.read_bytes()

    manifest = json.loads(first.read_text(encoding="utf-8"))
    assert manifest["version"] == built_cohort.version
    assert "post_install" not in manifest
    assert set(manifest["architecture"]) == {"64bit"}
    architecture = manifest["architecture"]["64bit"]
    assert architecture["url"] == [f"{built_cohort.release_base}/{artifact.name}" for artifact in artifacts]
    assert architecture["hash"] == [_sha256(artifact) for artifact in artifacts]
    assert manifest["depends"] == ["python", "uv"]
    assert manifest["bin"] == [["aeat.cmd", "aeat"], ["cadrumo-mcp.cmd", "cadrumo-mcp"]]
    assert manifest["persist"] == ["state"]

    hooks = manifest["pre_install"]
    assert len(hooks) == 6
    assert "Join-Path $dir 'state'" in hooks[0]
    assert "uv venv" in hooks[1]
    assert built_cohort.root.name in hooks[2]
    assert "'[agent]'" in hooks[2]
    assert built_cohort.manuals.name in hooks[2]
    assert built_cohort.official.name in hooks[2]
    assert "uv pip check" in hooks[3]
    assert sum("$LASTEXITCODE -ne 0" in hook for hook in hooks) == 3
    for executable, hook in zip(("aeat", "cadrumo-mcp"), hooks[4:], strict=True):
        assert ('if not defined CADRUMO_LOCAL_STORAGE_ROOT set `"CADRUMO_LOCAL_STORAGE_ROOT=$state`"') in hook
        assert f"venv\\Scripts\\{executable}.exe" in hook
        assert "%*" in hook
        assert f"Join-Path $dir '{executable}.cmd'" in hook
        assert "-NoNewline -Encoding ascii" in hook


@pytest.mark.parametrize(
    "release_base",
    [
        "http://github.com/nevenincs/cadrumo/releases/download/v0.2.1",
        "https://github.com/nevenincs/cadrumo/releases/latest/download",
        "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1?mutable=1",
    ],
)
def test_generator_rejects_mutable_release_urls(
    tmp_path: Path,
    built_cohort: BuiltCohort,
    release_base: str,
) -> None:
    """Require immutable HTTPS acquisition URLs."""
    command = _generator_command(built_cohort)
    command[command.index("--release-base-url") + 1] = release_base
    with pytest.raises(SystemExit):
        _run([*command, "--output", str(tmp_path / "manifest.json")], cwd=_REPO_ROOT)


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
        _run(
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
        _run(
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
        _run(
            [
                *_generator_command(built_cohort, cohort_dir=foreign_dir),
                "--output",
                str(tmp_path / "foreign.json"),
            ],
            cwd=_REPO_ROOT,
        )

    command = _generator_command(built_cohort)
    command[command.index("--version") + 1] = "999.0.0"
    command[command.index("--release-base-url") + 1] = "https://github.com/nevenincs/cadrumo/releases/download/v999.0.0"
    with pytest.raises(SystemExit):
        _run([*command, "--output", str(tmp_path / "version.json")], cwd=_REPO_ROOT)


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
        _run(
            [
                *_generator_command(built_cohort, cohort_dir=conditional_dir),
                "--output",
                str(tmp_path / "conditional.json"),
            ],
            cwd=_REPO_ROOT,
        )
