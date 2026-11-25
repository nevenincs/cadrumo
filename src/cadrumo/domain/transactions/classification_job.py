"""Domain record for a ledger classification job.

A job asks a model to classify one movement, a selection of movements or the
movements of a period. It is a backend record: it survives a restart, and the
window reads it rather than holding it.

The record carries identifiers and typed results only. It never holds the text
a model read, a document's bytes or the model's free-text reason, so nothing
private beyond the proposal's typed fields is stored with it.

Each item's result is a proposal bound to the movement revision it was made
against. The job never applies it; the person accepts, edits or rejects it
through the ledger review path, and an accepted proposal the ledger took is
marked applied. A movement that changed after its proposal makes the item
stale.

An off-host job runs under a person-granted consent. The person may grant a
new one, which may name the lane the agent now reads with; that is the only
way a job's lane or consent changes, and never without a consent.

A run interrupted mid-item leaves that item ``UNKNOWN``, never done, until it is
reconciled. Every change to the record is a successor at the next revision, and
:meth:`ClassificationJob.require_follows` checks each item and the job status
against their transition tables, so a writer cannot skip a state.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import UtcInstant
from ...core.unit_proportion import UnitProportion
from .enums import BusinessClassification
from .errors import ClassificationJobError

__all__ = [
    "CLASSIFICATION_ITEM_TRANSITIONS",
    "CLASSIFICATION_JOB_STATUS_TRANSITIONS",
    "ClassificationConsentScope",
    "ClassificationItemFailureCause",
    "ClassificationItemState",
    "ClassificationJob",
    "ClassificationJobConsent",
    "ClassificationJobId",
    "ClassificationJobItem",
    "ClassificationJobLane",
    "ClassificationJobScope",
    "ClassificationJobScopeKind",
    "ClassificationJobStatus",
    "ClassificationProposal",
    "new_classification_job_id",
]

type ClassificationJobId = Hex64Str
"""Random hex-64 identity of one classification job."""

_OpaqueToken = Annotated[str, StringConstraints(min_length=1, max_length=256)]
"""A token whose vocabulary another owner serves: a lane, a model, an effort, a registry token."""

_RevisionId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
"""An opaque storage revision of one ledger movement row."""


def new_classification_job_id() -> str:
    """Return a fresh random job identity."""
    return secrets.token_hex(32)


class ClassificationJobScopeKind(StrEnum):
    """What the person asked to classify."""

    SINGLE = "single"
    SELECTION = "selection"
    PERIOD = "period"


class ClassificationJobScope(BaseModel):
    """The scope a job was enqueued for.

    The movements themselves are the job's items; the scope records how they
    were chosen. A period scope keeps its inclusive bounds so the person sees
    which period the movements were resolved from.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: ClassificationJobScopeKind
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _period_bounds_match_kind(self) -> Self:
        if self.kind is ClassificationJobScopeKind.PERIOD:
            if self.period_start is None or self.period_end is None:
                raise ClassificationJobError("a period scope needs both bounds")
            if self.period_start > self.period_end:
                raise ClassificationJobError("a period scope cannot end before it starts")
        elif self.period_start is not None or self.period_end is not None:
            raise ClassificationJobError("only a period scope carries period bounds")
        return self


class ClassificationJobLane(BaseModel):
    """The lane, model and effort a job is bound to, as the agent's catalogue served them.

    ``reads_off_host`` is the lane's catalogue declaration; it decides whether
    the job needs a person-granted consent before it runs.
    """

    model_config = STRICT_FROZEN_CONFIG

    provider_id: _OpaqueToken
    transport: _OpaqueToken
    model: _OpaqueToken
    effort: _OpaqueToken | None = None
    reads_off_host: bool


class ClassificationConsentScope(StrEnum):
    """How long a person's off-host consent lasts."""

    ONCE = "once"
    AGENT_SESSION = "agent_session"
    REMEMBERED = "remembered"


class ClassificationJobConsent(BaseModel):
    """The person-granted consent an off-host job runs under.

    ``consent_reference`` names the grant held by its owner; the job holds the
    reference, not the grant, so a revocation is seen where the grant lives.
    """

    model_config = STRICT_FROZEN_CONFIG

    scope: ClassificationConsentScope
    consent_reference: _OpaqueToken
    granted_at: UtcInstant


