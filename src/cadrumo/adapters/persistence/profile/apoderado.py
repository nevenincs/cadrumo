"""Encrypted persistence adapter for apoderado configuration.

This module is the outward implementation of the application-owned
``ApoderadoConfigurationRepository``.  It owns the secure-envelope substrate,
namespace contract, bucket key derivation, and translation of row-identity
refusals into the application error understood by the service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from ....application.auth.apoderado_repository import ApoderadoConfigurationRepository
from ....application.auth.apoderado_service import (
    ApoderadoConfiguration,
    ApoderadoConfigurationIdentityError,
)
from ....core.classification.policies import SensitivityClass
from ....core.identity.bucket import canonical_bucket_id
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import SecureObjectRowIdentityError
from ..storage.path_safety import safe_repository_id
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import AUTH_APODERADO_CONFIGURATION_NAMESPACE

if TYPE_CHECKING:
    from ....core.config import Settings


class ApoderadoConfigRepository(SecureBoundRepository[ApoderadoConfiguration]):
    """Encrypted per-bucket adapter for apoderado configuration."""

    namespace: ClassVar[str] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.schema_version

    def __init__(self, *, bucket_id: str, settings: Settings) -> None:
        """Bind this adapter to one canonical bucket and explicit settings."""
        self._bound_bucket_id = canonical_bucket_id(bucket_id)
        self._safe_bucket_id = safe_repository_id(self._bound_bucket_id, context="bucket_id")
        super().__init__(
            bucket_id=self._safe_bucket_id,
            objects=secure_object_repository_for_bucket(self._bound_bucket_id, settings),
        )

    @override
    @classmethod
    def payload_model(cls) -> type[ApoderadoConfiguration]:
        """Return the application configuration DTO wrapped by this adapter."""
        return ApoderadoConfiguration

    @override
    def extract_identifier(self, payload: ApoderadoConfiguration) -> str:
        """Return the safe secure-object key for ``payload``'s bucket."""
        return safe_repository_id(canonical_bucket_id(payload.bucket_id), context="bucket_id")

    @override
    def _translate_row_identity_error(self, error: SecureObjectRowIdentityError) -> Exception:
        """Translate a misfiled storage row into the application error."""
        return ApoderadoConfigurationIdentityError(
            translated_message="errors.integrity.integrity_apoderado_configuration_identity",
            context={
                "repository_bucket_id": self._bound_bucket_id,
                "storage_row_identity": "payload_key_mismatch",
            },
        )

    @override
    def load(self) -> ApoderadoConfiguration | None:
        """Load this bucket's configuration, or return ``None`` when absent."""
        return super().load(self._safe_bucket_id)

    @override
    def save(self, configuration: ApoderadoConfiguration) -> None:
        """Persist a configuration only when it names this bound bucket."""
        payload_bucket_id = canonical_bucket_id(configuration.bucket_id)
        if payload_bucket_id != self._bound_bucket_id:
            raise ApoderadoConfigurationIdentityError(
                translated_message="errors.integrity.integrity_apoderado_configuration_identity",
                context={
                    "bucket_id": payload_bucket_id,
                    "repository_bucket_id": self._bound_bucket_id,
                },
            )
        super().save(configuration)

    @override
    def delete(self) -> bool:
        """Delete this bucket's configuration, returning whether it existed."""
        return super().delete(self._safe_bucket_id)


def build_apoderado_config_repository(
    *,
    bucket_id: str,
    settings: Settings,
) -> ApoderadoConfigurationRepository:
    """Build the concrete adapter for one explicitly routed bucket."""
    return ApoderadoConfigRepository(bucket_id=bucket_id, settings=settings)


__all__ = [
    "ApoderadoConfigRepository",
    "build_apoderado_config_repository",
]
