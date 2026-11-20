"""Ledger classification jobs through the registered operations, the real supervisor and the real repository.

Every operation runs through the production registry, the real supervisor,
journal and encrypted operand store, inside an enrolled profile whose jobs are
stored by the production encrypted repository. The agent service behind the
operation's execution authority is a recording stand-in, so a lane lookup is an
observation and a model run would be recorded. What each test reads back is
what a frontend in another process reads: the public result, or the recorded
error detail of a refusal.

No job operation runs a model or writes a ledger fact, and no result or refusal
carries a movement's text.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode, ModelRunTaskKind

from ...adapters.outbound.llm.tests.model_run_support import DEFAULT_LANE, ON_HOST_LANE
from ...adapters.persistence.profile.classification_jobs import ClassificationJobRepositoryAdapter
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.ledger.classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
    LedgerClassifyJobCancelRequest,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobDismissRequest,
    LedgerClassifyJobEnqueueRequest,
    LedgerClassifyJobListRequest,
    LedgerClassifyJobListResult,
    LedgerClassifyJobReadRequest,
    LedgerClassifyJobReadResult,
    LedgerClassifyJobRetryRequest,
)
from ...application.ledger.classification_job_errors import (
    CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY,
    ClassificationJobEmptyScopeError,
    ClassificationJobMovementUnknownError,
    ClassificationJobStaleRevisionError,
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from ...application.ledger.evidence_errors import LedgerOffHostConsentRequiredError, PurchaseInvoiceEvidenceReaderError
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.off_host_consent_refusal import OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY
from ...application.ledger.reading_model_refusal import NO_READING_MODEL_LOCALE_KEY
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.operations.error_detail import OperationErrorDetailV1
from ...application.operations.next_step import OperationChooseReadingModelStepV1, OperationResolveOffHostConsentStepV1
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.errors.error_codes import get_registered_error_code
from ...core.hashing import sha256_hex
from ...core.model_roles import ModelRole
from ...core.operations import OperationTerminalCondition
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_job import (
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
    ClassificationProposal,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import TransactionCatalogue
from ..ledger_action_composition import compose_ledger_action_ports
from .dependency_operation_gating_support import OperationRuntime, SettledOperation, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OTHER_PROFILE = UUID("0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0")
_DESCRIPTION = "synthetic classification queue row 7c41"
"""The movements' own text: what a model would read, so it must never reach a published result or detail."""


@dataclass(frozen=True)
class _Queue:
    """One enrolled profile, its stored movements and its job repository."""

    runtime: OperationRuntime
    operation: PinnedAuthorityOperation
    movements: tuple[str, ...]
    """Booked in January, February and May, in that order."""

    @property
    def profile_id(self) -> UUID:
        return self.runtime.profile_id

    def jobs(self) -> ClassificationJobRepositoryAdapter:
        bucket_id = str(self.profile_id)
        return ClassificationJobRepositoryAdapter(
            objects=secure_object_repository_for_bucket(bucket_id), bucket_id=bucket_id
        )

    def catalogue(self) -> TransactionCatalogue:
        return compose_ledger_action_ports(
            bucket_id=str(self.profile_id), operation=self.operation
        ).transaction_repository.load()

    def settle(self, definition_id: str, payload: BaseModel, result_type: type[BaseModel]) -> SettledOperation:
        return self.runtime.settle(definition_id, payload, result_type)

    def enqueue(self, request: LedgerClassifyJobEnqueueRequest) -> LedgerClassifyJobChangeResult:
        settled = self.settle(LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID, request, LedgerClassifyJobChangeResult)
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        assert isinstance(settled.published, LedgerClassifyJobChangeResult)
        return settled.published

    def single(self, movement_id: str) -> LedgerClassifyJobEnqueueRequest:
        return LedgerClassifyJobEnqueueRequest(
            profile_id=self.profile_id, scope=ClassificationJobScopeKind.SINGLE, movement_ids=(movement_id,)
        )

    def store(self, job: ClassificationJob) -> ClassificationJob:
        """Store ``job`` and every revision leading to it, as a run would have."""
        self.jobs().create(job)
        return job

    def advance(self, job: ClassificationJob, following: ClassificationJob) -> ClassificationJob:
        self.jobs().update(following)
        assert following.revision == job.revision + 1
        return following