class ClassificationItemState(StrEnum):
    """Where one movement of a job stands."""

    PENDING = "pending"
    RUNNING = "running"
    PROPOSED = "proposed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    """A run was interrupted while this item was in flight; its outcome is not known."""
    CANCELLED = "cancelled"
    STALE = "stale"
    """The movement changed after the proposal was made."""
    APPLIED = "applied"
    """The person accepted the proposal and the ledger took it."""


class ClassificationItemFailureCause(StrEnum):
    """Why one item failed, in a closed vocabulary the window renders."""

    MODEL_UNAVAILABLE = "model_unavailable"
    CONSENT_REQUIRED = "consent_required"
    CONSENT_REVOKED = "consent_revoked"
    CONSENT_EXPIRED = "consent_expired"
    """The consent covered the agent session it was granted in, and that session ended."""
    LANE_CHANGED = "lane_changed"
    """The agent now reads with another lane than the one the job is bound to."""
    LANE_REFUSED = "lane_refused"
    INVALID_RESPONSE = "invalid_response"
    TIMED_OUT = "timed_out"
    MOVEMENT_NOT_FOUND = "movement_not_found"


CLASSIFICATION_ITEM_TRANSITIONS: Final[Mapping[ClassificationItemState, frozenset[ClassificationItemState]]] = (
    MappingProxyType(
        {
            ClassificationItemState.PENDING: frozenset(
                {ClassificationItemState.RUNNING, ClassificationItemState.CANCELLED}
            ),
            ClassificationItemState.RUNNING: frozenset(
                {
                    ClassificationItemState.PROPOSED,
                    ClassificationItemState.FAILED,
                    ClassificationItemState.UNKNOWN,
                    ClassificationItemState.CANCELLED,
                }
            ),
            ClassificationItemState.PROPOSED: frozenset(
                {ClassificationItemState.STALE, ClassificationItemState.APPLIED}
            ),
            ClassificationItemState.FAILED: frozenset({ClassificationItemState.PENDING}),
            ClassificationItemState.UNKNOWN: frozenset(
                {ClassificationItemState.PENDING, ClassificationItemState.FAILED, ClassificationItemState.CANCELLED}
            ),
            ClassificationItemState.STALE: frozenset({ClassificationItemState.PENDING}),
            ClassificationItemState.CANCELLED: frozenset[ClassificationItemState](),
            ClassificationItemState.APPLIED: frozenset[ClassificationItemState](),
        }
    )
)
"""Which item state may follow which. A cancelled or applied item is final."""


class ClassificationProposal(BaseModel):
    """A model's typed proposal for one movement, bound to the movement revision it read.

    Category tokens are kept as the registry tokens the model chose and are
    resolved again when the person applies the proposal, so a stored job stays
    readable after a registry generation retires a token. ``provenance`` is the
    reader's own stamp, which an applied proposal records as who classified.
    """

    model_config = STRICT_FROZEN_CONFIG

    movement_revision_id: _RevisionId
    classification: BusinessClassification
    confidence: UnitProportion
    category: _OpaqueToken | None = None
    iva_category: _OpaqueToken | None = None
    business_pct: UnitProportion | None = None
    multiple_components: bool | None = None
    provenance: _OpaqueToken
    proposed_at: UtcInstant


_STATES_WITH_PROPOSAL: Final = frozenset(
    {ClassificationItemState.PROPOSED, ClassificationItemState.STALE, ClassificationItemState.APPLIED}
)
"""Item states that hold the proposal they were made or accepted with."""

_KEEPS_PROPOSAL: Final = frozenset({ClassificationItemState.STALE, ClassificationItemState.APPLIED})
"""Moves that keep the item's own proposal: one that went stale, or one the ledger took."""

_STATES_BEFORE_ANY_RUN: Final = frozenset({ClassificationItemState.PENDING, ClassificationItemState.CANCELLED})
"""Item states reachable without a run: a pending item can be cancelled before it starts."""


