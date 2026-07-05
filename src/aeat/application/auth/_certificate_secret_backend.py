"""Certificate-secret backend abstraction for named certificate sources.

Before this module, the certificate auth provider's passphrase came from
exactly one place: the env-only, never-persisted
:attr:`~core.config.Settings.aeat_certificate_password_secret`. That is a single
global secret shared by whichever certificate happens to be active — it cannot
express "the personal certificate uses passphrase A, the apoderado-acme
certificate uses passphrase B" once
:mod:`~application.auth._certificate_sources` lets an operator register
several named PKCS#12 sources with potentially different passphrases.

:class:`~application.auth.CertificateSecretBackend` is the typed seam a
per-source secret is read and written through. Two backends are provided:

- :class:`~application.auth.SecureStorageCertificateSecretBackend` (the default)
  persists the secret through the profile's own encrypted
  :class:`~adapters.persistence.storage.SecretStore`, at
  :attr:`~adapters.persistence.storage.SensitivityClass.SECRET`
  sensitivity (ciphertext at rest, per
  ``sensitive-financial-data-secure-storage-only``). It requires no
  optional dependency and is scoped by the natural key to the active
  bucket, so two profiles never see each other's secrets.
- :class:`~application.auth.KeyringCertificateSecretBackend` persists the secret
  in the OS keychain via the same
  :class:`~adapters.persistence.storage.master_key.KeyringClient` seam
  :class:`~adapters.persistence.storage.master_key.KeyringMasterKeyProvider`
  already uses, so a keychain-preferring operator keeps the certificate
  passphrase off the encrypted-file substrate entirely. ``keyring`` is
  already a project dependency (see ``pyproject.toml``); this backend is
  therefore available today, not a scoped follow-up.

Never store a resolved secret in :class:`~application.auth.AuthState` or
any other persisted workflow-state record — the secret lives ONLY inside
the backend; workflow state at most records which named sources exist,
never their passphrases (``sensitive-financial-data-secure-storage-only``).

See Also:
    :mod:`~application.auth._certificate_sources`
        Named certificate-source registry (path only, no secret) this
        module's backend complements.
    :class:`~adapters.persistence.storage.SecretStore`
        Encrypted substrate the default backend persists through.
    :class:`~adapters.persistence.storage.SensitivityClass`
        Storage classification policy used by the secure-storage backend for
        certificate passphrases.
    :class:`~adapters.persistence.storage.master_key.KeyringClient`
        Injection seam for the OS-keychain operations the keyring backend
        depends on; mirrored here rather than imported directly so this
        module does not reach into the master-key package's internals.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import SecretStr

from ...core.time import now

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecretStore

_KEYRING_SERVICE_PREFIX = "aeat:certificate-secret"
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


class CertificateSecretBackendKind(StrEnum):
    """Closed set of certificate-secret backends a named source may use."""

    SECURE_STORAGE = "secure_storage"
    KEYRING = "keyring"


class CertificateSecretNotFoundError(Exception):
    """Raised when no secret is registered for a certificate source."""


class CertificateSecretBackendUnavailableError(Exception):
    """Raised when the selected backend cannot currently store or retrieve a secret."""


@runtime_checkable
class CertificateSecretBackend(Protocol):
    """Typed seam for reading, writing, and removing a named certificate secret.

    Every method is keyed by the certificate source's registered
    ``name`` (see
    :attr:`~application.auth.CertificateSourceRecord.name`), scoping the
    secret to that one source. Implementations MUST scope storage to the
    active profile bucket so two profiles never share a namespace.
    """

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for source ``name``, or ``None`` when absent."""
        ...

    def set(self, name: str, secret: SecretStr) -> None:
        """Persist ``secret`` for source ``name``, overwriting any prior value (rotation)."""
        ...

    def remove(self, name: str) -> bool:
        """Remove the persisted secret for source ``name``.

        Returns:
            ``True`` when a secret was removed, ``False`` when none was
            registered (a no-op, not an error).
        """
        ...


def _secret_store_key(*, bucket_id: str, name: str) -> str:
    """Return the :class:`~adapters.persistence.storage.SecretStore` natural key for ``name``.

    Bucket-scoped so two profiles' certificate secrets never collide in
    the shared digest-keyed index.
    """
    return f"aeat:certificate-secret:{bucket_id}:{name.strip()}"


