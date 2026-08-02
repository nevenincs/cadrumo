"""Cryptographic hash helpers for SQL secure object revision metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeGuard

from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex


def _canonical_instant(value: datetime) -> str:
    """Return a round-trip-stable canonical form of an instant.

    The secure-object ``written_at`` column persists through SQLite as a
    timezone-naive value: a ``datetime.now(UTC)`` written as
    ``...+00:00`` reads back as the same wall instant with ``tzinfo``
    dropped. Mixing the raw ``isoformat()`` into the revision id would
    therefore make the *recomputed* revision id (from the read-back,
    naive column) diverge from the *stored* one (derived at write from
    the aware value) — fail-closing valid rows on the read-time
    self-consistency gate. Canonicalising every instant to naive-UTC
    isoformat makes the write-time and read-time derivations identical.
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).replace(tzinfo=None).isoformat()


def derive_revision_id(
    *,
    namespace: str,
    object_key: bytes,
    schema_version: int,
    written_at: datetime,
    payload_hash: str,
    ciphertext_hash: str,
    previous_revision_id: str | None,
    previous_payload_hash: str | None,
) -> str:
    """Derive a deterministic secure-object revision id from row metadata."""
    parts = (
        namespace,
        object_key.hex(),
        str(schema_version),
        _canonical_instant(written_at),
        payload_hash,
        ciphertext_hash,
        previous_revision_id or "",
        previous_payload_hash or "",
    )
    return sha256_hex("\x1f".join(parts).encode(UTF_8_ENCODING))


def verify_revision_self_consistency(
    revision_id: str | None,
    *,
    namespace: str,
    object_key: bytes,
    schema_version: int,
    written_at: datetime,
    previous_revision_id: str | None,
    payload_hash: str | None,
    ciphertext_hash: str | None,
    previous_payload_hash: str | None,
) -> TypeGuard[str]:
    """Return whether a stored ``revision_id`` recomputes from its lineage columns.

    The revision id is a content address over the whole revision-lineage
    metadata tuple (namespace, object-key digest, schema version,
    ``written_at``, ``payload_hash``, ``ciphertext_hash``, and the previous
    revision/payload-hash links). Recomputing it from the stored columns and
    comparing to the stored ``revision_id`` is a read-time integrity gate: a
    tamper of any single lineage column — including ``payload_hash`` — that
    does not also recompute ``revision_id`` is detected and can be failed
    closed. The check is purely metadata-internal (it never touches the
    encrypted payload bytes), so it does not interfere with the AEAD payload
    authentication or with corruption probes that re-encrypt a mutated payload
    without restamping the metadata.

    A row carrying no ``revision_id`` is REFUSED, not tolerated. Every write
    stamps revision metadata inside the same transaction that inserts the
    ciphertext, so a committed row without one is corruption *now* rather than
    an older shape this application ever wrote; the pre-release compatibility
    regime carries no read path for shapes nothing released produced. Refusing
    here is also what keeps this gate the single authority on the question:
    :class:`~._secure_object_records.SecureObjectRecord` types ``revision_id``
    as an exactly-64-character digest, so a row this function admitted with no
    revision id could only ever fail again — untyped, and past the gate — while
    the record was being built. A row whose ``revision_id`` is present but
    whose required hash inputs are absent is likewise inconsistent.

    Returning ``True`` narrows ``revision_id`` to :class:`str` for the caller,
    which is precisely the guarantee the record contract needs. The narrowing
    is a :class:`~typing.TypeGuard` rather than a :class:`~typing.TypeIs`
    because ``False`` carries no type claim at all: a genuine ``str`` whose
    lineage fails to recompute is refused too.
    """
    if revision_id is None:
        return False
    if payload_hash is None or ciphertext_hash is None:
        return False
    recomputed = derive_revision_id(
        namespace=namespace,
        object_key=object_key,
        schema_version=schema_version,
        written_at=written_at,
        payload_hash=payload_hash,
        ciphertext_hash=ciphertext_hash,
        previous_revision_id=previous_revision_id,
        previous_payload_hash=previous_payload_hash,
    )
    return recomputed == revision_id