def _seed(runtime: OperationRuntime, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    ports = compose_ledger_action_ports(bucket_id=str(runtime.profile_id), operation=operation)
    year = now().year - 1
    seeded: list[str] = []
    for index, booked in enumerate((date(year, 1, 14), date(year, 2, 3), date(year, 5, 20))):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(runtime.profile_id),
                booked_date=booked,
                amount=Decimal("42.10") + index,
                direction=TransactionDirection.OUTGOING,
                description=f"{_DESCRIPTION} {index}",
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                actor="classification-job-test",
            ),
            ports=ports,
            occurred_at=now(),
        )
        seeded.append(created.ref.transaction_id)
    return tuple(seeded)


@pytest.fixture
def queue(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[_Queue]:
    with operation_runtime(tmp_path, None, lane=ON_HOST_LANE) as runtime:
        yield _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation))


def _refusal(settled: SettledOperation, error_type: type[Exception]) -> OperationErrorDetailV1:
    """Return the recorded detail of a refusal that carries ``error_type``'s registered code."""
    code = get_registered_error_code(error_type).code
    assert settled.condition is OperationTerminalCondition.REFUSED, settled
    detail = settled.published
    assert isinstance(detail, OperationErrorDetailV1), settled
    assert detail.error_code == code
    assert _DESCRIPTION not in detail.model_dump_json(), "a refusal published a movement's text"
    return detail


def _private_text_absent(result: BaseModel) -> None:
    assert _DESCRIPTION not in result.model_dump_json(), "a result published a movement's text"


def _queued_job(queue: _Queue, *, movements: tuple[str, ...] | None = None) -> ClassificationJob:
    return queue.store(
        ClassificationJob.enqueue(
            bucket_id=str(queue.profile_id),
            scope=ClassificationJobScope(kind=ClassificationJobScopeKind.SELECTION),
            movement_ids=movements or queue.movements,
            lane=ClassificationJobLane(
                provider_id=ON_HOST_LANE.provider_id,
                transport=ON_HOST_LANE.transport,
                model=ON_HOST_LANE.model,
                reads_off_host=False,
            ),
            consent=None,
            at=now(),
        )
    )


def _running_job(queue: _Queue) -> ClassificationJob:
    """A job whose run has the first movement in flight."""
    job = _queued_job(queue)
    first, *rest = job.items
    return queue.advance(
        job,
        job.successor(
            at=now(),
            status=ClassificationJobStatus.RUNNING,
            items=(first.transitioned(ClassificationItemState.RUNNING), *rest),
        ),
    )


def _settled_job(queue: _Queue) -> ClassificationJob:
    """A finished job: the first movement proposed, the second failed, the third proposed."""
    job = _queued_job(queue)
    running = queue.advance(
        job,
        job.successor(
            at=now(),
            status=ClassificationJobStatus.RUNNING,
            items=tuple(item.transitioned(ClassificationItemState.RUNNING) for item in job.items),
        ),
    )
    proposal = ClassificationProposal(
        movement_revision_id="synthetic-movement-revision",
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.81"),
        category="synthetic_category",
        proposed_at=now(),
    )
    first, second, third = running.items
    return queue.advance(
        running,
        running.successor(
            at=now(),
            status=ClassificationJobStatus.SETTLED,
            items=(
                first.transitioned(ClassificationItemState.PROPOSED, proposal=proposal),
                second.transitioned(
                    ClassificationItemState.FAILED, failure_cause=ClassificationItemFailureCause.INVALID_RESPONSE
                ),
                third.transitioned(ClassificationItemState.PROPOSED, proposal=proposal),
            ),
        ),
    )


# -- enqueue ------------------------------------------------------------------------------------------------------------


