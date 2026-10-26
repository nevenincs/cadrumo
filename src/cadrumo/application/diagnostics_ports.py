"""Application-owned capabilities for secure-object diagnostics.

Diagnostic reports need a small read/mutation surface over secure objects and
one way to classify the expected cold-start session failure.  The application
owns these contracts; the storage adapter translates its records and errors
before binding them at an executable composition root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field, NonNegativeInt

from ..core.models import STRICT_FROZEN_CONFIG


class DiagnosticSecureObjectNamespace(BaseModel):
    """Application DTO for one secure-object namespace integrity result."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    readable: NonNegativeInt
    unreadable: NonNegativeInt


class DiagnosticSecureObjectRepository(Protocol):
    """Read and quarantine capabilities required by diagnostic reports."""

    def list_namespaces(self) -> tuple[str, ...]:
        """Return the populated secure-object namespaces."""
        ...

    def probe_namespace_integrity(self, namespace: str) -> DiagnosticSecureObjectNamespace:
        """Return translated decryptability counts for ``namespace``."""
        ...

    def quarantine_unreadable_rows(self) -> tuple[DiagnosticSecureObjectNamespace, ...]:
        """Move unreadable rows and return translated namespace counts."""
        ...


class DiagnosticSessionFailureClassifier(Protocol):
    """Classify storage failures without exposing adapter exception types."""

    def __call__(self, error: BaseException) -> bool:
        """Return whether ``error`` represents a missing active session."""
        ...


@dataclass(frozen=True, slots=True)
class DiagnosticsPorts:
    """Required secure-object capabilities for one diagnostics invocation."""

    secure_object_repository: DiagnosticSecureObjectRepository
    session_failure_classifier: DiagnosticSessionFailureClassifier


__all__ = [
    "DiagnosticSecureObjectNamespace",
    "DiagnosticSecureObjectRepository",
    "DiagnosticSessionFailureClassifier",
    "DiagnosticsPorts",
]
