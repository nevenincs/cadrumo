"""Encrypted persistence adapter for live verification observations.

The live verify application service owns the observation model and its query
semantics.  This adapter owns the secure-object wire format: one encrypted
``Envelope[VerifyObservation]`` per observation, addressed by the bucket and
content id under the registry-owned verify namespace.

The adapter is deliberately bucket-bound.  A command creates one instance for
its active bucket and injects it into :class:`VerifyService`; the service never
needs to know about secure-object records, envelopes, or hashed lookup keys.
"""

from __future__ import annotations

from hmac import compare_digest
from typing import TYPE_CHECKING, NoReturn

from pydantic import ValidationError

from ....application.live.errors import LiveApplicationError, LiveApplicationInputError
from ....application.live.verify import VerifyObservation, verify_observation_object_key
from ....application.live.verify_ports import VerifyObservationPersistencePort
from ....core.external_constants import UTF_8_ENCODING
from ....core.time.clock import now
from ..storage.crypto.encrypted_columns import HashedLookup
from ..storage.envelope.contract import Envelope
from ..storage.errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRowIdentityError,
    StorageError,
)
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.schema_lineage import inner_envelope_classification_is_expected, inner_envelope_version_is_current
from ..storage.secure_object_namespaces import LIVE_VERIFY_OBSERVATION_NAMESPACE

if TYPE_CHECKING:  # pragma: no cover - import-cycle/type-only guard
    from ....core.config import Settings
    from ..storage.sql.secure_object_records import SecureObjectRecord
    from ..storage.sql.secure_objects import SecureObjectRepository


_VERIFY_NAMESPACE = LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace
_VERIFY_SENSITIVITY = LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity
_VERIFY_SCHEMA_VERSION = LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version


def _raise_storage_failure(
    exc: StorageError,
    *,
    operation: str,
    requested_observation_id: str | None = None,
    payload_observation_id: str | None = None,
) -> NoReturn:
    """Translate a storage failure into the live application's vocabulary."""
    if isinstance(exc, SecureObjectRowIdentityError):
        if requested_observation_id is not None:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_id_mismatch",
                context={
                    "observation_id": payload_observation_id or requested_observation_id,
                    "requested_observation_id": requested_observation_id,
                },
            ) from exc
        raise LiveApplicationInputError(
            translated_message="application.live.verify.errors.observation_key_mismatch",
            context={"observation_id": payload_observation_id or ""},
        ) from exc

    if isinstance(exc, ClassificationError):
        message_key = "errors.integrity.integrity_storage_classification"
    elif isinstance(exc, EnvelopeVersionError):
        message_key = "errors.integrity.integrity_storage_envelope_version"
    else:
        message_key = getattr(exc, "translated_message", None) or "errors.error.error_application_live"

    raise LiveApplicationError(
        translated_message=message_key,
        context={
            "reason": "secure_object_integrity",
            "operation": operation,
            "cause_type": type(exc).__name__,
        },
    ) from exc


def _raise_payload_validation(
    exc: BaseException,
    *,
    operation: str,
) -> NoReturn:
    """Translate malformed envelope bytes without exposing parser details."""
    raise LiveApplicationError(
        translated_message="errors.storage.stored_data_validation_boundary",
        context={
            "reason": "verify_observation_envelope_validation",
            "operation": operation,
            "cause_type": type(exc).__name__,
        },
    ) from exc


