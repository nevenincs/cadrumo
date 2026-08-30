"""Encrypted SQL-backed content-addressed attachment store implementation.

Concrete adapter-layer implementation of the
:class:`~domain.attachments.AttachmentStoreProtocol`. The
domain declares the protocol; this module provides the implementation that
reads/writes encrypted attachment blobs and manifests through the
:class:`~adapters.persistence.storage.SecureObjectRepository` persistence
substrate. Blob rows are framed byte payloads governed by
:data:`adapters.persistence.storage.ATTACHMENT_BLOB_NAMESPACE`; manifest
rows wrap :class:`Attachment` payloads in
:class:`~adapters.persistence.storage.Envelope` records governed by
:data:`adapters.persistence.storage.ATTACHMENT_MANIFEST_NAMESPACE`.

Sensitivity rationale: attachment blobs and manifests are content-addressed
byte objects (invoice PDFs, bank statements, supporting documents) that are
FINANCIAL regardless of the modelo that triggered the upload. Attachments are
not modelo-scoped - a single blob may be referenced from multiple modelos and
filing revisions. The ``ModeloDefinition.output_sensitivity`` field governs
model *output* artefacts; attachment storage is an independent content-
addressed substrate and its sensitivity class is irreducibly FINANCIAL.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Iterator, Sequence
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ....core import STR_KEYED_MAPPING_ADAPTER
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.identity import BucketId
from ....core.logging import get_logger
from ....core.secure_object_write import SecureObjectWrite
from ....core.time import now
from ....domain.attachments.errors import AttachmentNotFoundError, AttachmentPersistenceError, AttachmentValidationError
from ....domain.attachments.models import Attachment, is_link_only_mime_type
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ._namespace_registry import (
    ATTACHMENT_BLOB_NAMESPACE as ATTACHMENT_BLOB_STORAGE_NAMESPACE,
)
from ._namespace_registry import (
    ATTACHMENT_MANIFEST_NAMESPACE as ATTACHMENT_MANIFEST_STORAGE_NAMESPACE,
)
from ._namespace_registry import secure_object_namespace_logical_path
from ._schema_lineage import inner_envelope_classification_is_expected, inner_envelope_version_is_current
from .crypto.encrypted_columns import HashedLookup
from .envelope import Envelope
from .runtime_repository import secure_object_repository_for_active_bucket
from .sql import SecureObjectRepository

_LOGGER = get_logger(__name__)

_HEX_DIGITS = frozenset("0123456789abcdef")
_ATTACHMENT_BLOB_VERSION = ATTACHMENT_BLOB_STORAGE_NAMESPACE.schema_version
_ATTACHMENT_BLOB_SENSITIVITY = ATTACHMENT_BLOB_STORAGE_NAMESPACE.sensitivity
_ATTACHMENT_MANIFEST_VERSION = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.schema_version
_ATTACHMENT_MANIFEST_SENSITIVITY = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.sensitivity
_ATTACHMENT_BLOB_NAMESPACE = ATTACHMENT_BLOB_STORAGE_NAMESPACE.namespace
_ATTACHMENT_MANIFEST_NAMESPACE = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.namespace
_ATTACHMENT_ERROR_CONTEXT = {"surface": "attachment_store"}


def _attachment_validation_error(message: str, *, violation: str) -> AttachmentValidationError:
    return AttachmentValidationError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "violation": violation},
        translated_message="errors.integrity.integrity_financial_attachments_attachment_validation",
    )


def _attachment_not_found_error(message: str, *, object_kind: str) -> AttachmentNotFoundError:
    return AttachmentNotFoundError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "object_kind": object_kind},
        translated_message="errors.error.error_financial_attachments_attachment_not_found",
    )


def _attachment_persistence_error(message: str, *, operation: str) -> AttachmentPersistenceError:
    return AttachmentPersistenceError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "operation": operation},
        translated_message="errors.fail.fail_financial_attachments_attachment_persistence",
    )


def _validate_manifest_envelope(envelope: Envelope[Attachment]) -> None:
    if not inner_envelope_classification_is_expected(envelope.classification, _ATTACHMENT_MANIFEST_SENSITIVITY):
        raise _attachment_validation_error(
            "invalid attachment manifest",
            violation="manifest_classification",
        )
    if not inner_envelope_version_is_current(envelope.schema_version, _ATTACHMENT_MANIFEST_VERSION):
        raise _attachment_validation_error(
            "invalid attachment manifest",
            violation="manifest_schema_version",
        )


def _assert_manifest_bound_to_row(attachment: Attachment, *, row_object_key: bytes) -> None:
    """Refuse a manifest whose identity is not the row key it is filed under.

    The row key is stored as a :class:`HashedLookup` digest, so the natural
    key cannot be read back off the row -- but it can be recomputed from the
    identity the manifest claims and compared. That makes the binding checkable
    from the listing path, which holds no natural key, at the cost of one HMAC
    rather than the blob decryption iteration deliberately avoids.

    Both read surfaces route through here so they cannot diverge again:
    :meth:`AttachmentStore.load_manifest` also compares the claimed identity
    with the natural key it was called with, and this states the same
    invariant against the row itself.
    """
    if not hmac.compare_digest(HashedLookup.compute(attachment.attachment_id), row_object_key):
        raise _attachment_validation_error(
            "manifest key does not match stored attachment_id",
            violation="manifest_key",
        )


def _decode_manifest_envelope(payload: bytes, *, attachment_id: str | None = None) -> Envelope[Attachment]:
    try:
        payload_dict = json.loads(payload.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload") from exc
    if not isinstance(payload_dict, dict):
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
    typed_payload_dict = STR_KEYED_MAPPING_ADAPTER.validate_python(payload_dict)
    raw_manifest_payload = typed_payload_dict.get("payload")
    if not isinstance(raw_manifest_payload, dict):
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
    manifest_payload = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_manifest_payload)
    if attachment_id is None:
        manifest_sha256 = manifest_payload.get("sha256")
        if not isinstance(manifest_sha256, str):
            raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
        attachment_id = _require_digest(manifest_sha256, field_name="sha256")
    manifest_payload["attachment_id"] = attachment_id
    # ``STR_KEYED_MAPPING_ADAPTER.validate_python`` returns a fresh dict, so the injected
    # attachment_id above lands on a copy — write it back into the envelope
    # dict actually serialized below.
    typed_payload_dict["payload"] = manifest_payload
    try:
        envelope_json = json.dumps(typed_payload_dict)
        envelope = Envelope[Attachment].model_validate_json(envelope_json)
    except ValidationError as exc:
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload") from exc
    _validate_manifest_envelope(envelope)
    return envelope


# Content-addressed blob payloads are the operator's raw bytes (a PDF, a bank
# statement). The secure-object integrity column ``payload_hash`` is
# ``sha256(plaintext payload)`` (high-entropy and unguessable for the JSON
# envelopes every other namespace stores), but for a bare-content blob the
# plaintext IS the content, so ``payload_hash`` would equal the content digest
# (== the attachment id) and a DB-read attacker holding a copy of a document
# could confirm its presence by computing its sha256. Framing the stored blob
# behind a fixed envelope prefix makes ``payload_hash`` hash the prefixed bytes
# instead, so the bare content digest never lands in a plaintext column. The
# object key stays HMAC-digested and the payload stays encrypted; this only
# removes the residual content-digest oracle.
_ATTACHMENT_BLOB_ENVELOPE_PREFIX = b"\x00aeat-attachment-blob-envelope-v1\x00"


def _wrap_blob_payload(data: bytes) -> bytes:
    """Frame raw blob bytes so the stored ``payload_hash`` is not the content digest."""
    return _ATTACHMENT_BLOB_ENVELOPE_PREFIX + data


def unwrap_blob_payload(stored: bytes) -> bytes:
    """Strip the envelope prefix from a stored blob; refuse an un-enveloped payload.

    Every blob is wrapped by :func:`_wrap_blob_payload` at write time, so a
    missing prefix can only mean corruption, never valid data. Refuse it
    rather than returning unframed bytes.
    """
    if not stored.startswith(_ATTACHMENT_BLOB_ENVELOPE_PREFIX):
        raise _attachment_validation_error(
            "attachment blob payload is missing its envelope prefix",
            violation="blob_envelope_prefix",
        )
    return stored[len(_ATTACHMENT_BLOB_ENVELOPE_PREFIX) :]


def _require_digest(value: str, *, field_name: str = "attachment_id") -> str:
    """Reject any digest input that is not a 64-char lowercase hex string."""
    if len(value) != 64 or any(char not in _HEX_DIGITS for char in value):
        raise _attachment_validation_error(
            f"{field_name} must be a 64-character lowercase hex digest",
            violation=f"{field_name}_invalid_digest",
        )
    return value


class AttachmentStore(BaseModel):
    """Encrypted SQL-backed content-addressed attachment store.

    Implements :class:`~domain.attachments.AttachmentStoreProtocol`
    by storing raw document bytes under their SHA-256 digest in
    :data:`adapters.persistence.storage.ATTACHMENT_BLOB_NAMESPACE` and
    encrypted :class:`Attachment` manifests in
    :data:`adapters.persistence.storage.ATTACHMENT_MANIFEST_NAMESPACE`.
    Both namespaces are profile-local FINANCIAL custody surfaces; the
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    encrypts the stored rows and HMAC-digests the object keys.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    objects: SecureObjectRepository | None = Field(default=None, exclude=True, repr=False)
    bucket_id: BucketId | None = Field(default=None)

    def _bound_bucket_id(self) -> str | None:
        """Return the profile bucket this store serves, when one is resolvable.

        An explicit ``bucket_id`` wins. Otherwise the store reads the active
        profile pointer, which is the same selection
        :func:`secure_object_repository_for_active_bucket` makes -- so the
        binding cannot disagree with the store the manifests land in. A store
        constructed against an injected secure-object repository with no
        declared bucket has no binding to enforce.
        """
        if self.bucket_id is not None:
            return self.bucket_id
        if self.objects is not None:
            return None
        from ....core.bucket_pointer import resolve_active_bucket_id

        return resolve_active_bucket_id()

    def _assert_manifest_bucket(self, attachment: Attachment, *, boundary: str) -> Attachment:
        """Refuse an evidence manifest that belongs to another profile's bucket.

        Attachment manifests are per-profile FINANCIAL custody records, but the
        store carried no bucket identity of its own, so nothing compared
        :attr:`Attachment.bucket_id` with the store the row was written into. A
        manifest naming bucket B could be written into bucket A and returned by
        A's load and list paths as local evidence.

        A manifest that names no bucket is stamped with the store's own on the
        way in: the bucket is not part of the content address, so recording it
        makes the persisted row self-describing rather than leaving the
        ownership question unanswerable at read time.
        """
        bound = self._bound_bucket_id()
        if bound is None or attachment.bucket_id == bound:
            return attachment
        if attachment.bucket_id is None and boundary == "write":
            return attachment.model_copy(update={"bucket_id": bound})
        raise _attachment_validation_error(
            "attachment manifest belongs to another profile bucket",
            violation="manifest_foreign_bucket",
        )

    def _objects_repo(self) -> SecureObjectRepository:
        return self.objects or secure_object_repository_for_active_bucket()

    @property
    def blobs_dir(self) -> Path:
        """Return the logical marker for the attachment blob namespace."""
        return secure_object_namespace_logical_path(_ATTACHMENT_BLOB_NAMESPACE)

    @property
    def manifests_dir(self) -> Path:
        """Return the logical marker for the attachment manifest namespace."""
        return secure_object_namespace_logical_path(_ATTACHMENT_MANIFEST_NAMESPACE)

    def manifest_path(self, attachment_id: str) -> Path:
        """Return a logical object marker for ``attachment_id``."""
        return self.manifests_dir / _require_digest(attachment_id)

    def put_bytes(self, data: bytes) -> str:
        """Write ``data`` under its SHA-256 digest in the blob namespace."""
        digest = sha256_hex(data)
        objects = self._objects_repo()
        if objects.exists(_ATTACHMENT_BLOB_NAMESPACE, digest):
            _LOGGER.debug("reusing existing attachment object for %s", digest)
            return digest
        objects.save(
            namespace=_ATTACHMENT_BLOB_NAMESPACE,
            object_key=digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=_ATTACHMENT_BLOB_SENSITIVITY,
            schema_version=_ATTACHMENT_BLOB_VERSION,
            written_at=now(),
            payload=_wrap_blob_payload(data),
        )
        _LOGGER.debug("stored attachment object %s (%d bytes)", digest, len(data))
        return digest

    def put_many_bytes(self, payloads: Sequence[bytes]) -> tuple[str, ...]:
        """Write every payload in one SQL unit of work; return digests in input order.

        The bulk counterpart of :meth:`put_bytes`. Ingesting evidence one
        record at a time opens one transaction per blob, which measured at
        ~5.3 ms/record against ~1.8 ms through the batched path — roughly 106
        seconds versus 35 at twenty thousand records, with encryption itself
        accounting for well under a tenth of a millisecond of that. The cost
        being removed is per-record session and transaction setup, not crypto.

        Deduplicates twice, because a bulk import legitimately repeats a
        document: once WITHIN the batch, so a digest repeated across rows is
        written once, and once against what is already stored. Both are safe
        precisely because the namespace is content-addressed — an identical
        digest means identical bytes.

        Atomicity differs from the per-record path, deliberately. The whole
        batch commits or none of it does, where N separate ``put_bytes`` calls
        leave the prefix that succeeded. For a content-addressed store
        all-or-nothing is the better failure mode: a partially-ingested batch
        cannot be told apart from a complete one without re-reading the source,
        while a rolled-back batch is simply re-runnable.

        Args:
            payloads: Raw blob payloads to store, in caller order.

        Returns:
            The SHA-256 digest of each payload, positionally matching
            ``payloads`` — including for entries that were already stored or
            that repeat an earlier entry.
        """
        if not payloads:
            return ()

        digests = [sha256_hex(data) for data in payloads]
        objects = self._objects_repo()

        # Two distinct jobs, not two spellings of one. The mapping is keyed by
        # digest, so it collapses the WRITE for a repeated payload; the batch
        # existence read answers the stored-side membership question for every
        # digest in one indexed query instead of one session per digest.
        stored = objects.exists_many(_ATTACHMENT_BLOB_NAMESPACE, digests)
        pending: dict[str, bytes] = {}
        for digest, data in zip(digests, payloads, strict=True):
            if digest in pending or digest in stored:
                continue
            pending[digest] = data

        if pending:
            objects.save_many(
                tuple(
                    SecureObjectWrite(
                        namespace=_ATTACHMENT_BLOB_NAMESPACE,
                        object_key=digest,
                        # rationale: blob sensitivity is FINANCIAL regardless of
                        # modelo; see module docstring.
                        classification=_ATTACHMENT_BLOB_SENSITIVITY,
                        schema_version=_ATTACHMENT_BLOB_VERSION,
                        written_at=now(),
                        payload=_wrap_blob_payload(data),
                    )
                    for digest, data in pending.items()
                ),
            )
            _LOGGER.debug("stored %d attachment objects in one batch", len(pending))

        return tuple(digests)

    def put_file(self, source: Path) -> tuple[str, int]:
        """Read ``source`` and store it via :meth:`put_bytes`, deduplicating by digest."""
        try:
            data = source.read_bytes()
        except OSError as exc:
            _LOGGER.debug("attachment source read failed error_type=%s", type(exc).__name__)
            raise _attachment_persistence_error("unable to read attachment source", operation="read_source") from exc
        digest = self.put_bytes(data)
        return digest, len(data)

    def read_bytes(self, sha256: str) -> bytes:
        """Return the raw bytes for ``sha256``."""
        digest = _require_digest(sha256, field_name="sha256")
        record = self._objects_repo().load(
            _ATTACHMENT_BLOB_NAMESPACE,
            digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=_ATTACHMENT_BLOB_SENSITIVITY,
            max_supported_version=_ATTACHMENT_BLOB_VERSION,
        )
        if record is None:
            raise _attachment_not_found_error("attachment blob not found", object_kind="blob")
        return unwrap_blob_payload(record.payload)

    def open_bytes(self, sha256: str) -> BinaryIO:
        """Open the blob for ``sha256`` as a streaming binary handle."""
        return BytesIO(self.read_bytes(sha256))

    def verify_blob(self, attachment_id: str) -> None:
        """Re-hash the stored blob and verify it matches ``attachment_id``."""
        digest = _require_digest(attachment_id)
        actual = sha256_hex(self.read_bytes(digest))
        if actual != digest:
            raise _attachment_validation_error("blob digest drift", violation="blob_digest_drift")

    def _merge_with_stored_manifest(self, attachment: Attachment) -> Attachment:
        """Fold ``attachment`` into any manifest already filed under the same bytes.

        Attachments are content-addressed, so two ingestions of byte-identical
        documents share one manifest key -- but they are two *observations*: an
        invoice mailed and then also downloaded from Drive evidences two
        transactions, from two channels, at two times. The unconditional upsert
        replaced the first manifest, so the earlier links and capture context
        silently vanished while the shared blob stayed intact, leaving evidence
        consumers seeing only the most recent observation.

        The merge is deterministic and independent of ingestion order for the
        facts that accumulate, and stable for the facts that do not:

        * ``linked_transaction_ids`` / ``linked_invoice_ids`` accumulate as a
          union in first-seen order -- a link is an assertion that this document
          evidences that row, and a later ingestion never retracts it.
        * ``captured_at`` keeps the earliest observation: it answers "since when
          do we hold these bytes".
        * ``source``, ``source_reference``, ``captured_by``, ``source_command``,
          and ``notes`` keep the FIRST observation's values. They describe the
          channel the bytes were obtained through, which the later ingestion did
          not change; treating them as immutable is what makes the merge
          order-stable.
        * ``metadata`` accumulates, with the earlier value winning a key
          collision for the same reason.

        Known limitation: the later observation's own channel reference is not
        retained. Recording every observation would need an observation list on
        :class:`Attachment` and a manifest schema-version bump; this merge stops
        the *loss* of established links and capture context without that change.
        """
        try:
            stored = self.load_manifest(attachment.attachment_id)
        except AttachmentNotFoundError:
            return attachment
        merged_transactions = (*stored.linked_transaction_ids, *attachment.linked_transaction_ids)
        merged_invoices = (*stored.linked_invoice_ids, *attachment.linked_invoice_ids)
        merged_metadata = {**dict(attachment.metadata), **dict(stored.metadata)}
        return stored.model_copy(
            update={
                # The model's own validators deduplicate the link tuples and
                # freeze the mapping, so the merge states intent and the domain
                # type enforces the shape.
                "linked_transaction_ids": merged_transactions,
                "linked_invoice_ids": merged_invoices,
                "metadata": merged_metadata,
                "captured_at": min(stored.captured_at, attachment.captured_at),
            },
        )

    def _assert_blob_present(self, attachment: Attachment) -> None:
        """Refuse a manifest that references bytes this store does not hold."""
        if not self._objects_repo().exists(_ATTACHMENT_BLOB_NAMESPACE, attachment.sha256):
            raise _attachment_validation_error(
                "attachment manifest references bytes that are not stored",
                violation="manifest_blob_missing",
            )

    def _assert_manifest_matches_blob(self, attachment: Attachment) -> None:
        """Verify the manifest's declared size and digest against the stored bytes.

        ``Attachment`` enforces ``attachment_id == sha256`` internally, but that
        is a self-consistency check on the manifest alone: nothing bound the
        declared :attr:`Attachment.bytes_size` to the payload the store actually
        holds, so a caller could persist a manifest claiming any length for the
        bytes. This reads the blob once and refuses a length or digest that does
        not reproduce from the stored payload.
        """
        self._assert_blob_present(attachment)
        stored = self.read_bytes(attachment.sha256)
        if len(stored) != attachment.bytes_size:
            raise _attachment_validation_error(
                "attachment manifest bytes_size does not match the stored payload",
                violation="manifest_bytes_size",
            )
        if sha256_hex(stored) != attachment.sha256:
            raise _attachment_validation_error(
                "attachment manifest sha256 does not match the stored payload",
                violation="manifest_blob_digest",
            )

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` as an encrypted manifest envelope."""
        if is_link_only_mime_type(attachment.mime_type):
            raise _attachment_validation_error(
                "attachment manifest must carry document bytes, not a link-only URI list",
                violation="manifest_link_only_mime_type",
            )
        self._assert_manifest_matches_blob(attachment)
        attachment = self._assert_manifest_bucket(attachment, boundary="write")
        attachment = self._merge_with_stored_manifest(attachment)
        # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
        envelope = Envelope[Attachment](
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=now(),
            classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
            payload=attachment,
        )
        envelope_dict = json.loads(envelope.model_dump_json())
        del envelope_dict["payload"]["attachment_id"]
        payload_json = json.dumps(envelope_dict)
        self._objects_repo().save(
            namespace=_ATTACHMENT_MANIFEST_NAMESPACE,
            object_key=attachment.attachment_id,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=envelope.written_at,
            payload=payload_json.encode(UTF_8_ENCODING),
        )
        _LOGGER.debug("wrote attachment manifest %s", attachment.attachment_id)

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the :class:`Attachment` manifest envelope."""
        digest = _require_digest(attachment_id)
        record = self._objects_repo().load(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            digest,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=_ATTACHMENT_MANIFEST_SENSITIVITY,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        )
        if record is None:
            raise _attachment_not_found_error("attachment manifest not found", object_kind="manifest")
        envelope = _decode_manifest_envelope(record.payload, attachment_id=digest)
        attachment = envelope.payload
        if attachment.attachment_id != digest:
            raise _attachment_validation_error(
                "manifest key does not match stored attachment_id",
                violation="manifest_key",
            )
        _assert_manifest_bound_to_row(attachment, row_object_key=record.object_key)
        self._assert_manifest_matches_blob(attachment)
        self._assert_manifest_bucket(attachment, boundary="load")
        return attachment

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every :class:`Attachment` manifest in sorted attachment-id order.

        Each manifest is bound to the row it was stored under and checked to
        reference bytes this store actually holds. The presence check is a key
        lookup rather than the full length/digest reproduction
        :meth:`load_manifest` performs: iteration is the listing path, and
        re-reading every blob would decrypt the whole evidence corpus to
        render a list. The declared size is bound to the payload at
        :meth:`write_manifest`, so a listed size cannot have been admitted
        unverified.

        The key binding is what iteration previously lacked. ``load_manifest``
        passes the row key into the decoder, so a manifest whose embedded
        ``sha256`` drifted from the key it is filed under is refused there.
        Iteration had no key to pass and derived the identity from that same
        embedded field instead, which is self-consistent by construction --
        so the one surface that could not detect the drift was the one that
        enumerates the whole corpus, and a tampered manifest ``load_manifest``
        rejected was listed as though it were sound.
        """
        manifests: list[Attachment] = []
        for record in self._objects_repo().list_records(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=_ATTACHMENT_MANIFEST_SENSITIVITY,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        ):
            envelope = _decode_manifest_envelope(record.payload)
            _assert_manifest_bound_to_row(envelope.payload, row_object_key=record.object_key)
            self._assert_blob_present(envelope.payload)
            self._assert_manifest_bucket(envelope.payload, boundary="iterate")
            manifests.append(envelope.payload)
        yield from sorted(manifests, key=lambda attachment: attachment.attachment_id)


def resolve_attachment_store(store: AttachmentStoreProtocol | None) -> AttachmentStoreProtocol:
    """Return the injected byte-custody port, or construct the default concrete store.

    Every service that accepts an optional
    :class:`~domain.attachments.AttachmentStoreProtocol` so a test can inject a
    real store into an isolated profile needs the same fallback, and that
    fallback names a concrete adapter. Resolving it here -- in the module that
    owns :class:`AttachmentStore` -- keeps the construction to one site. A copy
    per consuming package looks harmless while the constructor takes no
    arguments and drifts the moment it takes one; two such copies had already
    appeared, in the ledger action services and in the live notification
    custody service, and neither package owns the class.

    Args:
        store: The caller's injected port, or ``None`` to take the default.

    Returns:
        ``store`` unchanged when one was injected, otherwise a new
        :class:`AttachmentStore` bound to the active bucket's runtime.
    """
    if store is not None:
        return store
    return AttachmentStore()


__all__ = ["AttachmentStore", "resolve_attachment_store"]
