"""Encrypted persistence adapter for ledger classification jobs.

A job names the profile's movements and holds a model's typed proposal for
each, so it lives only in an encrypted payload of the profile's own bucket.
The row is stored under ``classification-job:{bucket_id}:{job_id}``, and the
key is digested again into the ``object_key`` column, as for every namespace.
The row-identity AAD binds namespace, key digest and schema version, and the
key is re-derived from the payload on load, so a substituted row is refused.

The adapter is bound to one bucket. It addresses only that bucket's keys and
refuses a stored job that names another bucket, so one profile's queue never
reads or writes another's.

A storage failure is translated into the application-owned error and never into
an empty result: a caller that cannot read the queue must not read that as there
being no jobs.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.domain.transactions.classification_job.ClassificationJob`,
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import ClassVar, Final, override

from ....application.ledger.classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobPersistenceError,
    ClassificationJobRepository,
    ClassificationJobRevisionConflictError,
    classification_job_object_key,
)
from ....core.classification.policies import SensitivityClass
from ....core.errors.hierarchy import InternalInvariantError
from ....core.hex import HEX_PATTERN_64
from ....core.identity.bucket import canonical_bucket_id
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.transactions.classification_job import ClassificationJob
from ....domain.transactions.errors import ClassificationJobError
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import STORED_RECORD_FAILURES, SecureObjectRevisionConflictError, SecureObjectRowIdentityError
from ..storage.secure_object_namespaces import LEDGER_CLASSIFICATION_JOBS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

__all__ = ["ClassificationJobRepositoryAdapter"]

_PASSED_THROUGH: Final = (
    ClassificationJobPersistenceError,
    ClassificationJobRevisionConflictError,
    ClassificationJobNotFoundError,
    ClassificationJobError,
    InternalInvariantError,
)


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate storage failures into the application-owned error, keeping the conflict distinct."""
    try:
        return action()
    except _PASSED_THROUGH:
        raise
    except SecureObjectRevisionConflictError as exc:
        raise ClassificationJobRevisionConflictError from exc
    except (*STORED_RECORD_FAILURES, TypeError, KeyError) as exc:
        raise ClassificationJobPersistenceError(operation) from exc


class ClassificationJobRepositoryAdapter(SecureBoundRepository[ClassificationJob], ClassificationJobRepository):
    """Bind the classification job port to one bucket's encrypted secure-object storage."""

    namespace: ClassVar[str] = LEDGER_CLASSIFICATION_JOBS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_CLASSIFICATION_JOBS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_CLASSIFICATION_JOBS_NAMESPACE.schema_version
    # Final: a constant narrowing of the base's mutable ``ClassVar[type[BaseModel]]``.
    payload_type: Final[type[ClassificationJob]] = ClassificationJob

    def __init__(self, *, objects: SecureObjectRepository, bucket_id: str) -> None:
        """Bind an already-composed secure-object store and the bucket it serves."""
        super().__init__(objects=objects)
        self._bucket_id = canonical_bucket_id(bucket_id)

    @override
    def extract_identifier(self, payload: ClassificationJob) -> str:
        return classification_job_object_key(bucket_id=payload.bucket_id, job_id=payload.job_id)

    def _require_own_bucket(self, job: ClassificationJob) -> None:
        if job.bucket_id != self._bucket_id:
            raise InternalInvariantError("a classification job is written only through its own profile's repository")

    @override
    def create(self, job: ClassificationJob) -> None:
        """Store a new job at revision 1; an existing job of this identity is a conflict."""
        self._require_own_bucket(job)
        if job.revision != 1:
            raise ClassificationJobError("a new job starts at revision 1")

        def save() -> None:
            self.secure_object_repository.save_many(
                (self.to_secure_object_write(job, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID),),
            )

        _translate_storage_failure("classification_job_create", save)

    @override
    def get(self, job_id: str) -> ClassificationJob:
        """Return this profile's job ``job_id``."""
        job, _revision_id = _translate_storage_failure("classification_job_get", lambda: self._load_revisioned(job_id))
        if job is None:
            raise ClassificationJobNotFoundError
        return job

    @override
    def list_jobs(self) -> tuple[ClassificationJob, ...]:
        """Return every job of this profile, oldest first and then by identity."""

        def scan() -> tuple[ClassificationJob, ...]:
            jobs = tuple(self.iter_records())
            if any(job.bucket_id != self._bucket_id for job in jobs):
                raise SecureObjectRowIdentityError(self.namespace, expected_identifier=self._bucket_id)
            return tuple(sorted(jobs, key=lambda job: (job.created_at, job.job_id)))

        return _translate_storage_failure("classification_job_list", scan)

    @override
    def update(self, job: ClassificationJob) -> None:
        """Store ``job`` only over the stored revision it follows."""
        self._require_own_bucket(job)

        def save() -> None:
            stored, revision_id = self._load_revisioned(job.job_id)
            if stored is None:
                raise ClassificationJobNotFoundError
            if stored.revision != job.revision - 1:
                raise ClassificationJobRevisionConflictError
            job.require_follows(stored)
            self.secure_object_repository.save_many(
                (self.to_secure_object_write(job, expected_revision_id=revision_id),),
            )

        _translate_storage_failure("classification_job_update", save)

    def _load_revisioned(self, job_id: str) -> tuple[ClassificationJob | None, str]:
        # An identity no job can have names no job; it never reaches the store as a key.
        if re.fullmatch(HEX_PATTERN_64, job_id) is None:
            return None, ABSENT_SECURE_OBJECT_REVISION_ID
        identifier = classification_job_object_key(bucket_id=self._bucket_id, job_id=job_id)
        stored = self.secure_object_repository.load(
            self.namespace,
            identifier,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        )
        if stored is None:
            return None, ABSENT_SECURE_OBJECT_REVISION_ID
        payload = self._validate_envelope(stored.payload, subject=f"{self.namespace} revisioned row").payload
        if self.extract_identifier(payload) != identifier:
            raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
        return payload, stored.revision_id
