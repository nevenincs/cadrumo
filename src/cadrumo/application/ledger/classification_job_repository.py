"""Application-owned persistence contract for ledger classification jobs.

The application owns the object key, the typed failures and the operations the
job lifecycle needs. Encrypting jobs and selecting a profile's store belong to
the persistence adapter, bound by an outer composition root.

A row is stored under ``classification-job:{bucket_id}:{job_id}``. A repository
is bound to one profile bucket, so a job of another profile is never found
through it. Every write after the first is revision guarded: an update names
the revision it follows, and a job that moved since it was read is refused
rather than overwritten.

Nothing here logs a movement, a proposal or the job's lane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol

from ...core.errors.hierarchy import CadrumoError

if TYPE_CHECKING:
    from ...domain.transactions.classification_job import ClassificationJob

__all__ = [
    "CLASSIFICATION_JOB_KEY_PREFIX",
    "ClassificationJobNotFoundError",
    "ClassificationJobPersistenceError",
    "ClassificationJobRepository",
    "ClassificationJobRevisionConflictError",
    "classification_job_object_key",
]

CLASSIFICATION_JOB_KEY_PREFIX: Final = "classification-job:"
"""The key prefix every job row of the namespace carries."""


def classification_job_object_key(*, bucket_id: str, job_id: str) -> str:
    """Return the object key ``classification-job:{bucket_id}:{job_id}``."""
    return f"{CLASSIFICATION_JOB_KEY_PREFIX}{bucket_id}:{job_id}"


class ClassificationJobPersistenceError(CadrumoError):
    """Translated failure from the classification job persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details or record content."""
        self.operation = operation
        super().__init__(f"classification job persistence operation failed: {operation}")


class ClassificationJobRevisionConflictError(CadrumoError):
    """The stored job moved since the revision the write was prepared against, or already exists."""

    def __init__(self) -> None:
        """Say only that the revision is stale; the job is named by nothing identifying."""
        super().__init__("the classification job changed since it was read")


class ClassificationJobNotFoundError(CadrumoError):
    """No job with the requested identity exists in this profile."""

    def __init__(self) -> None:
        """Name nothing of the identity asked for."""
        super().__init__("no classification job matches the requested identity in this profile")


class ClassificationJobRepository(Protocol):
    """The read and guarded-write capability over one profile's classification jobs."""

    def create(self, job: ClassificationJob) -> None:
        """Store a new job at revision 1.

        Raises:
            ClassificationJobRevisionConflictError: A job with this identity already exists.
            ClassificationJobPersistenceError: Storage failed.
        """
        ...

    def get(self, job_id: str) -> ClassificationJob:
        """Return the stored job.

        Raises:
            ClassificationJobNotFoundError: This profile holds no such job.
            ClassificationJobPersistenceError: Storage failed or the row is not this job's.
        """
        ...

    def list_jobs(self) -> tuple[ClassificationJob, ...]:
        """Return every job of the profile, oldest first.

        Raises:
            ClassificationJobPersistenceError: Storage could not be read. A caller
                never reads that as an empty queue.
        """
        ...

    def update(self, job: ClassificationJob) -> None:
        """Store ``job`` only if the stored job is still at ``job.revision - 1`` and ``job`` follows it.

        Raises:
            ClassificationJobNotFoundError: This profile holds no such job.
            ClassificationJobRevisionConflictError: The stored job moved.
            ClassificationJobError: ``job`` is not a valid successor of the stored job.
            ClassificationJobPersistenceError: Storage failed.
        """
        ...
