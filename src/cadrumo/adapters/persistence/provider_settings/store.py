"""Encrypted secure-object implementation of the provider-settings store.

Each provider's record is one row in
:data:`~adapters.persistence.storage.secure_object_namespaces.PROVIDER_SETTINGS_NAMESPACE`,
keyed by provider id, inside the exact profile bucket this store is bound to.
Every call obtains its repository through the runtime-owned door
(:func:`~adapters.persistence.storage.runtime_repository.secure_object_repository_for_bucket`),
so a profile that is signed out, locked or replaced refuses at the call rather
than serving a repository opened earlier.

Storage failures leave this module only as typed port values. A row that does
not decrypt or validate is reported unreadable, never absent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, override

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from ....application.provider_settings.ports import (
    AbsentProviderRecord,
    ProviderRecordRead,
    ProviderSettingsStore,
    StoredProviderRecord,
    StoreGenerations,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableProviderRecord,
)
from ....core.config import Settings, load_settings
from ....core.errors.hierarchy import CadrumoError
from ....core.hashing import sha256_hex
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.time.clock import now
from ....domain.provider_settings.record import (
    ProviderSettingsRecord,
    parse_provider_settings_record,
    provider_settings_record_document,
)
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.errors import SecureObjectRevisionConflictError, SessionExpiredError, StorageValidationError
from ..storage.master_key.active_session import current_active_bucket_session, session_serves_bucket
from ..storage.master_key.idle_timeout import evaluate_idle
from ..storage.runtime_readiness import StorageRuntimeReadinessCode
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import PROVIDER_SETTINGS_NAMESPACE
from ..storage.sql.secure_object_records import SecureObjectDeletion
from ..storage.sql.secure_objects import SecureObjectRepository

_WRITE_PROVENANCE: Final[str] = "provider-settings"

_LOCKED_READINESS: Final[frozenset[str]] = frozenset(
    {StorageRuntimeReadinessCode.SESSION_SEALED.value, StorageRuntimeReadinessCode.SESSION_EXPIRED.value},
)


class SecureProviderSettingsStore(ProviderSettingsStore):
    """Provider-settings records for one exact profile bucket."""

    def __init__(self, *, bucket_id: str, settings: Settings | None = None) -> None:
        """Bind the store to ``bucket_id``; the live session must serve that bucket."""
        self._bucket_id = bucket_id.strip()
        self._settings = settings

    @override
    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        """Return one typed read per provider, in request order, or a refusal."""
        try:
            repository = self._repository()
            revisions = repository.peek_many_revision_ids(PROVIDER_SETTINGS_NAMESPACE.namespace, provider_ids)
            return tuple(self._read_one(repository, provider_id, revisions) for provider_id in provider_ids)
        except (CadrumoError, SQLAlchemyError, OSError) as exc:
            return _refusal(exc)

    @override
    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Encrypt and commit ``record`` under a compare-and-swap on ``expected_revision``."""
        try:
            self._repository().save(
                namespace=PROVIDER_SETTINGS_NAMESPACE.namespace,
                object_key=record.provider,
                classification=PROVIDER_SETTINGS_NAMESPACE.sensitivity,
                schema_version=PROVIDER_SETTINGS_NAMESPACE.schema_version,
                written_at=record.updated_at,
                payload=provider_settings_record_document(record),
                write_provenance=_WRITE_PROVENANCE,
                expected_revision_id=expected_revision,
            )
        except (CadrumoError, SQLAlchemyError, OSError) as exc:
            return _refusal(exc)
        return None

    @override
    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        """Remove the provider's row under a revision guard; an absent row expected absent is a no-op."""
        try:
            repository = self._repository()
            digest = secure_object_key_digest(provider_id)
            if expected_revision == ABSENT_SECURE_OBJECT_REVISION_ID:
                if repository.exists_by_raw_key(PROVIDER_SETTINGS_NAMESPACE.namespace, digest):
                    return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
                return None
            repository.apply_batch(
                writes=(),
                deletions=(
                    SecureObjectDeletion(
                        namespace=PROVIDER_SETTINGS_NAMESPACE.namespace,
                        hashed_object_key=digest,
                        expected_revision_id=expected_revision,
                    ),
                ),
            )
        except (CadrumoError, SQLAlchemyError, OSError) as exc:
            return _refusal(exc)
        return None

    @override
    def observe_generations(self) -> StoreGenerations | None:
        """Return the sign-in and provider-settings generations without touching idle time.

        The sign-in generation digests the live session's bucket, opening
        instant and absolute deadline, which a fresh sign-in replaces and a
        resumed session in another process shares. The provider-settings
        generation digests every row revision in the namespace, and each
        revision hashes its row's ciphertext, so neither digest says anything
        about a key.
        """
        session = current_active_bucket_session()
        if not session_serves_bucket(session, self._bucket_id) or evaluate_idle(session=session, now=now()).expired:
            return None
        try:
            revisions = self._repository().observe_revision_ids(PROVIDER_SETTINGS_NAMESPACE.namespace)
        except (CadrumoError, SQLAlchemyError, OSError):
            return None
        sign_in = _digest(
            (session.bucket_id, session.opened_at.isoformat(), session.absolute_deadline.isoformat()),
        )
        provider_settings = _digest(tuple(revision or "" for revision in revisions))
        return StoreGenerations(sign_in=sign_in, provider_settings=provider_settings)

    def _repository(self) -> SecureObjectRepository:
        return secure_object_repository_for_bucket(self._bucket_id, self._settings or load_settings())

    @staticmethod
    def _read_one(
        repository: SecureObjectRepository,
        provider_id: str,
        revisions: Mapping[str, str | None],
    ) -> ProviderRecordRead:
        if provider_id not in revisions:
            return AbsentProviderRecord(provider=provider_id)
        peeked = revisions[provider_id]
        unreadable = UnreadableProviderRecord(provider=provider_id, revision=peeked)
        try:
            row = repository.load(
                PROVIDER_SETTINGS_NAMESPACE.namespace,
                provider_id,
                expected_class=PROVIDER_SETTINGS_NAMESPACE.sensitivity,
                max_supported_version=PROVIDER_SETTINGS_NAMESPACE.schema_version,
            )
        except (CadrumoError, SQLAlchemyError, ValueError) as exc:
            if _session_refusal_code(exc) is not None:
                raise
            return unreadable
        if row is None:
            return AbsentProviderRecord(provider=provider_id)
        try:
            record = parse_provider_settings_record(row.payload)
        except (ValidationError, UnicodeDecodeError):
            return unreadable
        if record.provider != provider_id:
            return unreadable
        return StoredProviderRecord(record=record, revision=row.revision_id)


