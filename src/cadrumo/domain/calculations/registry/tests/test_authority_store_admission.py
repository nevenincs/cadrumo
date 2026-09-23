"""Admitting a published authority hashes the whole database and recomputes its receipts.

Every test uses this checkout's real published pair. The first measures the
reader's peak Python allocation while it admits the database: hashing by
reading the file whole allocates at least the database's size, streaming it
allocates a few chunks. The second proves the streamed digest still refuses a
database whose bytes differ from the descriptor by a single byte. The rest
republish an edited copy under its own content address, so the digest admits
it and only the recorded compiler closure and format decide.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tracemalloc
from pathlib import Path

import pytest

from .....core.hashing import sha256_hex
from ..authority import bundled_authority_descriptor_path
from ..authority_store import (
    AuthorityDescriptor,
    AuthorityStoreCorruptionError,
    AuthorityStoreFormatError,
    SQLiteAuthorityReader,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_DESCRIPTOR_NAME = "authority.current.json"


def _published_database_size(descriptor_path: Path) -> int:
    return int(json.loads(descriptor_path.read_text(encoding="utf-8"))["database_size"])


def test_admission_hashes_the_published_database_without_loading_it_whole() -> None:
    descriptor_path = bundled_authority_descriptor_path()
    database_size = _published_database_size(descriptor_path)

    tracemalloc.start()
    try:
        reader = SQLiteAuthorityReader(descriptor_path, max_connections=1)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    reader.close()

    # The bound only means something against a database far larger than a chunk.
    assert database_size > 8 * 1024 * 1024
    assert peak < database_size // 8, f"admission allocated {peak} bytes for a {database_size}-byte database"


def test_admission_refuses_a_database_differing_from_its_descriptor_by_one_byte(tmp_path: Path) -> None:
    source_descriptor = bundled_authority_descriptor_path()
    database_name = json.loads(source_descriptor.read_text(encoding="utf-8"))["database"]
    shutil.copy2(source_descriptor, tmp_path / _DESCRIPTOR_NAME)
    tampered = tmp_path / database_name
    shutil.copy2(source_descriptor.parent / database_name, tampered)
    middle = tampered.stat().st_size // 2
    with tampered.open("r+b") as stream:
        stream.seek(middle)
        original = stream.read(1)
        stream.seek(middle)
        stream.write(bytes([original[0] ^ 0xFF]))

    with pytest.raises(AuthorityStoreCorruptionError, match="disagree with the published descriptor"):
        SQLiteAuthorityReader(tmp_path / _DESCRIPTOR_NAME, max_connections=1)


def _republished_copy(directory: Path, statements: tuple[tuple[str, tuple[str, ...]], ...]) -> Path:
    """Copy the published pair, apply ``statements`` and re-address the edited database."""
    source = AuthorityDescriptor.read(bundled_authority_descriptor_path())
    staging = directory / "edited.sqlite3"
    shutil.copy2(bundled_authority_descriptor_path().parent / source.database, staging)
    connection = sqlite3.connect(staging)
    try:
        for statement, parameters in statements:
            connection.execute(statement, parameters)
        connection.commit()
    finally:
        connection.close()
    payload = staging.read_bytes()
    digest = sha256_hex(payload)
    staging.replace(directory / f"authority-{digest}.sqlite3")
    descriptor = AuthorityDescriptor(
        database=f"authority-{digest}.sqlite3",
        database_size=len(payload),
        database_sha256=digest,
        logical_generation=source.logical_generation,
    )
    (directory / _DESCRIPTOR_NAME).write_bytes(descriptor.to_bytes())
    return directory / _DESCRIPTOR_NAME


def test_admission_exposes_the_recorded_compiler_closure_behind_the_compiler_receipt() -> None:
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path(), max_connections=1)
    try:
        closure = reader.compiler_closure()
        build = reader.build_identity()
    finally:
        reader.close()

    assert closure.sources
    assert closure.identity_digest == build.compiler_identity_digest
    assert "cadrumo/domain/calculations/registry/authority_compiler_closure.py" in {
        path for path, _digest in closure.sources
    }


def test_admission_refuses_a_compiler_closure_row_that_no_longer_recomputes_the_receipt(tmp_path: Path) -> None:
    descriptor = _republished_copy(
        tmp_path,
        (
            (
                "UPDATE compiler_sources SET sha256 = ? WHERE path = (SELECT min(path) FROM compiler_sources)",
                (sha256_hex(b"tampered compiler source"),),
            ),
        ),
    )

    with pytest.raises(AuthorityStoreCorruptionError, match="compiler closure does not recompute"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def test_admission_refuses_a_dropped_compiler_closure_row(tmp_path: Path) -> None:
    descriptor = _republished_copy(
        tmp_path,
        (("DELETE FROM compiler_sources WHERE path = (SELECT max(path) FROM compiler_sources)", ()),),
    )

    with pytest.raises(AuthorityStoreCorruptionError, match="compiler closure does not recompute"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def test_admission_refuses_the_previous_format_that_recorded_no_compiler_closure(tmp_path: Path) -> None:
    descriptor = _republished_copy(
        tmp_path,
        (
            ("UPDATE authority_manifest SET format = ?", ("cadrumo-authority-sqlite-v2",)),
            ("DROP TABLE compiler_sources", ()),
            ("DROP TABLE compiler_environment", ()),
        ),
    )

    with pytest.raises(AuthorityStoreFormatError, match="cadrumo-authority-sqlite-v2"):
        SQLiteAuthorityReader(descriptor, max_connections=1)