class VerifyObservationRepository(VerifyObservationPersistencePort):
    """Bucket-bound implementation of ``VerifyObservationPersistencePort``."""

    def __init__(
        self,
        *,
        bucket_id: str,
        objects: SecureObjectRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Bind one secure-object repository to ``bucket_id``."""
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.bucket_id_blank",
            )
        self._bucket_id = trimmed
        if objects is not None:
            self._objects = objects
            return
        try:
            self._objects = secure_object_repository_for_bucket(trimmed, settings)
        except StorageError as exc:
            _raise_storage_failure(exc, operation="bind")

    @property
    def bucket_id(self) -> str:
        """Return the bucket this adapter is bound to."""
        return self._bucket_id

    def _require_bound_bucket(self, bucket_id: str) -> str:
        """Normalize and validate the bucket supplied by the application port."""
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.bucket_id_blank",
            )
        if trimmed != self._bucket_id:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_bucket_mismatch",
                context={
                    "observation_bucket": trimmed,
                    "repository_bucket": self._bucket_id,
                },
            )
        return trimmed

    @staticmethod
    def _assert_record_metadata(record: SecureObjectRecord, *, operation: str) -> None:
        """Keep a malformed secure record from crossing into application code."""
        if record.namespace != _VERIFY_NAMESPACE:
            raise LiveApplicationError(
                translated_message="errors.integrity.integrity_storage_validation",
                context={
                    "reason": "verify_observation_namespace_mismatch",
                    "operation": operation,
                },
            )
        if record.classification is not _VERIFY_SENSITIVITY:
            raise LiveApplicationError(
                translated_message="errors.integrity.integrity_storage_classification",
                context={
                    "reason": "verify_observation_outer_classification_mismatch",
                    "operation": operation,
                },
            )
        if record.schema_version != _VERIFY_SCHEMA_VERSION:
            raise LiveApplicationError(
                translated_message="errors.integrity.integrity_storage_envelope_version",
                context={
                    "reason": "verify_observation_outer_schema_version_mismatch",
                    "operation": operation,
                },
            )

    @classmethod
    def _observation_from_record(
        cls,
        record: SecureObjectRecord,
        *,
        operation: str,
        requested_observation_id: str | None = None,
    ) -> VerifyObservation:
        """Decode and validate one secure record into an application model."""
        cls._assert_record_metadata(record, operation=operation)
        try:
            envelope = Envelope[VerifyObservation].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        except (TypeError, UnicodeDecodeError, ValidationError, ValueError) as exc:
            _raise_payload_validation(exc, operation=operation)

        if not inner_envelope_classification_is_expected(envelope.classification, _VERIFY_SENSITIVITY):
            _raise_storage_failure(
                ClassificationError("verify observation envelope classification does not match its namespace"),
                operation=operation,
                requested_observation_id=requested_observation_id,
                payload_observation_id=envelope.payload.observation_id,
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _VERIFY_SCHEMA_VERSION):
            _raise_storage_failure(
                EnvelopeVersionError("verify observation envelope schema version is not current"),
                operation=operation,
                requested_observation_id=requested_observation_id,
                payload_observation_id=envelope.payload.observation_id,
            )
        return envelope.payload

    def load(self, *, bucket_id: str, observation_id: str) -> VerifyObservation | None:
        """Load one observation by its full content id, or return ``None``."""
        bucket = self._require_bound_bucket(bucket_id)
        try:
            object_key = verify_observation_object_key(bucket, observation_id)
            record = self._objects.load(
                _VERIFY_NAMESPACE,
                object_key,
                expected_class=_VERIFY_SENSITIVITY,
                max_supported_version=_VERIFY_SCHEMA_VERSION,
            )
        except LiveApplicationInputError:
            raise
        except StorageError as exc:
            _raise_storage_failure(
                exc,
                operation="load",
                requested_observation_id=observation_id,
            )
        if record is None:
            return None

        observation = self._observation_from_record(
            record,
            operation="load",
            requested_observation_id=observation_id,
        )
        if observation.bucket_id != bucket:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_bucket_mismatch",
                context={
                    "observation_bucket": observation.bucket_id,
                    "repository_bucket": bucket,
                },
            )
        if observation.observation_id != observation_id:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_id_mismatch",
                context={
                    "observation_id": observation.observation_id,
                    "requested_observation_id": observation_id,
                },
            )
        self._assert_addressed_by_its_own_key(record, observation, bucket=bucket)
        return observation

    def list_observations(self, *, bucket_id: str) -> tuple[VerifyObservation, ...]:
        """List all observations in deterministic capture order."""
        bucket = self._require_bound_bucket(bucket_id)
        observations: list[VerifyObservation] = []
        try:
            records = self._objects.list_records(
                _VERIFY_NAMESPACE,
                expected_class=_VERIFY_SENSITIVITY,
                max_supported_version=_VERIFY_SCHEMA_VERSION,
            )
            for record in records:
                observation = self._observation_from_record(record, operation="list")
                if observation.bucket_id != bucket:
                    raise LiveApplicationInputError(
                        translated_message="application.live.verify.errors.observation_bucket_mismatch",
                        context={
                            "observation_bucket": observation.bucket_id,
                            "repository_bucket": bucket,
                        },
                    )
                self._assert_addressed_by_its_own_key(record, observation, bucket=bucket)
                observations.append(observation)
        except LiveApplicationInputError:
            raise
        except LiveApplicationError:
            raise
        except StorageError as exc:
            _raise_storage_failure(exc, operation="list")
        return tuple(sorted(observations, key=lambda item: (item.checked_at, item.observation_id)))

    @staticmethod
    def _assert_addressed_by_its_own_key(
        record: SecureObjectRecord,
        observation: VerifyObservation,
        *,
        bucket: str,
    ) -> None:
        """Refuse a valid observation stored under a different hashed key."""
        try:
            expected_key = HashedLookup.compute(verify_observation_object_key(bucket, observation.observation_id))
            matches = compare_digest(expected_key, record.object_key)
        except StorageError as exc:
            _raise_storage_failure(
                exc,
                operation="key_check",
                payload_observation_id=observation.observation_id,
            )
        except (TypeError, ValueError) as exc:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_key_mismatch",
                context={"observation_id": observation.observation_id},
            ) from exc
        if not matches:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_key_mismatch",
                context={"observation_id": observation.observation_id},
            )

    def save(self, observation: VerifyObservation) -> None:
        """Encrypt and persist one application-level verify observation."""
        if observation.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                translated_message="application.live.verify.errors.observation_bucket_mismatch",
                context={
                    "observation_bucket": observation.bucket_id,
                    "repository_bucket": self._bucket_id,
                },
            )
        try:
            envelope = Envelope[VerifyObservation](
                schema_version=_VERIFY_SCHEMA_VERSION,
                written_at=now(),
                classification=_VERIFY_SENSITIVITY,
                payload=observation,
            )
            self._objects.save(
                namespace=_VERIFY_NAMESPACE,
                object_key=verify_observation_object_key(self._bucket_id, observation.observation_id),
                classification=_VERIFY_SENSITIVITY,
                schema_version=_VERIFY_SCHEMA_VERSION,
                written_at=envelope.written_at,
                payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
            )
        except LiveApplicationInputError:
            raise
        except (TypeError, ValidationError, ValueError) as exc:
            _raise_payload_validation(exc, operation="save")
        except StorageError as exc:
            _raise_storage_failure(exc, operation="save")


__all__ = ["VerifyObservationRepository"]
