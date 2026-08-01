"""Content-digest alias for surfaces that content-address a payload.

A content digest is the lowercase hex SHA-256 of a payload's exact bytes.
It is not an identity minted by a service; it is a re-computable claim
about bytes, so every consumer that stores one must be able to recompute
it and compare. Pinning the hex-64 shape at the pydantic boundary keeps a
malformed digest out of persisted records and wire payloads, where the
mismatch would otherwise surface only when a later verification pass
recomputes the hash.

The alias reuses :data:`core.HEX_PATTERN_64`, the one declaration of the
SHA-256 hex shape, and lives beside :data:`SnapshotId` in
:mod:`cadrumo.core.identity` because digest-bearing records span the
application, adapter, and persistence layers with no single owner.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

from .._hex import HEX_PATTERN_64

ContentDigest = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64),
]
"""Lowercase hex-64 SHA-256 digest of a payload's exact bytes."""

__all__ = ("ContentDigest",)
