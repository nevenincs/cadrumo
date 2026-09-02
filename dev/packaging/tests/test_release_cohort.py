"""Real archive tests for one-shot release-cohort construction."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from .. import python_cohort as python_cohort_module
from .. import release_cohort as release_cohort_module
from ..python_cohort import digest_install_target
from ..release_cohort import _REQUIRED_PYTHON_VERSION, build_release_cohort, deterministic_zip_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXACT_PYTHON: Final[str] = r"3\.\d+\.\d+"


class _CleanBuilderInvocationObservedError(RuntimeError):
    """Stop the harness after it has assembled the clean-child command."""


def _assert_clean_builder_invocation(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None,
    expected_commit: str,
) -> None:
    """Protect package imports, clean-source isolation, and commit binding."""
    assert argv[1:3] == ["-m", "dev.packaging.release_cohort"], (
        "clean release-cohort construction must invoke the package module"
    )
    assert cwd.name == "source"
    assert env is not None
    assert env["PYTHONPATH"] == os.pathsep.join((str(cwd / "src"), str(cwd)))
    assert argv[argv.index("--expected-commit") + 1] == expected_commit


def test_clean_builder_subprocess_is_package_correct_and_detector_bites(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The clean child keeps relative imports and the exact source assertion."""
    repo_root = tmp_path / "repo"
    (repo_root / "var").mkdir(parents=True)
    output = repo_root / "var" / "cohort"
    expected_commit = "a" * 40
    captured: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_git(_repo: Path, *_args: str) -> str:
        return expected_commit

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

    monkeypatch.setattr(release_cohort_module, "_git", fake_git)
    monkeypatch.setattr(release_cohort_module, "_run", fake_run)
    monkeypatch.setattr(release_cohort_module.shutil, "which", lambda executable: executable)

    with pytest.raises(_CleanBuilderInvocationObservedError):
        build_release_cohort(
            repo_root=repo_root,
            output_dir=output,
            expected_commit=expected_commit,
        )

    child_calls = [call for call in captured if "build-clean" in call[0]]
    assert len(child_calls) == 1
    argv, cwd, env = child_calls[0]
    _assert_clean_builder_invocation(
        argv,
        cwd=cwd,
        env=env,
        expected_commit=expected_commit,
    )

    file_path_regression = list(argv)
    file_path_regression[1:3] = [str(cwd / "dev" / "packaging" / "release_cohort.py"), "build-clean"]
    with pytest.raises(AssertionError, match="package module"):
        _assert_clean_builder_invocation(
            file_path_regression,
            cwd=cwd,
            env=env,
            expected_commit=expected_commit,
        )


def _assert_digest_bound_local_wheel_install(argv: list[str], *, root_wheel: Path) -> None:
    """Protect the attestation install from hash-mode rejection and drift."""
    assert argv[-1] == digest_install_target("cadrumo", root_wheel)


def test_command_spec_attestation_digest_binds_local_wheel_under_hash_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The local attestation wheel remains accepted while dependency hashes stay required."""
    root_wheel = tmp_path / "cadrumo-0.2.2-py3-none-any.whl"
    root_sdist = tmp_path / "cadrumo-0.2.2.tar.gz"
    source_archive = tmp_path / "cadrumo-source.zip"
    for artifact in (root_wheel, root_sdist, source_archive):
        artifact.write_bytes(artifact.name.encode())
    work_root = tmp_path / "work"
    work_root.mkdir()
    captured_install: list[list[str]] = []
    probe_environments: list[dict[str, str]] = []
    probe_payload = {
        "identities": [["cadrumo", "root"]],
        "locales": ["en"],
        "policies": ["policy"],
        "schemas": ["schema"],
        "import_budgets": {
            "graph_projection_first_party_modules": ["cadrumo"],
            "handler_modules_loaded": ["handler"],
            "selected_path_deltas": [],
        },
        "origins": ["root"],
    }

    def fake_run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        captured_install.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def fake_probe(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
        errors: str,
    ) -> subprocess.CompletedProcess[str]:
        probe_environments.append(env)
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(probe_payload), stderr="")

    monkeypatch.setenv("UV_REQUIRE_HASHES", "1")
    monkeypatch.setattr(python_cohort_module, "_run", fake_run)
    monkeypatch.setattr(python_cohort_module.subprocess, "run", fake_probe)
    monkeypatch.setattr(python_cohort_module, "_artifact_command_projection", lambda *_args: ())

    python_cohort_module._attest_installed_command_specs(
        root_wheel,
        root_sdist,
        "a" * 40,
        source_archive,
        work_root=work_root,
        uv="uv",
    )

    assert len(captured_install) == 1
    assert len(probe_environments) == 4
    argv = captured_install[0]
    _assert_digest_bound_local_wheel_install(argv, root_wheel=root_wheel)
    assert "#sha256=" in argv[-1]
    assert all(environment["UV_REQUIRE_HASHES"] == "1" for environment in probe_environments)

    bare_path_regression = list(argv)
    bare_path_regression[-1] = str(root_wheel)
    with pytest.raises(AssertionError):
        _assert_digest_bound_local_wheel_install(bare_path_regression, root_wheel=root_wheel)


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


def test_build_refuses_an_expected_commit_other_than_checked_out_head() -> None:
    """The commit option is an assertion and never silently selects other bytes."""
    repo_root = REPO_ROOT
    output = repo_root / "var" / f"release-cohort-refusal-{uuid.uuid4().hex}"

    with pytest.raises(SystemExit, match="does not equal the currently checked-out HEAD"):
        build_release_cohort(
            repo_root=repo_root,
            output_dir=output,
            expected_commit="0" * 40,
        )

    assert not output.exists()


def test_release_builder_identity_is_the_exact_checked_in_cpython_pin() -> None:
    """The release cohort's build identity remains separate from the open support floor."""
    pin = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert re.fullmatch(_EXACT_PYTHON, pin) is not None
    assert pin == _REQUIRED_PYTHON_VERSION

    identity = release_cohort_module._build_identity(REPO_ROOT)

    assert identity.implementation == "dev.packaging.release_cohort"
    assert identity.python == pin


@pytest.mark.parametrize(
    ("implementation", "version"),
    [("PyPy", _REQUIRED_PYTHON_VERSION), ("CPython", "3.14.0")],
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
