"""Encrypted persistence adapter for application filing-history ports."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, override

from ....application.filing.history_models import ModeloHistory
from ....application.filing.history_ports import (
    FILING_HISTORY_NAMESPACE,
    FILING_HISTORY_SCHEMA_VERSION,
    FILING_HISTORY_SENSITIVITY,
    FilingHistoryPersistenceError,
    FilingHistoryRepositoryPort,
)
from ....core.classification.policies import SensitivityClass
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import StorageError
from ..storage.sql.secure_objects import SecureObjectRepository


class FilingHistoryRepositoryAdapter(
    SecureBoundRepository[ModeloHistory],
    FilingHistoryRepositoryPort,
):
    """Bind the application contract to the encrypted secure-object repository."""

    namespace: ClassVar[str] = FILING_HISTORY_NAMESPACE
    sensitivity: ClassVar[SensitivityClass] = FILING_HISTORY_SENSITIVITY
    schema_version: ClassVar[int] = FILING_HISTORY_SCHEMA_VERSION
    payload_type: ClassVar[type[ModeloHistory]] = ModeloHistory

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store; never resolve one here."""
        super().__init__(objects=objects)

    @override
    def extract_identifier(self, payload: ModeloHistory) -> str:
        return str(payload.modelo)

    @staticmethod
    def _translate(operation: str, error: StorageError) -> FilingHistoryPersistenceError:
        """Translate storage-specific failures before they cross the port."""
        return FilingHistoryPersistenceError(
            translated_message="application.filing.errors.persistence",
            context={"operation": operation, "adapter_error": type(error).__name__},
        )

    def load(self, identifier: str) -> ModeloHistory | None:
        """Load one encrypted history and translate storage failures."""
        try:
            return super().load(identifier)
        except StorageError as error:
            raise self._translate("load", error) from error

    def save(self, payload: ModeloHistory) -> None:
        """Save one encrypted history and translate storage failures."""
        try:
            super().save(payload)
        except StorageError as error:
            raise self._translate("save", error) from error

    def delete(self, identifier: str) -> bool:
        """Delete one encrypted history and translate storage failures."""
        try:
            return super().delete(identifier)
        except StorageError as error:
            raise self._translate("delete", error) from error

    def iter_records(self) -> Iterator[ModeloHistory]:
        """Iterate encrypted histories and translate scan failures."""
        try:
            yield from super().iter_records()
        except StorageError as error:
            raise self._translate("iter_records", error) from error


__all__ = ["FilingHistoryRepositoryAdapter"]