def test_a_single_movement_enqueue_stores_a_queued_job_on_the_reading_lane_and_writes_no_ledger_fact(
    queue: _Queue,
) -> None:
    catalogue_before = queue.catalogue()

    result = queue.enqueue(queue.single(queue.movements[0]))

    assert result.outcome == "enqueued"
    job = result.job
    assert (job.status, job.revision, job.scope) == (
        ClassificationJobStatus.QUEUED,
        1,
        ClassificationJobScopeKind.SINGLE,
    )
    assert [(item.movement_id, item.state, item.attempt) for item in job.items] == [
        (queue.movements[0], ClassificationItemState.PENDING, 0)
    ]
    assert job.counts.pending == 1
    assert (job.lane.provider_id, job.lane.transport, job.lane.model, job.lane.reads_off_host) == (
        ON_HOST_LANE.provider_id,
        ON_HOST_LANE.transport,
        ON_HOST_LANE.model,
        False,
    )
    assert job.consent_scope is None
    stored = queue.jobs().get(job.job_id)
    assert stored.movement_ids == (queue.movements[0],)
    assert stored.status is ClassificationJobStatus.QUEUED
    assert queue.runtime.service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert queue.runtime.service.lookup_task_kinds == [ModelRunTaskKind.CLASSIFICATION]
    assert queue.runtime.service.runs == [], "an enqueue ran a model"
    assert queue.catalogue() == catalogue_before, "an enqueue wrote a ledger fact"
    _private_text_absent(result)


def test_a_selection_enqueue_keeps_the_named_movements_in_their_order(queue: _Queue) -> None:
    named = (queue.movements[2], queue.movements[0])

    result = queue.enqueue(
        LedgerClassifyJobEnqueueRequest(
            profile_id=queue.profile_id, scope=ClassificationJobScopeKind.SELECTION, movement_ids=named
        )
    )

    assert tuple(item.movement_id for item in result.job.items) == named
    assert result.job.counts.pending == len(named)


def test_a_period_enqueue_takes_every_movement_whose_filing_date_is_within_its_bounds(queue: _Queue) -> None:
    year = now().year - 1

    result = queue.enqueue(
        LedgerClassifyJobEnqueueRequest(
            profile_id=queue.profile_id,
            scope=ClassificationJobScopeKind.PERIOD,
            period_start=date(year, 1, 1),
            period_end=date(year, 3, 31),
        )
    )

    assert {item.movement_id for item in result.job.items} == set(queue.movements[:2])
    assert (result.job.period_start, result.job.period_end) == (date(year, 1, 1), date(year, 3, 31))


@pytest.mark.parametrize("scope", [ClassificationJobScopeKind.SELECTION, ClassificationJobScopeKind.SINGLE])
def test_an_enqueue_naming_no_movement_is_refused_as_an_empty_scope_and_stores_nothing(
    queue: _Queue, scope: ClassificationJobScopeKind
) -> None:
    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
        LedgerClassifyJobEnqueueRequest(profile_id=queue.profile_id, scope=scope),
        LedgerClassifyJobChangeResult,
    )

    detail = _refusal(settled, ClassificationJobEmptyScopeError)
    assert ("scope", scope.value) in {(entry.key, entry.value) for entry in detail.context}
    assert queue.jobs().list_jobs() == ()


def test_a_period_holding_no_movement_is_refused_as_an_empty_scope(queue: _Queue) -> None:
    year = now().year - 1

    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
        LedgerClassifyJobEnqueueRequest(
            profile_id=queue.profile_id,
            scope=ClassificationJobScopeKind.PERIOD,
            period_start=date(year, 7, 1),
            period_end=date(year, 9, 30),
        ),
        LedgerClassifyJobChangeResult,
    )

    _refusal(settled, ClassificationJobEmptyScopeError)
    assert queue.jobs().list_jobs() == ()


