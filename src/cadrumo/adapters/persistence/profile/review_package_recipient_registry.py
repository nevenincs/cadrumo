"""Secure-object adapter for the trusted recipient registry capability.

The application layer owns recipient DTOs and registration policy.  This
adapter owns the bucket namespace and secure-object encoding, translating
storage failures into the application's registered registry error before they
cross the port boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ....application.modelo.review_package_recipient_registry import (
    RecipientFingerprintRegister,
    RecipientFingerprintRegistryError,
)
from ....application.modelo.review_package_recipient_registry_ports import (
    RecipientFingerprintRegistryPorts,
    RecipientFingerprintRegistryRepositoryPort,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.identity.bucket import canonical_bucket_id
from ....core.time.clock import now as _utc_now
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE as _NAMESPACE,
)
from ..storage.sql.secure_objects import SecureObjectRepository

T = TypeVar("T")


def _translate_registry_failure(operation: str, action: Callable[[], T]) -> T:
    """Translate secure-object failures to the application registry contract."""
    try:
        return action()
    except RecipientFingerprintRegistryError:
        raise
    except (StorageError, OSError, TypeError, ValueError, KeyError) as exc:
        raise RecipientFingerprintRegistryError(
            f"recipient fingerprint registry {operation} failed",
            context={"operation": operation},
            translated_message="application.modelo.errors.recipient_registry_load_failed",
        ) from exc


class RecipientFingerprintRegistryAdapter(RecipientFingerprintRegistryRepositoryPort):
    """Bind the trusted-recipient port to one bucket's encrypted object store."""

    def __init__(self, *, repository: SecureObjectRepository) -> None:
        self._repository = repository

    def load(self) -> RecipientFingerprintRegister:
        """Load the register, preserving an absent row as an empty register."""

        def _load() -> RecipientFingerprintRegister:
            record = self._repository.load(
                _NAMESPACE.namespace,
                self._object_key,
                expected_class=_NAMESPACE.sensitivity,
                max_supported_version=_NAMESPACE.schema_version,
            )
            if record is None:
                return RecipientFingerprintRegister()
            return RecipientFingerprintRegister.model_validate_json(record.payload.decode(UTF_8_ENCODING))

        return _translate_registry_failure("load", _load)

    def save(self, register: RecipientFingerprintRegister) -> None:
        """Persist one validated register as the bucket's encrypted singleton."""

        def _save() -> None:
            self._repository.save(
                namespace=_NAMESPACE.namespace,
                object_key=self._object_key,
                classification=_NAMESPACE.sensitivity,
                schema_version=_NAMESPACE.schema_version,
                written_at=_utc_now(),
                payload=register.model_dump_json().encode(UTF_8_ENCODING),
                write_provenance="adapters.persistence.profile.review_package_recipient_registry",
            )

        _translate_registry_failure("save", _save)

    @property
    def _object_key(self) -> str:
        return _NAMESPACE.require_default_object_key()


def build_recipient_fingerprint_registry_ports(*, bucket_id: str) -> RecipientFingerprintRegistryPorts:
    """Bind the trusted-recipient registry to one profile bucket."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    return RecipientFingerprintRegistryPorts(
        registry_repository=RecipientFingerprintRegistryAdapter(
            repository=secure_object_repository_for_bucket(normalized_bucket_id),
        ),
    )


__all__ = [
    "RecipientFingerprintRegistryAdapter",
    "build_recipient_fingerprint_registry_ports",
]
