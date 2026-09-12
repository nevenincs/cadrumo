"""Application-owned capability contract for named certificate secrets.

Certificate authentication owns the policy around a named source: callers
need a bucket-scoped capability that can resolve, rotate, remove, and witness a
passphrase without knowing how the secret is kept at rest.  The encrypted
storage implementation is an outward adapter and is bound by each executable
composition root below this contract.

The application never receives a persistence record.  Reads project either a
``SecretStr`` or absence, and mutation retries use only the non-secret witness
and operation-id methods declared here.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from pydantic import SecretStr

if TYPE_CHECKING:
    from ...core.config import Settings


class CertificateSecretBackend(Protocol):
    """Bucket-scoped capability for named certificate passphrases."""

    def get(self, name: str) -> SecretStr | None:
        """Return the passphrase for ``name``, or ``None`` when it is absent."""
        ...

    def set(
        self,
        name: str,
        secret: SecretStr,
        *,
        operation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Persist or rotate one named passphrase."""
        ...

    def remove(self, name: str) -> bool:
        """Remove one named passphrase, returning whether it existed."""
        ...

    def mutation_operation_id(self, name: str) -> str | None:
        """Return the non-secret operation id attached to ``name``, if present."""
        ...

    def request_witness(self, name: str, secret: SecretStr) -> str:
        """Return a non-secret witness for an idempotent set/rotate retry."""
        ...


class CertificateSecretBackendFactory(Protocol):
    """Construct one certificate-secret capability for a routed bucket."""

    def __call__(self, *, bucket_id: str, settings: Settings) -> CertificateSecretBackend:
        """Return the capability bound to ``bucket_id`` and ``settings``."""
        ...


__all__ = [
    "CertificateSecretBackend",
    "CertificateSecretBackendFactory",
]
