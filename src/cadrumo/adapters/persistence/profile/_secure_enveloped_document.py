"""Canonical encrypted persistence kernel for Envelope-wrapped profile singleton documents.

Both kernels read and write through a :class:`SecureObjectRepository` supplied
at construction; neither opens storage of its own.

Sibling of :class:`~adapters.persistence.profile._secure_model_document.ProfileBareModelSecurePersistence`
(``_secure_model_document.py``). The two kernels cover two DIFFERENT on-disk wire
shapes that both happen to persist "one whole singleton Pydantic document per
profile bucket" — they are not interchangeable, and a namespace's existing shape
decides which kernel it enrolls in, never the other way round:

- :class:`ProfileBareModelSecurePersistence` stores the document's own
  ``model_dump_json()`` bytes directly. Classification, schema version, and
  write timestamp live ONLY as columns on the encrypted SQL row
  (:class:`~adapters.persistence.storage.SecureObjectWrite`); nothing is
  duplicated inside the JSON payload.
- :class:`ProfileEnvelopedModelSecurePersistence` (this module) wraps the
  document in :class:`~adapters.persistence.storage.Envelope` before
  serialising, so classification/schema-version/written-at are duplicated
  BOTH as SQL-row columns AND as fields inside the stored JSON. The inner
  fields are re-checked against the consumer's expectation on every load, as
  defense-in-depth against a row whose column metadata and embedded payload
  metadata have drifted apart.

Twelve profile repositories predate either kernel and hand-rolled the
Envelope-wrapped shape independently: this module is the shared home for that
shape now, so a namespace already carrying Envelope-wrapped rows on disk can
enroll in a kernel WITHOUT a wire-format break. Picking
:class:`ProfileBareModelSecurePersistence` for one of those namespaces would
silently change what bytes get written and, symmetrically, would fail to parse
the Envelope-wrapped rows already on disk for that namespace — a real
behaviour change, not a refactor. A brand-new namespace with no format to
preserve should default to the leaner :class:`ProfileBareModelSecurePersistence`
instead of adopting this one; this module exists to converge EXISTING
Envelope-wrapped repositories on one implementation, not to grow the
Envelope-wrapped shape's footprint.
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
)


class ProfileEnvelopedModelSecurePersistence[DocumentT: BaseModel]:
    """Persist one Envelope-wrapped strict Pydantic document through a governed secure object.

    The namespace definition remains the authority for object key, sensitivity,
    and schema version. ``save`` delegates to :meth:`to_secure_object_write` so
    an ordinary singleton save and a caller-composed co-commit write build the
    identical :class:`~adapters.persistence.storage.Envelope` bytes and cannot
    drift apart.
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

    def exists(self) -> bool:
        """Report whether the singleton object has been persisted.

        Checks the encrypted store for an object under this namespace and key
        without decrypting or validating it, so ``True`` attests to presence
        only, not integrity.
        """
        return self._objects.exists(self.namespace, self.object_key)

    def load(self) -> DocumentT:
        """Load, decrypt, and unwrap the persisted document, or return its declared empty form.

        The outer SQL-row classification/schema-version columns are checked by
        the underlying ``expected_class``/``max_supported_version`` load
        arguments; the inner :class:`~adapters.persistence.storage.Envelope`
        fields are re-checked independently as defense-in-depth against a row
        whose embedded payload metadata has drifted from its own columns.

        Raises:
            :class:`~adapters.persistence.storage.ClassificationError`: The
                inner envelope's classification disagrees with this
                repository's declared sensitivity.
            :class:`~adapters.persistence.storage.EnvelopeVersionError`: The
                inner envelope's schema version is not the consumer's current
                version.
        """
        from ..storage import Envelope, inner_envelope_classification_is_expected, inner_envelope_version_is_current

        record = self._objects.load(
            self.namespace,
            self.object_key,
            expected_class=self._definition.sensitivity,
            max_supported_version=self._definition.schema_version,
        )
        if record is None:
            return self._empty_document()
        envelope = Envelope[self._model_type].model_validate_json(record.payload)  # ty: ignore[invalid-type-form]  # reason: pydantic runtime generic parameterisation; the model type is a per-instance value, which no static type expression can carry
        if not inner_envelope_classification_is_expected(envelope.classification, self._definition.sensitivity):
            from ..storage import ClassificationError

            raise ClassificationError(
                f"{self.namespace}/{self.object_key} has classification {envelope.classification}; "
                f"consumer expected {self._definition.sensitivity}",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, self._definition.schema_version):
            from ..storage import EnvelopeVersionError

            raise EnvelopeVersionError(
                f"{self.namespace}/{self.object_key} is at version {envelope.schema_version}; "
                f"consumer supports up to {self._definition.schema_version}",
            )
        return envelope.payload

    def to_secure_object_write(self, document: DocumentT) -> SecureObjectWrite:
        """Prepare the Envelope-wrapped encrypted-SQL upsert without committing it.

        Callers that need to co-commit this document with sibling secure
        objects pass the returned value into their existing ``save_many``
        transaction. The returned write carries the identical
        :class:`~adapters.persistence.storage.Envelope` bytes :meth:`save`
        would persist directly.
        """
        from ..storage import Envelope

        envelope = Envelope[self._model_type](  # ty: ignore[invalid-type-form]  # reason: pydantic runtime generic parameterisation; the model type is a per-instance value, which no static type expression can carry
            schema_version=self._definition.schema_version,
            written_at=now(),
            classification=self._definition.sensitivity,
            payload=document,
        )
        return SecureObjectWrite(
            namespace=self.namespace,
            object_key=self.object_key,
            classification=self._definition.sensitivity,
            schema_version=self._definition.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )

    def save(self, document: DocumentT) -> None:
        """Encrypt, wrap in an Envelope, and save one document."""
        write = self.to_secure_object_write(document)
        self._objects.save(
            namespace=write.namespace,
            object_key=write.object_key,
            classification=write.classification,
            schema_version=write.schema_version,
            written_at=write.written_at,
            payload=write.payload,
        )


__all__ = [
    "ProfileEnvelopedModelSecurePersistence",
]
