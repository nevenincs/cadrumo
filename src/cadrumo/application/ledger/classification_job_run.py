"""Registered cooperative, resumable run of one ledger classification job.

A run works one stored job. It takes the job's pending movements a batch at a
time, marks the batch running, reads each movement through the same
classification reader the ledger's review asks, and commits the batch's
results in one revision-guarded write. Each result is a proposal bound to the
revision of the movement it read, or a typed failure cause. A run never
applies a proposal and never writes a ledger fact.

The job record is the run's checkpoint. A run that stopped with a movement in
flight left that movement ``running``; the next run reconciles it as
``unknown``, never as done, and the person asks for it again through retry.
Running a job again continues from what is stored. A run stopped between
movements leaves nothing in flight, and the next run queues the job again.

Cancel is cooperative. The person's cancel marks the job ``cancelling``; the
run re-reads the job at every write, lets the movement in flight settle, and
then finishes the cancel. A stop asked of the operation itself is honoured at
the next boundary where nothing is in flight; a movement whose result could
not be committed stays ``running`` and is reconciled as ``unknown``.

Before the first movement and before every batch, the run asks the agent which
lane it reads with. A lane other than the job's is refused as changed: nothing
is read on another lane. On a lane that reads off this computer the job's grant
must still cover it in the consent ledger: recorded, not revoked, for this job,
the agent session open now or remembered, and for this lane and the
classification task kind. Each read then sends under its own consent, bound to
the revision of the movement it sends, and the dispatch is recorded in the
consent ledger before anything leaves.

A refusal that concerns the lane rather than one movement, a changed lane, no
usable consent to read off this computer or no reader at all, fails every
movement still to ask with its typed cause, settles the job and then refuses
the run with the ledger's typed refusal and the step that puts it right. A failure of one movement, a
model refusal, a reply that does not parse or a movement that changed or went
away, is recorded on that movement and the run goes on.

The log names the job, counts and closed cause tokens only; never a
movement's text, a model's input or its reply.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.model_runs import ModelRunRefusalCode, ModelRunTaskKind

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import sha256_hex
from ...core.logging import get_logger
from ...core.model_roles import ModelRole
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.evidence_consent.grant import ConsentGrantStanding
from ...domain.transactions.classification_job import (
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobItem,
    ClassificationJobStatus,
    ClassificationProposal,
)
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.errors import LLMClassifierError
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .classification_job_consent import lane_changed, off_host_consent_refused, reads_with, standing_failure_cause
from .classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
    LedgerClassifyJobProjection,
    LedgerClassifyJobRunRequest,
    LedgerClassifyJobRunResult,
)
from .classification_job_errors import (
    ClassificationJobStaleRevisionError,
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from .classification_job_ports import ClassificationJobReader, ClassificationJobRunPorts
from .classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobRepository,
    ClassificationJobRevisionConflictError,
)
from .evidence_errors import LedgerOffHostConsentRequiredError, PurchaseInvoiceEvidenceReaderError
from .llm_classification import suggest_llm_classification
from .read_access import resolve_ledger_commit_access

__all__ = [
    "MODEL_RUN_REFUSAL_CONTEXT_KEY",
    "ClassificationJobRunExecutor",
    "ClassificationRunBatch",
    "build_ledger_classify_job_run_definition",
    "build_ledger_classify_job_run_registration",
    "classification_failure_cause",
    "movement_revision_id",
    "next_classification_batch",
    "reconciled_job",
    "resolve_ledger_classify_job_run_access",
]

_log = get_logger(__name__)

MODEL_RUN_REFUSAL_CONTEXT_KEY: Final = "model_run_refusal"
"""The context key under which a failed model run names the agent's refusal code.

