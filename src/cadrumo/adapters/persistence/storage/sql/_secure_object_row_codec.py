"""Row-level codec helpers for SQL secure-object records.

This module keeps the encrypted row decode path close to the SQL
secure-object adapter without leaving the algorithm embedded in the
repository class. It validates row classification and the schema-lineage
ceiling before decrypting (a version above the consumer's current version is
refused; an older version decrypts under its written version and is
chain-upgraded to current), and refuses rows whose revision hashes no longer
match their stored metadata. Revision lineage is derived and stamped by the
repository's write funnel inside the same statement that persists the
ciphertext.

See Also:
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        Repository that owns the write funnel and delegates row decoding here.
    :func:`~adapters.persistence.storage.sql._secure_object_crypto.derive_revision_id`
        Deterministic revision-id primitive the write funnel stamps rows with.
    :func:`~adapters.persistence.storage.sql._secure_object_crypto.verify_revision_self_consistency`
        Integrity check applied before decrypting an existing row.
    :func:`~adapters.persistence.storage.sql._secure_object_schema.build_revision_ancestor_ids`
        Revision-lineage helper used to persist ancestor chains.
    :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectRecord`
        Plaintext record returned after classification, schema, lineage, and
        AEAD checks pass.
    :func:`~adapters.persistence.storage.crypto.secure_object_payload_aad`
        Associated-data builder that binds ciphertext to row identity.
    :class:`SensitivityClass`
        Expected row classification validated before a row is decoded.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast

from .....core.classification.policies import SensitivityClass
from .....core.errors.error_codes import resolve_error_message
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.time.utc import coerce_utc_aware
from ..crypto.encrypted_columns import decrypt_secure_object_payload, secure_object_payload_aad
from ..errors import ClassificationError, DecryptionError, EnvelopeVersionError, SecureObjectUnreadableError
from ..schema_lineage import (
    ensure_schema_version_readable,
    inner_envelope_classification_is_expected,
    upgrade_secure_object_payload,
)
from ..secure_object_namespaces import SecureObjectNamespaceDefinition
from . import orm as _orm
from ._secure_object_records import SecureObjectBatchLoadItem, SecureObjectRecord, SecureObjectUnreadable
from .secure_object_crypto import verify_revision_self_consistency

_log = get_logger(__name__)


class _SecureObjectListRawRow(Protocol):
    """Typed SQL projection consumed by the batch-list decode boundary."""

    id: int
    object_key: str | bytes
    classification: str
    schema_version: int
    written_at: datetime
    payload: bytes
    revision_id: str | None
    previous_revision_id: str | None
    payload_hash: str | None
    ciphertext_hash: str | None
    previous_payload_hash: str | None


def decode_secure_object_row(
    *,
    namespace: str,
    row_id: int,
    object_key: bytes,
    classification_str: str,
    schema_version: int,
    written_at: datetime,
    payload_wire: bytes,
    revision_id: str | None,
    previous_revision_id: str | None,
    payload_hash: str | None,
    ciphertext_hash: str | None,
    previous_payload_hash: str | None,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectRecord:
    """Validate and decrypt one secure-object row, raising on every failure.

    The single decode pipeline behind both read surfaces. It always RAISES;
    choosing between propagating that failure and converting it to an
    unreadable row is the caller's policy, so the two surfaces cannot drift in
    WHAT they check or in WHICH ORDER, only in how they report.

    Order is part of the contract, and is deliberately integrity-before-crypto:

    1. classification is a known value, and is the one this namespace expects
    2. the stored schema version is readable, and registered for the namespace
    3. revision lineage is self-consistent
    4. the AEAD opens
    5. a below-current payload is chain-upgraded

    Step 3 runs before step 4 on purpose: a row whose stored lineage metadata
    already contradicts itself is refused without spending an AEAD open on it.
    That metadata is UNAUTHENTICATED until step 4 verifies the tag, so the
    pre-decrypt check is strictly refuse-only -- it can reject a row, and it can
    do nothing else. It never marks a row readable, never skips a later step,
    and never selects a decode branch, so hostile header metadata cannot buy an
    attacker anything beyond a refusal they could have caused anyway.

    Args:
        namespace: The secure-object namespace the row was stored under; it
            selects the registered row schema and scopes the diagnostics.
        row_id: The row's primary key, carried only so a refusal can name the
            offending row.
        object_key: The row's opaque object key, used as AEAD associated data
            so a payload cannot be replayed under a different key.
        classification_str: The classification exactly as stored. Parsed in
            step 1 and matched against ``expected_class``.
        schema_version: The payload schema version as stored. Checked for
            readability and namespace registration in step 2, and drives the
            chain upgrade in step 5.
        written_at: The row's stored write timestamp, carried onto the decoded
            record.
        payload_wire: The stored wire bytes -- the sealed envelope the AEAD
            opens in step 4.
        revision_id: The row's own revision identifier, or ``None`` when the
            row carries no revision metadata.
        previous_revision_id: The revision this row supersedes, or ``None`` for
            a chain head.
        payload_hash: Digest of this row's plaintext payload, or ``None``.
        ciphertext_hash: Digest of this row's wire bytes, or ``None``.
        previous_payload_hash: Digest of the superseded row's payload, or
            ``None``. Together with the two revision ids this forms the
            lineage triple checked in step 3.
        expected_class: The :class:`SensitivityClass` this namespace declares;
            the stored row's own classification must match it exactly.
        max_supported_version: The highest schema version this reader can
            handle. A row above it is refused rather than guessed at; a row
            below it is chain-upgraded.
        namespace_definition: The namespace's registered definition, or
            ``None`` when the namespace is unregistered.
        enforce_registered_row_schema: The namespace-registration check
            invoked in step 2. Injected so the codec does not reach back into
            the registry, and so tests can drive registration failures
            directly.

    Raises:
        ClassificationError: Unknown classification, or one that does not match
            the namespace's expected class.
        EnvelopeVersionError: Schema version unreadable, unregistered for the
            namespace, or an upgrade hop failure.
        SecureObjectUnreadableError: Revision lineage self-consistency failed,
            which includes a row carrying no revision metadata at all.
        DecryptionError: The AEAD did not open.
    """
    try:
        classification = SensitivityClass(classification_str)
    except ValueError as exc:
        raise ClassificationError(
            context={
                "namespace": namespace,
                "classification": classification_str,
            },
            translated_message="errors.storage.namespace.unknown_classification",
        ) from exc
    if not inner_envelope_classification_is_expected(classification, expected_class):
        raise ClassificationError(
            context={
                "namespace": namespace,
                "classification": classification.value,
                "expected": expected_class.value,
            },
            translated_message="errors.storage.namespace.classification_mismatch",
        )
    ensure_schema_version_readable(
        namespace=namespace,
        schema_version=schema_version,
        current_version=max_supported_version,
    )
    enforce_registered_row_schema(
        namespace=namespace,
        schema_version=schema_version,
        definition=namespace_definition,
    )
    if not verify_revision_self_consistency(
        revision_id,
        namespace=namespace,
        object_key=object_key,
        schema_version=schema_version,
        written_at=written_at,
        previous_revision_id=previous_revision_id,
        payload_hash=payload_hash,
        ciphertext_hash=ciphertext_hash,
        previous_payload_hash=previous_payload_hash,
    ):
        _log.error(
            "secure_objects: revision lineage self-consistency failed for namespace=%s row id=%s",
            namespace,
            row_id,
        )
        raise SecureObjectUnreadableError(namespace, row_id)
    payload_plain = decrypt_secure_object_payload(
        payload_wire,
        associated_data=secure_object_payload_aad(namespace, object_key, schema_version),
    )
    if schema_version < max_supported_version:
        payload_plain = upgrade_secure_object_payload(
            payload_plain,
            namespace=namespace,
            from_version=schema_version,
            to_version=max_supported_version,
        )
    return SecureObjectRecord(
        namespace=namespace,
        object_key=object_key,
        classification=classification,
        schema_version=max_supported_version,
        # The write funnel admits only UTC-aware instants, and SQLite returns
        # the column with ``tzinfo`` dropped. Re-attaching UTC restores the
        # exact value that was written, so the record round-trips to an equal
        # instant instead of a naive look-alike. This is reattachment, not a
        # guess: the stored wall clock is UTC by write-time construction.
        written_at=coerce_utc_aware(written_at),
        payload=payload_plain,
        revision_id=revision_id,
    )


def _classification_reason(exc: ClassificationError) -> str:
    """Render a classification failure as the batch surface's diagnostic string.

    The batch reason stays a stable, structural English string rather than the
    error's translated message: it is a diagnostic field on a machine-readable
    unreadable-row record, not operator-facing prose, and callers match on its
    shape.
    """
    context = getattr(exc, "context", None) or {}
    classification = str(context.get("classification", ""))
    expected = context.get("expected")
    if expected is None:
        return f"unknown classification {classification!r}"
    return f"classification {classification!r} does not match expected {str(expected)!r}"


def secure_object_record_from_row(
    row: _orm.SecureObjectRow,
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None = None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectRecord:
    """Decode one ORM row, propagating the typed failure.

    Fail-closed policy: a caller loading a specific row wants the typed error,
    not a placeholder. Normalisation of the ORM row is the only thing this
    wrapper adds; every check lives in :func:`decode_secure_object_row`.

    Args:
        row: The ORM row to decode. Its columns are coerced to the concrete
            types the codec requires (``int`` id, ``bytes`` object key and
            payload) and forwarded; nothing is otherwise interpreted here.
        expected_class: The :class:`SensitivityClass` the row's own
            classification must match, forwarded verbatim to
            :func:`decode_secure_object_row`.
        max_supported_version: The highest schema version this reader can
            handle, forwarded verbatim.
        namespace_definition: The namespace's registered definition, or
            ``None`` when unregistered, forwarded verbatim.
        enforce_registered_row_schema: The namespace-registration check,
            forwarded verbatim.
    """
    return decode_secure_object_row(
        namespace=row.namespace,
        row_id=int(row.id),
        object_key=bytes(row.object_key),
        classification_str=row.classification,
        schema_version=row.schema_version,
        written_at=row.written_at,
        payload_wire=bytes(row.payload),
        revision_id=row.revision_id,
        previous_revision_id=row.previous_revision_id,
        payload_hash=row.payload_hash,
        ciphertext_hash=row.ciphertext_hash,
        previous_payload_hash=row.previous_payload_hash,
        expected_class=expected_class,
        max_supported_version=max_supported_version,
        namespace_definition=namespace_definition,
        enforce_registered_row_schema=enforce_registered_row_schema,
    )


@dataclass(frozen=True, slots=True)
class _NormalisedListRawRow:
    """One scan row's metadata coerced to the types the outcome models require."""

    row_id: int
    object_key: bytes
    classification: str
    schema_version: int
    written_at: datetime
    payload: bytes


