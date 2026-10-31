"""The run publication is keyed on its inputs and admitted only by its digests.

A changed input derives another identity, so it gets its own publication and is
never served the old one; an entry whose bytes or recorded generation disagree
with its key is refused rather than reused. Each case runs on an isolated small
source tree, and the publisher stand-in installs a real database through the
real installer, so only the canonical child compile is replaced.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.authority import AuthoritySourceSet
from ..pipeline.authority_publication import authority_source_identity, install_validated_authority_database
from ._authority_generation_support import synthetic_authority_artifact
from .committed_authority_publication import AuthorityPublisher, published_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _stage_inputs(root: Path) -> AuthoritySourceSet:
    registry_root = root / "registry" / "aeat"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (registry_root / "modelos" / "999" / "manifest.toml").write_bytes(b'[modelo]\nid = "999"\n')
    (revision_dir / "revision.toml").write_bytes(b'id = "2025"\nvalid_from = 2025-01-01\n')
    evidence_dir = root / "corpus" / "test"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "ley.html").write_bytes(b"<html>provision text</html>\n")
    profile_schema = root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    profile_schema.parent.mkdir(parents=True)
    shutil.copyfile(bundled_path("registry", "cadrumo", "user_profile", "schema.toml"), profile_schema)
    return AuthoritySourceSet(
        registry_root=registry_root,
        source_evidence_root=root,
        profile_schema_path=profile_schema,
    )


def _identity(sources: AuthoritySourceSet) -> str:
    return authority_source_identity(
        registry_root=sources.registry_root,
        source_root=sources.source_evidence_root,
        profile_schema_path=sources.profile_schema_path,
    )


def _recording_publisher(calls: list[Path], *, recorded_identity: str | None = None) -> AuthorityPublisher:
    """Install a real database recording the sources' identity, or ``recorded_identity`` when given."""

    def publish(sources: AuthoritySourceSet, destination: Path) -> None:
        calls.append(destination)
        install_validated_authority_database(
            replace(synthetic_authority_artifact(), identity_digest=recorded_identity or _identity(sources)),
            destination=destination,
            require_current=lambda: None,
        )

    return publish


def test_a_changed_input_gets_a_new_publication_and_never_reuses_the_old_one(tmp_path: Path) -> None:
    sources = _stage_inputs(tmp_path / "inputs")
    cache_root = tmp_path / "cache"
    calls: list[Path] = []

    first = published_authority(sources, cache_root=cache_root, publish=_recording_publisher(calls))
    reused = published_authority(sources, cache_root=cache_root, publish=_recording_publisher(calls))

    assert first.published_by_this_call
    assert not reused.published_by_this_call
    assert reused.descriptor == first.descriptor
    assert len(calls) == 1

    revision = sources.registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(b'id = "2025"\nvalid_from = 2025-02-01\n')
    changed = published_authority(sources, cache_root=cache_root, publish=_recording_publisher(calls))

    assert changed.published_by_this_call
    assert len(calls) == 2
    assert changed.root != first.root
    assert changed.source_identity_digest == _identity(sources) != first.source_identity_digest
    assert changed.descriptor.logical_generation == changed.source_identity_digest
    assert first.descriptor.logical_generation == first.source_identity_digest


def test_an_entry_whose_database_bytes_changed_is_refused_not_admitted(tmp_path: Path) -> None:
    sources = _stage_inputs(tmp_path / "inputs")
    cache_root = tmp_path / "cache"
    calls: list[Path] = []
    first = published_authority(sources, cache_root=cache_root, publish=_recording_publisher(calls))
    database = first.root / first.descriptor.database
    tampered = bytearray(database.read_bytes())
    tampered[-1] ^= 0xFF
    database.write_bytes(bytes(tampered))
    assert sha256_hex(bytes(tampered)) != first.descriptor.database_sha256

    with pytest.raises(RegistryValidationError, match="collision"):
        published_authority(sources, cache_root=cache_root, publish=_recording_publisher(calls))
    assert len(calls) == 2


def test_a_publication_recording_other_sources_is_refused(tmp_path: Path) -> None:
    sources = _stage_inputs(tmp_path / "inputs")
    calls: list[Path] = []
    publisher = _recording_publisher(calls, recorded_identity=sha256_hex(b"sources that changed mid-publication"))

    with pytest.raises(RegistryValidationError, match="does not record the sources"):
        published_authority(sources, cache_root=tmp_path / "cache", publish=publisher)
    assert len(calls) == 1
