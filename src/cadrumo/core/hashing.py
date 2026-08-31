"""Canonical SHA-256 utilities for bytes, files, and JSON content ids.

Provides :func:`sha256_hex`, :func:`sha256_file`, :func:`hash_file`,
:func:`canonical_json_bytes`, and :func:`content_hash_hex` as the single
authoritative SHA-256 implementations. Byte callers hash in memory; file
callers pass a :class:`~pathlib.Path` and share the chunked-read loop. All
adapters, application services, and domain modules import from here rather than
inlining ``hashlib.sha256(data).hexdigest()`` or re-deriving the canonical-JSON
content-hash serialisation.

This module is also the sole owner of the **canonical record encoding**: the one
byte spelling every digest-keyed or persisted JSON record uses. That encoding is
UTF-8, unescaped, refusing non-finite numbers -- see
:func:`canonical_json_bytes` for why each of those is the ruled choice. The
strict-decode counterparts belong here for the same reason: a reader that
accepts a duplicate member or a ``NaN`` token re-opens on the way in exactly
what the encoder closed on the way out, so :func:`reject_duplicate_json_members`
and :func:`reject_json_constant` are the hooks every strict ``json.loads`` of a
canonical record passes, and :func:`validate_prefixed_digest` is the one reader
of the ``sha256:``-prefixed spelling :func:`prefixed_digest` writes.

This module owns digest mechanics only. Domain identities such as profile
snapshots, calculation revisions, evidence bundles, and filing records own the
payload schema, value normalisation, contract-change policy, and pinned digest tests
that make a digest semantically stable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final, NoReturn

# Local UTF-8 constant rather than importing ``UTF_8_ENCODING`` from
# ``external_constants``: that module imports ``core.errors``, which pulls in
# ``core.redaction`` -> ``core.hashing``, so the import would close a cycle.
_UTF_8: Final[str] = "utf-8"

_HASH_CHUNK_SIZE = 65536

CONTENT_DIGEST_PREFIX: Final[str] = "sha256:"
"""Algorithm tag prefixing a digest wherever the record spells it out."""

_PREFIXED_DIGEST_LENGTH: Final[int] = len(CONTENT_DIGEST_PREFIX) + 64
_HEX_ALPHABET: Final[frozenset[str]] = frozenset("0123456789abcdef")
#: BLAKE2b digest width for content discriminators, in bytes.
_BLAKE2B_DISCRIMINATOR_BYTES: Final[int] = 16


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``.

    Use this for in-memory payloads once the caller has already chosen the byte
    representation (serialised JSON, string keys, ciphertext, etc.). It does
    not normalise text or domain values. For file-path inputs use
    :func:`sha256_file` or :func:`hash_file`.
    """
    return hashlib.sha256(data).hexdigest()


def blake2b_hex(data: bytes) -> str:
    """Return the lowercase hex BLAKE2b digest of ``data`` at discriminator width.

    A content DISCRIMINATOR, not a proof: these digests answer "did these bytes
    change since the last look", so they are deliberately compact rather than
    collision-proof against an adversary. Use :func:`sha256_hex` wherever a
    digest is evidence. The width is fixed here because two discriminators are
    only comparable when both were computed at the same size.
    """
    return hashlib.blake2b(data, digest_size=_BLAKE2B_DISCRIMINATOR_BYTES).hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    r"""Return deterministic canonical-JSON bytes.

    Sorted keys, compact separators, UTF-8, so two semantically equal payloads
    produce the same bytes.

    Two uses, both legitimate. Content hashing is the origin: this is the
    single serialisation the content-hash helpers feed into SHA-256, so equal
    payloads yield the same content hash / id. **Persisting a JSON payload is
    the other**, and it is not a widening of the contract — determinism is a
    stronger property than a storage payload needs, not a weaker one, so a
    serialisation fit to key a digest is fit to write to a row. Callers that
    persist through this helper get byte-stable payloads for free, which is
    what makes a stored payload comparable across writes at all.

    Prefer it over an ad-hoc ``json.dumps`` for either use. A hand-rolled
    ``indent=``/``default=`` call is not equivalent: ``indent`` inflates bytes
    for a reader that does not exist once the payload is encrypted, and
    ``default=str`` silently coerces a value this helper would have refused,
    turning a type error into a wrong stored value.

    The payload must already be JSON-compatible — that refusal is the point,
    not a limitation. Callers normalise ``Decimal``, :class:`~pathlib.Path`,
    datetimes, enums, and domain objects into stable strings or dictionaries
    before entering this helper (``model_dump(mode="json")`` does this for a
    pydantic model); any change to that projection is a caller-owned identity
    change.

    Two encoder choices are ruled here rather than left to each caller, because
    a record encoded one way and re-encoded another compares unequal while
    meaning the same thing.

    ``ensure_ascii=False`` — emit UTF-8, not ``\\uXXXX`` escapes. Escaping is
    lossless but it inflates accented content roughly threefold, and this is a
    Spanish tax application where accents in labels, names, addresses and
    activity descriptions are the ordinary case, not the exception. The cost is
    not the bytes; it is that a byte ceiling means two different things
    depending on the encoder, so a label that fits a record's declared limit
    under one spelling overflows it under the other.

    ``allow_nan=False`` — refuse the non-finite constants. Python's default
    emits the bare tokens ``NaN`` and ``Infinity``, which are not JSON and which
    every strict reader on the other side of the boundary rejects; permitting
    them here only moves the failure to load time, with the invalid token
    already persisted.
    """
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8)


