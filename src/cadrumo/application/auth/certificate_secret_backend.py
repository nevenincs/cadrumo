"""Secure-storage certificate-secret backend for named certificate sources.

Before this module, the certificate auth provider's passphrase came from
exactly one place: the env-only, never-persisted
:attr:`~core.config.Settings.cadrumo_certificate_password_secret`. That is a single
global secret shared by whichever certificate happens to be active — it cannot
express "the personal certificate uses passphrase A, the apoderado-acme
certificate uses passphrase B" once
:mod:`~application.auth.certificate_sources` lets an operator register
several named PKCS#12 sources with potentially different passphrases.

:class:`~application.auth.SecureStorageCertificateSecretBackend` is the sole
per-source secret backend: each certificate passphrase persists through the
profile's own encrypted
:class:`~adapters.persistence.storage.SecretStore`, at
:attr:`~adapters.persistence.storage.SensitivityClass.SECRET`
sensitivity (ciphertext at rest, per
``sensitive-financial-data-secure-storage-only``). It requires no optional
dependency and is scoped by the natural key to the active bucket, so two
profiles never see each other's secrets. There is no keyring backend, backend
selector, or backend factory: secure storage is the single authority for a
named certificate secret, and the master-key OS-keyring custody backend (a
separate concern) is untouched by this module.

Never store a resolved secret in :class:`~application.auth.models.AuthState` or
any other persisted workflow-state record — the secret lives ONLY inside
the backend; workflow state at most records which named sources exist,
never their passphrases (``sensitive-financial-data-secure-storage-only``).

See Also:
    :mod:`~application.auth.certificate_sources`
        Named certificate-source registry (path only, no secret) this
        module's backend complements.
    :class:`~adapters.persistence.storage.SecretStore`
        Encrypted substrate the backend persists through.
    :class:`~adapters.persistence.storage.SensitivityClass`
        Storage classification policy used for certificate passphrases.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import SecretStr, TypeAdapter

from cadrumo.application.auth.models import CertificateSourceName

from ...adapters.persistence.storage import (
    SecretNotFoundError,
    SecretRecord,
    SecretStore,
    SensitivityClass,
    get_secret_store,
)
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import now

if TYPE_CHECKING:
    from ...core.config import Settings

_CERTIFICATE_SOURCE_NAME: TypeAdapter[str] = TypeAdapter(CertificateSourceName)

_SECRET_ROTATION_HORIZON = timedelta(days=365 * 10)
"""Effectively unbounded expiry for a rotation-driven, operator-managed secret.

:class:`~adapters.persistence.storage.SensitivityClass.SECRET` requires an
explicit ``expires_at`` at the ``SecretStore`` boundary
(``require_explicit_expiry=True``). A certificate passphrase has no
natural TTL of its own — it lives as long as the certificate does, and
rotation is an explicit operator action (``certificate secret set``),
not a clock. A ten-year horizon satisfies the retention contract without
asserting a false expiry; renewing the underlying PKCS#12 bundle rotates
the secret explicitly via the same verb.
"""

_MUTATION_OPERATION_ID_METADATA_KEY = "certificate_secret_mutation_operation_id"


@runtime_checkable
class CertificateSecretBackend(Protocol):
    """Typed seam for reading, writing, and removing a named certificate secret.

    Every method is keyed by the certificate source's registered
    ``name`` (the key carried by
    :class:`~application.auth.models.CertificateSourceRecord`), scoping the
    secret to that one source. The sole implementation
    (:class:`~application.auth.SecureStorageCertificateSecretBackend`)
    scopes storage to the active profile bucket so two profiles never share
    a namespace.
    """

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for source ``name``, or ``None`` when absent."""
        ...

    def set(
        self,
        name: str,
        secret: SecretStr,
        *,
        operation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Persist ``secret`` for ``name`` with an optional recovery witness."""
        ...

    def remove(self, name: str) -> bool:
        """Remove the persisted secret for source ``name``.

        Returns:
            ``True`` when a secret was removed, ``False`` when none was
            registered (a no-op, not an error).
        """
        ...

    def mutation_operation_id(self, name: str) -> str | None:
        """Return the non-secret operation id stamped on ``name``, when present."""
        ...

    def request_witness(self, name: str, secret: SecretStr) -> str:
        """Return a master-keyed witness for matching a retried set request."""
        ...


def _secret_store_key(*, bucket_id: str, name: str) -> str:
    """Return the :class:`~adapters.persistence.storage.SecretStore` natural key for ``name``.

    Bucket-scoped so two profiles' certificate secrets never collide in
    the shared digest-keyed index. The name is canonicalized through the same
    :data:`~application.auth.models.CertificateSourceName` contract the durable
    registry record carries, so the key cannot address a spelling the registry
    would refuse — a locally-stripping key would otherwise file two distinct
    persisted spellings under one secret.

    Raises:
        pydantic.ValidationError: When ``name`` is blank after stripping or
            exceeds the canonical length bound.
    """
    canonical = _CERTIFICATE_SOURCE_NAME.validate_python(name)
    return f"aeat:certificate-secret:{bucket_id}:{canonical}"


class SecureStorageCertificateSecretBackend:
    """The sole :class:`~application.auth.CertificateSecretBackend`, backed by storage.

    Persists each certificate passphrase as a
    :class:`~adapters.persistence.storage.SecretRecord` at
    :attr:`~adapters.persistence.storage.SensitivityClass.SECRET`
    sensitivity, scoped to ``bucket_id`` via the natural key. Requires no
    optional dependency; this is the backend every profile gets without
    further configuration, and the only one there is.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        store: SecretStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Bind the backend to one profile bucket and an optional injected store.

        Args:
            bucket_id: Active profile bucket id; scopes every key this
                backend reads or writes.
            store: Optional :class:`~adapters.persistence.storage.SecretStore`
                override. Tests inject an isolated store; production
                falls back to the canonical route-aware factory via
                :func:`~adapters.persistence.storage.get_secret_store`.
            settings: Optional route Settings forwarded to the canonical
                secret-store factory.
        """
        self._bucket_id = bucket_id
        self._store = store
        self._settings = settings

    def _resolved_store(self) -> SecretStore:
        if self._store is not None:
            return self._store

        return get_secret_store(settings=self._settings)

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for ``name``, or ``None`` when absent."""
        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            record = store.get(key)
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
        store = self._resolved_store()
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
        store.put(record, overwrite=True)

    def remove(self, name: str) -> bool:
        """Remove the persisted passphrase for ``name``; a no-op when absent."""
        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            store.delete(key)
        except SecretNotFoundError:
            return False
        return True

    def mutation_operation_id(self, name: str) -> str | None:
        """Return the non-secret operation id stamped on ``name``, when present."""
        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            record = store.get(key)
        except SecretNotFoundError:
            return None
        return record.metadata.get(_MUTATION_OPERATION_ID_METADATA_KEY)

    def request_witness(self, name: str, secret: SecretStr) -> str:
        """Return a master-keyed witness for matching a retried set request."""
        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        return store.value_witness(
            key=key,
            value=secret.get_secret_value().encode(UTF_8_ENCODING),
        )


__all__ = [
    "CertificateSecretBackend",
    "SecureStorageCertificateSecretBackend",
]
