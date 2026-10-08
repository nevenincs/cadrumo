"""Cohort identity names captured bytes and refuses changes before any build."""

from __future__ import annotations

import hashlib
import os
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Never

import pytest

from dev.source_tree import content_digest, repository_files, snapshot

from .. import python_cohort, release_cohort
from ..cohort_attestation import make_minimal_test_python_cohort
from ..cohort_manifest import BuildIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _BuildInterceptedError(RuntimeError):
    """Stop after proving the real snapshot and archive boundary."""


def _expected_identity(members: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(members.items()):
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(content).digest() + b"\n")
    return digest.hexdigest()


@pytest.mark.parametrize("mutation", ("before_copy", "after_copy", "captured_attributes"))
def test_ordinary_cohort_names_the_bytes_actually_captured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitattributes").write_bytes(b"*.py text eol=lf\n")
    (root / "program.py").write_bytes(b"original\r\n")
    expected = {".gitattributes": b"*.py text eol=lf\n", "program.py": b"original\n"}

    def changing_snapshot(source: Path, files: Sequence[str], destination: Path) -> None:
        if mutation == "before_copy":
            (source / "program.py").write_bytes(b"captured\r\n")
            expected["program.py"] = b"captured\n"
        snapshot(source, files, destination)
        if mutation == "after_copy":
            (source / "program.py").write_bytes(b"later live edit\r\n")
        elif mutation == "captured_attributes":
            # A copied policy can differ from the one that normalized a member.
            # Naming the captured bytes must not normalize that member again.
            expected[".gitattributes"] = b"*.py text eol=crlf\n"
            (destination / ".gitattributes").write_bytes(expected[".gitattributes"])

    def inspect_capture(
        *,
        build_root: Path,
        output: Path,
        source_files: Sequence[str],
        source_digest: str,
        authority_source_root: Path | None,
        remove_build_root: bool,
    ) -> Never:
        assert authority_source_root == root and remove_build_root
        assert source_digest == _expected_identity(expected)
        archive_path = python_cohort._archive_source_snapshot(
            build_root, source_files, output / "captured.zip", expected_source_digest=source_digest
        )
        with zipfile.ZipFile(archive_path) as archive:
            assert {name: archive.read(name) for name in archive.namelist()} == expected
        raise _BuildInterceptedError

    monkeypatch.setattr(python_cohort, "snapshot", changing_snapshot)
    monkeypatch.setattr(python_cohort, "_build_python_cohort_from_snapshot", inspect_capture)
    with pytest.raises(_BuildInterceptedError):
        python_cohort.build_python_cohort(root, root / "var" / "cohort")


@pytest.mark.parametrize("mutation", ("unchanged", "wrong_identity", "changed_before_archive"))
def test_clean_release_identity_is_verified_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    root = tmp_path / "clean"
    root.mkdir()
    (root / "program.py").write_bytes(b"verified source\n")
    expected = _expected_identity({"program.py": b"verified source\n"})
    archive_snapshot = python_cohort._archive_source_snapshot

    def changed_archive(
        build_root: Path, files: Sequence[str], destination: Path, *, expected_source_digest: str
    ) -> Path:
        if mutation == "changed_before_archive":
            (build_root / "program.py").write_bytes(b"unverified replacement\n")
        return archive_snapshot(build_root, files, destination, expected_source_digest=expected_source_digest)

    def forbid_staging(*_args: object, **_kwargs: object) -> Never:
        if mutation == "unchanged":
            raise _BuildInterceptedError
        pytest.fail("a changed source reached staging before its identity was verified")

    monkeypatch.setattr(python_cohort, "_archive_source_snapshot", changed_archive)
    monkeypatch.setattr(python_cohort, "build_client_json", forbid_staging)
    expected_error = _BuildInterceptedError if mutation == "unchanged" else SystemExit
    with pytest.raises(expected_error) as caught:
        python_cohort.build_python_cohort_from_clean_snapshot(
            root,
            root / "var" / "cohort",
            source_files=("program.py",),
            source_digest="0" * 64 if mutation == "wrong_identity" else expected,
        )
    if mutation != "unchanged":
        assert "source archive does not match its source digest" in str(caught.value)
    assert not list((root / "var" / "cohort").glob("*.whl"))


@pytest.mark.parametrize("changed_during_copy", (False, True))
def test_release_wrapper_preserves_requested_identity_in_default_snapshot_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_during_copy: bool
) -> None:
    root = tmp_path / "release-source"
    (root / "packaging").mkdir(parents=True)
    (root / ".gitignore").write_text("var/\n", encoding="utf-8")
    (root / "program.py").write_bytes(b"requested source\n")
    (root / "packaging" / "build-system-constraints.txt").write_bytes(b"fixture constraints\n")
    expected = content_digest(root, repository_files(root))
    identity = BuildIdentity(
        implementation="dev.packaging.release_cohort",
        format_version=1,
        python="3.13.15",
        uv="uv fixture",
        platform="fixture",
        architecture="fixture",
        build_constraints_sha256="a" * 64,
    )
    for environment_key in (
        "SOURCE_DATE_EPOCH",
        "PYTHONHASHSEED",
        "UV_BUILD_CONSTRAINT",
        "UV_REQUIRE_HASHES",
        "UV_PYTHON",
        "UV_PYTHON_DOWNLOADS",
    ):
        monkeypatch.setenv(environment_key, os.environ.get(environment_key, ""))

    def capture(source: Path, destination: Path) -> python_cohort.PythonCohort:
        if changed_during_copy:
            (source / "program.py").write_bytes(b"changed after release verification\n")
        captured = content_digest(source, repository_files(source))
        make_minimal_test_python_cohort(destination, version="1.0.0", source_digest=captured)
        return python_cohort.load_python_cohort(destination)

    def copy_boundary(_cohort: python_cohort.PythonCohort, _destination: Path) -> Never:
        if changed_during_copy:
            pytest.fail("a newly captured identity reached release artifact copying")
        raise _BuildInterceptedError

    monkeypatch.setattr(release_cohort, "_build_identity", lambda _root: identity)
    monkeypatch.setattr(release_cohort, "build_python_cohort", capture)
    monkeypatch.setattr(release_cohort, "_copy_python_cohort", copy_boundary)
    expected_error = SystemExit if changed_during_copy else _BuildInterceptedError
    with pytest.raises(expected_error) as caught:
        release_cohort.build_from_clean_source(
            clean_root=root,
            output_dir=tmp_path / "release-output",
            expected_source_digest=expected,
            requested_tag=None,
        )
    if changed_during_copy:
        assert "differs from the requested release source" in str(caught.value)