A reader failure that carries it was refused by the model run; one without it
is a reply the classification parse did not accept.
"""

_RUN_CAPABILITIES: Final = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    # A stop is honoured where no movement is in flight; the job record keeps where the run was.
    cancellation=OperationCancellation.COOPERATIVE,
    deadline=OperationDeadline.ABSENT,
    # Resuming is the job record's: a new run continues from it, so no submission is replayed.
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    # One run per profile at a time: a stored running job with no live run was left by one that stopped.
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)

_FINISHED: Final = frozenset(
    {ClassificationJobStatus.SETTLED, ClassificationJobStatus.CANCELLED, ClassificationJobStatus.DISMISSED}
)
_CANCELLED_ON_FINISH: Final = frozenset(
    {ClassificationItemState.PENDING, ClassificationItemState.RUNNING, ClassificationItemState.UNKNOWN}
)
_WRITE_ATTEMPTS: Final = 3
"""How often one write re-reads the job after a concurrent change, such as a cancel, moved it first."""

_TIMED_OUT_REFUSALS: Final = frozenset({ModelRunRefusalCode.TIMEOUT.value})
_INVALID_OUTPUT_REFUSALS: Final = frozenset({ModelRunRefusalCode.OUTPUT_INVALID.value})

type _RunOutcome = Literal["settled", "interrupted", "cancelled"]


# -- the job's own transitions -----------------------------------------------------------------------------------------


def movement_revision_id(transaction: Transaction) -> str:
    """Return the opaque revision of one movement: the digest of its canonical stored form.

    Any change to the movement changes it, so a proposal bound to it is current
    only while the movement is exactly what the model read.
    """
    return sha256_hex(transaction.model_dump_json().encode("utf-8"))


@dataclass(frozen=True, slots=True)
class ClassificationRunBatch:
    """The movements one batch takes, by item position: marked running together and committed together."""

    positions: tuple[int, ...]


def next_classification_batch(job: ClassificationJob) -> ClassificationRunBatch | None:
    """Return the next batch of pending movements, or ``None`` when none is pending.

    A batch is the first pending movement alone: one model request at a time,
    each result committed as soon as it is known.
    """
    for position, item in enumerate(job.items):
        if item.state is ClassificationItemState.PENDING:
            return ClassificationRunBatch(positions=(position,))
    return None


def _has(job: ClassificationJob, state: ClassificationItemState) -> bool:
    return any(item.state is state for item in job.items)


def _finished_status(items: Sequence[ClassificationJobItem]) -> ClassificationJobStatus:
    """The status of a job with nothing pending or in flight: interrupted while an unknown movement remains."""
    if any(item.state is ClassificationItemState.UNKNOWN for item in items):
        return ClassificationJobStatus.INTERRUPTED
    return ClassificationJobStatus.SETTLED


def _cancel_finished(
    job: ClassificationJob, items: Sequence[ClassificationJobItem], *, at: datetime
) -> ClassificationJob:
    """Finish a cancel: every movement not settled is cancelled and the job with it."""
    return job.successor(
        at=at,
        status=ClassificationJobStatus.CANCELLED,
        items=tuple(
            item.transitioned(ClassificationItemState.CANCELLED) if item.state in _CANCELLED_ON_FINISH else item
            for item in items
        ),
    )


def reconciled_job(job: ClassificationJob, *, at: datetime) -> ClassificationJob | None:
    """Return the stored job as a new run finds it, or ``None`` when it needs no reconciling.

    A job stored ``running`` or ``cancelling`` has no live run: runs of one
    profile do not overlap. A movement left in flight reads ``unknown``. A
    cancelling job finishes its cancel. A running job with nothing in flight
    stopped between movements and is queued again, or finished when nothing is
    left to ask.
    """
    if job.status is ClassificationJobStatus.CANCELLING:
        return _cancel_finished(job, job.items, at=at)
    if job.status is not ClassificationJobStatus.RUNNING:
        return None
    items = tuple(
        item.transitioned(ClassificationItemState.UNKNOWN) if item.state is ClassificationItemState.RUNNING else item
        for item in job.items
    )
    if any(item.state is ClassificationItemState.UNKNOWN for item in items):
        status = ClassificationJobStatus.INTERRUPTED
    elif any(item.state is ClassificationItemState.PENDING for item in items):
        status = ClassificationJobStatus.QUEUED
    else:
        status = ClassificationJobStatus.SETTLED
    return job.successor(at=at, status=status, items=items)


def _started(job: ClassificationJob, batch: ClassificationRunBatch, *, at: datetime) -> tuple[ClassificationJob, ...]:
    """Mark the batch running, queueing an interrupted job first; a cancelling job finishes its cancel instead."""
    if job.status is ClassificationJobStatus.CANCELLING:
        return (_cancel_finished(job, job.items, at=at),)
    steps: list[ClassificationJob] = []
    current = job
    if current.status is ClassificationJobStatus.INTERRUPTED:
        current = current.successor(at=at, status=ClassificationJobStatus.QUEUED)
        steps.append(current)
    if any(current.items[position].state is not ClassificationItemState.PENDING for position in batch.positions):
        raise ClassificationJobStateRefusedError(action="run", job_status=current.status.value)
    items = list(current.items)
    for position in batch.positions:
        items[position] = items[position].transitioned(ClassificationItemState.RUNNING)
    steps.append(current.successor(at=at, status=ClassificationJobStatus.RUNNING, items=items))
    return tuple(steps)


@dataclass(frozen=True, slots=True)
class _Settled:
    """One movement's settled result: a proposal, or the cause it failed with."""

    position: int
    proposal: ClassificationProposal | None = None
    cause: ClassificationItemFailureCause | None = None
    stale: bool = False


