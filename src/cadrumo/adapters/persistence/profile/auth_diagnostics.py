"""Encrypted persistence adapter for application auth diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import override

from ....application.auth.diagnostics_ports import (
    AuthDiagnosticPersistenceError,
    AuthDiagnosticPersistencePort,
    AuthDiagnosticPersistenceRecord,
)
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.secure_object_namespaces import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE


class AuthDiagnosticPersistenceAdapter(AuthDiagnosticPersistencePort):
    """Translate the active bucket's secure-object store to the auth port."""

    @staticmethod
    def _repository():
        """Resolve the repository only when an operation has an active bucket."""
        return secure_object_repository_for_active_bucket()

    @staticmethod
    def _record(payload: bytes) -> AuthDiagnosticPersistenceRecord:
        """Translate a storage payload into the application-owned record."""
        return AuthDiagnosticPersistenceRecord(payload=payload)

    @override
    def list_records(self) -> tuple[AuthDiagnosticPersistenceRecord, ...]:
        """List readable diagnostic payloads from the canonical namespace."""
        try:
            return tuple(
                self._record(record.payload)
                for record in self._repository().list_records(
                    CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
                    expected_class=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
                    max_supported_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
                )
            )
        except StorageError as error:
            raise AuthDiagnosticPersistenceError("list") from error

    @override
    def load_record(self, diagnostic_id: str) -> AuthDiagnosticPersistenceRecord | None:
        """Load one readable diagnostic payload from the canonical namespace."""
        try:
            record = self._repository().load(
                CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
                diagnostic_id,
                expected_class=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
                max_supported_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
            )
        except StorageError as error:
            raise AuthDiagnosticPersistenceError("load") from error
        return None if record is None else self._record(record.payload)

    @override
    def save_record(self, diagnostic_id: str, payload: bytes, *, written_at: datetime) -> None:
        """Save one diagnostic payload under the canonical namespace contract."""
        try:
            self._repository().save(
                namespace=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
                object_key=diagnostic_id,
                classification=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
                schema_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
                written_at=written_at,
                payload=payload,
            )
        except StorageError as error:
            raise AuthDiagnosticPersistenceError("save") from error


def build_auth_diagnostic_persistence() -> AuthDiagnosticPersistencePort:
    """Build the stateless active-bucket auth-diagnostic adapter."""
    return AuthDiagnosticPersistenceAdapter()


__all__ = ["AuthDiagnosticPersistenceAdapter", "build_auth_diagnostic_persistence"]