def test_an_enqueue_naming_a_movement_this_profile_does_not_hold_is_refused_with_the_count_only(
    queue: _Queue,
) -> None:
    absent = sha256_hex(b"a movement of another profile")

    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
        LedgerClassifyJobEnqueueRequest(
            profile_id=queue.profile_id,
            scope=ClassificationJobScopeKind.SELECTION,
            movement_ids=(queue.movements[0], absent),
        ),
        LedgerClassifyJobChangeResult,
    )

    detail = _refusal(settled, ClassificationJobMovementUnknownError)
    assert ("unknown_count", "1") in {(entry.key, entry.value) for entry in detail.context}
    assert absent not in detail.model_dump_json()
    assert queue.jobs().list_jobs() == ()
    assert queue.runtime.service.lookups == [], "an unknown movement was refused after the lane was asked for"


def test_an_off_host_lane_without_consent_refuses_the_enqueue_with_both_remedies(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with operation_runtime(tmp_path, None, lane=DEFAULT_LANE) as runtime:
        movements = _seed(runtime, operation)
        queue = _Queue(runtime=runtime, operation=operation, movements=movements)
        settled = queue.settle(
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID, queue.single(movements[0]), LedgerClassifyJobChangeResult
        )
        stored = queue.jobs().list_jobs()
        runs = list(runtime.service.runs)

    assert DEFAULT_LANE.reads_off_host
    detail = _refusal(settled, LedgerOffHostConsentRequiredError)
    assert detail.message_key == OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == ModelRunRefusalCode.CONSENT_MISSING.value
    step = detail.next_step
    assert isinstance(step, OperationResolveOffHostConsentStepV1)
    assert [remedy.kind for remedy in step.remedies] == ["authorise_off_host", "switch_to_local_lane"]
    assert stored == ()
    assert runs == [], "an off-host enqueue sent a model run"


def test_an_enqueue_with_no_picked_reading_model_is_refused_with_the_step_to_pick_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with operation_runtime(tmp_path, ModelRunRefusalCode.NO_SELECTION) as runtime:
        movements = _seed(runtime, operation)
        queue = _Queue(runtime=runtime, operation=operation, movements=movements)
        settled = queue.settle(
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID, queue.single(movements[0]), LedgerClassifyJobChangeResult
        )
        stored = queue.jobs().list_jobs()

    detail = _refusal(settled, PurchaseInvoiceEvidenceReaderError)
    assert detail.message_key == NO_READING_MODEL_LOCALE_KEY
    assert isinstance(detail.next_step, OperationChooseReadingModelStepV1)
    assert stored == ()


# -- read and list ------------------------------------------------------------------------------------------------------


def test_a_read_returns_the_stored_job_with_each_movement_state_and_its_revision(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
        LedgerClassifyJobReadRequest(profile_id=queue.profile_id, job_id=job.job_id),
        LedgerClassifyJobReadResult,
    )

    assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
    read = settled.published
    assert isinstance(read, LedgerClassifyJobReadResult)
    assert (read.job.job_id, read.job.revision, read.job.status) == (
        job.job_id,
        job.revision,
        ClassificationJobStatus.SETTLED,
    )
    assert [item.state for item in read.job.items] == [
        ClassificationItemState.PROPOSED,
        ClassificationItemState.FAILED,
        ClassificationItemState.PROPOSED,
    ]
    assert read.job.items[1].failure_cause is ClassificationItemFailureCause.INVALID_RESPONSE
    proposal = read.job.items[0].proposal
    assert proposal is not None
    assert (proposal.classification, Decimal(proposal.confidence)) == (BusinessClassification.BUSINESS, Decimal("0.81"))
    assert (read.job.counts.proposed, read.job.counts.failed) == (2, 1)
    _private_text_absent(read)


def test_reading_a_job_this_profile_does_not_hold_is_refused_as_unknown(queue: _Queue) -> None:
    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
        LedgerClassifyJobReadRequest(profile_id=queue.profile_id, job_id=sha256_hex(b"no such job")),
        LedgerClassifyJobReadResult,
    )

    _refusal(settled, ClassificationJobUnknownError)


def _listed(queue: _Queue, **options: object) -> LedgerClassifyJobListResult:
    settled = queue.settle(
        LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
        LedgerClassifyJobListRequest.model_validate({"profile_id": queue.profile_id, **options}),
        LedgerClassifyJobListResult,
    )
    assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
    assert isinstance(settled.published, LedgerClassifyJobListResult)
    return settled.published