def _committed(
    job: ClassificationJob, results: Sequence[_Settled], *, at: datetime, stopping: bool
) -> tuple[ClassificationJob, ...]:
    """Store the batch's results, then mark stale any proposal whose movement changed while it was read.

    A cancelling job finishes its cancel in the same write. A job with nothing
    left to ask finishes. A run asked to stop queues the job again.
    """
    items = list(job.items)
    for result in results:
        item = items[result.position]
        if item.state is not ClassificationItemState.RUNNING:
            raise ClassificationJobStateRefusedError(action="run", job_status=job.status.value)
        if result.proposal is not None:
            items[result.position] = item.transitioned(ClassificationItemState.PROPOSED, proposal=result.proposal)
        else:
            items[result.position] = item.transitioned(ClassificationItemState.FAILED, failure_cause=result.cause)
    if job.status is ClassificationJobStatus.CANCELLING:
        committed = _cancel_finished(job, items, at=at)
    elif any(item.state is ClassificationItemState.RUNNING for item in items):
        committed = job.successor(at=at, items=items)
    elif not any(item.state is ClassificationItemState.PENDING for item in items):
        committed = job.successor(at=at, status=_finished_status(items), items=items)
    elif stopping:
        committed = job.successor(at=at, status=ClassificationJobStatus.QUEUED, items=items)
    else:
        committed = job.successor(at=at, items=items)
    stale = [result.position for result in results if result.stale and result.proposal is not None]
    if not stale:
        return (committed,)
    staled = list(committed.items)
    for position in stale:
        staled[position] = staled[position].transitioned(ClassificationItemState.STALE)
    return committed, committed.successor(at=at, items=staled)


def _failed_onwards(
    job: ClassificationJob, cause: ClassificationItemFailureCause, *, at: datetime
) -> tuple[ClassificationJob, ...]:
    """Fail every movement in flight or still to ask with ``cause``, then finish the job.

    A pending movement is taken as running before it fails, as any movement a
    run takes is, so the record shows this run reached it.
    """
    if job.status is ClassificationJobStatus.CANCELLING:
        return (_cancel_finished(job, job.items, at=at),)
    steps: list[ClassificationJob] = []
    current = job
    if current.status is ClassificationJobStatus.INTERRUPTED and _has(current, ClassificationItemState.PENDING):
        current = current.successor(at=at, status=ClassificationJobStatus.QUEUED)
        steps.append(current)
    while _has(current, ClassificationItemState.PENDING) or _has(current, ClassificationItemState.RUNNING):
        items = tuple(
            item.transitioned(ClassificationItemState.FAILED, failure_cause=cause)
            if item.state is ClassificationItemState.RUNNING
            else item.transitioned(ClassificationItemState.RUNNING)
            if item.state is ClassificationItemState.PENDING
            else item
            for item in current.items
        )
        in_flight = any(item.state is ClassificationItemState.RUNNING for item in items)
        current = current.successor(
            at=at, status=ClassificationJobStatus.RUNNING if in_flight else _finished_status(items), items=items
        )
        steps.append(current)
    return tuple(steps)


# -- reading one movement ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _LaneRefused:
    """A refusal that concerns the lane, not one movement: every movement still to ask would meet it."""

    cause: ClassificationItemFailureCause
    error: CadrumoError


def classification_failure_cause(error: LLMClassifierError) -> ClassificationItemFailureCause:
    """Return the item cause of one movement's reader failure.

    A failure that names the agent's refusal code was refused by the model run;
    one without it is a reply the classification parse did not accept.
    """
    refusal = (error.context or {}).get(MODEL_RUN_REFUSAL_CONTEXT_KEY)
    if refusal is None or refusal in _INVALID_OUTPUT_REFUSALS:
        return ClassificationItemFailureCause.INVALID_RESPONSE
    if refusal in _TIMED_OUT_REFUSALS:
        return ClassificationItemFailureCause.TIMED_OUT
    return ClassificationItemFailureCause.LANE_REFUSED


