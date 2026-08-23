"""Real repository and artifact tests for immutable Python cohort construction."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from ..python_cohort import load_python_cohort, source_snapshot_drift
from ._cohort_attestation import (
    add_test_runtime_wheelhouse,
    add_test_source_archive,
    make_test_command_spec_attestation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    assert git is not None
    return subprocess.run(  # noqa: S603 - resolved Git with test-owned declarative argv.
        [git, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_source_snapshot_drift_detects_worktree_index_and_untracked_bytes(
    tmp_path: Path,
) -> None:
    """A HEAD archive cannot be labelled current while any source byte is excluded."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "cohort-test@example.invalid")
    _git(tmp_path, "config", "user.name", "Cohort Test")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "seed")
    assert source_snapshot_drift(tmp_path) == ()

    tracked.write_text("working\n", encoding="utf-8")
    untracked = tmp_path / "untracked.txt"
    untracked.write_text("untracked\n", encoding="utf-8")
    working = source_snapshot_drift(tmp_path)
    assert " M tracked.txt" in working
    assert "?? untracked.txt" in working

    _git(tmp_path, "add", "tracked.txt")
    staged = source_snapshot_drift(tmp_path)
    assert "M  tracked.txt" in staged
    assert "?? untracked.txt" in staged


def _write_placeholder_cohort(root: Path) -> dict[str, str]:
    """Write a digest-consistent cohort whose artifact bytes are placeholders.

    The bytes are not real wheels, so loading reaches -- and fails at -- the
    wheel-contract stage. That makes this fixture a precise probe for the
    checks that run *before* metadata parsing.
    """
    names = {
        "cadrumo": "cadrumo-1.0.0-py3-none-any.whl",
        "cadrumo-sdist": "cadrumo-1.0.0.tar.gz",
        "cadrumo-data-manuals": "cadrumo_data_manuals-1.0.0-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": "cadrumo_data_manuals-1.0.0.tar.gz",
        "cadrumo-data-official": "cadrumo_data_official-1.0.0-py3-none-any.whl",
        "cadrumo-data-official-sdist": "cadrumo_data_official-1.0.0.tar.gz",
    }
    sha256: dict[str, str] = {}
    for label, filename in names.items():
        payload = f"{label}\n".encode()
        (root / filename).write_bytes(payload)
        sha256[label] = hashlib.sha256(payload).hexdigest()
    add_test_source_archive(root, names, sha256)
    add_test_runtime_wheelhouse(root, names, sha256)
    (root / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": sha256,
                "source_commit": "a" * 40,
                "version": "1.0.0",
                "command_spec_attestation": make_test_command_spec_attestation(
                    root, names, source_commit="a" * 40
                ),
            },
        ),
        encoding="utf-8",
    )
    return names


def test_load_python_cohort_refuses_an_unmanifested_file(tmp_path: Path) -> None:
    """The cohort directory is a closed world: manifest plus declared artifacts only.

    The release-cohort authority already refuses inventory drift. A Python cohort
    carrying an undeclared file must fail the same way, or the extra file crosses
    every acquisition, smoke, and promote gate that loads it.
    """
    _write_placeholder_cohort(tmp_path)
    (tmp_path / "unmanifested-extra.bin").write_bytes(b"stowaway")

    with pytest.raises(SystemExit, match="file inventory drifted"):
        load_python_cohort(tmp_path)


def test_load_python_cohort_accepts_the_declared_inventory(tmp_path: Path) -> None:
    """The inventory check does not fire on a cohort holding exactly its declared files.

    Loading proceeds past the inventory gate into wheel-metadata parsing, where the
    placeholder bytes fail for an unrelated reason. That later failure is the proof
    the inventory comparison passed rather than short-circuiting every cohort.
    """
    _write_placeholder_cohort(tmp_path)

    with pytest.raises(zipfile.BadZipFile):
        load_python_cohort(tmp_path)


def test_load_python_cohort_rejects_digest_drift_before_metadata_parsing(
    tmp_path: Path,
) -> None:
    """A changed retained artifact fails closed before it could be promoted."""
    names = {
        "cadrumo": "cadrumo-1.0.0-py3-none-any.whl",
        "cadrumo-sdist": "cadrumo-1.0.0.tar.gz",
        "cadrumo-data-manuals": "cadrumo_data_manuals-1.0.0-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": "cadrumo_data_manuals-1.0.0.tar.gz",
        "cadrumo-data-official": "cadrumo_data_official-1.0.0-py3-none-any.whl",
        "cadrumo-data-official-sdist": "cadrumo_data_official-1.0.0.tar.gz",
    }
    sha256: dict[str, str] = {}
    for label, filename in names.items():
        payload = f"{label}\n".encode()
        (tmp_path / filename).write_bytes(payload)
        sha256[label] = hashlib.sha256(payload).hexdigest()
    add_test_source_archive(tmp_path, names, sha256)
    add_test_runtime_wheelhouse(tmp_path, names, sha256)
    (tmp_path / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": sha256,
                "source_commit": "a" * 40,
                "version": "1.0.0",
                "command_spec_attestation": make_test_command_spec_attestation(
                    tmp_path, names, source_commit="a" * 40
                ),
            },
        ),
        encoding="utf-8",
    )
    (tmp_path / names["cadrumo"]).write_bytes(b"changed")

    with pytest.raises(SystemExit, match="digest mismatch"):
        load_python_cohort(tmp_path)
