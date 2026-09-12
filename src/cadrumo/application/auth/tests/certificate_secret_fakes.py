"""Application-boundary fakes for certificate-secret use-case tests."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from pydantic import SecretStr

from ..certificate_secret_backend import CertificateSecretBackend, CertificateSecretBackendFactory


class InMemoryCertificateSecretBackend:
    """Small bucket-scoped fake implementing only the application port."""

    def __init__(self, values: dict[str, SecretStr], operation_ids: dict[str, str | None]) -> None:
        self._values = values
        self._operation_ids = operation_ids

    def get(self, name: str) -> SecretStr | None:
        return self._values.get(name)

    def set(
        self,
        name: str,
        secret: SecretStr,
        *,
        operation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        del occurred_at
        self._values[name] = SecretStr(secret.get_secret_value())
        self._operation_ids[name] = operation_id

    def remove(self, name: str) -> bool:
        if name not in self._values:
            return False
        del self._values[name]
        self._operation_ids.pop(name, None)
        return True

    def mutation_operation_id(self, name: str) -> str | None:
        return self._operation_ids.get(name)

    def request_witness(self, name: str, secret: SecretStr) -> str:
        del name
        return sha256(secret.get_secret_value().encode("utf-8")).hexdigest()


class InMemoryCertificateSecretBackendFactory:
    """Construct fakes by bucket id without importing persistence adapters."""

    def __init__(self) -> None:
        self._values_by_bucket: dict[str, dict[str, SecretStr]] = {}
        self._operation_ids_by_bucket: dict[str, dict[str, str | None]] = {}

    def __call__(self, *, bucket_id: str, settings: object) -> CertificateSecretBackend:
        storage_scope = getattr(settings, "cadrumo_local_storage_root", None)
        if storage_scope is None:
            storage_scope = getattr(settings, "cadrumo_blob_store_dir", None)
        scope_key = f"{bucket_id}:{storage_scope}"
        values = self._values_by_bucket.setdefault(scope_key, {})
        operation_ids = self._operation_ids_by_bucket.setdefault(scope_key, {})
        return InMemoryCertificateSecretBackend(values, operation_ids)


__all__ = ["InMemoryCertificateSecretBackendFactory"]