def _current_movement(reader: ClassificationJobReader, movement_id: str) -> Transaction | None:
    """Return the movement as stored now, or ``None`` when it is gone or no longer active."""
    transaction = reader.transactions.load_by_ids((movement_id,)).get(movement_id)
    if transaction is None or transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return None
    return transaction


def _read_movement(
    reader: ClassificationJobReader,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    position: int,
    movement_id: str,
) -> _Settled | _LaneRefused:
    """Read one movement through the classification reader and bind its proposal to the revision read."""
    with validating_governed_facts(operation):
        transaction = _current_movement(reader, movement_id)
        if transaction is None:
            return _Settled(position, cause=ClassificationItemFailureCause.MOVEMENT_NOT_FOUND)
        read_revision = movement_revision_id(transaction)
        try:
            # The read's consent, where its lane needs one, is bound to the revision it sends.
            suggestion = suggest_llm_classification(
                bucket_id=bucket_id,
                transaction_id=movement_id,
                operation=operation,
                transaction_repository=reader.transactions,
                settings=reader.settings,
                ports=reader.llm_for(read_revision),
                reviewed_transaction=transaction,
            )
        except LedgerOffHostConsentRequiredError as exc:
            return _LaneRefused(ClassificationItemFailureCause.CONSENT_REQUIRED, exc)
        except PurchaseInvoiceEvidenceReaderError as exc:
            return _LaneRefused(ClassificationItemFailureCause.MODEL_UNAVAILABLE, exc)
        except LLMClassifierError as exc:
            return _Settled(position, cause=classification_failure_cause(exc))
        proposal = ClassificationProposal(
            movement_revision_id=read_revision,
            classification=suggestion.classification,
            confidence=suggestion.confidence,
            category=None if suggestion.category is None else suggestion.category.value,
            multiple_components=suggestion.multiple_components,
            provenance=suggestion.provenance,
            proposed_at=now(),
        )
        # The movement may have changed while the model read it: the proposal then
        # belongs to a revision that is gone, or to a movement that is.
        after = _current_movement(reader, movement_id)
    if after is None:
        return _Settled(position, cause=ClassificationItemFailureCause.MOVEMENT_NOT_FOUND)
    return _Settled(position, proposal=proposal, stale=movement_revision_id(after) != read_revision)


# -- the run -----------------------------------------------------------------------------------------------------------


def _at(job: ClassificationJob) -> datetime:
    """The time of a change: now, but never before the job's last change, so a clock stepped back refuses nothing."""
    return max(now(), job.updated_at)


def _outcome(job: ClassificationJob) -> _RunOutcome:
    if job.status is ClassificationJobStatus.SETTLED:
        return "settled"
    if job.status is ClassificationJobStatus.CANCELLED:
        return "cancelled"
    if job.status is ClassificationJobStatus.INTERRUPTED:
        return "interrupted"
    raise ClassificationJobStateRefusedError(action="run", job_status=job.status.value)


def _causes(causes: Sequence[ClassificationItemFailureCause]) -> str:
    """Closed cause tokens with their counts, for the log."""
    counted = Counter(cause.value for cause in causes)
    return ",".join(f"{cause}:{count}" for cause, count in sorted(counted.items())) or "none"


def _state_counts(job: ClassificationJob) -> str:
    counted = Counter(item.state.value for item in job.items)
    return ",".join(f"{state.value}:{counted.get(state.value, 0)}" for state in ClassificationItemState)


type _Change = Callable[[ClassificationJob], tuple[ClassificationJob, ...]]


