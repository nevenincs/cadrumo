"""Real archive tests for one-shot release-cohort construction."""

from __future__ import annotations

import uuid
import zipfile
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..release_cohort import build_release_cohort, deterministic_zip_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


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
