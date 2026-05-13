"""Encrypted persistence for AEAT browser session state."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ....persistence.storage import SensitivityClass
from ....persistence.storage.sql import SecureObjectRepository

_SESSION_NAMESPACE = "aeat.outbound.aeat.auth.sessions"
_SESSION_VERSION = 1


class PersistedBrowserSession(BaseModel):
    """Encrypted browser session state plus provider-specific metadata."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: int = Field(default=_SESSION_VERSION, ge=1)
    storage_state: dict[str, Any]
    metadata: dict[str, Any]
    written_at: datetime

    @property
    def storage_state_sha256(self) -> str:
        """Return the canonical SHA-256 of the Playwright storage state."""

        return _storage_state_sha256(self.storage_state)


def exists(path: Path) -> bool:
    """Return whether a browser session exists for logical ``path``."""

    return SecureObjectRepository().exists(_SESSION_NAMESPACE, _key(path))


def save(path: Path, *, storage_state: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Persist ``storage_state`` and ``metadata`` encrypted at SESSION class."""

    payload = PersistedBrowserSession(
        storage_state=storage_state,
        metadata=metadata,
        written_at=datetime.now(UTC),
    )
    SecureObjectRepository().save(
        namespace=_SESSION_NAMESPACE,
        object_key=_key(path),
        classification=SensitivityClass.SESSION,
        schema_version=_SESSION_VERSION,
        written_at=payload.written_at,
        payload=payload.model_dump_json().encode("utf-8"),
    )


def load(path: Path) -> PersistedBrowserSession | None:
    """Load a persisted browser session for logical ``path``."""

    record = SecureObjectRepository().load(
        _SESSION_NAMESPACE,
        _key(path),
        expected_class=SensitivityClass.SESSION,
        max_supported_version=_SESSION_VERSION,
    )
    if record is None:
        return None
    return PersistedBrowserSession.model_validate_json(record.payload.decode("utf-8"))


def delete(path: Path) -> bool:
    """Delete persisted browser session state for logical ``path``."""

    return SecureObjectRepository().delete(_SESSION_NAMESPACE, _key(path))


def storage_state_sha256(storage_state: dict[str, Any]) -> str:
    """Return the canonical SHA-256 of a Playwright storage-state payload."""

    return _storage_state_sha256(storage_state)


def _key(path: Path) -> str:
    return Path(path).as_posix()


def _storage_state_sha256(storage_state: dict[str, Any]) -> str:
    payload = json.dumps(storage_state, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
