"""Shared mint-or-load-winner primitive for a bucket-scoped singleton keypair.

:func:`~application.modelo.ensure_recipient_encryption_keypair` (X25519) and
:func:`~application.modelo.ensure_review_package_signing_keypair` (Ed25519)
each persist a per-bucket cryptographic keypair as a
:class:`~adapters.persistence.storage.SecureObjectRepository` singleton row:
load the existing row when present; otherwise mint a fresh keypair, attempt a
create-only write, and on a losing race against a concurrent minter, reload
and return whichever keypair actually landed. That control flow -- not the
key material itself, which differs by algorithm -- is identical between the
two, so it lives here once. Each caller supplies its own key-generation
callback, its own typed keypair model, and its own domain error for a
bucket-identity mismatch; this module owns only the load/generate/race-retry
orchestration.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ...adapters.persistence.storage._secure_object_namespaces import SecureObjectNamespaceDefinition
from ...adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core.external_constants import UTF_8_ENCODING
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.utc import UtcInstant


def ensure_singleton_keypair[KeypairT: BaseModel](
    *,
    repository: SecureObjectRepository,
    namespace: SecureObjectNamespaceDefinition,
    object_key: str,
    model_type: type[KeypairT],
    generate: Callable[[], KeypairT],
    bucket_id_of: Callable[[KeypairT], str],
    created_at_of: Callable[[KeypairT], UtcInstant],
    expected_bucket_id: str,
    mismatch_error: Callable[[], Exception],
    write_provenance: str,
) -> KeypairT:
    """Return the bucket's singleton keypair, minting one via ``generate`` on first use.

    Idempotent: a second call against the same bucket returns the SAME
    keypair rather than rotating it, so material sealed/signed against it
    today still verifies/decrypts next week. Concurrency-safe: a losing
    writer in a mint race reloads and returns the winner's keypair rather
    than erroring or silently persisting a second, orphaned key.

    Args:
        repository: The bucket's
            :class:`~adapters.persistence.storage.SecureObjectRepository`.
        namespace: The namespace definition owning this keypair's storage
            contract (object key grammar, sensitivity, schema version).
        object_key: The natural object key this bucket's keypair is filed
            under (already resolved by the caller, e.g. from the bucket id).
        model_type: The concrete typed keypair model to decode a stored row
            into.
        generate: Builds a fresh keypair (new key material, ``created_at``
            already stamped) when none exists yet. Called at most once per
            invocation, even under a losing race -- the loser discards its
            freshly generated key material entirely.
        bucket_id_of: Extracts the bucket id a decoded keypair claims to
            belong to, for the mismatch check below.
        created_at_of: Extracts the keypair's own ``created_at`` instant, so
            the persisted row's ``written_at`` column agrees with the
            model's stamped value exactly (including a test's
            ``generated_at`` override) rather than drifting by a second,
            independently-read clock instant.
        expected_bucket_id: The bucket id every decoded keypair must match.
        mismatch_error: Builds the caller's domain-specific error for a
            stored keypair whose payload names a different bucket than the
            key it was read from (a foreign keypair re-keyed under this
            bucket must never silently become this bucket's key).
        write_provenance: Audit-trail identifier naming the calling module,
            stamped on the persisted row.

    Returns:
        The bucket's keypair -- freshly minted, freshly loaded, or the
        winner of a concurrent mint race.
    """

    def _validated(payload: bytes) -> KeypairT:
        keypair = model_type.model_validate_json(payload)
        if bucket_id_of(keypair) != expected_bucket_id:
            raise mismatch_error()
        return keypair

    existing = repository.load(
        namespace.namespace,
        object_key,
        expected_class=namespace.sensitivity,
        max_supported_version=namespace.schema_version,
    )
    if existing is not None:
        return _validated(existing.payload)

    keypair = generate()
    try:
        repository.save(
            namespace=namespace.namespace,
            object_key=object_key,
            classification=namespace.sensitivity,
            schema_version=namespace.schema_version,
            written_at=created_at_of(keypair),
            payload=keypair.model_dump_json().encode(UTF_8_ENCODING),
            write_provenance=write_provenance,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    except SecureObjectRevisionConflictError:
        winner = repository.load(
            namespace.namespace,
            object_key,
            expected_class=namespace.sensitivity,
            max_supported_version=namespace.schema_version,
        )
        if winner is None:
            raise
        return _validated(winner.payload)
    return keypair


__all__ = [
    "ensure_singleton_keypair",
]
