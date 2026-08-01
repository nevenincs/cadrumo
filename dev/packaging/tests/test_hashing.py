"""Independent contracts for streamed packaging artifact hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dev.packaging._hashing import sha256_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_sha256_path_hashes_real_multichunk_bytes(tmp_path: Path) -> None:
    """A file crossing the stream boundary has the standard-library digest."""
    payload = b"cohort-byte-contract\n" * 60_000
    artifact = tmp_path / "cohort-artifact.bin"
    artifact.write_bytes(payload)

    assert sha256_path(artifact) == hashlib.sha256(payload).hexdigest()
