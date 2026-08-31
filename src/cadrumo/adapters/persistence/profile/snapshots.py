"""Encrypted secure-object persistence for bucket-scoped snapshot payloads.

:class:`SecureSnapshotRepository` is the one concrete backend behind the
application-layer ``SnapshotRepository`` port. Each stored snapshot is a typed
:class:`Envelope` row written through
:class:`SecureObjectRepository`, addressed by an object key carrying the bucket
id and the content-addressed snapshot id.

The repository is generic over its payload model and is driven entirely by
caller-supplied data: the payload type, the namespace definition, the object-key
grammar, the error types to raise, and a domain label used in diagnostics. That
is what lets one implementation serve the live snapshot services, the M036
declaration lifecycle, and the M145 communication records without any of them
sharing a payload shape.

It lives here, in the persistence adapter, rather than beside the port it
implements: the secure-object coupling is then a same-layer
``adapters -> adapters.persistence.storage`` import instead of an
``application -> adapters`` one. This mirrors the treatment the prorrata
register already receives.

Errors are injected rather than imported. A repository serving three different
application packages cannot name any one package's error type without either
reaching into that package's private module or importing its facade, and the
facade import would close a cycle: the live facade eagerly imports the services
that construct this class. Taking the class as a constructor argument keeps the
adapter self-contained and leaves every caller raising exactly what it raised
before.

See Also:
    :mod:`application.live`
        Declares the ``SnapshotRepository`` port this class satisfies and the
        lifecycle service bases that consume it.
    :mod:`adapters.persistence.profile.prorrata_register`
        Sibling profile-local secure-object adapter whose placement this
        follows.
"""

from __future__ import annotations

from hmac import compare_digest
from typing import TYPE_CHECKING

# Runtime import, not TYPE_CHECKING: the PEP 695 bound on ``TPayload`` is
# evaluated lazily, and pydantic resolves it when it builds the envelope schema.
from pydantic import BaseModel

from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import UTF_8_ENCODING
from ....core.time.clock import now
from ..storage.crypto.encrypted_columns import HashedLookup
from ..storage.envelope.contract import Envelope
from ..storage.errors import ClassificationError, EnvelopeVersionError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.schema_lineage import inner_envelope_classification_is_expected, inner_envelope_version_is_current
from ..storage.sql import SecureObjectRepository, SecureObjectWrite

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....core.classification.policies import SensitivityClass
    from ..storage.secure_object_namespaces import SecureObjectNamespaceDefinition
    from ..storage.sql import SecureObjectRecord

__all__ = ["SecureSnapshotRepository"]


