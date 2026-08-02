"""Shared lowercase-hex field patterns for cryptographic material.

One canonical home for the two hex shapes the signing and encryption
boundaries validate at, consumed by
:class:`core.corpus_manifest.SignedCorpusBundle`,
:class:`application.modelo.SignedReviewPackage`, and
:class:`application.modelo.CounterSignedReceipt`. Keeping the patterns in
``core`` lets the corpus-bundle signer and the review-package signer share one
declaration without either importing the other (``core`` may not import
``application``).

The patterns are the structural gate only: they fix the encoding (lowercase
hex) and the exact decoded length. They say nothing about whether the decoded
bytes are a well-formed key, digest, or signature -- that is the
``cryptography`` primitive's job at use time.

Both names count HEX CHARACTERS, not decoded bytes: :data:`HEX_PATTERN_64`
admits 32 decoded bytes and :data:`HEX_PATTERN_128` admits 64.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

HEX_PATTERN_64 = r"^[0-9a-f]{64}$"
"""Exactly 64 lowercase hex characters, i.e. 32 decoded bytes.

The shape of a SHA-256 digest and of a raw Ed25519 or X25519 key.
"""

HEX_PATTERN_128 = r"^[0-9a-f]{128}$"
"""Exactly 128 lowercase hex characters, i.e. 64 decoded bytes.

The shape of a raw Ed25519 signature, whose 64-byte size is fixed by RFC 8032.
Because the pattern pins the length exactly, a value that matches it is
already guaranteed to decode to a correctly-sized signature; no separate
length check is needed at the pydantic boundary.
"""

Hex64Str = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64),
]
"""The canonical hex-64 constrained shape (lowercase, exactly 64 hex chars).

Every unrelated hex-64 IDENTITY concept the codebase carries — a registry
snapshot id, a ledger transaction id, a content digest, a bucket event id, a
durable auth-operation id, and any future concept sharing this shape — is
declared as its OWN semantic alias assigned FROM this one primitive
(``SnapshotId = Hex64Str``), never by re-declaring the
``StringConstraints(...)`` call. One declaration means a future shape change
(a different digest width, admitting uppercase) is made once, here, and
every semantic alias picks it up; each alias still keeps its own name so a
value of one identity concept is never confused for another at the call
site, even though they are not distinguishable at the type-checker level
(plain ``Annotated[str, ...]`` aliases carry no nominal distinction; the
naming discipline is the enforcement).
"""

__all__ = ["HEX_PATTERN_64", "HEX_PATTERN_128", "Hex64Str"]
