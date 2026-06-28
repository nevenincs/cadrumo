"""Encrypted persistence for AEAT browser session state.

This module is the concrete adapter behind
:class:`aeat.application.auth._protocols.SessionStoreProtocol`. It stores
:class:`PersistedBrowserSession` envelopes in
:data:`AEAT_BROWSER_SESSION_NAMESPACE`, whose registry entry pins the records
to bucket-local :class:`SensitivityClass` ``SESSION`` storage.

:class:`SecureObjectRepository` encrypts payload bytes and digests the logical
object key at the column boundary, so Playwright cookies, local storage, and
provider metadata never appear as plaintext files.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.time import now
from ....persistence.storage import AEAT_BROWSER_SESSION_NAMESPACE
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....persistence.storage.sql import SecureObjectRepository

_SESSION_VERSION = AEAT_BROWSER_SESSION_NAMESPACE.schema_version


class PersistedBrowserSession(BaseModel):
    """Encrypted Playwright storage state plus provider-owned metadata.

    ``storage_state`` carries the payload returned by
    ``BrowserContext.storage_state()``. ``metadata`` remains a provider-owned
    mapping so certificate auth and Cl@ve Móvil can persist different validated
    metadata models while exposing the same encrypted envelope to callers.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=_SESSION_VERSION, ge=1)
    storage_state: Mapping[str, object]
    metadata: Mapping[str, object]
    written_at: datetime

    @property
    def storage_state_sha256(self) -> str:
        """Return the canonical SHA-256 fingerprint of the storage-state payload."""
        return _storage_state_sha256(self.storage_state)


def exists(path: Path) -> bool:
    """Return whether an encrypted session exists for logical ``path``.

    ``path`` is the logical storage-state identifier produced by
    :func:`~aeat.application.auth.storage_state_paths` or provider-specific
    helpers, not a plaintext file path to inspect.
    """
    return _repository().exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def save(path: Path, *, storage_state: Mapping[str, object], metadata: Mapping[str, object]) -> None:
    """Persist ``storage_state`` and ``metadata`` in :class:`SensitivityClass` ``SESSION`` storage.

    The values are wrapped in a :class:`PersistedBrowserSession` envelope before
    :class:`SecureObjectRepository` encrypts the serialized JSON payload.
    """
    payload = PersistedBrowserSession(
        storage_state=storage_state,
        metadata=metadata,
        written_at=now(),
    )
    _repository().save(
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
    from :data:`AEAT_BROWSER_SESSION_NAMESPACE` with the expected
    :class:`SensitivityClass` and current namespace schema version.
    """
    record = _repository().load(
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
    return _repository().delete(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    """Return the canonical SHA-256 for a Playwright storage-state payload.

    Certificate auth and Cl@ve Móvil metadata store this fingerprint so resume
    paths can reject a metadata envelope that no longer matches the encrypted
    storage-state payload.
    """
    return _storage_state_sha256(storage_state)


def logical_object_key(path: Path) -> str:
    """Return the natural secure-object key for a browser-session ``path``.

    :class:`SecureObjectRepository` HMAC-digests this value before writing the
    row, so callers can use the same logical key without exposing it on disk.
    """
    return _key(path)


def _key(path: Path) -> str:
    return Path(path).as_posix()


def _repository() -> SecureObjectRepository:
    return secure_object_repository_for_active_bucket()


def _storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    payload = json.dumps(storage_state, sort_keys=True, separators=(",", ":"), default=str).encode(UTF_8_ENCODING)
    return sha256_hex(payload)
