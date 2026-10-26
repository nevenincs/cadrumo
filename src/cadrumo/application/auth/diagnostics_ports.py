"""Application-owned persistence contract for encrypted auth diagnostics.

The auth diagnostic use case only needs decrypted payload bytes.  This narrow
port keeps secure-object namespaces, repository construction, and storage
failures in the persistence adapter while giving application callers a stable
capability contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG


class AuthDiagnosticPersistenceRecord(BaseModel):
    """One decrypted auth-diagnostic payload supplied by persistence."""

    model_config = STRICT_FROZEN_CONFIG

    payload: bytes


class AuthDiagnosticPersistenceError(CadrumoError):
    """A persistence operation for auth diagnostics failed at the adapter boundary."""

    def __init__(self, operation: str) -> None:
        """Carry only the capability operation, leaving storage details behind."""
        self.operation = operation
        super().__init__(f"auth diagnostic persistence operation failed: {operation}")


@runtime_checkable
class AuthDiagnosticPersistencePort(Protocol):
    """Read and update encrypted auth-diagnostic payloads for the active profile."""

    def list_records(self) -> tuple[AuthDiagnosticPersistenceRecord, ...]:
        """Return every readable diagnostic payload for the active profile."""
        ...

    def load_record(self, diagnostic_id: str) -> AuthDiagnosticPersistenceRecord | None:
        """Return one diagnostic payload, or ``None`` when it is absent."""
        ...

    def save_record(self, diagnostic_id: str, payload: bytes, *, written_at: datetime) -> None:
        """Persist one diagnostic payload for the active profile."""
        ...


__all__ = [
    "AuthDiagnosticPersistenceError",
    "AuthDiagnosticPersistencePort",
    "AuthDiagnosticPersistenceRecord",
]
