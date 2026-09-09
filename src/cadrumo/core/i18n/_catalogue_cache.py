"""Stable source digest for a sharded locale catalogue."""

from __future__ import annotations

from ..external_constants import UTF_8_ENCODING


def compute_directory_source_digest(shards: list[tuple[str, bytes]]) -> str:
    """Return the hex SHA-256 digest of a multi-file locale catalogue directory.

    Combines each shard's relative path and raw bytes in sorted order.
    """
    import hashlib

    hasher = hashlib.sha256()
    for rel_path, raw_bytes in sorted(shards, key=lambda x: x[0]):
        hasher.update(rel_path.encode(UTF_8_ENCODING))
        hasher.update(b"\x00")
        hasher.update(raw_bytes)
        hasher.update(b"\x00")
    return hasher.hexdigest()


__all__ = ["compute_directory_source_digest"]