class ClassificationJobItem(BaseModel):
    """One movement of a job, its state and its result."""

    model_config = STRICT_FROZEN_CONFIG

    movement_id: TransactionId
    state: ClassificationItemState
    attempt: int = Field(ge=0)
    """How many runs have started on this item."""
    proposal: ClassificationProposal | None = None
    failure_cause: ClassificationItemFailureCause | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _result_matches_state(self) -> Self:
        carries_proposal = self.state in _STATES_WITH_PROPOSAL
        if carries_proposal != (self.proposal is not None):
            raise ClassificationJobError(
                f"a {self.state.value} item {'needs' if carries_proposal else 'has no'} proposal"
            )
        failed = self.state is ClassificationItemState.FAILED
        if failed != (self.failure_cause is not None):
            raise ClassificationJobError(f"a {self.state.value} item {'needs' if failed else 'has no'} failure cause")
        if self.state not in _STATES_BEFORE_ANY_RUN and self.attempt == 0:
            raise ClassificationJobError(f"a {self.state.value} item has been run at least once")
        return self

    @classmethod
    def pending(cls, movement_id: str) -> ClassificationJobItem:
        """Return a fresh item that has not been run."""
        return cls(movement_id=movement_id, state=ClassificationItemState.PENDING, attempt=0)

    def transitioned(
        self,
        state: ClassificationItemState,
        *,
        proposal: ClassificationProposal | None = None,
        failure_cause: ClassificationItemFailureCause | None = None,
    ) -> ClassificationJobItem:
        """Return this item moved to ``state``.

        A move to ``RUNNING`` starts a new attempt. A move to ``STALE`` keeps the
        proposal that went stale, so the person still sees what was proposed;
        a move to ``APPLIED`` keeps the proposal the ledger took.

        Raises:
            ClassificationJobError: The transition table forbids the move.
        """
        if state not in CLASSIFICATION_ITEM_TRANSITIONS[self.state]:
            raise ClassificationJobError(f"an item cannot move from {self.state.value} to {state.value}")
        kept_proposal = self.proposal if state in _KEEPS_PROPOSAL else proposal
        if state in _KEEPS_PROPOSAL and proposal is not None:
            raise ClassificationJobError(f"a {state.value} item keeps its own proposal")
        return ClassificationJobItem(
            movement_id=self.movement_id,
            state=state,
            attempt=self.attempt + 1 if state is ClassificationItemState.RUNNING else self.attempt,
            proposal=kept_proposal,
            failure_cause=failure_cause,
        )

    def proposal_is_current(self, movement_revision_id: str | None) -> bool:
        """Return whether this item's proposal was made against ``movement_revision_id``.

        ``None`` means the movement no longer exists, so no proposal is current.
        """
        return (
            self.proposal is not None
            and movement_revision_id is not None
            and self.proposal.movement_revision_id == movement_revision_id
        )


class ClassificationJobStatus(StrEnum):
    """Where a job stands as a whole."""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    """Cancel was asked for; an in-flight model run settles before its item is cancelled."""
    INTERRUPTED = "interrupted"
    """A run stopped mid-job; its in-flight items are ``UNKNOWN`` until reconciled."""
    SETTLED = "settled"
    CANCELLED = "cancelled"
    DISMISSED = "dismissed"


CLASSIFICATION_JOB_STATUS_TRANSITIONS: Final[Mapping[ClassificationJobStatus, frozenset[ClassificationJobStatus]]] = (
    MappingProxyType(
        {
            ClassificationJobStatus.QUEUED: frozenset(
                {ClassificationJobStatus.RUNNING, ClassificationJobStatus.CANCELLED}
            ),
            ClassificationJobStatus.RUNNING: frozenset(
                {
                    ClassificationJobStatus.QUEUED,
                    ClassificationJobStatus.SETTLED,
                    ClassificationJobStatus.CANCELLING,
                    ClassificationJobStatus.INTERRUPTED,
                }
            ),
            ClassificationJobStatus.CANCELLING: frozenset(
                {ClassificationJobStatus.CANCELLED, ClassificationJobStatus.INTERRUPTED}
            ),
            ClassificationJobStatus.INTERRUPTED: frozenset(
                {
                    ClassificationJobStatus.QUEUED,
                    ClassificationJobStatus.SETTLED,
                    ClassificationJobStatus.CANCELLED,
                }
            ),
            ClassificationJobStatus.SETTLED: frozenset(
                {ClassificationJobStatus.QUEUED, ClassificationJobStatus.DISMISSED}
            ),
            ClassificationJobStatus.CANCELLED: frozenset(
                {ClassificationJobStatus.QUEUED, ClassificationJobStatus.DISMISSED}
            ),
            ClassificationJobStatus.DISMISSED: frozenset[ClassificationJobStatus](),
        }
    )
)
"""Which job status may follow which. A dismissed job is final.

A run stopped between items returns its job to ``QUEUED``; one stopped with an
item in flight leaves the job ``INTERRUPTED`` with that item ``UNKNOWN``.
"""

