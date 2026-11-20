"""Public request and result contracts of the ledger classification job operations.

A job is the backend's record of a person's request to have a model classify
one movement, a selection of movements or the movements of a period. These
contracts carry what a window renders and gates on: the job's identity,
status and revision, each movement's state, a failed movement's typed cause and
a proposed movement's typed proposal. They never carry a movement's text, the
model's input or the model's free-text reason, and a consent is shown by its
scope only, never by the reference its owner holds it under.

The job's ``revision`` rises with every stored change, and the list carries one
``queue_revision`` over every job of the profile, so a window re-reads only when
what it holds has moved.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobItem,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
    ClassificationProposal,
)
from ...domain.transactions.enums import BusinessClassification
from ..operations.models import CredentialFreeOperationRequest
from .actions_common import display_decimal

__all__ = [
    "LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_CHANGE_DEFINITION_IDS",
    "LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_PAGE_DEFAULT",
    "LEDGER_CLASSIFY_JOB_PAGE_MAX",
    "LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID",
    "LedgerClassifyJobCancelRequest",
    "LedgerClassifyJobChangeResult",
    "LedgerClassifyJobDismissRequest",
    "LedgerClassifyJobEnqueueRequest",
    "LedgerClassifyJobItemProjection",
    "LedgerClassifyJobLaneProjection",
    "LedgerClassifyJobListRequest",
    "LedgerClassifyJobListResult",
    "LedgerClassifyJobProjection",
    "LedgerClassifyJobProposalProjection",
    "LedgerClassifyJobReadRequest",
    "LedgerClassifyJobReadResult",
    "LedgerClassifyJobRetryRequest",
    "LedgerClassifyJobRunRequest",
    "LedgerClassifyJobRunResult",
    "LedgerClassifyJobStateCounts",
    "classification_queue_revision",
]

LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID: Final = "ledger.classify.job.enqueue"
LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID: Final = "ledger.classify.job.read"
LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID: Final = "ledger.classify.job.list"
LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID: Final = "ledger.classify.job.cancel"
LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID: Final = "ledger.classify.job.retry"
LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID: Final = "ledger.classify.job.dismiss"
LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID: Final = "ledger.classify.job.run"
LEDGER_CLASSIFY_JOB_CHANGE_DEFINITION_IDS: Final = frozenset(
    {
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
    }
)

LEDGER_CLASSIFY_JOB_PAGE_DEFAULT: Final = 20
LEDGER_CLASSIFY_JOB_PAGE_MAX: Final = 50
"""The most jobs one list read returns, newest first."""

_Token = Annotated[str, Field(min_length=1, max_length=256)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerClassifyJobEnqueueRequest(BaseModel):
    """Ask for one job over one movement, a selection of movements or the movements of a period.

    Movements are named by their canonical id; a frontend resolves a person's
    handle first. A period names its inclusive bounds and takes every active
    movement whose ledger filing date falls within them. Whether the scope
    names any movement, and whether this profile holds each named one, is the
    operation's typed refusal, not a shape error.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    scope: ClassificationJobScopeKind
    movement_ids: Annotated[tuple[TransactionId, ...], Field(max_length=10_000)] = ()
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def _scope_shape(self) -> LedgerClassifyJobEnqueueRequest:
        if len(set(self.movement_ids)) != len(self.movement_ids):
            raise ValueError("a classification job names each movement once")
        if self.scope is ClassificationJobScopeKind.PERIOD:
            if self.movement_ids:
                raise ValueError("a period scope takes its movements from its bounds")
            if self.period_start is None or self.period_end is None:
                raise ValueError("a period scope needs both bounds")
            if self.period_start > self.period_end:
                raise ValueError("a period scope cannot end before it starts")
            return self
        if self.period_start is not None or self.period_end is not None:
            raise ValueError("only a period scope carries period bounds")
        if self.scope is ClassificationJobScopeKind.SINGLE and len(self.movement_ids) > 1:
            raise ValueError("a single-movement scope names one movement")
        return self


class LedgerClassifyJobReadRequest(CredentialFreeOperationRequest):
    """Read one job of the profile."""

    profile_id: UUID
    job_id: Hex64Str


class LedgerClassifyJobListRequest(CredentialFreeOperationRequest):
    """Read the profile's newest jobs; a dismissed job is left out unless asked for."""

    profile_id: UUID
    limit: Annotated[int, Field(ge=1, le=LEDGER_CLASSIFY_JOB_PAGE_MAX)] = LEDGER_CLASSIFY_JOB_PAGE_DEFAULT
    include_dismissed: bool = False


class LedgerClassifyJobCancelRequest(CredentialFreeOperationRequest):
    """Cancel a job at the revision the person saw.

    Movements not yet asked are cancelled at once. A movement whose model run is
    in flight settles first; the job reads ``cancelling`` until it has.
    """

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]


class LedgerClassifyJobRetryRequest(CredentialFreeOperationRequest):
    """Ask again for every failed movement and every movement whose run was interrupted."""

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]


class LedgerClassifyJobDismissRequest(CredentialFreeOperationRequest):
    """Put away a settled or cancelled job; its proposals are not applied by dismissing it."""

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]


class LedgerClassifyJobRunRequest(CredentialFreeOperationRequest):
    """Work one job's pending movements until none is left, the job is cancelled or the run is stopped.

    A run takes the job as stored, so it names no revision: running a job again
    continues from where the last run left it.
    """

    profile_id: UUID
    job_id: Hex64Str


