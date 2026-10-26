"""Concrete adapter for the application certificate-secret capability.

This module owns the encrypted secret-store record and its persistence errors.
The application-facing contract receives only ``SecretStr`` values, absence,
and non-secret mutation witnesses; storage records never cross that boundary.

Core types:
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import SecretStr, TypeAdapter

from ....application.auth.certificate_secret_backend import CertificateSecretBackend
from ....application.auth.models import CertificateSourceName
from ....core.classification.policies import SensitivityClass
from ....core.external_constants import UTF_8_ENCODING
from ....core.time.clock import now
from .blob_store.materialisation import get_secret_store
from .errors import SecretNotFoundError
from .secret_store.store import SecretRecord, SecretStore

if TYPE_CHECKING:
    from ....core.config import Settings


_CERTIFICATE_SOURCE_NAME: TypeAdapter[str] = TypeAdapter(CertificateSourceName)

_SECRET_ROTATION_HORIZON = timedelta(days=365 * 10)
"""Effectively unbounded expiry for a rotation-driven operator secret."""

_MUTATION_OPERATION_ID_METADATA_KEY = "certificate_secret_mutation_operation_id"


def _secret_store_key(*, bucket_id: str, name: str) -> str:
    """Return the bucket-scoped natural key for one certificate source."""
    canonical = _CERTIFICATE_SOURCE_NAME.validate_python(name)
    return f"aeat:certificate-secret:{bucket_id}:{canonical}"


class SecureStorageCertificateSecretBackend:
    """Persist named certificate passphrases through encrypted secure storage."""

    def __init__(self, *, bucket_id: str, store: SecretStore) -> None:
        """Bind this adapter to one profile bucket and one explicit store."""
        self._bucket_id = bucket_id
        self._store = store

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for ``name``, or ``None`` when absent."""
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            record = self._store.get(key)
        except SecretNotFoundError:
            return None
        return SecretStr(record.value.decode(UTF_8_ENCODING))

    def set(
        self,
        name: str,
        secret: SecretStr,
        *,
        operation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Persist (or rotate) the passphrase for ``name``."""
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        written_at = occurred_at or now()
        metadata = {_MUTATION_OPERATION_ID_METADATA_KEY: operation_id} if operation_id is not None else {}
        record = SecretRecord(
            key=key,
            value=secret.get_secret_value().encode(UTF_8_ENCODING),
            classification=SensitivityClass.SECRET,
            metadata=metadata,
            created_at=written_at,
            expires_at=written_at + _SECRET_ROTATION_HORIZON,
        )
        self._store.put(record, overwrite=True)

    def remove(self, name: str) -> bool:
        """Remove the persisted passphrase for ``name``; absent is a no-op."""
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            self._store.delete(key)
        except SecretNotFoundError:
            return False
        return True

    def mutation_operation_id(self, name: str) -> str | None:
        """Return the non-secret operation id stamped on ``name``, if present."""
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            record = self._store.get(key)
        except SecretNotFoundError:
            return None
        return record.metadata.get(_MUTATION_OPERATION_ID_METADATA_KEY)

    def request_witness(self, name: str, secret: SecretStr) -> str:
        """Return a master-keyed witness for matching a retried set request."""
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        return self._store.value_witness(
            key=key,
            value=secret.get_secret_value().encode(UTF_8_ENCODING),
        )


def build_certificate_secret_backend(
    *,
    bucket_id: str,
    settings: Settings,
) -> CertificateSecretBackend:
    """Build one bucket-scoped adapter from the explicit routed store."""
    return SecureStorageCertificateSecretBackend(
        bucket_id=bucket_id,
        store=get_secret_store(settings=settings),
    )


__all__ = [
    "SecureStorageCertificateSecretBackend",
    "build_certificate_secret_backend",
]
