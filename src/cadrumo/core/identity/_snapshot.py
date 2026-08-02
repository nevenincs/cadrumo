"""Snapshot-identity alias for content-addressed snapshot surfaces.

A snapshot identity is the SHA-256 hex digest of the canonical JSON
form of the underlying snapshot payload. Two equal snapshots serialise
to identical ids, so consumers can deduplicate captures cheaply and
verify content addressing offline without contacting AEAT.

The hex-64 constraint is pinned at the pydantic boundary so a malformed
identifier is rejected on construction rather than leaking into
persisted records or wire payloads. The alias lives in
:mod:`cadrumo.core.identity` because snapshot surfaces are owned by
application services but consumed by adapters and persistence with no
single application-layer owner.

Surfaces that mint a snapshot id with a non-hex shape (notably the
censo snapshot, which derives its id from a JSON-canonical
``content_hash_hex`` family) do not consume this alias;
they are referential identities outside the content-addressed-hex
family.
"""

from __future__ import annotations

from .._hex import Hex64Str

SnapshotId = Hex64Str
"""Hex-64 content-addressed snapshot identity."""

__all__ = ("SnapshotId",)
