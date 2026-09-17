"""Secure-object singleton keypair persistence shared by profile adapters.

The mint-or-load-winner transaction belongs to the persistence adapter: it
knows secure-object namespaces, create-only revisions, and the storage row
representation.  Application modules receive typed capabilities instead of
depending on any of those adapter details.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ....core.external_constants import UTF_8_ENCODING
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.time.utc import UtcInstant
from ..storage.errors import SecureObjectRevisionConflictError
from ..storage.secure_object_namespaces import SecureObjectNamespaceDefinition
from ..storage.sql.secure_objects import SecureObjectRepository


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
    """Return a bucket singleton, minting once and returning a race winner.

    Core types:
    :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
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


__all__ = ["ensure_singleton_keypair"]