def test_the_list_is_newest_first_bounded_leaves_dismissed_jobs_out_and_moves_its_revision(queue: _Queue) -> None:
    empty = _listed(queue)
    assert (empty.jobs, empty.more) == ((), False)

    oldest = _settled_job(queue)
    middle = _queued_job(queue, movements=queue.movements[:1])
    newest = _queued_job(queue, movements=queue.movements[1:])
    full = _listed(queue)
    assert [job.job_id for job in full.jobs] == [newest.job_id, middle.job_id, oldest.job_id]
    assert full.more is False
    assert full.queue_revision != empty.queue_revision

    bounded = _listed(queue, limit=2)
    assert [job.job_id for job in bounded.jobs] == [newest.job_id, middle.job_id]
    assert bounded.more is True
    assert bounded.queue_revision == full.queue_revision

    dismissed = queue.advance(oldest, oldest.successor(at=now(), status=ClassificationJobStatus.DISMISSED))
    after = _listed(queue)
    assert [job.job_id for job in after.jobs] == [newest.job_id, middle.job_id]
    assert after.queue_revision != full.queue_revision
    with_dismissed = _listed(queue, include_dismissed=True)
    assert [job.job_id for job in with_dismissed.jobs][-1] == dismissed.job_id


# -- cancel -------------------------------------------------------------------------------------------------------------


def _change(
    queue: _Queue,
    definition_id: str,
    request_type: type[LedgerClassifyJobCancelRequest]
    | type[LedgerClassifyJobRetryRequest]
    | type[LedgerClassifyJobDismissRequest],
    job: ClassificationJob,
    *,
    expected_revision: int | None = None,
    job_id: str | None = None,
) -> SettledOperation:
    return queue.settle(
        definition_id,
        request_type(
            profile_id=queue.profile_id,
            job_id=job_id or job.job_id,
            expected_revision=job.revision if expected_revision is None else expected_revision,
        ),
        LedgerClassifyJobChangeResult,
    )


def _changed(settled: SettledOperation) -> LedgerClassifyJobChangeResult:
    assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
    assert isinstance(settled.published, LedgerClassifyJobChangeResult)
    return settled.published


def test_cancelling_a_queued_job_cancels_every_movement_at_the_next_revision(queue: _Queue) -> None:
    job = _queued_job(queue)

    result = _changed(_change(queue, LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID, LedgerClassifyJobCancelRequest, job))

    assert (result.outcome, result.job.status, result.job.revision) == (
        "cancelled",
        ClassificationJobStatus.CANCELLED,
        job.revision + 1,
    )
    assert {item.state for item in result.job.items} == {ClassificationItemState.CANCELLED}
    assert queue.jobs().get(job.job_id).status is ClassificationJobStatus.CANCELLED


def test_cancelling_a_running_job_cancels_what_was_not_asked_and_lets_the_movement_in_flight_settle(
    queue: _Queue,
) -> None:
    job = _running_job(queue)

    result = _changed(_change(queue, LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID, LedgerClassifyJobCancelRequest, job))

    assert (result.outcome, result.job.status) == ("cancelling", ClassificationJobStatus.CANCELLING)
    assert [item.state for item in result.job.items] == [
        ClassificationItemState.RUNNING,
        ClassificationItemState.CANCELLED,
        ClassificationItemState.CANCELLED,
    ]


def test_a_cancel_at_a_revision_the_job_has_moved_past_is_refused_and_changes_nothing(queue: _Queue) -> None:
    job = _queued_job(queue)

    settled = _change(
        queue,
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
        LedgerClassifyJobCancelRequest,
        job,
        expected_revision=job.revision + 1,
    )

    detail = _refusal(settled, ClassificationJobStaleRevisionError)
    assert ("stored_revision", str(job.revision)) in {(entry.key, entry.value) for entry in detail.context}
    assert queue.jobs().get(job.job_id) == job


