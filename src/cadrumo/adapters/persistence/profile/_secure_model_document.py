"""Canonical encrypted persistence kernel for profile singleton Pydantic documents.

Profile adapters that persist one whole typed document share the same durable
contract: bytes are serialised directly from the strict Pydantic model, then
encrypted by :class:`SecureObjectRepository` under a registry-owned namespace.
This module owns that mechanical boundary so individual repositories retain
only their domain mutations and translated load failures. It deliberately
exposes :class:`SecureObjectWrite` construction for callers such as the
prorrata filing path that co-commit the document with sibling writes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ....core.external_constants import UTF_8_ENCODING
from ....core.time import now
from ..storage import (
    SecureObjectNamespaceDefinition,
    SecureObjectRepository,
    SecureObjectWrite,
    secure_object_logical_path,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
)


def resolve_profile_secure_object_repository(
    *,
    objects: SecureObjectRepository | None = None,
    bucket_id: str | None = None,
) -> SecureObjectRepository:
    """Resolve the one secure-object repository for a profile document.

    Explicit repositories are the real encrypted-SQL test seam. An explicit
    bucket is for application callers whose authoritative context already names
    the target bucket; every other production caller resolves through the
    active-bucket runtime wrapper. No plaintext or filesystem fallback exists.
    """
    if objects is not None:
        return objects
    if bucket_id is not None:
        return secure_object_repository_for_bucket(bucket_id)
    return secure_object_repository_for_active_bucket()


class ProfileBareModelSecurePersistence[DocumentT: BaseModel]:
    """Persist one strict Pydantic document through a governed secure object.

    The namespace definition remains the authority for object key, sensitivity,
    and schema version. ``save`` always delegates to ``save_many`` so an
    ordinary singleton save and a caller-composed ``to_secure_object_write``
    follow the same encrypted SQL write path.
    """

    def __init__(
        self,
        *,
        objects: SecureObjectRepository,
        definition: SecureObjectNamespaceDefinition,
        model_type: type[DocumentT],
        empty_document: Callable[[], DocumentT],
    ) -> None:
        self._objects = objects
        self._definition = definition
        self._model_type = model_type
        self._empty_document = empty_document

    @property
    def object_key(self) -> str:
        """Return the registry-owned singleton object key."""
        return self._definition.require_default_object_key()

    @property
    def namespace(self) -> str:
        """Return the registry-owned namespace value."""
        return self._definition.namespace

    def logical_path(self, marker: str) -> Path:
        """Return the registry-defined logical marker for one repository surface."""
        return secure_object_logical_path(self._definition.namespace, marker)

    def load(self) -> DocumentT:
        """Load and strictly decode the document, or return its declared empty form."""
        record = self._objects.load(
            self._definition.namespace,
            self.object_key,
            expected_class=self._definition.sensitivity,
            max_supported_version=self._definition.schema_version,
        )
        if record is None:
            return self._empty_document()
        return self._model_type.model_validate_json(record.payload)

    def to_secure_object_write(self, document: DocumentT) -> SecureObjectWrite:
        """Prepare the encrypted-SQL upsert without committing it.

        Callers that need to co-commit this document with sibling secure objects
        pass the returned value into their existing ``save_many`` transaction.
        """
        return SecureObjectWrite(
            namespace=self._definition.namespace,
            object_key=self.object_key,
            classification=self._definition.sensitivity,
            schema_version=self._definition.schema_version,
            written_at=now(),
            payload=document.model_dump_json().encode(UTF_8_ENCODING),
        )

    def save(self, document: DocumentT) -> None:
        """Encrypt and save one document in the transactional secure-object path."""
        self._objects.save_many((self.to_secure_object_write(document),))


__all__ = [
    "ProfileBareModelSecurePersistence",
    "resolve_profile_secure_object_repository",
]
