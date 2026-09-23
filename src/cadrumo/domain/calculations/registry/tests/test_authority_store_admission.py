"""Admitting a published authority hashes the whole database without holding it in memory.

Both tests use this checkout's real published pair. The first measures the
reader's peak Python allocation while it admits the database: hashing by
reading the file whole allocates at least the database's size, streaming it
allocates a few chunks. The second proves the streamed digest still refuses a
database whose bytes differ from the descriptor by a single byte.
"""

from __future__ import annotations

import json
import shutil
import tracemalloc
from pathlib import Path

import pytest

from ..authority import bundled_authority_descriptor_path
from ..authority_store import AuthorityStoreCorruptionError, SQLiteAuthorityReader

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
