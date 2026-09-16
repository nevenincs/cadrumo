"""Application-owned persistence contract for local filing history.

The filing-history service owns the payload and repository semantics.  An outer
composition supplies the encrypted persistence capability through this module;
the application surface never names the storage implementation or its errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from ...core.classification.policies import SensitivityClass
from .errors import ModeloApplicationError
from .history_models import ModeloHistory

FILING_HISTORY_NAMESPACE = "cadrumo.application.filing.history"
FILING_HISTORY_SENSITIVITY: Final[SensitivityClass] = SensitivityClass("audit")
FILING_HISTORY_SCHEMA_VERSION = 1


class FilingHistoryPersistenceError(ModeloApplicationError):
    """Translated persistence failure for the filing-history boundary."""


class FilingHistoryRepositoryPort(Protocol):
    """Bucket-bound filing-history persistence capability."""

    @property
    def store_dir(self) -> Path:
        """Return the logical secure-store marker used for diagnostics."""
        ...

    def envelope_path_for(self, identifier: str) -> Path:
        """Return the logical marker for one history identifier."""
        ...

    def lock_target_for(self, identifier: str) -> Path:
        """Return the logical lock marker for one history identifier."""
        ...

    def load(self, identifier: str) -> ModeloHistory | None:
        """Load one history, returning ``None`` when it is absent."""
        ...

    def save(self, payload: ModeloHistory) -> None:
        """Persist one validated history payload."""
        ...

    def delete(self, identifier: str) -> bool:
        """Delete one history and report whether it existed."""
        ...

    def iter_records(self) -> Iterator[ModeloHistory]:
        """Iterate all persisted history payloads with integrity checks."""
        ...


@dataclass(frozen=True, slots=True)
class FilingHistoryPorts:
    """Required authorities for one bucket-local filing-history repository."""

    repository: FilingHistoryRepositoryPort
    bucket_id: str


__all__ = [
    "FILING_HISTORY_NAMESPACE",
    "FILING_HISTORY_SCHEMA_VERSION",
    "FILING_HISTORY_SENSITIVITY",
    "FilingHistoryPersistenceError",
    "FilingHistoryPorts",
    "FilingHistoryRepositoryPort",
]