#: Placeholders used only when a metadata column cannot be coerced at all.
#:
#: They exist so an unreadable OUTCOME can still be constructed for the row --
#: :class:`SecureObjectUnreadable` requires a non-negative id, a non-empty
#: classification, a schema version of at least 1, and a real instant. They are
#: deliberately implausible, and the accompanying ``reason`` names every column
#: that drifted, so a sentinel is never mistaken for a value read off the row.
_UNREADABLE_ROW_ID = 0
_UNREADABLE_CLASSIFICATION = "<unreadable>"
_UNREADABLE_SCHEMA_VERSION = 1
_UNREADABLE_INSTANT = datetime(1, 1, 1, tzinfo=UTC)


def _normalised_list_raw_row(row: _SecureObjectListRawRow) -> tuple[_NormalisedListRawRow, tuple[str, ...]]:
    """Coerce one raw scan row, reporting which columns could not be read.

    Never raises. A column that cannot be coerced contributes its name to the
    returned tuple and a documented sentinel to the normalised row, so the
    caller can always report a typed per-row failure instead of aborting the
    scan on a raw ``ValueError`` or ``TypeError``.
    """
    malformed: list[str] = []

    try:
        row_id = int(row.id)
    except (TypeError, ValueError):
        malformed.append("id")
        row_id = _UNREADABLE_ROW_ID
    if row_id < 0:
        malformed.append("id")
        row_id = _UNREADABLE_ROW_ID

    # ``object_key`` is a HashedLookup digest. Keep the bytes surface
    # stable for diagnostics and raw mirror consumers.
    raw_object_key = row.object_key
    try:
        object_key = raw_object_key.encode(UTF_8_ENCODING) if isinstance(raw_object_key, str) else bytes(raw_object_key)
    except (TypeError, ValueError):
        malformed.append("object_key")
        object_key = b""

    classification_str = str(row.classification)
    if not classification_str:
        malformed.append("classification")
        classification_str = _UNREADABLE_CLASSIFICATION

    try:
        schema_version = int(row.schema_version)
    except (TypeError, ValueError):
        malformed.append("schema_version")
        schema_version = _UNREADABLE_SCHEMA_VERSION
    if schema_version < 1:
        malformed.append("schema_version")
        schema_version = _UNREADABLE_SCHEMA_VERSION

    written_at = row.written_at
    if not isinstance(written_at, datetime):
        malformed.append("written_at")
        written_at = _UNREADABLE_INSTANT

    try:
        payload_wire = bytes(row.payload)
    except (TypeError, ValueError):
        malformed.append("payload")
        payload_wire = b""

    return (
        _NormalisedListRawRow(
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            payload=payload_wire,
        ),
        tuple(malformed),
    )