_STATES_FORBIDDEN_BY_STATUS: Final[Mapping[ClassificationJobStatus, frozenset[ClassificationItemState]]] = (
    MappingProxyType(
        {
            ClassificationJobStatus.QUEUED: frozenset({ClassificationItemState.RUNNING}),
            ClassificationJobStatus.RUNNING: frozenset[ClassificationItemState](),
            ClassificationJobStatus.CANCELLING: frozenset[ClassificationItemState](),
            ClassificationJobStatus.INTERRUPTED: frozenset({ClassificationItemState.RUNNING}),
            ClassificationJobStatus.SETTLED: frozenset(
                {ClassificationItemState.PENDING, ClassificationItemState.RUNNING, ClassificationItemState.UNKNOWN}
            ),
            ClassificationJobStatus.CANCELLED: frozenset(
                {ClassificationItemState.PENDING, ClassificationItemState.RUNNING, ClassificationItemState.UNKNOWN}
            ),
            ClassificationJobStatus.DISMISSED: frozenset(
                {ClassificationItemState.PENDING, ClassificationItemState.RUNNING, ClassificationItemState.UNKNOWN}
            ),
        }
    )
)
"""Item states a job status cannot hold.

Only a running or cancelling job has an item in flight, and a finished job holds
no unknown item: an interrupted item is reconciled before its job settles.
"""