class LedgerClassifyJobLaneProjection(BaseModel):
    """The lane, model and effort the job is bound to, as the agent served them."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider_id: _Token
    transport: _Token
    model: _Token
    effort: _Token | None
    reads_off_host: bool


class LedgerClassifyJobProposalProjection(BaseModel):
    """A model's typed proposal for one movement, and the movement revision it was made against.

    It is a proposal: nothing is applied until the person accepts it through
    the ledger review.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_revision_id: _Token
    classification: BusinessClassification
    confidence: _DecimalText
    category: _Token | None
    iva_category: _Token | None
    business_pct: _DecimalText | None
    multiple_components: bool | None
    proposed_at: datetime

    @classmethod
    def from_proposal(cls, proposal: ClassificationProposal) -> LedgerClassifyJobProposalProjection:
        """Project the stored proposal, its decimals as canonical text."""
        return cls(
            movement_revision_id=proposal.movement_revision_id,
            classification=proposal.classification,
            confidence=display_decimal(proposal.confidence),
            category=proposal.category,
            iva_category=proposal.iva_category,
            business_pct=None if proposal.business_pct is None else display_decimal(proposal.business_pct),
            multiple_components=proposal.multiple_components,
            proposed_at=proposal.proposed_at,
        )


class LedgerClassifyJobItemProjection(BaseModel):
    """One movement of a job: its state, how many runs started on it, and its result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_id: TransactionId
    state: ClassificationItemState
    attempt: Annotated[int, Field(ge=0)]
    failure_cause: ClassificationItemFailureCause | None
    proposal: LedgerClassifyJobProposalProjection | None

    @classmethod
    def from_item(cls, item: ClassificationJobItem) -> LedgerClassifyJobItemProjection:
        """Project one stored item."""
        return cls(
            movement_id=item.movement_id,
            state=item.state,
            attempt=item.attempt,
            failure_cause=item.failure_cause,
            proposal=None
            if item.proposal is None
            else LedgerClassifyJobProposalProjection.from_proposal(item.proposal),
        )


class LedgerClassifyJobStateCounts(BaseModel):
    """How many of the job's movements are in each state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    pending: Annotated[int, Field(ge=0)]
    running: Annotated[int, Field(ge=0)]
    proposed: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]
    unknown: Annotated[int, Field(ge=0)]
    cancelled: Annotated[int, Field(ge=0)]
    stale: Annotated[int, Field(ge=0)]

    @classmethod
    def of(cls, items: Iterable[ClassificationJobItem]) -> LedgerClassifyJobStateCounts:
        """Count ``items`` by state."""
        counts = Counter(item.state for item in items)
        return cls(**{state.value: counts.get(state, 0) for state in ClassificationItemState})


class LedgerClassifyJobProjection(BaseModel):
    """One job as a window renders it and gates on it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    job_id: Hex64Str
    scope: ClassificationJobScopeKind
    period_start: date | None
    period_end: date | None
    lane: LedgerClassifyJobLaneProjection
    consent_scope: ClassificationConsentScope | None
    status: ClassificationJobStatus
    revision: Annotated[int, Field(ge=1)]
    created_at: datetime
    updated_at: datetime
    counts: LedgerClassifyJobStateCounts
    items: tuple[LedgerClassifyJobItemProjection, ...]

    @classmethod
    def from_job(cls, job: ClassificationJob) -> LedgerClassifyJobProjection:
        """Project one stored job; the consent's reference stays with its owner."""
        return cls(
            job_id=job.job_id,
            scope=job.scope.kind,
            period_start=job.scope.period_start,
            period_end=job.scope.period_end,
            lane=LedgerClassifyJobLaneProjection(
                provider_id=job.lane.provider_id,
                transport=job.lane.transport,
                model=job.lane.model,
                effort=job.lane.effort,
                reads_off_host=job.lane.reads_off_host,
            ),
            consent_scope=None if job.consent is None else job.consent.scope,
            status=job.status,
            revision=job.revision,
            created_at=job.created_at,
            updated_at=job.updated_at,
            counts=LedgerClassifyJobStateCounts.of(job.items),
            items=tuple(LedgerClassifyJobItemProjection.from_item(item) for item in job.items),
        )


class LedgerClassifyJobChangeResult(BaseModel):
    """The job as stored after an enqueue, a cancel, a retry or a dismiss."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["enqueued", "cancelled", "cancelling", "retried", "dismissed"]
    job: LedgerClassifyJobProjection


class LedgerClassifyJobRunResult(BaseModel):
    """The job as stored when its run ended.

    ``settled``: no movement is left to ask. ``interrupted``: an earlier run
    stopped with a movement in flight, and that movement reads ``unknown`` until
    the person asks for it again. ``cancelled``: the person cancelled the job.
    Nothing a run proposes is applied.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["settled", "interrupted", "cancelled"]
    job: LedgerClassifyJobProjection


class LedgerClassifyJobReadResult(BaseModel):
    """One job of the profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    job: LedgerClassifyJobProjection


class LedgerClassifyJobListResult(BaseModel):
    """The profile's newest jobs and the revision of the whole queue.

    ``queue_revision`` changes whenever any job of the profile is stored again,
    added or dismissed, so a window compares it before it re-reads. ``more``
    says the profile holds listed jobs beyond ``limit``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    queue_revision: Hex64Str
    jobs: tuple[LedgerClassifyJobProjection, ...]
    more: bool


def classification_queue_revision(jobs: Iterable[ClassificationJob]) -> str:
    """Return one opaque revision over every job's identity and revision, in identity order."""
    lines = sorted(f"{job.job_id}:{job.revision}" for job in jobs)
    return sha256_hex("\n".join(lines).encode("utf-8"))