class _JobRun:
    """One run of one job: every write re-reads the stored job, so a concurrent cancel is seen at once."""

    def __init__(
        self,
        context: OperationExecutorContext,
        repository: ClassificationJobRepository,
        payload: LedgerClassifyJobRunRequest,
        ports: ClassificationJobRunPorts,
    ) -> None:
        self._context = context
        self._repository = repository
        self._payload = payload
        self._ports = ports
        self._wrote = False

    def _stored(self) -> ClassificationJob:
        try:
            return self._repository.get(self._payload.job_id)
        except ClassificationJobNotFoundError as exc:
            raise ClassificationJobUnknownError from exc

    def _apply(self, change: _Change) -> ClassificationJob:
        """Apply ``change`` to the job as stored now, reading it again when a concurrent write moved it first."""
        attempts_left = _WRITE_ATTEMPTS
        while True:
            stored = self._stored()
            current = stored
            try:
                for step in change(stored):
                    self._repository.update(step)
                    self._wrote = True
                    current = step
            except ClassificationJobRevisionConflictError as exc:
                attempts_left -= 1
                if attempts_left == 0:
                    raise ClassificationJobStaleRevisionError(
                        expected_revision=stored.revision, stored_revision=None
                    ) from exc
                continue
            except ClassificationJobNotFoundError as exc:
                raise ClassificationJobUnknownError from exc
            return current

    async def _store(self, change: _Change) -> ClassificationJob | None:
        """Write ``change`` inside an irreversible section; ``None`` when a stop was asked before it could begin."""
        entered = False

        async def write() -> ClassificationJob:
            nonlocal entered
            async with self._context.cancellation.irreversible_section():
                entered = True
                await self._context.events.effect(OperationEffect.UNKNOWN)
                try:
                    stored = await asyncio.to_thread(self._apply, change)
                finally:
                    await self._context.events.effect(OperationEffect.UPDATED if self._wrote else OperationEffect.NONE)
                return stored

        try:
            return await await_cancellation_complete(write(), task_name="ledger-classify-job-run")
        except ValueError:
            # A stop asked before the section began refuses its entry: nothing of this write happened.
            if not entered and self._context.cancellation.cancellation_requested:
                await self._context.cancellation.acknowledge_cancellation()
                return None
            raise

    async def _publish(self, job: ClassificationJob) -> str:
        _log.info(
            "ledger classification run ended job=%s status=%s revision=%d items=%s",
            job.job_id,
            job.status.value,
            job.revision,
            _state_counts(job),
        )
        result = LedgerClassifyJobRunResult(
            profile_id=self._payload.profile_id, outcome=_outcome(job), job=LedgerClassifyJobProjection.from_job(job)
        )
        await self._context.events.effect(OperationEffect.UPDATED if self._wrote else OperationEffect.NONE)
        return await self._context.operands.put(result, written_at=now())

    async def _refuse_onwards(self, cause: ClassificationItemFailureCause, error: CadrumoError) -> str | None:
        """Fail every movement still to ask with ``cause``, finish the job, then refuse the run with ``error``."""
        failed = await self._store(lambda stored: _failed_onwards(stored, cause, at=_at(stored)))
        if failed is None:
            return None
        _log.info(
            "ledger classification run refused job=%s cause=%s status=%s revision=%d items=%s",
            failed.job_id,
            cause.value,
            failed.status.value,
            failed.revision,
            _state_counts(failed),
        )
        raise error

    async def _lane_refused(self, job: ClassificationJob, *, bucket_id: str) -> _LaneRefused | None:
        """Return why no movement of ``job`` may be read now, or ``None`` when its lane and grant still hold."""
        try:
            lane = await self._ports.resolve_lane(ModelRole.TEXT_EXTRACTION, task_kind=ModelRunTaskKind.CLASSIFICATION)
        except LedgerOffHostConsentRequiredError as exc:
            return _LaneRefused(ClassificationItemFailureCause.CONSENT_REQUIRED, exc)
        except PurchaseInvoiceEvidenceReaderError as exc:
            return _LaneRefused(ClassificationItemFailureCause.MODEL_UNAVAILABLE, exc)
        if not reads_with(job.lane, lane):
            # Never read on a lane the job was not bound to: the person enqueues again or grants the new lane.
            return _LaneRefused(ClassificationItemFailureCause.LANE_CHANGED, lane_changed(lane))
        if not job.lane.reads_off_host:
            return None
        consent = job.consent
        if consent is None:
            return _LaneRefused(
                ClassificationItemFailureCause.CONSENT_REQUIRED, off_host_consent_refused(consent_present=False)
            )
        standing = await asyncio.to_thread(
            self._ports.consent.standing, bucket_id=bucket_id, lane=job.lane, consent=consent, job_id=job.job_id
        )
        if standing is ConsentGrantStanding.VALID:
            return None
        return _LaneRefused(
            standing_failure_cause(standing), off_host_consent_refused(consent_present=True, standing=standing)
        )

    async def run(self, *, bucket_id: str) -> str | None:
        """Reconcile what an earlier run left, then work the pending movements until none is left."""
        job = await asyncio.to_thread(self._stored)
        if job.status in _FINISHED:
            raise ClassificationJobStateRefusedError(action="run", job_status=job.status.value)
        if reconciled_job(job, at=_at(job)) is not None:
            reconciled = await self._store(
                lambda stored: tuple(step for step in (reconciled_job(stored, at=_at(stored)),) if step is not None)
            )
            if reconciled is None:
                return None
            job = reconciled
        if job.status in _FINISHED or next_classification_batch(job) is None:
            return await self._publish(job)
        try:
            reader = await asyncio.to_thread(
                self._ports.readers,
                bucket_id=bucket_id,
                operation=self._context.authority_operation,
                lane=job.lane,
                consent=job.consent,
                job_id=job.job_id,
            )
        except LedgerOffHostConsentRequiredError as exc:
            return await self._refuse_onwards(ClassificationItemFailureCause.CONSENT_REQUIRED, exc)
        if reader.transactions.bucket_id != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return await self._work(job, reader, bucket_id=bucket_id)

    async def _work(self, job: ClassificationJob, reader: ClassificationJobReader, *, bucket_id: str) -> str | None:
        cancellation = self._context.cancellation
        while (batch := next_classification_batch(job)) is not None and job.status not in _FINISHED:
            if cancellation.cancellation_requested:
                await cancellation.acknowledge_cancellation()
                return None
            if job.status is not ClassificationJobStatus.CANCELLING and (
                lane_refused := await self._lane_refused(job, bucket_id=bucket_id)
            ):
                # The lane or the grant changed since the last batch: what is left is not read.
                return await self._refuse_onwards(lane_refused.cause, lane_refused.error)
            started = await self._store(lambda stored, taken=batch: _started(stored, taken, at=_at(stored)))
            if started is None:
                return None
            job = started
            if job.status is not ClassificationJobStatus.RUNNING:
                break
            results: list[_Settled] = []
            refused: _LaneRefused | None = None
            for position in batch.positions:
                read = await asyncio.to_thread(
                    _read_movement,
                    reader,
                    bucket_id=bucket_id,
                    operation=self._context.authority_operation,
                    position=position,
                    movement_id=job.items[position].movement_id,
                )
                if isinstance(read, _LaneRefused):
                    refused = read
                    break
                results.append(read)
            if results:
                read_results = tuple(results)
                committed = await self._store(
                    lambda stored, settled=read_results: _committed(
                        stored, settled, at=_at(stored), stopping=cancellation.cancellation_requested
                    )
                )
                if committed is None:
                    # The movements read stay running and the next run reconciles them as unknown.
                    return None
                job = committed
                _log.info(
                    "ledger classification batch job=%s revision=%d proposed=%d stale=%d failed=%d causes=%s",
                    job.job_id,
                    job.revision,
                    sum(result.proposal is not None for result in read_results),
                    sum(result.stale for result in read_results),
                    sum(result.cause is not None for result in read_results),
                    _causes(tuple(result.cause for result in read_results if result.cause is not None)),
                )
            if refused is not None:
                return await self._refuse_onwards(refused.cause, refused.error)
        return await self._publish(job)