class ClassificationJob(BaseModel):
    """One persisted ledger classification job of one profile.

    ``revision`` starts at 1 and rises by exactly one with every stored change;
    it is the opaque revision the window compares before re-reading.
    """

    model_config = STRICT_FROZEN_CONFIG

    job_id: ClassificationJobId
    bucket_id: BucketId
    scope: ClassificationJobScope
    lane: ClassificationJobLane
    consent: ClassificationJobConsent | None
    items: tuple[ClassificationJobItem, ...] = Field(min_length=1)
    status: ClassificationJobStatus
    created_at: UtcInstant
    updated_at: UtcInstant
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _record_is_consistent(self) -> Self:
        movement_ids = self.movement_ids
        if len(set(movement_ids)) != len(movement_ids):
            raise ClassificationJobError("a job names each movement once")
        if self.scope.kind is ClassificationJobScopeKind.SINGLE and len(movement_ids) != 1:
            raise ClassificationJobError("a single-movement job holds exactly one item")
        if self.lane.reads_off_host != (self.consent is not None):
            raise ClassificationJobError(
                "an off-host lane needs a consent" if self.lane.reads_off_host else "an on-host lane takes no consent"
            )
        if self.updated_at < self.created_at:
            raise ClassificationJobError("a job cannot be updated before it was created")
        forbidden = _STATES_FORBIDDEN_BY_STATUS[self.status]
        if any(item.state in forbidden for item in self.items):
            raise ClassificationJobError(f"a {self.status.value} job cannot hold an item in a forbidden state")
        if self.status is ClassificationJobStatus.INTERRUPTED and not any(
            item.state is ClassificationItemState.UNKNOWN for item in self.items
        ):
            raise ClassificationJobError("an interrupted job holds at least one unknown item")
        return self

    @property
    def movement_ids(self) -> tuple[str, ...]:
        """Return the job's movements in item order."""
        return tuple(item.movement_id for item in self.items)

    @classmethod
    def enqueue(
        cls,
        *,
        bucket_id: str,
        scope: ClassificationJobScope,
        movement_ids: Sequence[str],
        lane: ClassificationJobLane,
        consent: ClassificationJobConsent | None,
        at: UtcInstant,
        job_id: str | None = None,
    ) -> ClassificationJob:
        """Return a new queued job at revision 1 with every movement pending."""
        return cls(
            job_id=job_id or new_classification_job_id(),
            bucket_id=bucket_id,
            scope=scope,
            lane=lane,
            consent=consent,
            items=tuple(ClassificationJobItem.pending(movement_id) for movement_id in movement_ids),
            status=ClassificationJobStatus.QUEUED,
            created_at=at,
            updated_at=at,
            revision=1,
        )

    def successor(
        self,
        *,
        at: UtcInstant,
        status: ClassificationJobStatus | None = None,
        items: Sequence[ClassificationJobItem] | None = None,
    ) -> ClassificationJob:
        """Return the next revision of this job with a new status, new items or both.

        Raises:
            ClassificationJobError: A status or item move is not allowed, or an
                item names another movement.
        """
        following = ClassificationJob(
            job_id=self.job_id,
            bucket_id=self.bucket_id,
            scope=self.scope,
            lane=self.lane,
            consent=self.consent,
            items=self.items if items is None else tuple(items),
            status=self.status if status is None else status,
            created_at=self.created_at,
            updated_at=at,
            revision=self.revision + 1,
        )
        following.require_follows(self)
        return following

    def authorised(
        self,
        *,
        at: UtcInstant,
        lane: ClassificationJobLane,
        consent: ClassificationJobConsent,
        status: ClassificationJobStatus,
        items: Sequence[ClassificationJobItem],
    ) -> ClassificationJob:
        """Return the next revision of this job under a consent the person has just granted.

        The new consent may name the lane the agent now reads with, which then
        becomes the job's lane. Nothing else of the job's identity changes.

        Raises:
            ClassificationJobError: The consent is the one the job already holds,
                or a status or item move is not allowed.
        """
        following = ClassificationJob(
            job_id=self.job_id,
            bucket_id=self.bucket_id,
            scope=self.scope,
            lane=lane,
            consent=consent,
            items=tuple(items),
            status=status,
            created_at=self.created_at,
            updated_at=at,
            revision=self.revision + 1,
        )
        following.require_follows(self)
        return following

    def require_follows(self, previous: ClassificationJob) -> None:
        """Refuse this record unless it is a valid next revision of ``previous``.

        The identity, scope, creation time and movements stay fixed. The lane
        and consent change only together with a new consent the person
        granted. The revision rises by one. A changed status follows the status
        table; a changed item is exactly the transition of its predecessor.

        Raises:
            ClassificationJobError: The record does not follow ``previous``.
        """
        if (self.job_id, self.bucket_id, self.scope, self.created_at) != (
            previous.job_id,
            previous.bucket_id,
            previous.scope,
            previous.created_at,
        ):
            raise ClassificationJobError("a job's identity and scope never change")
        if (self.lane, self.consent) != (previous.lane, previous.consent) and (
            self.consent is None
            or (previous.consent is not None and self.consent.consent_reference == previous.consent.consent_reference)
        ):
            raise ClassificationJobError("a job's lane and consent never change without a new consent")
        if self.revision != previous.revision + 1:
            raise ClassificationJobError("a job's revision rises by exactly one")
        if self.updated_at < previous.updated_at:
            raise ClassificationJobError("a job's update time never goes back")
        if self.movement_ids != previous.movement_ids:
            raise ClassificationJobError("a job's movements never change")
        if (
            self.status is not previous.status
            and self.status not in CLASSIFICATION_JOB_STATUS_TRANSITIONS[previous.status]
        ):
            raise ClassificationJobError(f"a job cannot move from {previous.status.value} to {self.status.value}")
        for before, after in zip(previous.items, self.items, strict=True):
            if after == before:
                continue
            expected = before.transitioned(
                after.state,
                proposal=None if after.state in _KEEPS_PROPOSAL else after.proposal,
                failure_cause=after.failure_cause,
            )
            if after != expected:
                raise ClassificationJobError("an item changed without a valid transition")
