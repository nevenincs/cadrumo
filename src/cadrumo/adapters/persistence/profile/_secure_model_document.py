"""Canonical encrypted persistence kernel for BARE-document profile singletons.

Profile adapters that persist one whole typed document as bare JSON bytes
(``document.model_dump_json()``, with classification/schema-version/written-at
carried only as SQL-row columns, nothing duplicated inside the payload) share
the same durable contract. This module owns that mechanical boundary so
individual repositories retain only their domain mutations and translated
load failures. It deliberately exposes :class:`SecureObjectWrite` construction
for callers such as the prorrata filing path that co-commit the document with
sibling writes.

This is NOT the only singleton-document persistence kernel: a namespace whose
on-disk rows are wrapped in :class:`~adapters.persistence.storage.Envelope`
(classification/schema-version/written-at duplicated inside the JSON payload
itself) is a different wire shape and belongs on
:class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
(``_secure_enveloped_document.py``) instead — enrolling an Envelope-wrapped
namespace here would change what bytes get written and fail to read what is
already on disk. See that module's docstring for the two shapes compared side
by side and the rule for which one a given namespace belongs to.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel

from ....core.external_constants import UTF_8_ENCODING
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, DEFAULT_WRITE_PROVENANCE
from ....core.time.clock import now
from ..storage.namespace_registry import secure_object_logical_path
from ..storage.runtime_repository import secure_object_repository_for_active_bucket, secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import SecureObjectNamespaceDefinition
from ..storage.sql import SecureObjectRepository, SecureObjectWrite
from ._revision_guarded_singleton_mutation import mutate_revision_guarded_singleton


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

    Args:
        objects: An explicit :class:`SecureObjectRepository` to reuse (the
            test seam), bypassing bucket resolution entirely when supplied.
        bucket_id: An explicit bucket id to resolve against, for a caller
            whose authoritative context already names the target bucket.
    """
    if objects is not None:
        return objects
    if bucket_id is not None:
        return secure_object_repository_for_bucket(bucket_id)
    return secure_object_repository_for_active_bucket()


class ProfileBareModelSecurePersistence[DocumentT: BaseModel]:
    """Persist one strict Pydantic document, stored bare, through a governed secure object.

    "Stored bare" means ``document.model_dump_json()`` is written directly as
    the row payload — no :class:`~adapters.persistence.storage.Envelope`
    wrapper. Use this kernel only for a namespace whose on-disk rows are
    already in that shape, or a brand-new namespace with no format to
    preserve; an Envelope-wrapped namespace belongs on
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    instead (see the module docstring).

    The namespace definition remains the authority for object key, sensitivity,
    and schema version. ``save`` always delegates to ``save_many`` so an
    ordinary singleton save and a caller-composed ``to_secure_object_write``
    follow the same encrypted SQL write path. ``write_provenance`` is optional
    and defaults to the substrate's own default; a caller that already stamps
    a specific provenance string on its writes (an audit-trail identifier
    naming the owning module) passes it through the constructor rather than
    losing it to enrollment.
    """

    def __init__(
        self,
        *,
        objects: SecureObjectRepository,
        definition: SecureObjectNamespaceDefinition,
        model_type: type[DocumentT],
        empty_document: Callable[[], DocumentT],
        write_provenance: str = DEFAULT_WRITE_PROVENANCE,
    ) -> None:
        self._objects = objects
        self._definition = definition
        self._model_type = model_type
        self._empty_document = empty_document
        self._write_provenance = write_provenance

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
        document, _revision_id = self.load_revisioned()
        return document

    def _decode_record(self, payload: bytes) -> DocumentT:
        """Validate one loaded encrypted bare-document payload."""
        return self._model_type.model_validate_json(payload)

    def load_revisioned(self) -> tuple[DocumentT, str]:
        """Return the document and revision from one secure-object record."""
        record = self._objects.load(
            self._definition.namespace,
            self.object_key,
            expected_class=self._definition.sensitivity,
            max_supported_version=self._definition.schema_version,
        )
        if record is None:
            return self._empty_document(), ABSENT_SECURE_OBJECT_REVISION_ID
        return self._decode_record(record.payload), record.revision_id

    def _validate_payloads(self, payloads: Mapping[str, bytes]) -> None:
        """Validate all upgraded singleton bytes before the migration batch writes."""
        for payload in payloads.values():
            self._model_type.model_validate_json(payload)

    def to_secure_object_write(
        self,
        document: DocumentT,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare the encrypted-SQL upsert without committing it.

        Callers that need to co-commit this document with sibling secure objects
        pass the returned value into their existing ``save_many`` transaction.

        ``expected_revision_id`` is the compare-and-swap half. These documents
        are singletons, so a co-commit composed from an unguarded read writes
        the whole document back and discards any entry another caller added in
        between. Pass the revision :meth:`load_revisioned` reported.
        """
        return SecureObjectWrite(
            namespace=self._definition.namespace,
            object_key=self.object_key,
            classification=self._definition.sensitivity,
            schema_version=self._definition.schema_version,
            written_at=now(),
            payload=document.model_dump_json().encode(UTF_8_ENCODING),
            write_provenance=self._write_provenance,
            expected_revision_id=expected_revision_id,
        )

    def save(self, document: DocumentT) -> None:
        """Encrypt and save one document in the transactional secure-object path."""
        self._objects.save_many((self.to_secure_object_write(document),))

    def mutate(self, mutation: Callable[[DocumentT], DocumentT], *, attempts: int = 4) -> DocumentT:
        """Apply ``mutation`` to the stored document as one guarded unit of work.

        These documents are SINGLETONS: every entry lives in one encrypted row,
        so an "add one record" is really read-whole-document, rebuild, write
        whole document. Performed unguarded, two callers adding DIFFERENT
        entries both read the same document and the later write silently
        discards the earlier caller's entry -- a lost update, not a conflict any
        uniqueness check would notice, because the two entries never met.

        The write carries the revision the document was READ at, so the
        substrate refuses it if the row moved in between; the mutation is then
        re-applied to the newly-current document. ``mutation`` is therefore
        called once per attempt and MUST be a pure function of the document it
        is handed -- it must not close over a value derived from an earlier
        read, or the retry re-applies a stale decision.

        Args:
            mutation: Builds the next document from the current one. May raise
                to refuse the mutation outright (a duplicate-identifier check,
                for instance); the refusal propagates unretried, since a
                conflict is what the retry exists for and a refusal is not one.
            attempts: Maximum reads of the current document. Exceeding them
                raises the substrate's conflict error rather than looping.

        Returns:
            The document as written.

        Raises:
            SecureObjectRevisionConflictError: Contention persisted across
                every attempt.
        """
        def write(document: DocumentT, *, expected_revision_id: str) -> SecureObjectWrite:
            return self.to_secure_object_write(document, expected_revision_id=expected_revision_id)

        def save(secure_object_write: SecureObjectWrite) -> None:
            self._objects.save_many((secure_object_write,))

        return mutate_revision_guarded_singleton(
            mutation,
            load_revisioned=self.load_revisioned,
            write=write,
            save=save,
            attempts=attempts,
        )


__all__ = [
    "ProfileBareModelSecurePersistence",
    "resolve_profile_secure_object_repository",
]
