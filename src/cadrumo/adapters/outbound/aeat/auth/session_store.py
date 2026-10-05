"""Encrypted persistence for AEAT browser session state.

This module is the concrete adapter behind
:class:`application.auth.protocols.SessionStoreProtocol`. It stores
:class:`PersistedBrowserSession` payloads in
:data:`adapters.persistence.storage.secure_object_namespaces.AEAT_BROWSER_SESSION_NAMESPACE`,
whose registry entry pins the records to bucket-local
``SESSION`` :class:`~core.classification.policies.SensitivityClass`
storage, schema version, process-local custody, and logical-path object-key
grammar.

:class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository` encrypts
payload bytes and digests the logical object key at the column boundary, so
Playwright cookies, local storage, and provider metadata never appear as
plaintext files.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, JsonValue, TypeAdapter, model_validator

from .....core.auth_session_keys import (
    former_product_auth_session_path_for,
    is_former_product_auth_session_path,
)
from .....core.errors.hierarchy import AuthError, InternalInvariantError, pydantic_validation_boundary
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import content_hash_hex
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.time.clock import now
from ....persistence.storage.secure_object_namespaces import AEAT_BROWSER_SESSION_NAMESPACE

if TYPE_CHECKING:
    from ....persistence.storage.sql.secure_objects import SecureObjectRepository

_SESSION_VERSION = AEAT_BROWSER_SESSION_NAMESPACE.schema_version
type JsonObject = Mapping[str, JsonValue]
type PlaywrightStorageState = JsonObject
type ProviderSessionMetadata = JsonObject

_JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


class DeferredSessionWrites:
    """One task's transient browser state, published only by its application owner."""

    def __init__(self) -> None:
        self._changes: dict[Path, PersistedBrowserSession | None] = {}
        self._published = False

    @property
    def has_changes(self) -> bool:
        """Report whether this stage would change encrypted session storage."""
        return bool(self._changes)

    def pending(self, path: Path) -> tuple[bool, PersistedBrowserSession | None]:
        """Resolve a staged logical path without consulting durable storage."""
        return path in self._changes, self._changes.get(path)

    def save(self, path: Path, payload: PersistedBrowserSession) -> None:
        """Replace an earlier staged write for the same provider path."""
        self._changes[path] = payload

    def delete(self, path: Path) -> None:
        """Stage deletion of one provider path."""
        self._changes[path] = None

    def discard(self) -> None:
        """Drop uncommitted browser credentials without touching encrypted storage."""
        self._changes.clear()

    def publish(self) -> None:
        """Apply final provider states while the caller holds current COMMIT authority."""
        if self._published:
            raise InternalInvariantError("deferred auth session writes already published")
        self._published = True
        token = _DEFERRED_WRITES.set(None)
        try:
            for path, payload in self._changes.items():
                if payload is None:
                    delete(path)
                else:
                    _save_payload(path, payload)
        finally:
            _DEFERRED_WRITES.reset(token)
            self.discard()


_DEFERRED_WRITES: ContextVar[DeferredSessionWrites | None] = ContextVar(
    "cadrumo_deferred_auth_session_writes", default=None
)


@contextmanager
def defer_writes() -> Generator[DeferredSessionWrites]:
    """Isolate provider saves and deletes during remote authentication."""
    if _DEFERRED_WRITES.get() is not None:
        raise InternalInvariantError("nested deferred auth session writes are unsupported")
    stage = DeferredSessionWrites()
    token = _DEFERRED_WRITES.set(stage)
    try:
        yield stage
    finally:
        _DEFERRED_WRITES.reset(token)
        stage.discard()


class FormerProductAuthSessionStateError(AuthError):
    """Raised when Cadrumo detects retired product session custody.

    Unlike :class:`core.config_state_root.FormerProductStateError`, this
    refusal is raised at the adapter/storage boundary, not during
    ``Settings``/pydantic bootstrap, so no bootstrap-cycle constraint bars it
    from the registry-bound hierarchy: it derives from the same
    :class:`AuthError` base as every other outbound AEAT authentication
    domain error, so a caller catching ``AuthError`` (or ``CadrumoError``) at an
    adapter or CLI boundary observes this refusal too, instead of it
    propagating as an unclassified internal error.
    """


