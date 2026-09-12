"""Application repository facade for local filing-history records.

The repository persists lightweight :class:`ModeloHistory` payloads keyed by
modelo.  Encrypted storage, envelope validation, and persistence failures are
owned by the required outer capability in :mod:`history_ports`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from ...core.classification.policies import SensitivityClass
from .history_models import ModeloHistory
from .history_ports import (
    FILING_HISTORY_NAMESPACE,
    FILING_HISTORY_SCHEMA_VERSION,
    FILING_HISTORY_SENSITIVITY,
    FilingHistoryPorts,
)


class ModeloHistoryRepository:
    """Bucket-bound application facade over the filing-history capability."""

    namespace: ClassVar[str] = FILING_HISTORY_NAMESPACE
    sensitivity: ClassVar[SensitivityClass] = FILING_HISTORY_SENSITIVITY
    schema_version: ClassVar[int] = FILING_HISTORY_SCHEMA_VERSION
    payload_type: ClassVar[type[ModeloHistory]] = ModeloHistory

    def __init__(self, *, ports: FilingHistoryPorts) -> None:
        """Bind one complete, already-composed filing-history capability."""
        if not ports.bucket_id.strip():
            raise ValueError("filing-history bucket_id must not be blank")
        self._ports = ports

    @property
    def bucket_id(self) -> str:
        """Return the bucket identity carried by the required port bundle."""
        return self._ports.bucket_id

    @property
    def store_dir(self) -> Path:
        """Return the logical secure-store marker for this repository."""
        return self._ports.repository.store_dir

    def envelope_path_for(self, identifier: str) -> Path:
        """Return the logical marker for ``identifier``."""
        return self._ports.repository.envelope_path_for(identifier)

    def lock_target_for(self, identifier: str) -> Path:
        """Return the logical lock marker for ``identifier``."""
        return self._ports.repository.lock_target_for(identifier)

    def extract_identifier(self, payload: ModeloHistory) -> str:
        """Return the natural modelo identifier carried by ``payload``."""
        return str(payload.modelo)

    @classmethod
    def payload_model(cls) -> type[ModeloHistory]:
        """Return the payload type for outer custody-key inspection."""
        return cls.payload_type

    def load(self, identifier: str) -> ModeloHistory | None:
        """Load one history through the composed application capability."""
        return self._ports.repository.load(identifier)

    def save(self, payload: ModeloHistory) -> None:
        """Persist one history through the composed application capability."""
        self._ports.repository.save(payload)

    def delete(self, identifier: str) -> bool:
        """Delete one history through the composed application capability."""
        return self._ports.repository.delete(identifier)

    def iter_records(self) -> Iterator[ModeloHistory]:
        """Iterate all histories through the composed application capability."""
        return self._ports.repository.iter_records()

    def list_modelos(self) -> tuple[str, ...]:
        """Return every modelo persisted in this repository, sorted."""
        return tuple(sorted(str(history.modelo) for history in self.iter_records()))

    def iter_histories(self) -> Iterator[tuple[str, ModeloHistory]]:
        """Yield ``(modelo, history)`` tuples of :class:`ModeloHistory` for every persisted modelo."""
        for history in self._ports.repository.iter_records():
            yield str(history.modelo), history


__all__ = [
    "ModeloHistory",
    "ModeloHistoryRepository",
]
