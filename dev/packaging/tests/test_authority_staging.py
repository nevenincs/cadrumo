"""Prove build-root staging carries the payload and leaves the sidecar alone.

Two invariants meet here, and they pull in opposite directions often enough that
a plausible helper gets one right and the other wrong.

The first is *exclusion*: a build root receives the descriptor and the one
database it selects, and nothing else the authority directory happens to hold.
A real directory also holds the publication lock sidecar, which is retained
after every publish by design, may hold a superseded database whose unlink the
OS refused while a reader held it open, and holds an ``authority-candidate-*``
directory while a publication is in flight. A helper that stages the directory
wholesale drags all three into a distribution.

The second is *preservation*: excluding the sidecar is not deleting it. A helper
that "tidies" the authority directory by removing the sidecar opens a TOCTOU
window in which two publishers each believe they hold the lock. The defect is
only reachable from outside the publisher — inside it, cleanup runs while the
descriptor is still open and the OS refuses the unlink outright — so this is
where it has to be caught.

Both defects are exercised against stand-in helpers defined in this module,
alongside the real one on the same fixture, so the oracle is shown to have teeth
rather than merely to pass. Nothing here touches the contributor's working tree
or patches a production module.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

from ..authority_staging import AUTHORING_AUTHORITY_DIRECTORY, AUTHORITY_ROOT_ENV, stage_published_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DESCRIPTOR_NAME = "authority.current.json"
_SIDECAR_NAME = f"{_DESCRIPTOR_NAME}.lock"
_CANDIDATE_DIRECTORY = "authority-candidate-3f9c"


def _write_database(directory: Path, payload: bytes) -> tuple[str, str, int]:
    """Write a content-addressed database and return its name, digest and size."""

    digest = hashlib.sha256(payload).hexdigest()
    name = f"authority-{digest}.sqlite3"
    (directory / name).write_bytes(payload)
    return name, digest, len(payload)


@pytest.fixture
def published_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a repository root whose authority directory looks like a real one.

    Deliberately not a clean directory: it carries the retained sidecar, a
    superseded database the OS refused to unlink, and an in-flight candidate
    staging directory, because that is the state every published tree is
    actually in and the state a directory-wide helper mis-handles.
    """

    monkeypatch.delenv(AUTHORITY_ROOT_ENV, raising=False)
    repo_root = tmp_path / "repository"
    authority = repo_root / AUTHORING_AUTHORITY_DIRECTORY
    authority.mkdir(parents=True)

    selected, digest, size = _write_database(authority, b"selected-authority-payload")
    _write_database(authority, b"superseded-authority-payload")
    (authority / _SIDECAR_NAME).touch()
    candidate = authority / _CANDIDATE_DIRECTORY
    candidate.mkdir()
    (candidate / _DESCRIPTOR_NAME).write_bytes(b"{}")

    descriptor = AuthorityDescriptor(
        database=selected,
        database_size=size,
        database_sha256=digest,
        logical_generation="c" * 64,
    )
    (authority / _DESCRIPTOR_NAME).write_bytes(descriptor.to_bytes())
    return repo_root


def _staging_findings(source_root: Path, destination_root: Path) -> list[str]:
    """Return every way a staging run violated exclusion or preservation."""

    source = source_root / AUTHORING_AUTHORITY_DIRECTORY
    selected = AuthorityDescriptor.read(source / _DESCRIPTOR_NAME).database
    findings: list[str] = []

    staged_root = destination_root / AUTHORING_AUTHORITY_DIRECTORY
    staged = (
        {path.relative_to(staged_root).as_posix() for path in staged_root.rglob("*") if path.is_file()}
        if staged_root.is_dir()
        else set()
    )
    expected = {_DESCRIPTOR_NAME, selected}
    for extra in sorted(staged - expected):
        if extra.endswith(".lock"):
            findings.append(f"staged the retained publication lock sidecar: {extra}")
        elif extra.startswith("authority-candidate-"):
            findings.append(f"staged an in-flight publication candidate: {extra}")
        else:
            findings.append(f"staged a file the descriptor does not select: {extra}")
    for missing in sorted(expected - staged):
        findings.append(f"did not stage required payload: {missing}")

    if not (source / _SIDECAR_NAME).is_file():
        findings.append("deleted the publication lock sidecar from the source tree")
    if not (source / _CANDIDATE_DIRECTORY).is_dir():
        findings.append("deleted an in-flight publication candidate from the source tree")
    return findings


def _tidying_helper(source_root: Path, destination_root: Path) -> None:
    """Stand-in defect: stages correctly, then "tidies" the sidecar away."""

    stage_published_authority(source_root, destination_root)
    (source_root / AUTHORING_AUTHORITY_DIRECTORY / _SIDECAR_NAME).unlink()


def _directory_copy_helper(source_root: Path, destination_root: Path) -> None:
    """Stand-in defect: stages the whole authority directory instead of the pair."""

    shutil.copytree(
        source_root / AUTHORING_AUTHORITY_DIRECTORY,
        destination_root / AUTHORING_AUTHORITY_DIRECTORY,
    )


def test_staging_carries_the_selected_pair_and_preserves_the_sidecar(published_authority: Path, tmp_path: Path) -> None:
    """The real helper stages exactly the payload and leaves the source untouched."""

    destination = tmp_path / "build-root"
    destination.mkdir()

    descriptor, database = stage_published_authority(published_authority, destination)

    assert descriptor.is_file()
    assert database.is_file()
    assert _staging_findings(published_authority, destination) == []


def test_staging_oracle_detects_a_helper_that_deletes_the_sidecar(published_authority: Path, tmp_path: Path) -> None:
    """Removing the retained sidecar is caught, though the staged payload is correct."""

    destination = tmp_path / "build-root"
    destination.mkdir()

    _tidying_helper(published_authority, destination)

    assert _staging_findings(published_authority, destination) == [
        "deleted the publication lock sidecar from the source tree"
    ]


def test_staging_oracle_detects_a_helper_that_copies_the_whole_directory(
    published_authority: Path, tmp_path: Path
) -> None:
    """A directory-wide copy is caught on the sidecar, the candidate and the superseded database."""

    destination = tmp_path / "build-root"
    destination.mkdir()

    _directory_copy_helper(published_authority, destination)

    findings = _staging_findings(published_authority, destination)
    assert any("lock sidecar" in finding and "staged" in finding for finding in findings)
    assert any("candidate" in finding and "staged" in finding for finding in findings)
    assert any("does not select" in finding for finding in findings)
    assert not any("deleted" in finding for finding in findings)


def test_staging_refuses_a_tree_that_has_never_published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A source tree with no published authority fails loudly rather than staging nothing."""

    monkeypatch.delenv(AUTHORITY_ROOT_ENV, raising=False)
    destination = tmp_path / "build-root"
    destination.mkdir()

    with pytest.raises(FileNotFoundError, match="no published registry authority to stage"):
        stage_published_authority(tmp_path / "empty-repository", destination)