class ClassificationJobRunExecutor:
    """Work one job of the profile until no movement is left to ask."""

    def __init__(self, ports: ClassificationJobRunPorts) -> None:
        """Bind the job repository factory and the reader factory."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobRunRequest], context: OperationExecutorContext
    ) -> str | None:
        """Run the job, publishing it as stored when the run ends; ``None`` when the run was asked to stop."""
        payload = request.payload
        if request.definition_id != LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID)
        bucket_id = str(payload.profile_id)
        repository = await asyncio.to_thread(self._ports.jobs, bucket_id=bucket_id)
        return await _JobRun(context, repository, payload, self._ports).run(bucket_id=bucket_id)


def build_ledger_classify_job_run_definition(ports: ClassificationJobRunPorts) -> OperationDefinition:
    """Declare one recorded, cooperatively stoppable run whose refusals carry their typed detail and next step."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
        request_type=LedgerClassifyJobRunRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobRunResult,
        executor_type=ClassificationJobRunExecutor,
        build=lambda: ClassificationJobRunExecutor(ports),
        capabilities=_RUN_CAPABILITIES,
        # A refused lane carries the agent's verdict and the step that puts it right;
        # its context names refusal codes and counts, never a movement.
        public_error_detail=True,
    )


def resolve_ledger_classify_job_run_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile."""
    if request.definition_id != LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID or not isinstance(
        request.payload, LedgerClassifyJobRunRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_classify_job_run_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobRunResult,
        access_resolver=resolve_ledger_classify_job_run_access,
    )
