"""Content-digest alias for surfaces that content-address a payload.

A content digest is the lowercase hex SHA-256 of a payload's exact bytes.
It is not an identity minted by a service; it is a re-computable claim
about bytes, so every consumer that stores one must be able to recompute
it and compare. Pinning the hex-64 shape at the pydantic boundary keeps a
malformed digest out of persisted records and wire payloads, where the
mismatch would otherwise surface only when a later verification pass
recomputes the hash.

The alias derives from :data:`core.Hex64Str`, the one canonical hex-64
constrained primitive every unrelated hex-64 identity concept is defined
from, and lives beside :data:`SnapshotId` in :mod:`cadrumo.core.identity`
because digest-bearing records span the application, adapter, and
persistence layers with no single owner.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

from .._hex import HEX_PATTERN_64, Hex64Str

ContentDigest = Hex64Str
"""Lowercase hex-64 SHA-256 digest of a payload's exact bytes."""

#: The digest shape widened to admit the empty string, derived from the same
#: canonical pattern so the two cannot drift apart.
_ABSENT_OR_HEX_64 = f"^(?:{HEX_PATTERN_64.removeprefix('^').removesuffix('$')})?$"

ContentDigestOrAbsent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=64, pattern=_ABSENT_OR_HEX_64),
]
"""A :data:`ContentDigest`, or ``""`` where absence is a documented outcome.

Some fingerprints are genuinely optional -- a certificate fingerprint is ``""``
when no certificate is configured, and that is a real state rather than a
missing value. Such a field still must not accept a *malformed* digest, so this
alias admits exactly two shapes: the canonical hex-64 digest, or nothing at
all. Prefer :data:`ContentDigest` wherever a digest is always produced.
"""

#: The same digest carried in its self-describing ``sha256:`` form, derived from
#: the one canonical pattern so the bare and prefixed shapes cannot drift apart.
_PREFIXED_HEX_64 = f"^sha256:{HEX_PATTERN_64.removeprefix('^').removesuffix('$')}$"

PrefixedContentDigest = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=71, max_length=71, pattern=_PREFIXED_HEX_64),
]
"""A :data:`ContentDigest` written as ``sha256:<hex64>``.

The custody label surface stores digests self-describing rather than bare, so a
reader never has to know which algorithm produced the 64 characters it is
holding. The two shapes are NOT interchangeable: a field typed
:data:`ContentDigest` refuses the prefixed form and vice versa, which is the
point -- the prefix is part of the stored value, not decoration.

Promoted here because the shape repeats across the custody, filing and
operations surfaces, and one module had already grown a private copy of the
constraint.
"""

__all__ = ("ContentDigest", "ContentDigestOrAbsent", "PrefixedContentDigest")
