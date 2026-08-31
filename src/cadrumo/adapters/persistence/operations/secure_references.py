"""Encrypted, content-addressed secure operands for durable operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ValidationError

from ....core.classification.policies import AtRestTreatment, SensitivityClass, default_policy_for
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.identity import ContentDigest
from ....core.time.utc import validate_utc_aware
from ..storage._secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE, SecureObjectNamespaceDefinition
from ..storage.errors import RepositoryError
from ..storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.sql import SecureObjectRepository

_SECURE_REFERENCE_SCHEMA_VERSION = 1
_CONTENT_DIGEST_OBJECT_KEY_GRAMMAR = "{content_digest}"
_PERMITTED_SENSITIVITIES = frozenset(
    (SensitivityClass.IDENTITY, SensitivityClass.FINANCIAL, SensitivityClass.AUDIT),
)


class OperationSecureReferenceRepository:
    """Persist typed operation operands in an injected encrypted namespace.

    The journal carries only the SHA-256 content digest.  The corresponding
    serialized operand is encrypted by :class:`SecureObjectRepository`, which
    is injected by the caller that owns secure-storage routing and namespace
    registration.
    """

    def __init__(
        self,
        *,
        objects: SecureObjectRepository | None = None,
        objects_factory: Callable[[], SecureObjectRepository] | None = None,
        namespace: SecureObjectNamespaceDefinition,
    ) -> None:
        """Bind one encrypted object source to its registered operand namespace."""
        if objects is not None and objects_factory is not None:
            raise ValueError("operation secure references accept one repository source")
        if objects is None and objects_factory is None:
            raise ValueError("operation secure references require one repository source")
        self._validate_namespace(namespace)
        self._objects = objects
        self._objects_factory = objects_factory
        self._namespace = namespace

    def _repository(self) -> SecureObjectRepository:
        if self._objects is not None:
            return self._objects
        assert self._objects_factory is not None
        return self._objects_factory()

    @staticmethod
    def _validate_namespace(namespace: SecureObjectNamespaceDefinition) -> None:
        if namespace.schema_version != _SECURE_REFERENCE_SCHEMA_VERSION:
            raise ValueError("operation secure-reference namespace must use schema version 1")
        if namespace.object_key_grammar != _CONTENT_DIGEST_OBJECT_KEY_GRAMMAR:
            raise ValueError("operation secure-reference namespace must be keyed by {content_digest}")
        if namespace.sensitivity not in _PERMITTED_SENSITIVITIES:
            raise ValueError("operation secure-reference namespace has unsuitable sensitivity")
        if default_policy_for(namespace.sensitivity).at_rest is not AtRestTreatment.CIPHERTEXT_REQUIRED:
            raise ValueError("operation secure-reference namespace must require ciphertext at rest")

    @staticmethod
    def _serialized_operand(operand: BaseModel) -> bytes:
        """Return the exact typed JSON bytes addressed by the content digest."""
        return operand.model_dump_json(
            by_alias=True,
            exclude_defaults=False,
            exclude_none=False,
            exclude_unset=False,
        ).encode(UTF_8_ENCODING)

    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        """Encrypt ``operand`` under its exact typed-content digest."""
        validate_utc_aware(written_at)
        payload = self._serialized_operand(operand)
        reference = sha256_hex(payload)
        objects = self._repository()
        existing = objects.load(
            self._namespace.namespace,
            reference,
            expected_class=self._namespace.sensitivity,
            max_supported_version=self._namespace.schema_version,
        )
        if existing is not None:
            self._require_matching_digest(reference, existing.payload)
            return reference
        objects.save(
            namespace=self._namespace.namespace,
            object_key=reference,
            classification=self._namespace.sensitivity,
            schema_version=self._namespace.schema_version,
            written_at=written_at,
            payload=payload,
        )
        return reference

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        """Load, re-hash, and strictly hydrate one typed secure operand."""
        record = self._repository().load(
            self._namespace.namespace,
            reference,
            expected_class=self._namespace.sensitivity,
            max_supported_version=self._namespace.schema_version,
        )
        if record is None:
            raise RepositoryError("operation secure reference is absent")
        self._require_matching_digest(reference, record.payload)
        try:
            return operand_type.model_validate_json(record.payload, strict=True)
        except ValidationError as exc:
            raise RepositoryError("operation secure reference payload does not match requested operand type") from exc

    @staticmethod
    def _require_matching_digest(reference: ContentDigest, payload: bytes) -> None:
        if sha256_hex(payload) != reference:
            raise RepositoryError("operation secure reference content digest mismatch")


def operation_secure_reference_repository(
    *,
    objects: SecureObjectRepository | None = None,
) -> OperationSecureReferenceRepository:
    """Bind explicit test storage or lazily resolve the live active profile."""
    return OperationSecureReferenceRepository(
        objects=objects,
        objects_factory=None if objects is not None else secure_object_repository_for_active_bucket,
        namespace=OPERATION_SECURE_REFERENCE_NAMESPACE,
    )


__all__ = [
    "OPERATION_SECURE_REFERENCE_NAMESPACE",
    "OperationSecureReferenceRepository",
    "operation_secure_reference_repository",
]
