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

Every name counts HEX CHARACTERS, not decoded bytes: :data:`HEX_PATTERN_64`
admits 32 decoded bytes and :data:`HEX_PATTERN_128` admits 64.
:data:`HEX_PATTERN_16` is not cryptographic material at all -- it is the
shape of a TRUNCATED digest used as a short content address, and it lives
here so the truncated form is declared once beside the full one rather than
as an inline constraint at each carrier.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

HEX_PATTERN_64 = r"^[0-9a-f]{64}$"
"""Exactly 64 lowercase hex characters, i.e. 32 decoded bytes.

The shape of a SHA-256 digest and of a raw Ed25519 or X25519 key.
"""

HEX_PATTERN_16 = r"^[0-9a-f]{16}$"
"""Exactly 16 lowercase hex characters: a SHA-256 digest truncated to 8 bytes.

The shape of a short CONTENT ADDRESS rather than a full digest -- notably
:func:`domain.filing.compute_modelo_draft_id`, which content-addresses a
filing draft by the first 16 hex characters of its payload hash. A truncated
digest is a weaker collision claim than the full 64 and must never be used
where a cryptographic digest is required; it exists so a human-quotable
identifier can still be re-derived and compared.
"""

HEX_PATTERN_128 = r"^[0-9a-f]{128}$"
"""Exactly 128 lowercase hex characters, i.e. 64 decoded bytes.

The shape of a raw Ed25519 signature, whose 64-byte size is fixed by RFC 8032.
Because the pattern pins the length exactly, a value that matches it is
already guaranteed to decode to a correctly-sized signature; no separate
length check is needed at the pydantic boundary.
"""

Hex16Str = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=16, max_length=16, pattern=HEX_PATTERN_16),
]
"""The canonical hex-16 constrained shape (lowercase, exactly 16 hex chars).

The truncated-content-address counterpart of :data:`Hex64Str`, and governed by
the same discipline: a concept carrying this shape USES this primitive, and
never re-declares the ``StringConstraints(...)`` call.
"""

Hex64Str = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64),
]
"""The canonical hex-64 constrained shape (lowercase, exactly 64 hex chars).

Every unrelated hex-64 concept the codebase carries — a registry snapshot id, a
ledger transaction id, a content digest, a bucket event id, a durable
auth-operation id — USES this primitive, or the one existing semantic alias for
that concept in :mod:`core.identity`. It is never re-declared by writing the
``StringConstraints(...)`` call or the pattern out again. One declaration means
a future shape change — a different digest width, admitting uppercase — is made
once, here, and reaches every consumer.

**Do not mint a new per-concept alias.** A field whose concept already has one
(``TransactionId``, ``WorkUnitId``, ``FilingRecordId``, ``SnapshotId``,
``InvoiceId``, ``CalculationRevisionId``, ``VerificationReportId``,
``ContentDigest``) uses it; a field whose concept has none takes ``Hex64Str``
directly, or ``ContentDigest`` where the value is a payload digest.

This reverses an earlier instruction in this docstring, and the reason is worth
keeping because the earlier argument is easy to re-derive. A per-concept alias
was said to stop a value of one identity being confused for another at the call
site. It cannot: a plain ``Annotated[str, ...]`` alias carries **no nominal
distinction**, so a type checker separates ``TransactionId`` from
``SnapshotId`` exactly as much as it separates two ``str`` fields — not at all.
The protection was naming convention, never enforcement. Weighed against a
codebase that had accumulated dozens of parallel spellings of one shape, the
convention cost more than it bought.
"""

__all__ = ["HEX_PATTERN_16", "HEX_PATTERN_64", "HEX_PATTERN_128", "Hex16Str", "Hex64Str"]