def _digest(parts: tuple[str, ...]) -> str:
    return sha256_hex("".join(parts).encode("utf-8"))


def _session_refusal_code(exc: BaseException) -> StoreRefusalCode | None:
    """Return the sign-in refusal ``exc`` carries, or ``None`` when it is not a session failure."""
    if isinstance(exc, SessionExpiredError):
        return StoreRefusalCode.PROFILE_LOCKED
    if isinstance(exc, StorageValidationError) and exc.context is not None:
        readiness = exc.context.get("readiness_code")
        if isinstance(readiness, str):
            if readiness in _LOCKED_READINESS:
                return StoreRefusalCode.PROFILE_LOCKED
            return StoreRefusalCode.NOT_SIGNED_IN
    return None


def _refusal(exc: BaseException) -> StoreRefusal:
    session_code = _session_refusal_code(exc)
    if session_code is not None:
        return StoreRefusal(code=session_code)
    if isinstance(exc, SecureObjectRevisionConflictError):
        return StoreRefusal(code=StoreRefusalCode.REVISION_CONFLICT)
    return StoreRefusal(code=StoreRefusalCode.UNKNOWN)


def build_provider_settings_store(*, bucket_id: str, settings: Settings | None = None) -> ProviderSettingsStore:
    """Return the encrypted provider-settings store for one exact profile bucket."""
    return SecureProviderSettingsStore(bucket_id=bucket_id, settings=settings)


__all__ = [
    "SecureProviderSettingsStore",
    "build_provider_settings_store",
]
