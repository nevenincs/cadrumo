"""Typed refusals of the ledger classification job operations.

Each refusal names its cause and nothing the job or the profile's movements
hold: a refused enqueue says how many named movements this profile does not
hold, never which, and a refused change says the job's status, never its lane
or its proposals. The persistence port keeps its own errors; an operation
translates them into these, so a frontend in another process reads one
registered refusal per cause.
"""

from __future__ import annotations

from typing import Final

from ...core.errors.hierarchy import CadrumoError

__all__ = [
    "CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY",
    "ClassificationJobConsentNotNeededError",
    "ClassificationJobEmptyScopeError",
    "ClassificationJobLaneChangedError",
    "ClassificationJobMovementUnknownError",
    "ClassificationJobStaleRevisionError",
    "ClassificationJobStateRefusedError",
    "ClassificationJobUnknownError",
]

CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY: Final = (
    "errors.refused.refused_ledger_classification_job_nothing_to_retry"
)
"""The state refusal's sentence when the job holds no failed or unknown movement to ask again."""


class ClassificationJobUnknownError(CadrumoError):
    """This profile holds no classification job with the requested identity."""

    def __init__(self) -> None:
        """Name nothing of the identity asked for."""
        super().__init__(context={"cause": "unknown_job"})


class ClassificationJobStaleRevisionError(CadrumoError):
    """The job moved since the revision the request was prepared against.

    The person reads the job again and decides on what it now holds; the same
    request sent again meets the same newer revision.
    """

    def __init__(self, *, expected_revision: int, stored_revision: int | None) -> None:
        """Carry both revisions, which are opaque counters and name nothing private."""
        context: dict[str, object] = {"cause": "revision_conflict", "expected_revision": expected_revision}
        if stored_revision is not None:
            context["stored_revision"] = stored_revision
        super().__init__(context=context)


class ClassificationJobStateRefusedError(CadrumoError):
    """The job's status does not allow the asked change, or the job holds nothing it applies to."""

    def __init__(self, *, action: str, job_status: str, translated_message: str | None = None) -> None:
        """Carry the asked action and the job's status, both closed vocabularies."""
        super().__init__(
            context={"cause": "job_state", "action": action, "job_status": job_status},
            translated_message=translated_message,
        )


class ClassificationJobEmptyScopeError(CadrumoError):
    """The asked scope names no movement to classify."""

    def __init__(self, *, scope: str) -> None:
        """Carry the scope kind the request named."""
        super().__init__(context={"cause": "empty_scope", "scope": scope})


class ClassificationJobMovementUnknownError(CadrumoError):
    """The request names movements this profile does not hold.

    A movement of another profile is not held by this one, so it is refused the
    same way as an identity no profile holds.
    """

    def __init__(self, *, unknown_count: int) -> None:
        """Carry how many named movements are unknown, never which."""
        super().__init__(context={"cause": "unknown_movement", "unknown_count": unknown_count})


class ClassificationJobLaneChangedError(CadrumoError):
    """The agent reads with another lane than the one the job, or the person's grant, names.

    Nothing is read on the other lane. The person enqueues the movements again
    on the lane the agent reads with, or grants the job's reads for that lane.
    The lane the agent now reads with is named so a window can show what a new
    grant would cover; a lane names no taxpayer fact.
    """

    def __init__(self, *, provider_id: str, transport: str, model: str, reads_off_host: bool) -> None:
        """Carry the lane the agent now reads with."""
        super().__init__(
            context={
                "cause": "lane_changed",
                "provider_id": provider_id,
                "transport": transport,
                "model": model,
                "reads_off_host": reads_off_host,
            }
        )


class ClassificationJobConsentNotNeededError(CadrumoError):
    """A consent was offered for a lane that reads on this computer, where none is needed or recorded."""

    def __init__(self) -> None:
        """Name the cause only."""
        super().__init__(context={"cause": "consent_not_needed"})