class PersistedBrowserSession(BaseModel):
    """Encrypted Playwright storage state plus provider-owned metadata.

    This is the typed payload stored under
    :data:`adapters.persistence.storage.secure_object_namespaces.AEAT_BROWSER_SESSION_NAMESPACE`.
    ``storage_state`` carries the payload returned by
    ``BrowserContext.storage_state()``. ``metadata`` remains a provider-owned
    mapping so certificate auth and Cl@ve Móvil can persist different validated
    metadata models while exposing the same encrypted envelope to callers.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = _SESSION_VERSION
    storage_state: PlaywrightStorageState
    metadata: ProviderSessionMetadata
    written_at: datetime

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _schema_is_current(self) -> PersistedBrowserSession:
        if self.schema_version != _SESSION_VERSION:
            raise ValueError("persisted browser session schema version is unsupported")
        return self

    @property
    def storage_state_sha256(self) -> str:
        """Return the canonical SHA-256 fingerprint of the storage-state payload."""
        return _storage_state_sha256(self.storage_state)


def exists(path: Path) -> bool:
    """Return whether an encrypted session exists for logical ``path``.

    ``path`` is the logical storage-state identifier produced by
    :func:`~application.auth.sessions.storage_state_paths` or provider-specific
    helpers, not a plaintext file path to inspect.
    """
    stage = _DEFERRED_WRITES.get()
    if stage is not None:
        found, payload = stage.pending(path)
        if found:
            return payload is not None
    repository = _repository_for_path(path)
    return repository.exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def save(path: Path, *, storage_state: Mapping[str, object], metadata: Mapping[str, object]) -> None:
    """Persist ``storage_state`` and ``metadata`` in the browser-session namespace.

    The values are wrapped in a :class:`PersistedBrowserSession` envelope before
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
    encrypts the serialized JSON payload. The namespace definition supplies the
    ``SESSION`` :class:`~core.classification.policies.SensitivityClass`
    classification and schema version. ``storage_state``/``metadata`` are
    validated JSON-safe here (mirroring :func:`_storage_state_sha256`) so the
    caller-facing boundary stays the wide ``Mapping[str, object]`` shape
    :class:`~cadrumo.application.auth.protocols.BrowserContextPort` exposes.
    """
    payload = PersistedBrowserSession(
        storage_state=_JSON_OBJECT_ADAPTER.validate_python(storage_state),
        metadata=_JSON_OBJECT_ADAPTER.validate_python(metadata),
        written_at=now(),
    )
    stage = _DEFERRED_WRITES.get()
    if stage is not None:
        _repository_for_path(path)
        stage.save(path, payload)
        return
    _save_payload(path, payload)


def _save_payload(path: Path, payload: PersistedBrowserSession) -> None:
    repository = _repository_for_path(path)
    repository.save(
        namespace=AEAT_BROWSER_SESSION_NAMESPACE.namespace,
        object_key=_key(path),
        classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
        schema_version=_SESSION_VERSION,
        written_at=payload.written_at,
        payload=payload.model_dump_json().encode(UTF_8_ENCODING),
    )


def load(path: Path) -> PersistedBrowserSession | None:
    """Load the :class:`PersistedBrowserSession` for logical ``path``.

    Returns ``None`` when the logical key is absent. A present record is read
    from
    :data:`adapters.persistence.storage.secure_object_namespaces.AEAT_BROWSER_SESSION_NAMESPACE`
    with the expected
    :class:`~core.classification.policies.SensitivityClass` and current
    namespace schema version.
    """
    stage = _DEFERRED_WRITES.get()
    if stage is not None:
        found, payload = stage.pending(path)
        if found:
            return payload
    repository = _repository_for_path(path)
    record = repository.load(
        AEAT_BROWSER_SESSION_NAMESPACE.namespace,
        _key(path),
        expected_class=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
        max_supported_version=_SESSION_VERSION,
    )
    if record is None:
        return None
    return PersistedBrowserSession.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def delete(path: Path) -> bool:
    """Delete the encrypted browser session for logical ``path``."""
    stage = _DEFERRED_WRITES.get()
    if stage is not None:
        existed = exists(path)
        stage.delete(path)
        return existed
    repository = _repository_for_path(path)
    return repository.delete(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    """Return the canonical SHA-256 for a Playwright storage-state payload.

    Certificate auth and Cl@ve Móvil metadata store this fingerprint so resume
    paths can reject a metadata envelope that no longer matches the encrypted
    storage-state payload.
    """
    return _storage_state_sha256(storage_state)


def _key(path: Path) -> str:
    return Path(path).as_posix()


def _repository() -> SecureObjectRepository:
    # The storage runtime loads on first session access, not when a host binds the store.
    from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

    return secure_object_repository_for_active_bucket()


def _repository_for_path(path: Path) -> SecureObjectRepository:
    """Return the repository after enforcing the one-way Cadrumo custody cut."""
    if is_former_product_auth_session_path(path):
        raise FormerProductAuthSessionStateError(
            "Cadrumo refuses former-product AEAT session custody and will not read, move, re-key, delete, or adopt it",
        )
    repository = _repository()
    former_path = former_product_auth_session_path_for(path)
    if former_path is not None and repository.exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(former_path)):
        raise FormerProductAuthSessionStateError(
            "Cadrumo detected incompatible former-product AEAT session state and will not read, move, re-key, "
            "delete, or adopt it",
        )
    return repository


def _storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    validated = _JSON_OBJECT_ADAPTER.validate_python(storage_state)
    return content_hash_hex(validated)


class AeatSessionStoreAdapter:
    """Application-port adapter over the canonical encrypted store functions."""

    def exists(self, path: Path) -> bool:
        """Return whether the logical session exists."""
        return exists(path)

    def load(self, path: Path) -> PersistedBrowserSession | None:
        """Load the persisted session at ``path``."""
        return load(path)

    def delete(self, path: Path) -> bool:
        """Delete the persisted session at ``path``."""
        return delete(path)

    def defer_writes(self) -> AbstractContextManager[DeferredSessionWrites]:
        """Stage direct provider and application writes in the current context."""
        return defer_writes()


def build_session_store() -> AeatSessionStoreAdapter:
    """Build the stateless concrete application-port adapter."""
    return AeatSessionStoreAdapter()


__all__ = [
    "AeatSessionStoreAdapter",
    "FormerProductAuthSessionStateError",
    "PersistedBrowserSession",
    "build_session_store",
    "delete",
    "exists",
    "load",
    "save",
    "storage_state_sha256",
]
