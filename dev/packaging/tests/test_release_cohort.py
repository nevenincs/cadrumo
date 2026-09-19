"""Real archive tests for one-shot release-cohort construction."""

from __future__ import annotations

import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from dev._paths import REPO_ROOT
from dev.source_tree import content_digest, repository_files

from .. import release_cohort as release_cohort_module
from ..cohort_manifest import CohortManifest, SourceIdentity
from ..hashing import sha256_path
from ..python_cohort import PythonCohort
from ..release_cohort import (
    REQUIRED_PYTHON_VERSION,
    build_from_clean_source,
    build_release_cohort,
    deterministic_zip_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXACT_PYTHON: Final[str] = r"3\.\d+\.\d+"


class _CleanBuilderInvocationObservedError(RuntimeError):
    """Stop the harness after it has assembled the clean-child command."""


def _assert_clean_builder_invocation(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None,
    expected_source_digest: str,
) -> None:
    """Protect package imports, clean-source isolation, and digest binding."""
    assert argv[1:3] == ["-m", "dev.packaging.release_cohort"], (
        "clean release-cohort construction must invoke the package module"
    )
    assert cwd.name == "source"
    assert env is not None
    assert env["PYTHONPATH"] == os.pathsep.join((str(cwd / "src"), str(cwd)))
    assert argv[argv.index("--expected-source-digest") + 1] == expected_source_digest
    assert "--use-prepared-source" in argv
    assert "--defer-output-validation" in argv


def test_clean_builder_subprocess_is_package_correct_and_detector_bites(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The clean child keeps relative imports and the exact source assertion."""
    repo_root = tmp_path / "repo"
    (repo_root / "var").mkdir(parents=True)
    output = repo_root / "var" / "cohort"
    expected_source_digest = content_digest(repo_root, repository_files(repo_root))
    captured: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_run(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        captured.append((argv, cwd, env))
        if "build-clean" in argv:
            raise _CleanBuilderInvocationObservedError
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(release_cohort_module, "_run", fake_run)

    with pytest.raises(_CleanBuilderInvocationObservedError):
        build_release_cohort(
            repo_root=repo_root,
            output_dir=output,
        )

    child_calls = [call for call in captured if "build-clean" in call[0]]
    assert len(child_calls) == 1
    argv, cwd, env = child_calls[0]
    _assert_clean_builder_invocation(
        argv,
        cwd=cwd,
        env=env,
        expected_source_digest=expected_source_digest,
    )

    file_path_regression = list(argv)
    file_path_regression[1:3] = [str(cwd / "dev" / "packaging" / "release_cohort.py"), "build-clean"]
    with pytest.raises(AssertionError, match="package module"):
        _assert_clean_builder_invocation(
            file_path_regression,
            cwd=cwd,
            env=env,
            expected_source_digest=expected_source_digest,
        )


def test_direct_clean_builder_keeps_validation_and_snapshot_defaults() -> None:
    """Only the release parent can opt into its already-verified source path."""
    parser = release_cohort_module._parser()
    direct = parser.parse_args(
        [
            "build-clean",
            "--output",
            "staging",
            "--expected-source-digest",
            "a" * 64,
        ],
    )
    parent = parser.parse_args(
        [
            "build-clean",
            "--output",
            "staging",
            "--expected-source-digest",
            "a" * 64,
            "--use-prepared-source",
            "--defer-output-validation",
        ],
    )

    assert direct.use_prepared_source is False
    assert direct.defer_output_validation is False
    assert parent.use_prepared_source is True
    assert parent.defer_output_validation is True


def test_parent_defers_only_the_validation_it_repeats_after_the_move(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Direct clean builds load their output; parent builds defer to the final load."""
    output = tmp_path / "staging"
    output.mkdir()
    manifest_path = output / "release-cohort.json"
    manifest_path.write_text("{}", encoding="utf-8")
    manifest = CohortManifest.model_construct()
    loaded = release_cohort_module.LoadedReleaseCohort(output, manifest_path, manifest)
    calls: list[Path] = []

    def fake_load(directory: Path) -> object:
        calls.append(directory)
        return loaded

    monkeypatch.setattr(release_cohort_module, "load_release_cohort", fake_load)

    assert (
        release_cohort_module._complete_release_cohort(
            output=output,
            manifest_path=manifest_path,
            manifest=manifest,
            validate_output=True,
        )
        is loaded
    )
    deferred = release_cohort_module._complete_release_cohort(
        output=output,
        manifest_path=manifest_path,
        manifest=manifest,
        validate_output=False,
    )

    assert calls == [output]
    assert deferred.directory == output.resolve()
    assert deferred.manifest_path == manifest_path.resolve()
    assert deferred.manifest is manifest


def test_python_cohort_copy_checks_artifacts_without_reloading_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A copy is bound to the source cohort's digests without another archive parse."""
    source = tmp_path / "source"
    source.mkdir()
    filenames = {
        "cadrumo": "cadrumo-1.0.0-py3-none-any.whl",
        "cadrumo-sdist": "cadrumo-1.0.0.tar.gz",
        "source-archive": "cadrumo-source.zip",
        "runtime-wheelhouse": "cadrumo-runtime-wheelhouse.zip",
        "cadrumo-data-manuals": "cadrumo_data_manuals-1.0.0-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": "cadrumo_data_manuals-1.0.0.tar.gz",
        "cadrumo-data-official": "cadrumo_data_official-1.0.0-py3-none-any.whl",
        "cadrumo-data-official-sdist": "cadrumo_data_official-1.0.0.tar.gz",
    }
    artifacts = {name: source / filename for name, filename in filenames.items()}
    for name, artifact in artifacts.items():
        artifact.write_text(name, encoding="utf-8")
    manifest = source / "python-cohort.json"
    manifest.write_text("not parsed during transfer", encoding="utf-8")
    cohort = PythonCohort(
        directory=source,
        manifest=manifest,
        source_digest="a" * 64,
        version="1.0.0",
        root_wheel=artifacts["cadrumo"],
        root_sdist=artifacts["cadrumo-sdist"],
        source_archive=artifacts["source-archive"],
        runtime_wheelhouse=artifacts["runtime-wheelhouse"],
        runtime_wheelhouse_manifest={},
        manuals_wheel=artifacts["cadrumo-data-manuals"],
        manuals_sdist=artifacts["cadrumo-data-manuals-sdist"],
        official_wheel=artifacts["cadrumo-data-official"],
        official_sdist=artifacts["cadrumo-data-official-sdist"],
        sha256={name: sha256_path(artifact) for name, artifact in artifacts.items()},
    )

    copied = release_cohort_module._copy_python_cohort(cohort, tmp_path / "copied")

    assert copied.directory == (tmp_path / "copied").resolve()
    assert copied.manifest.read_text(encoding="utf-8") == "not parsed during transfer"
    assert copied.sha256 == cohort.sha256
    assert all(path.parent == copied.directory for path in copied.product_wheels)

    real_copytree = release_cohort_module.shutil.copytree

    def corrupting_copytree(origin: Path, destination: Path) -> Path:
        copied_directory = real_copytree(origin, destination)
        (destination / filenames["cadrumo"]).write_text("changed", encoding="utf-8")
        return copied_directory

    monkeypatch.setattr(release_cohort_module.shutil, "copytree", corrupting_copytree)
    with pytest.raises(SystemExit, match="copied Python cohort artifact digest mismatch"):
        release_cohort_module._copy_python_cohort(cohort, tmp_path / "corrupted")


_COMMIT: Final[str] = "0123456789abcdef0123456789abcdef01234567"


def test_clean_builder_subprocess_carries_the_requested_source_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The caller's commit reaches the clean child that stamps the manifest."""
    repo_root = tmp_path / "repo"
    (repo_root / "var").mkdir(parents=True)
    captured: list[list[str]] = []

    def fake_run(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, env
        captured.append(argv)
        raise _CleanBuilderInvocationObservedError

    monkeypatch.setattr(release_cohort_module, "_run", fake_run)

    with pytest.raises(_CleanBuilderInvocationObservedError):
        build_release_cohort(repo_root=repo_root, output_dir=repo_root / "var" / "cohort", source_commit=_COMMIT)

    assert len(captured) == 1
    argv = captured[0]
    assert argv[argv.index("--source-commit") + 1] == _COMMIT


@pytest.mark.parametrize(
    "commit",
    ["abc123", _COMMIT.upper(), f"{_COMMIT}0", "refs/heads/main"],
    ids=("short", "uppercase", "too-long", "ref-name"),
)
def test_release_cohort_refuses_a_malformed_source_commit(tmp_path: Path, commit: str) -> None:
    """Only a full commit identifier is stamped; anything else fails before building."""
    repo_root = tmp_path / "repo"
    (repo_root / "var").mkdir(parents=True)
    output = repo_root / "var" / "cohort"

    with pytest.raises(SystemExit, match="not a full lowercase commit identifier"):
        build_release_cohort(repo_root=repo_root, output_dir=output, source_commit=commit)

    assert not output.exists()


def test_source_identity_records_the_commit_and_refuses_a_malformed_one() -> None:
    """The manifest carries the source commit as a validated coordinate."""
    identity = SourceIdentity(source_digest="a" * 64, tag="v0.2.1", commit=_COMMIT)

    assert identity.commit == _COMMIT
    assert SourceIdentity(source_digest="a" * 64).commit is None
    with pytest.raises(ValidationError):
        SourceIdentity(source_digest="a" * 64, commit="abc123")


def test_deterministic_zip_preserves_real_tree_bytes(tmp_path: Path) -> None:
    """Repeated packaging changes neither archive bytes nor member payloads."""
    source = tmp_path / "payload"
    (source / "metadata").mkdir(parents=True)
    (source / "wheels").mkdir(parents=True)
    manifest = b'{"name":"cadrumo","version":"0.2.1"}\n'
    wheel = b"wheel-bytes\n"
    (source / "metadata" / "manifest.json").write_bytes(manifest)
    (source / "wheels" / "cadrumo.whl").write_bytes(wheel)

    first = deterministic_zip_tree(source, tmp_path / "first.zip")
    second = deterministic_zip_tree(source, tmp_path / "second.zip")

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == [
            "metadata/manifest.json",
            "wheels/cadrumo.whl",
        ]
        assert archive.read("metadata/manifest.json") == manifest
        assert archive.read("wheels/cadrumo.whl") == wheel
        assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_deterministic_zip_refuses_empty_or_existing_output(tmp_path: Path) -> None:
    """Assembly never invents a payload or replaces retained artifact bytes."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="empty artifact tree"):
        deterministic_zip_tree(empty, tmp_path / "empty.zip")

    source = tmp_path / "source"
    source.mkdir()
    (source / "member.txt").write_text("member\n", encoding="utf-8")
    destination = tmp_path / "retained.zip"
    destination.write_bytes(b"retained")
    with pytest.raises(FileExistsError):
        deterministic_zip_tree(source, destination)

    assert destination.read_bytes() == b"retained"


def test_build_from_clean_source_refuses_a_digest_other_than_its_own_content(tmp_path: Path) -> None:
    """The supplied digest is an assertion against the clean source's own content, never a silent select."""
    clean_root = tmp_path / "clean-source"
    (clean_root / "src").mkdir(parents=True)
    (clean_root / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    output = tmp_path / "staged-cohort"

    with pytest.raises(SystemExit, match="clean source digest drifted"):
        build_from_clean_source(
            clean_root=clean_root,
            output_dir=output,
            expected_source_digest="0" * 64,
            requested_tag=None,
        )

    assert not output.exists()


def test_release_builder_identity_is_the_exact_checked_in_cpython_pin() -> None:
    """The release cohort's build identity remains separate from the open support floor."""
    pin = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert re.fullmatch(_EXACT_PYTHON, pin) is not None
    assert pin == REQUIRED_PYTHON_VERSION

    identity = release_cohort_module._build_identity(REPO_ROOT)

    assert identity.implementation == "dev.packaging.release_cohort"
    assert identity.python == pin


@pytest.mark.parametrize(
    ("implementation", "version"),
    [("PyPy", REQUIRED_PYTHON_VERSION), ("CPython", "3.14.0")],
    ids=("alternative-implementation", "different-patch"),
)
def test_release_builder_refuses_a_non_exact_cpython_identity(
    monkeypatch: pytest.MonkeyPatch,
    implementation: str,
    version: str,
) -> None:
    """A compatibility runtime cannot silently become the reproducible builder."""
    monkeypatch.setattr(release_cohort_module.platform, "python_implementation", lambda: implementation)
    monkeypatch.setattr(release_cohort_module.platform, "python_version", lambda: version)

    with pytest.raises(SystemExit, match="release cohort requires"):
        release_cohort_module._build_identity(REPO_ROOT)