def secure_object_list_item_from_raw_row(
    raw: object,
    *,
    namespace: str,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectBatchLoadItem:
    """Decode one raw ``iter_records_with_failures`` row into a typed outcome.

    ``expected_class`` is the :class:`SensitivityClass` required for the
    namespace.

    Fault-isolated: every failure mode (unknown classification, classification
    mismatch, unreadable schema version, revision-lineage inconsistency,
    decrypt failure, upgrade failure) returns a
    :class:`~._secure_object_records.SecureObjectUnreadable` carrying the
    reason instead of raising, so a caller iterating many rows can attribute a
    failure to its own row and keep inspecting the rest.

    Fault isolation is the ONLY thing this wrapper adds to
    :func:`decode_secure_object_row`; the checks and their order live there, so
    the batch surface cannot validate a row differently from the single-row
    surface. Note ``SecureObjectUnreadableError`` subclasses ``DecryptionError``
    and so must be caught first.
    """
    # CAST-RATIONALE-SECURE-OBJECT-RAW-ROW: SQL row tuples are structurally validated by this codec.
    row = cast(_SecureObjectListRawRow, raw)
    # Normalisation runs inside the fault-isolated boundary, not ahead of it.
    # These coercions used to sit above the try block, so a tampered SQL
    # ``schema_version = 'bogus'`` raised a raw ValueError out of ``int()`` and
    # aborted the entire namespace scan -- the exact opposite of the
    # one-outcome-per-row contract this function promises, and it never even
    # reached the shared decode core.
    normalised, malformed_fields = _normalised_list_raw_row(row)
    row_id = normalised.row_id
    object_key = normalised.object_key
    classification_str = normalised.classification
    schema_version = normalised.schema_version
    written_at = normalised.written_at
    payload_wire = normalised.payload

    def unreadable(reason: str) -> SecureObjectUnreadable:
        """Report this row as unreadable, carrying the identity every reason shares.

        Every failure mode below reports the SAME row identity and differs
        only in why it could not be read, so the seven shared fields are
        bound once here. Fault isolation is the point: a caller iterating
        many rows can attribute a failure to its own row and keep going.
        """
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=reason,
        )

    if malformed_fields:
        # The row's own metadata columns are unusable, so the decode core
        # cannot be reached at all. Report it as this row's failure, naming
        # the columns that drifted, rather than letting the coercion escape
        # and take every remaining row of the scan with it.
        return unreadable(f"row metadata is malformed: {', '.join(malformed_fields)}")

    try:
        return decode_secure_object_row(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification_str=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            payload_wire=payload_wire,
            revision_id=row.revision_id,
            previous_revision_id=row.previous_revision_id,
            payload_hash=row.payload_hash,
            ciphertext_hash=row.ciphertext_hash,
            previous_payload_hash=row.previous_payload_hash,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
            namespace_definition=namespace_definition,
            enforce_registered_row_schema=enforce_registered_row_schema,
        )
    except SecureObjectUnreadableError:
        return unreadable("revision lineage self-consistency check failed")
    except DecryptionError as exc:
        return unreadable(str(exc))
    except ClassificationError as exc:
        return unreadable(_classification_reason(exc))
    except EnvelopeVersionError as exc:
        return unreadable(resolve_error_message(exc))
    except Exception as exc:
        # An upgrade hop is namespace-supplied and may raise anything; a batch
        # scan must attribute that to its row rather than abort the whole scan.
        return unreadable(str(exc))
