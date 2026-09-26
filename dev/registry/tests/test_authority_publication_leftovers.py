"""A publication over an interrupted one publishes fresh bytes and never adopts the leftovers.

A publication killed part-way leaves its staging directory, and possibly a
database file, in the destination with no descriptor naming them. The next
publication must validate and install its own candidate, and the leftovers must
never become the published generation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

from ..pipeline.authority_publication import install_validated_authority_database
from ._authority_generation_support import publishable_artifact

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_CORRUPT = b"SQLite format 3\x00" + b"\x00" * 64


def test_a_publication_over_interrupted_leftovers_installs_fresh_validated_bytes(tmp_path: Path) -> None:
    staging = tmp_path / "authority-candidate-interrupted"
    staging.mkdir()
    (staging / "candidate.sqlite3").write_bytes(_CORRUPT)
    orphan_name = f"authority-{hashlib.sha256(_CORRUPT).hexdigest()}.sqlite3"
    (tmp_path / orphan_name).write_bytes(_CORRUPT[:20])

    published = install_validated_authority_database(
        publishable_artifact("fresh"),
        destination=tmp_path,
        require_current=lambda: None,
    )

    document = AuthorityDescriptor.read(tmp_path / "authority.current.json")
    assert document.database == published.database
    assert published.database != orphan_name
    payload = (tmp_path / published.database).read_bytes()
    assert document.database_sha256 == hashlib.sha256(payload).hexdigest()
    assert document.database_size == len(payload)
    assert not (tmp_path / orphan_name).exists(), "an unnamed leftover database must be retired, not kept"
    assert (staging / "candidate.sqlite3").read_bytes() == _CORRUPT, "the leftover staging is never read"

    authority = IndexedRegistryAuthority(tmp_path / "authority.current.json")
    try:
        with authority.operation() as operation:
            assert operation.profile_schema().title == "Profile schema fresh"
    finally:
        authority.close()
