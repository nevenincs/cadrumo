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

A consent a person grants names the lane they saw: its provider, transport and
model. A grant for a lane the agent no longer reads with is refused, never
moved to another lane. Applying a job's proposals names each accepted movement
with the movement revision its proposal was made against, so a movement that
changed since is refused for that movement alone.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
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
    "LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_PAGE_DEFAULT",
    "LEDGER_CLASSIFY_JOB_PAGE_MAX",
    "LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID",
    "LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID",
    "LedgerClassifyJobAcceptedProposal",
    "LedgerClassifyJobApplyItemResult",
    "LedgerClassifyJobApplyRefusal",
    "LedgerClassifyJobApplyRequest",
    "LedgerClassifyJobApplyResult",
    "LedgerClassifyJobAuthoriseRequest",
    "LedgerClassifyJobCancelRequest",
    "LedgerClassifyJobChangeResult",
    "LedgerClassifyJobConsentGrant",
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
    "LedgerClassifyJobRevokeConsentRequest",
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
LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID: Final = "ledger.classify.job.authorise"
LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID: Final = "ledger.classify.job.revoke-consent"
LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID: Final = "ledger.classify.job.apply"
LEDGER_CLASSIFY_JOB_PAGE_DEFAULT: Final = 20
LEDGER_CLASSIFY_JOB_PAGE_MAX: Final = 50
"""The most jobs one list read returns, newest first."""

_Token = Annotated[str, Field(min_length=1, max_length=256)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=64)]
class LedgerClassifyJobConsentGrant(BaseModel):
    """A person's consent to read a job's movements off this computer, for the lane they saw.

    ``scope`` is how long it lasts: this job only, the agent session, or until
    the person revokes it. The lane names what the person consented to; it
    must be the lane the agent reads with when the grant is recorded.
    ``connection`` is the lane's transport.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    scope: ClassificationConsentScope
    provider_id: _Token
    # The lane's transport, under a name a journalled request may carry.
    connection: _Token
    model: _Token


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
    consent: LedgerClassifyJobConsentGrant | None = None
    """The person's consent for a lane that reads off this computer; a lane that does not refuses one."""

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


class LedgerClassifyJobAuthoriseRequest(CredentialFreeOperationRequest):
    """Grant a job's off-host reads at the revision the person saw.

    The movements that failed for want of a usable consent, or because the
    agent now reads with another lane, are asked again under the new grant.
    """

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]
    consent: LedgerClassifyJobConsentGrant


class LedgerClassifyJobRevokeConsentRequest(CredentialFreeOperationRequest):
    """Withdraw the grant a job runs under, at the revision the person saw.

    A grant for the agent session or a remembered one covers other jobs too;
    revoking it withdraws it for every read from now on.
    """

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]


class LedgerClassifyJobAcceptedProposal(BaseModel):
    """One movement whose proposal the person accepted, as the revision the proposal was made against.

    ``business_pct`` is the person's own business share, in canonical decimal
    text within 0..1, for a mixed classification; a model proposes no share.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_id: TransactionId
    movement_revision_id: _Token
    business_pct: _DecimalText | None = None

    @field_validator("business_pct")
    @classmethod
    def _canonical_share(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = try_parse_canonical_decimal(value, signed=False)
            if parsed is None or display_decimal(parsed) != value or not Decimal("0") <= parsed <= Decimal("1"):
                raise ValueError("business percentage must use canonical decimal text within 0..1")
        return value


class LedgerClassifyJobApplyRequest(BaseModel):
    """Apply the proposals the person accepted, at the job revision the person saw.

    Only the named movements are applied; every other proposal stays a
    proposal. Nothing is applied that the person did not name.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    job_id: Hex64Str
    expected_revision: Annotated[int, Field(ge=1)]
    accepted: Annotated[tuple[LedgerClassifyJobAcceptedProposal, ...], Field(min_length=1, max_length=10_000)]

    @model_validator(mode="after")
    def _each_movement_once(self) -> LedgerClassifyJobApplyRequest:
        movements = [proposal.movement_id for proposal in self.accepted]
        if len(set(movements)) != len(movements):
            raise ValueError("an apply names each movement once")
        return self


class LedgerClassifyJobApplyRefusal(StrEnum):
    """Why one accepted proposal was not applied, in a closed vocabulary the window renders."""

    STALE = "stale"
    """The movement changed after the proposal was made; the person reads it again."""
    NOT_PROPOSED = "not_proposed"
    """The job holds no current proposal for the movement, or the accepted revision is not the proposal's."""
    NOT_IN_JOB = "not_in_job"
    MOVEMENT_NOT_FOUND = "movement_not_found"
    BUSINESS_PCT_REQUIRED = "business_pct_required"
    """A mixed classification needs the person's business share."""
    BUSINESS_PCT_NOT_APPLICABLE = "business_pct_not_applicable"
    """A business share applies only to a mixed classification."""
    CATEGORY_UNAVAILABLE = "category_unavailable"
    """The proposed category is not in the registry the ledger now reads."""
    REJECTED = "rejected"
    """The ledger refused the classification for this movement as it stands now."""


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
    applied: Annotated[int, Field(ge=0)]

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
    outcome: Literal["enqueued", "cancelled", "cancelling", "retried", "dismissed", "authorised", "consent_revoked"]
    job: LedgerClassifyJobProjection


class LedgerClassifyJobApplyItemResult(BaseModel):
    """What became of one accepted proposal: applied, or refused with its typed cause."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_id: TransactionId
    outcome: Literal["applied", "refused"]
    refusal: LedgerClassifyJobApplyRefusal | None

    @model_validator(mode="after")
    def _refusal_matches_outcome(self) -> LedgerClassifyJobApplyItemResult:
        if (self.outcome == "refused") != (self.refusal is not None):
            raise ValueError("only a refused proposal names its cause")
        return self


class LedgerClassifyJobApplyResult(BaseModel):
    """The job as stored after the apply, and what became of each accepted proposal, in request order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    job: LedgerClassifyJobProjection
    items: tuple[LedgerClassifyJobApplyItemResult, ...]


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