class SecureStorageCertificateSecretBackend:
    """Default :class:`~application.auth.CertificateSecretBackend` backed by storage.

    Persists each certificate passphrase as a
    :class:`~adapters.persistence.storage.SecretRecord` at
    :attr:`~adapters.persistence.storage.SensitivityClass.SECRET`
    sensitivity, scoped to ``bucket_id`` via the natural key. Requires no
    optional dependency; this is the backend every profile gets without
    further configuration.
    """

    def __init__(self, *, bucket_id: str, store: SecretStore | None = None) -> None:
        """Bind the backend to one profile bucket and an optional injected store.

        Args:
            bucket_id: Active profile bucket id; scopes every key this
                backend reads or writes.
            store: Optional :class:`~adapters.persistence.storage.SecretStore`
                override. Tests inject an isolated store; production
                falls back to the process-wide singleton via
                :func:`~adapters.persistence.storage.get_secret_store`.
        """
        self._bucket_id = bucket_id
        self._store = store

    def _resolved_store(self) -> SecretStore:
        if self._store is not None:
            return self._store
        from ...adapters.persistence.storage import get_secret_store

        return get_secret_store()

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for ``name``, or ``None`` when absent."""
        from ...adapters.persistence.storage import SecretNotFoundError

        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            record = store.get(key)
        except SecretNotFoundError:
            return None
        return SecretStr(record.value.decode("utf-8"))

    def set(self, name: str, secret: SecretStr) -> None:
        """Persist (or rotate) the passphrase for ``name``."""
        from ...adapters.persistence.storage import SecretRecord, SensitivityClass

        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        record = SecretRecord(
            key=key,
            value=secret.get_secret_value().encode("utf-8"),
            classification=SensitivityClass.SECRET,
            created_at=now(),
            expires_at=now() + _SECRET_ROTATION_HORIZON,
        )
        store.put(record, overwrite=True)

    def remove(self, name: str) -> bool:
        """Remove the persisted passphrase for ``name``; a no-op when absent."""
        from ...adapters.persistence.storage import SecretNotFoundError

        store = self._resolved_store()
        key = _secret_store_key(bucket_id=self._bucket_id, name=name)
        try:
            store.delete(key)
        except SecretNotFoundError:
            return False
        return True


class KeyringCertificateSecretBackend:
    """:class:`~application.auth.CertificateSecretBackend` backed by ``keyring``.

    Mirrors :class:`~adapters.persistence.storage.master_key.KeyringMasterKeyProvider`:
    the active backend is probed before any read or write so the no-op
    ``fail.Keyring`` / ``null.Keyring`` placeholders raise
    :class:`~application.auth.CertificateSecretBackendUnavailableError` rather than
    silently dropping the secret. Every account is
    ``f"{bucket_id}:{name}"`` under one service string, so profiles and
    sources never collide in the OS keychain namespace.
    """

    def __init__(self, *, bucket_id: str) -> None:
        """Bind the backend to one profile bucket.

        Args:
            bucket_id: Active profile bucket id; scopes every keychain
                account this backend reads or writes.
        """
        self._bucket_id = bucket_id
        self._service = _KEYRING_SERVICE_PREFIX

    def _account(self, name: str) -> str:
        return f"{self._bucket_id}:{name.strip()}"

    def _probe_backend(self) -> None:
        try:
            import keyring
        except ImportError as exc:
            raise CertificateSecretBackendUnavailableError(
                f"keyring package not importable: {exc}",
            ) from exc
        try:
            from keyring.backends import fail as _fail_backend

            backend = keyring.get_keyring()
        except Exception as exc:
            raise CertificateSecretBackendUnavailableError(
                f"unable to inspect OS keychain backend: {exc}",
            ) from exc
        if isinstance(backend, _fail_backend.Keyring):
            raise CertificateSecretBackendUnavailableError(
                "OS keychain backend is the no-op fail.Keyring; "
                "install a usable backend or use the secure-storage backend instead.",
            )
        if type(backend).__name__ == "Keyring" and type(backend).__module__.endswith(".null"):
            raise CertificateSecretBackendUnavailableError(
                "OS keychain backend is the no-op null.Keyring; "
                "install a usable backend or use the secure-storage backend instead.",
            )

    def get(self, name: str) -> SecretStr | None:
        """Return the persisted passphrase for ``name``, or ``None`` when absent."""
        import keyring
        from keyring.errors import KeyringError

        self._probe_backend()
        try:
            value = keyring.get_password(self._service, self._account(name))
        except KeyringError as exc:
            raise CertificateSecretBackendUnavailableError(
                f"OS keychain refused get_password: {exc}",
            ) from exc
        if value is None:
            return None
        return SecretStr(value)

    def set(self, name: str, secret: SecretStr) -> None:
        """Persist (or rotate) the passphrase for ``name``."""
        import keyring
        from keyring.errors import KeyringError

        self._probe_backend()
        try:
            keyring.set_password(self._service, self._account(name), secret.get_secret_value())
        except KeyringError as exc:
            raise CertificateSecretBackendUnavailableError(
                f"OS keychain refused set_password: {exc}",
            ) from exc

    def remove(self, name: str) -> bool:
        """Remove the persisted passphrase for ``name``; a no-op when absent."""
        import keyring
        from keyring.errors import KeyringError, PasswordDeleteError

        self._probe_backend()
        try:
            keyring.delete_password(self._service, self._account(name))
        except PasswordDeleteError:
            return False
        except KeyringError as exc:
            raise CertificateSecretBackendUnavailableError(
                f"OS keychain refused delete_password: {exc}",
            ) from exc
        return True


def certificate_secret_backend(
    *,
    bucket_id: str,
    kind: CertificateSecretBackendKind = CertificateSecretBackendKind.SECURE_STORAGE,
) -> CertificateSecretBackend:
    """Return the :class:`~application.auth.CertificateSecretBackend` for ``kind``.

    ``SECURE_STORAGE`` is the default and requires no optional
    dependency; ``KEYRING`` requires a usable OS keychain backend and
    raises
    :class:`~application.auth.CertificateSecretBackendUnavailableError` (via the
    backend's own probe) when none is available. The returned backend is scoped
    to ``bucket_id``.
    """
    if kind is CertificateSecretBackendKind.KEYRING:
        return KeyringCertificateSecretBackend(bucket_id=bucket_id)
    return SecureStorageCertificateSecretBackend(bucket_id=bucket_id)


__all__ = [
    "CertificateSecretBackend",
    "CertificateSecretBackendKind",
    "CertificateSecretBackendUnavailableError",
    "CertificateSecretNotFoundError",
    "KeyringCertificateSecretBackend",
    "SecureStorageCertificateSecretBackend",
    "certificate_secret_backend",
]
