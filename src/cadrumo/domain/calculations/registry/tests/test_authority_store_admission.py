"""Admitting a published authority hashes the whole database and binds it to its descriptor.

Every test uses this checkout's real published pair. The first measures the
reader's peak Python allocation while it admits the database: hashing by
reading the file whole allocates at least the database's size, streaming it
allocates a few chunks. The second proves the streamed digest still refuses a
database whose bytes differ from the descriptor by a single byte. Receipts let
a later process skip the hash for the very file object an earlier one proved,
and the receipt cases show a rewrite is hashed again. The rest republish an
edited copy under its own content address, so the digest admits it and only
the manifest decides.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tracemalloc
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.hashing import sha256_hex
from .. import authority_store
from ..authority_location import bundled_authority_descriptor_path
from ..authority_store import (
    AuthorityDescriptor,
    AuthorityStoreCorruptionError,
    AuthorityStoreFormatError,
    SQLiteAuthorityReader,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _own_receipts(tmp_path: Path) -> object:
    """Keep admission receipts to this test, so every case starts from a database nobody has proved."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "storage"):
        yield


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


def test_admission_refuses_a_manifest_naming_another_generation_than_its_descriptor(tmp_path: Path) -> None:
    descriptor = _republished_copy(
        tmp_path,
        (("UPDATE authority_manifest SET logical_generation = ?", (sha256_hex(b"another generation"),)),),
    )

    with pytest.raises(AuthorityStoreCorruptionError, match="manifest disagrees with its descriptor"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def test_admission_refuses_the_previous_format_that_recorded_the_compiler_and_its_environment(
    tmp_path: Path,
) -> None:
    descriptor = _republished_copy(
        tmp_path,
        (("UPDATE authority_manifest SET format = ?", ("cadrumo-authority-sqlite-v3",)),),
    )

    with pytest.raises(AuthorityStoreFormatError, match="cadrumo-authority-sqlite-v3"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def _counting_hashes(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    hashed: list[Path] = []
    real = authority_store.hash_file

    def counted(path: Path) -> tuple[str, int]:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(authority_store, "hash_file", counted)
    return hashed


def _copied_pair(directory: Path) -> tuple[Path, Path]:
    source_descriptor = bundled_authority_descriptor_path()
    database_name = json.loads(source_descriptor.read_text(encoding="utf-8"))["database"]
    directory.mkdir()
    shutil.copy2(source_descriptor, directory / _DESCRIPTOR_NAME)
    shutil.copy2(source_descriptor.parent / database_name, directory / database_name)
    return directory / _DESCRIPTOR_NAME, directory / database_name


def test_a_later_reader_of_the_same_file_relies_on_the_proof_an_earlier_one_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, database = _copied_pair(tmp_path / "pair")
    hashed = _counting_hashes(monkeypatch)
    SQLiteAuthorityReader(descriptor, max_connections=1).close()
    SQLiteAuthorityReader(descriptor, max_connections=1).close()
    assert hashed == [database]


def test_a_rewritten_database_is_hashed_again_although_its_bytes_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor, database = _copied_pair(tmp_path / "pair")
    hashed = _counting_hashes(monkeypatch)
    SQLiteAuthorityReader(descriptor, max_connections=1).close()
    database.write_bytes(database.read_bytes())
    SQLiteAuthorityReader(descriptor, max_connections=1).close()
    assert hashed == [database, database]


def test_a_proved_database_edited_with_its_write_time_restored_is_still_refused(tmp_path: Path) -> None:
    descriptor, database = _copied_pair(tmp_path / "pair")
    SQLiteAuthorityReader(descriptor, max_connections=1).close()
    before = database.stat()
    middle = before.st_size // 2
    with database.open("r+b") as stream:
        stream.seek(middle)
        original = stream.read(1)
        stream.seek(middle)
        stream.write(bytes([original[0] ^ 0xFF]))
    os.utime(database, ns=(before.st_atime_ns, before.st_mtime_ns))

    with pytest.raises(AuthorityStoreCorruptionError, match="disagree with the published descriptor"):
        SQLiteAuthorityReader(descriptor, max_connections=1)