def bounded_canonical_json_bytes(payload: object, *, maximum_bytes: int, subject: str) -> bytes:
    """Return :func:`canonical_json_bytes` refused above ``maximum_bytes``.

    A record with a fixed on-disk or on-wire slot declares its own ceiling and
    the ``subject`` naming it in the refusal. The bound is measured on the
    encoded bytes, which is the only measurement that means anything: a scalar
    count and a byte count diverge for exactly the accented content this
    encoding exists to carry unescaped.
    """
    encoded = canonical_json_bytes(payload)
    if len(encoded) > maximum_bytes:
        raise ValueError(f"{subject} exceeds its {maximum_bytes}-byte canonical limit")
    return encoded


def prefixed_digest(data: bytes) -> str:
    """Return the ``sha256:``-prefixed digest of ``data``.

    The spelling records use when the digest is stored as a self-describing
    string rather than a bare hex field. Pair with
    :func:`validate_prefixed_digest` on the reading side.
    """
    return f"{CONTENT_DIGEST_PREFIX}{sha256_hex(data)}"


def canonical_json_digest(payload: object, *, maximum_bytes: int, subject: str) -> str:
    """Return the ``sha256:``-prefixed digest of one bounded canonical record."""
    return prefixed_digest(bounded_canonical_json_bytes(payload, maximum_bytes=maximum_bytes, subject=subject))


def validate_prefixed_digest(value: str, *, field_name: str) -> str:
    """Return ``value`` when it is a lowercase ``sha256:``-prefixed digest.

    Uppercase hex is refused rather than folded: two spellings of one digest
    compare unequal as strings, and these values are compared as strings.
    """
    if (
        len(value) != _PREFIXED_DIGEST_LENGTH
        or not value.startswith(CONTENT_DIGEST_PREFIX)
        or any(character not in _HEX_ALPHABET for character in value[len(CONTENT_DIGEST_PREFIX) :])
    ):
        raise ValueError(f"{field_name} must be a lowercase sha256 digest")
    return value


def reject_duplicate_json_members(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    """Build one JSON object, refusing a repeated member name.

    ``json.loads`` keeps the last of a repeated key by default, so a payload
    carrying a member twice decodes to something its own canonical re-encoding
    does not reproduce. Pass as ``object_pairs_hook`` when decoding a record
    whose bytes are digest-bound.
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> NoReturn:
    """Refuse ``NaN``/``Infinity`` on decode, mirroring ``allow_nan=False``.

    Pass as ``parse_constant`` so a record this encoder would never have
    written cannot be read back in.
    """
    raise ValueError(f"non-finite JSON constant {value!r} is forbidden")


def content_hash_hex(payload: object) -> str:
    """Return the SHA-256 hex digest of the canonical-JSON form of ``payload``.

    The canonical content-addressing primitive: equivalent to
    ``sha256_hex(canonical_json_bytes(payload))``. Callers that need a truncated
    id slice the returned digest (``content_hash_hex(payload)[:16]``).

    Use this only after the caller's payload shape is part of that domain's
    identity contract. Changing keys, value normalisation, or included fields
    changes the digest and should be handled as an explicit identity contract change
    backed by pinned fixtures.
    """
    return sha256_hex(canonical_json_bytes(payload))


def hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256_hex, byte_count)`` for the file at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory. Hashes file contents
    exactly; path metadata, permissions, archive member names, and manifest
    normalisation stay outside this helper. Use this variant when the caller
    needs both the digest and the content length.
    """
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory. Hashes file contents
    exactly, not the file's path or metadata. Use :func:`hash_file` when the
    byte count is also needed.
    """
    hex_digest, _ = hash_file(path)
    return hex_digest


__all__ = [
    "CONTENT_DIGEST_PREFIX",
    "bounded_canonical_json_bytes",
    "canonical_json_bytes",
    "canonical_json_digest",
    "content_hash_hex",
    "hash_file",
    "prefixed_digest",
    "reject_duplicate_json_members",
    "reject_json_constant",
    "sha256_file",
    "sha256_hex",
    "validate_prefixed_digest",
]