def test_cancelling_a_finished_job_is_refused_for_its_state(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = _change(queue, LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID, LedgerClassifyJobCancelRequest, job)

    detail = _refusal(settled, ClassificationJobStateRefusedError)
    assert ("job_status", "settled") in {(entry.key, entry.value) for entry in detail.context}
    assert queue.jobs().get(job.job_id) == job


def test_cancelling_a_job_this_profile_does_not_hold_is_refused_as_unknown(queue: _Queue) -> None:
    job = _queued_job(queue)

    settled = _change(
        queue,
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
        LedgerClassifyJobCancelRequest,
        job,
        job_id=sha256_hex(b"no such job"),
    )

    _refusal(settled, ClassificationJobUnknownError)


# -- retry --------------------------------------------------------------------------------------------------------------


def test_retrying_a_settled_job_asks_again_for_its_failed_movement_and_keeps_its_proposals(queue: _Queue) -> None:
    job = _settled_job(queue)

    result = _changed(_change(queue, LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID, LedgerClassifyJobRetryRequest, job))

    assert (result.outcome, result.job.status, result.job.revision) == (
        "retried",
        ClassificationJobStatus.QUEUED,
        job.revision + 1,
    )
    assert [item.state for item in result.job.items] == [
        ClassificationItemState.PROPOSED,
        ClassificationItemState.PENDING,
        ClassificationItemState.PROPOSED,
    ]
    assert result.job.items[1].failure_cause is None
    assert queue.jobs().get(job.job_id).items[1].state is ClassificationItemState.PENDING


def test_retrying_a_job_with_nothing_failed_is_refused_saying_so(queue: _Queue) -> None:
    job = _queued_job(queue)

    settled = _change(queue, LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID, LedgerClassifyJobRetryRequest, job)

    detail = _refusal(settled, ClassificationJobStateRefusedError)
    assert detail.message_key == CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY
    assert queue.jobs().get(job.job_id) == job


def test_retrying_a_job_a_run_owns_is_refused_for_its_state(queue: _Queue) -> None:
    job = _running_job(queue)

    settled = _change(queue, LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID, LedgerClassifyJobRetryRequest, job)

    detail = _refusal(settled, ClassificationJobStateRefusedError)
    assert ("job_status", "running") in {(entry.key, entry.value) for entry in detail.context}


def test_a_retry_at_a_stale_revision_is_refused(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = _change(
        queue, LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID, LedgerClassifyJobRetryRequest, job, expected_revision=1
    )

    _refusal(settled, ClassificationJobStaleRevisionError)
    assert queue.jobs().get(job.job_id) == job


def test_retrying_a_job_this_profile_does_not_hold_is_refused_as_unknown(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = _change(
        queue,
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
        LedgerClassifyJobRetryRequest,
        job,
        job_id=sha256_hex(b"no such job"),
    )

    _refusal(settled, ClassificationJobUnknownError)


# -- dismiss ------------------------------------------------------------------------------------------------------------


def test_dismissing_a_settled_job_puts_it_away_without_touching_its_proposals_or_the_ledger(queue: _Queue) -> None:
    job = _settled_job(queue)
    catalogue_before = queue.catalogue()

    result = _changed(_change(queue, LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID, LedgerClassifyJobDismissRequest, job))

    assert (result.outcome, result.job.status) == ("dismissed", ClassificationJobStatus.DISMISSED)
    stored = queue.jobs().get(job.job_id)
    assert stored.items == job.items
    assert queue.catalogue() == catalogue_before


def test_dismissing_a_job_that_has_not_finished_is_refused_for_its_state(queue: _Queue) -> None:
    job = _queued_job(queue)

    settled = _change(queue, LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID, LedgerClassifyJobDismissRequest, job)

    detail = _refusal(settled, ClassificationJobStateRefusedError)
    assert ("action", "dismiss") in {(entry.key, entry.value) for entry in detail.context}
    assert queue.jobs().get(job.job_id) == job


def test_a_dismiss_at_a_stale_revision_is_refused(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = _change(
        queue,
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
        LedgerClassifyJobDismissRequest,
        job,
        expected_revision=job.revision - 1,
    )

    _refusal(settled, ClassificationJobStaleRevisionError)


def test_dismissing_a_job_this_profile_does_not_hold_is_refused_as_unknown(queue: _Queue) -> None:
    job = _settled_job(queue)

    settled = _change(
        queue,
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
        LedgerClassifyJobDismissRequest,
        job,
        job_id=sha256_hex(b"no such job"),
    )

    _refusal(settled, ClassificationJobUnknownError)


# -- profile isolation --------------------------------------------------------------------------------------------------


def _foreign_requests(job_id: str) -> tuple[tuple[str, BaseModel], ...]:
    return (
        (
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
            LedgerClassifyJobEnqueueRequest(
                profile_id=_OTHER_PROFILE,
                scope=ClassificationJobScopeKind.SINGLE,
                movement_ids=(sha256_hex(b"foreign movement"),),
            ),
        ),
        (
            LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
            LedgerClassifyJobReadRequest(profile_id=_OTHER_PROFILE, job_id=job_id),
        ),
        (LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID, LedgerClassifyJobListRequest(profile_id=_OTHER_PROFILE)),
        (
            LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
            LedgerClassifyJobCancelRequest(profile_id=_OTHER_PROFILE, job_id=job_id, expected_revision=1),
        ),
        (
            LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
            LedgerClassifyJobRetryRequest(profile_id=_OTHER_PROFILE, job_id=job_id, expected_revision=1),
        ),
        (
            LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
            LedgerClassifyJobDismissRequest(profile_id=_OTHER_PROFILE, job_id=job_id, expected_revision=1),
        ),
    )


def test_every_job_operation_naming_another_profile_is_refused_before_it_reads_or_writes(queue: _Queue) -> None:
    job = _queued_job(queue)

    for definition_id, payload in _foreign_requests(job.job_id):
        settled = queue.settle(definition_id, payload, LedgerClassifyJobChangeResult)
        _refusal(settled, ProfileAccessRefusedError)

    assert queue.jobs().list_jobs() == (job,)
    assert queue.runtime.service.lookups == [], "a foreign enqueue asked for a lane"


def test_a_job_stored_in_one_profile_store_is_unknown_to_another_store(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Each runtime holds its own encrypted profile store; a job identity carries no access to another's.

    Both runtimes enrol a copy of one registered subject, so this proves store separation; a request naming
    another profile is refused at admission, as the test above shows.
    """
    with operation_runtime(tmp_path / "first", None, lane=ON_HOST_LANE) as runtime:
        first = _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation))
        job = first.enqueue(first.single(first.movements[0])).job

    with operation_runtime(tmp_path / "second", None, lane=ON_HOST_LANE) as runtime:
        second = _Queue(runtime=runtime, operation=operation, movements=())
        settled = second.settle(
            LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
            LedgerClassifyJobReadRequest(profile_id=second.profile_id, job_id=job.job_id),
            LedgerClassifyJobReadResult,
        )
        listed = _listed(second)

    _refusal(settled, ClassificationJobUnknownError)
    assert listed.jobs == ()


def test_an_interrupted_job_settles_unknown_movements_when_cancelled(queue: _Queue) -> None:
    """A movement whose run was interrupted is cancelled with the rest; nothing reads it as done.

    The interruption is stamped ahead of the wall clock, so the cancel also shows that a clock stepped back does not
    make the change go back in time and fail.
    """
    running = _running_job(queue)
    first, *rest = running.items
    interrupted = queue.advance(
        running,
        running.successor(
            at=now() + timedelta(seconds=1),
            status=ClassificationJobStatus.INTERRUPTED,
            items=(first.transitioned(ClassificationItemState.UNKNOWN), *rest),
        ),
    )

    result = _changed(
        _change(queue, LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID, LedgerClassifyJobCancelRequest, interrupted)
    )

    assert result.job.status is ClassificationJobStatus.CANCELLED
    assert {item.state for item in result.job.items} == {ClassificationItemState.CANCELLED}
    assert result.job.counts.proposed == 0
