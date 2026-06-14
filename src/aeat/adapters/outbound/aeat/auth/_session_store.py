"""Encrypted persistence for AEAT browser session state.

Stores the serialized session as a record classified at
:class:`SensitivityClass` SESSION through :class:`SecureObjectRepository`,
so the browser cookies and tokens never touch disk in plaintext.
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
    """Encrypted browser session state plus provider-specific metadata."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=_SESSION_VERSION, ge=1)
    storage_state: Mapping[str, object]
    metadata: Mapping[str, object]
    written_at: datetime

    @property
    def storage_state_sha256(self) -> str:
        """Return the canonical SHA-256 of the Playwright storage state."""
        return _storage_state_sha256(self.storage_state)


def exists(path: Path) -> bool:
    """Return whether a browser session exists for logical ``path``."""
    return _repository().exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def save(path: Path, *, storage_state: Mapping[str, object], metadata: Mapping[str, object]) -> None:
    """Persist ``storage_state`` and ``metadata`` encrypted at SESSION class."""
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
    """Load a :class:`PersistedBrowserSession` for logical ``path``, or ``None`` when absent."""
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
    """Delete persisted browser session state for logical ``path``."""
    return _repository().delete(AEAT_BROWSER_SESSION_NAMESPACE.namespace, _key(path))


def storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    """Return the canonical SHA-256 of a Playwright storage-state payload."""
    return _storage_state_sha256(storage_state)


def logical_object_key(path: Path) -> str:
    """Return the secure-object logical key for a browser-session path."""
    return _key(path)


def _key(path: Path) -> str:
    return Path(path).as_posix()


def _repository() -> SecureObjectRepository:
    return secure_object_repository_for_active_bucket()


def _storage_state_sha256(storage_state: Mapping[str, object]) -> str:
    payload = json.dumps(storage_state, sort_keys=True, separators=(",", ":"), default=str).encode(UTF_8_ENCODING)
    return sha256_hex(payload)