class SecureSnapshotRepository[TPayload: BaseModel]:
    """Generic secure-object snapshot repository for one runtime bucket.

    The repository satisfies the ``SnapshotRepository`` structural contract used
    by the live snapshot services while replacing one-file-per-bucket JSONL
    stores with encrypted secure-object rows. Each row is a typed
    :class:`Envelope` whose object key carries the bucket id and
    content-addressed snapshot id.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        payload_model: type[TPayload],
        namespace_definition: SecureObjectNamespaceDefinition,
        object_key: Callable[[str, str], str],
        not_found_factory: Callable[[str], Exception],
        ambiguous_prefix_factory: Callable[[str, tuple[str, ...]], Exception],
        domain_label: str,
        input_error_cls: type[CadrumoError],
        objects: SecureObjectRepository | None = None,
        enforce_payload_identity: bool = True,
        classification_error_factory: Callable[[str, SensitivityClass, SensitivityClass], Exception] | None = None,
        version_error_factory: Callable[[str, int, int], Exception] | None = None,
    ) -> None:
        """Bind the repository to one bucket and one payload namespace.

        Args:
            bucket_id: Runtime bucket whose encrypted store backs this
                repository. Must not be blank.
            payload_model: Concrete payload model persisted in the envelope.
            namespace_definition: Secure-object namespace, sensitivity class and
                schema version this repository reads and writes under.
            object_key: Builds the plaintext object key from bucket id and
                snapshot id.
            not_found_factory: Builds the caller's lookup-miss exception.
            ambiguous_prefix_factory: Builds the caller's ambiguous-prefix
                exception from the requested prefix and the matching ids.
            domain_label: Short noun used in diagnostics (``"deudas"``).
            input_error_cls: Exception class raised for invariant violations —
                blank ids, bucket mismatches, and rows addressed by another
                snapshot's key. Injected so this adapter names no single
                application package's error type.
            objects: Secure-object store override. Resolved for ``bucket_id``
                when omitted.
            enforce_payload_identity: Whether this generic adapter owns the
                payload bucket/id checks. Application repositories with a
                different identity field keep that policy at their typed port
                and disable this generic ``bucket_id`` convention.
            classification_error_factory: Optional typed refusal factory for
                callers whose port must not expose persistence errors.
            version_error_factory: Optional typed version-refusal factory for
                callers whose port must not expose persistence errors.
        """
        self._input_error_cls = input_error_cls
        trimmed = bucket_id.strip()
        if not trimmed:
            raise input_error_cls("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._payload_model = payload_model
        self._namespace_definition = namespace_definition
        self._object_key = object_key
        self._not_found_factory = not_found_factory
        self._ambiguous_prefix_factory = ambiguous_prefix_factory
        self._domain_label = domain_label
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)
        self._enforce_payload_identity = enforce_payload_identity
        self._classification_error_factory = classification_error_factory
        self._version_error_factory = version_error_factory

    @property
    def bucket_id(self) -> str:
        """Return the runtime bucket this repository is bound to."""
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        """Return whether a snapshot is stored under ``snapshot_id``."""
        return self._objects.exists(
            self._namespace_definition.namespace,
            self._object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> TPayload:
        """Return the snapshot stored under ``snapshot_id``.

        Re-addresses the decrypted row: both its payload bucket and its
        snapshot id must agree with what was requested.
        """
        record = self._objects.load(
            self._namespace_definition.namespace,
            self._object_key(self._bucket_id, snapshot_id),
            expected_class=self._namespace_definition.sensitivity,
            max_supported_version=self._namespace_definition.schema_version,
        )
        if record is None:
            raise self._not_found_factory(snapshot_id)
        snapshot = self._snapshot_from_record(record, requested_snapshot_id=snapshot_id)
        if self._enforce_payload_identity and self._bucket_id_of(snapshot) != self._bucket_id:
            raise self._input_error_cls(
                f"{self._domain_label} snapshot bucket_id={self._bucket_id_of(snapshot)!r} "
                f"does not match repository bucket {self._bucket_id!r}",
            )
        if self._snapshot_id_of(snapshot) != snapshot_id:
            raise self._input_error_cls(
                f"{self._domain_label} snapshot id={self._snapshot_id_of(snapshot)!r} "
                f"does not match requested snapshot {snapshot_id!r}",
            )
        return snapshot

    def list_snapshots(self) -> tuple[TPayload, ...]:
        """Return every stored snapshot, refusing any row that is not its own.

        ``load`` verifies the decrypted snapshot id against the id that was
        requested. Enumeration reached the same rows without that check, so a
        valid snapshot re-encrypted under another snapshot's key was returned
        by ``list_snapshots``/``latest``/``resolve`` -- and by every shared
        consumer built on them -- while a targeted ``load`` of that key
        refused it. Both doors now re-address the row.

        Raises:
            CadrumoError: The caller-supplied input-error class, when a row's
                payload bucket differs from the repository's bucket, or when
                its snapshot id does not agree with the key it is stored under.
        """
        snapshots: list[TPayload] = []
        for record in self._objects.list_records(
            self._namespace_definition.namespace,
            expected_class=self._namespace_definition.sensitivity,
            max_supported_version=self._namespace_definition.schema_version,
        ):
            snapshot = self._snapshot_from_record(record)
            snapshot_bucket = self._bucket_id_of(snapshot)
            if snapshot_bucket != self._bucket_id:
                raise self._input_error_cls(
                    f"{self._domain_label} snapshot bucket_id={snapshot_bucket!r} "
                    f"does not match repository bucket {self._bucket_id!r}",
                    translated_message="application.live.snapshot_base.errors.snapshot_bucket_mismatch",
                    context={
                        "domain_label": self._domain_label,
                        "snapshot_bucket": snapshot_bucket,
                        "repository_bucket": self._bucket_id,
                    },
                )
            self._assert_addressed_by_its_own_key(record, snapshot)
            snapshots.append(snapshot)
        return tuple(sorted(snapshots, key=lambda item: self._snapshot_id_of(item)))

    def _assert_addressed_by_its_own_key(self, record: SecureObjectRecord, snapshot: TPayload) -> None:
        """Refuse a snapshot stored under a different snapshot's key.

        The stored ``object_key`` is a :class:`HashedLookup` digest from which
        the plaintext key cannot be recovered, so the check recomputes the
        digest of the key this snapshot *should* occupy and compares the two
        in constant time.
        """
        snapshot_id = self._snapshot_id_of(snapshot)
        expected_key = HashedLookup.compute(self._object_key(self._bucket_id, snapshot_id))
        if not compare_digest(expected_key, record.object_key):
            raise self._input_error_cls(
                f"{self._domain_label} snapshot id={snapshot_id!r} is stored under a different snapshot's key",
                translated_message="application.live.snapshot_base.errors.snapshot_key_mismatch",
                context={
                    "domain_label": self._domain_label,
                    "snapshot_id": snapshot_id,
                    "repository_bucket": self._bucket_id,
                },
            )

    def resolve(self, snapshot_id: str) -> TPayload:
        """Return the one snapshot matching ``snapshot_id`` or a unique prefix."""
        trimmed_snapshot_id = snapshot_id.strip()
        if not trimmed_snapshot_id:
            raise self._input_error_cls("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if self._snapshot_id_of(snapshot) == trimmed_snapshot_id
            or self._snapshot_id_of(snapshot).startswith(trimmed_snapshot_id)
        ]
        if not matches:
            raise self._not_found_factory(snapshot_id)
        if len(matches) > 1:
            full_ids = tuple(sorted(self._snapshot_id_of(snapshot) for snapshot in matches))
            raise self._ambiguous_prefix_factory(snapshot_id, full_ids)
        return matches[0]

    def save(self, snapshot: TPayload) -> None:
        """Persist ``snapshot`` as an encrypted secure-object row."""
        write = self.to_secure_object_write(snapshot)
        self._objects.save(
            namespace=write.namespace,
            object_key=write.object_key,
            classification=write.classification,
            schema_version=write.schema_version,
            written_at=write.written_at,
            payload=write.payload,
        )

    def to_secure_object_write(self, snapshot: TPayload) -> SecureObjectWrite:
        """Return the secure-object upsert for ``snapshot`` without committing it.

        Lets a caller commit a snapshot in the SAME unit of work as the bucket
        event that records it. A snapshot saved first and its event emitted
        afterwards can come to rest durable-but-unrecorded: the declaration
        survives while the history has no matching entry and no retryable
        marker names the gap.

        Carries the identical envelope, classification and schema version
        :meth:`save` would persist directly — both build it here, so the
        committed and the prepared forms cannot drift apart.
        """
        snapshot_bucket = self._bucket_id_of(snapshot) if self._enforce_payload_identity else self._bucket_id
        if snapshot_bucket != self._bucket_id:
            raise self._input_error_cls(
                f"{self._domain_label} snapshot bucket_id={snapshot_bucket!r} "
                f"does not match repository bucket {self._bucket_id!r}",
            )
        envelope = self._envelope_cls()(
            schema_version=self._namespace_definition.schema_version,
            written_at=now(),
            classification=self._namespace_definition.sensitivity,
            payload=snapshot,
        )
        return SecureObjectWrite(
            namespace=self._namespace_definition.namespace,
            object_key=self._object_key(self._bucket_id, self._snapshot_id_of(snapshot)),
            classification=self._namespace_definition.sensitivity,
            schema_version=self._namespace_definition.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )

    def save_with_secure_object_writes(
        self,
        snapshot: TPayload,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``snapshot`` plus related secure objects in one unit of work.

        The snapshot save and every extra write land or fail together in a
        single SQL transaction, so a lifecycle event co-emitted here can never
        drift from the snapshot it records.

        Args:
            snapshot: The snapshot payload to persist.
            extra_writes: Additional
                :class:`~adapters.persistence.storage.SecureObjectWrite`
                objects to commit atomically with the snapshot.
        """
        self._objects.save_many((self.to_secure_object_write(snapshot), *extra_writes))

    def _snapshot_from_record(
        self,
        record: SecureObjectRecord,
        requested_snapshot_id: str | None = None,
    ) -> TPayload:
        envelope = self._envelope_cls().model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if not inner_envelope_classification_is_expected(
            envelope.classification,
            self._namespace_definition.sensitivity,
        ):
            snapshot_label = requested_snapshot_id or self._snapshot_id_of(envelope.payload)
            if self._classification_error_factory is not None:
                raise self._classification_error_factory(
                    snapshot_label,
                    envelope.classification,
                    self._namespace_definition.sensitivity,
                )
            raise ClassificationError(
                f"{self._domain_label} snapshot {snapshot_label!r} has classification "
                f"{envelope.classification}; consumer expected {self._namespace_definition.sensitivity}",
            )
        if not inner_envelope_version_is_current(
            envelope.schema_version,
            self._namespace_definition.schema_version,
        ):
            snapshot_label = requested_snapshot_id or self._snapshot_id_of(envelope.payload)
            if self._version_error_factory is not None:
                raise self._version_error_factory(
                    snapshot_label,
                    envelope.schema_version,
                    self._namespace_definition.schema_version,
                )
            raise EnvelopeVersionError(
                f"{self._domain_label} snapshot {snapshot_label!r} is at version "
                f"{envelope.schema_version}; consumer supports up to "
                f"{self._namespace_definition.schema_version}",
            )
        return envelope.payload

    def _envelope_cls(self) -> type[Envelope[TPayload]]:
        return Envelope[TPayload].for_payload_type(self._payload_model)

    def _snapshot_id_of(self, payload: BaseModel) -> str:
        snapshot_id = getattr(payload, "snapshot_id", None)
        if not isinstance(snapshot_id, str):
            raise self._input_error_cls(f"payload {type(payload).__name__} has no string snapshot_id attribute")
        return snapshot_id

    def _bucket_id_of(self, payload: BaseModel) -> str:
        bucket_id = getattr(payload, "bucket_id", None)
        if not isinstance(bucket_id, str):
            raise self._input_error_cls(f"payload {type(payload).__name__} has no string bucket_id attribute")
        return bucket_id
