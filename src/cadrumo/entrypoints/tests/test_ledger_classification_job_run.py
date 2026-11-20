"""The ledger classification job run through the registered operation, the real supervisor and the real repository.

Every run settles through the production registry, the real supervisor,
journal and encrypted operand store, inside an enrolled profile whose jobs and
movements are stored by the production encrypted repositories. The model
boundary is the agent service behind the operation's execution authority: a
recording stand-in that answers each run with a scripted reply, or refuses it.
Everything between, the classification reader, its prompt and its parse, is the
production composition.

A hook can act while the stand-in answers, as a person or another writer would
while the model reads: cancel the job, or edit or replace a movement.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo_client.contracts.model_runs import ModelRunBody, ModelRunRefusalCode, ModelRunTaskKind

from ...adapters.outbound.llm.tests.model_run_support import DEFAULT_LANE, ON_HOST_LANE
from ...adapters.persistence.profile.classification_jobs import ClassificationJobRepositoryAdapter
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.ledger.classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobEnqueueRequest,
    LedgerClassifyJobRetryRequest,
    LedgerClassifyJobRunRequest,
    LedgerClassifyJobRunResult,
)
from ...application.ledger.classification_job_errors import (
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from ...application.ledger.classification_job_operation import cancelled_job
from ...application.ledger.classification_job_run import movement_revision_id
from ...application.ledger.evidence_errors import LedgerOffHostConsentRequiredError, PurchaseInvoiceEvidenceReaderError
from ...application.ledger.manual_update import update_manual_transaction_fields
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...application.ledger.off_host_consent_refusal import OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.operations.error_detail import OperationErrorDetailV1
from ...application.operations.next_step import OperationChooseReadingModelStepV1, OperationResolveOffHostConsentStepV1
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.errors.error_codes import get_registered_error_code
from ...core.hashing import sha256_hex
from ...core.operations import OperationTerminalCondition
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobConsent,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import TransactionCatalogue
from ..ledger_action_composition import compose_ledger_action_ports
from .dependency_operation_gating_support import OperationRuntime, SettledOperation, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OTHER_PROFILE = UUID("0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0")
_DESCRIPTION = "synthetic classification run row 5d93"
"""The movements' own text: what the model reads, so it must never reach a published result or detail."""
_REPLY = json.dumps({"classification": "BUSINESS", "confidence": "0.85", "reason": "synthetic office supplies"})


@dataclass
class _Answers:
    """The stand-in's replies, and what happens while it answers each run, in run order."""

    reply: str = _REPLY
    while_reading: list[Callable[[], object] | None] = field(default_factory=list)

    def __call__(self, body: ModelRunBody) -> str:
        del body
        if self.while_reading:
            hook = self.while_reading.pop(0)
            if hook is not None:
                hook()
        return self.reply


@dataclass(frozen=True)
class _Queue:
    """One enrolled profile, its stored movements and its job repository."""

    runtime: OperationRuntime
    operation: PinnedAuthorityOperation
    movements: tuple[str, ...]
    answers: _Answers

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

    def enqueue(self, movements: tuple[str, ...] | None = None) -> ClassificationJob:
        settled = self.runtime.settle(
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
            LedgerClassifyJobEnqueueRequest(
                profile_id=self.profile_id,
                scope=ClassificationJobScopeKind.SELECTION,
                movement_ids=movements or self.movements,
            ),
            LedgerClassifyJobChangeResult,
        )
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        assert isinstance(settled.published, LedgerClassifyJobChangeResult)
        return self.jobs().get(settled.published.job.job_id)

    def run(self, job_id: str, *, profile_id: UUID | None = None) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
            LedgerClassifyJobRunRequest(profile_id=profile_id or self.profile_id, job_id=job_id),
            LedgerClassifyJobRunResult,
        )

    def ran(self, job_id: str) -> LedgerClassifyJobRunResult:
        settled = self.run(job_id)
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        assert isinstance(settled.published, LedgerClassifyJobRunResult)
        assert _DESCRIPTION not in settled.published.model_dump_json(), "a run published a movement's text"
        return settled.published

    def edit_notes(self, movement_id: str, notes: str) -> str:
        """Edit a movement in place, as the person would; its identity stays and its revision moves."""
        return self._edit(movement_id, ManualLedgerTransactionPatch(notes=notes))

    def edit_description(self, movement_id: str, description: str) -> str:
        """Edit a movement's description, which replaces it with a movement of another identity."""
        return self._edit(movement_id, ManualLedgerTransactionPatch(description=description))

    def _edit(self, movement_id: str, patch: ManualLedgerTransactionPatch) -> str:
        return update_manual_transaction_fields(
            bucket_id=str(self.profile_id),
            transaction_id=movement_id,
            patch=patch,
            actor="classification-run-test",
            source_command="synthetic edit",
            ports=compose_ledger_action_ports(bucket_id=str(self.profile_id), operation=self.operation),
        ).transaction.transaction_id

    def cancel_stored(self, job_id: str) -> None:
        """Store the person's cancel of the job as it stands, as the registered cancel stores it."""
        jobs = self.jobs()
        changed, _outcome = cancelled_job(jobs.get(job_id), at=now())
        jobs.update(changed)


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
                actor="classification-run-test",
            ),
            ports=ports,
            occurred_at=now(),
        )
        seeded.append(created.ref.transaction_id)
    return tuple(seeded)


@pytest.fixture
def answers() -> _Answers:
    return _Answers()


@pytest.fixture
def queue(tmp_path: Path, operation: PinnedAuthorityOperation, answers: _Answers) -> Iterator[_Queue]:
    with operation_runtime(tmp_path, None, lane=ON_HOST_LANE, answer=answers) as runtime:
        yield _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)


def _refusal(settled: SettledOperation, error_type: type[Exception]) -> OperationErrorDetailV1:
    """Return the recorded detail of a refusal that carries ``error_type``'s registered code."""
    assert settled.condition is OperationTerminalCondition.REFUSED, settled
    detail = settled.published
    assert isinstance(detail, OperationErrorDetailV1), settled
    assert detail.error_code == get_registered_error_code(error_type).code
    assert _DESCRIPTION not in detail.model_dump_json(), "a refusal published a movement's text"
    return detail


def _stored_job(
    queue: _Queue, *, lane: ClassificationJobLane, consent: ClassificationJobConsent | None
) -> ClassificationJob:
    job = ClassificationJob.enqueue(
        bucket_id=str(queue.profile_id),
        scope=ClassificationJobScope(kind=ClassificationJobScopeKind.SELECTION),
        movement_ids=queue.movements,
        lane=lane,
        consent=consent,
        at=now(),
    )
    queue.jobs().create(job)
    return job


def _interrupted_mid_movement(queue: _Queue) -> ClassificationJob:
    """A job whose run stopped with its first movement in flight: stored running, as the run last wrote it."""
    job = queue.enqueue()
    first, *rest = job.items
    running = job.successor(
        at=now(),
        status=ClassificationJobStatus.RUNNING,
        items=(first.transitioned(ClassificationItemState.RUNNING), *rest),
    )
    queue.jobs().update(running)
    return running


def _states(job: ClassificationJob) -> list[ClassificationItemState]:
    return [item.state for item in job.items]


def _causes(job: ClassificationJob) -> list[ClassificationItemFailureCause | None]:
    return [item.failure_cause for item in job.items]


# -- success -------------------------------------------------------------------------------------------------------------


def test_a_run_proposes_for_every_movement_bound_to_the_revision_it_read_and_writes_no_ledger_fact(
    queue: _Queue,
) -> None:
    job = queue.enqueue()
    catalogue_before = queue.catalogue()

    result = queue.ran(job.job_id)

    assert (result.outcome, result.job.status) == ("settled", ClassificationJobStatus.SETTLED)
    stored = queue.jobs().get(job.job_id)
    assert stored.revision == result.job.revision
    assert _states(stored) == [ClassificationItemState.PROPOSED] * 3
    revisions = {movement_revision_id(catalogue_before.transactions[movement]) for movement in queue.movements}
    assert len(revisions) == 3, "three distinct movements share a revision"
    for item in stored.items:
        assert item.proposal is not None
        assert item.attempt == 1
        assert item.proposal.movement_revision_id == movement_revision_id(
            catalogue_before.transactions[item.movement_id]
        )
        assert item.proposal.classification is BusinessClassification.BUSINESS
        assert item.proposal.confidence == Decimal("0.85")
    assert len(queue.runtime.service.runs) == 3
    assert {header.task_kind for header, _body in queue.runtime.service.runs} == {ModelRunTaskKind.CLASSIFICATION}
    assert queue.catalogue() == catalogue_before, "a run wrote a ledger fact"


def test_running_a_settled_job_again_is_refused_for_its_state_and_asks_no_model(queue: _Queue) -> None:
    job = queue.enqueue()
    queue.ran(job.job_id)
    runs = len(queue.runtime.service.runs)

    detail = _refusal(queue.run(job.job_id), ClassificationJobStateRefusedError)

    assert ("job_status", ClassificationJobStatus.SETTLED.value) in {
        (entry.key, entry.value) for entry in detail.context
    }
    assert len(queue.runtime.service.runs) == runs


# -- resume ----------------------------------------------------------------------------------------------------------------


def test_a_movement_left_in_flight_reads_unknown_on_the_next_run_and_is_asked_again_only_through_retry(
    queue: _Queue,
) -> None:
    interrupted = _interrupted_mid_movement(queue)

    first_run = queue.ran(interrupted.job_id)

    assert (first_run.outcome, first_run.job.status) == ("interrupted", ClassificationJobStatus.INTERRUPTED)
    stored = queue.jobs().get(interrupted.job_id)
    assert _states(stored) == [
        ClassificationItemState.UNKNOWN,
        ClassificationItemState.PROPOSED,
        ClassificationItemState.PROPOSED,
    ]
    assert stored.items[0].proposal is None, "an interrupted movement was read as done"
    assert len(queue.runtime.service.runs) == 2, "the movement in flight was asked again without a retry"

    again = queue.ran(interrupted.job_id)
    assert again.outcome == "interrupted"
    assert len(queue.runtime.service.runs) == 2, "a run with nothing pending asked a model"

    retried = queue.runtime.settle(
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
        LedgerClassifyJobRetryRequest(
            profile_id=queue.profile_id, job_id=interrupted.job_id, expected_revision=again.job.revision
        ),
        LedgerClassifyJobChangeResult,
    )
    assert retried.condition is OperationTerminalCondition.SUCCEEDED, retried
    resumed = queue.ran(interrupted.job_id)

    assert (resumed.outcome, resumed.job.status) == ("settled", ClassificationJobStatus.SETTLED)
    final = queue.jobs().get(interrupted.job_id)
    assert _states(final) == [ClassificationItemState.PROPOSED] * 3
    assert [item.attempt for item in final.items] == [2, 1, 1]
    assert len(queue.runtime.service.runs) == 3


def test_a_run_stopped_between_movements_is_queued_again_and_the_next_run_continues(queue: _Queue) -> None:
    job = queue.enqueue()
    # A run that stopped with nothing in flight left its job running with only pending movements.
    stopped = job.successor(at=now(), status=ClassificationJobStatus.RUNNING)
    queue.jobs().update(stopped)

    result = queue.ran(job.job_id)

    assert (result.outcome, result.job.status) == ("settled", ClassificationJobStatus.SETTLED)
    stored = queue.jobs().get(job.job_id)
    assert _states(stored) == [ClassificationItemState.PROPOSED] * 3
    assert [item.attempt for item in stored.items] == [1, 1, 1]
    assert len(queue.runtime.service.runs) == 3


# -- cancel ----------------------------------------------------------------------------------------------------------------


def test_a_cancel_while_a_movement_is_read_lets_it_settle_and_cancels_the_rest(queue: _Queue) -> None:
    job = queue.enqueue()
    queue.answers.while_reading.append(lambda: queue.cancel_stored(job.job_id))

    result = queue.ran(job.job_id)

    assert (result.outcome, result.job.status) == ("cancelled", ClassificationJobStatus.CANCELLED)
    stored = queue.jobs().get(job.job_id)
    assert _states(stored) == [
        ClassificationItemState.PROPOSED,
        ClassificationItemState.CANCELLED,
        ClassificationItemState.CANCELLED,
    ]
    assert len(queue.runtime.service.runs) == 1, "a cancelled movement was still asked"


def test_a_job_left_cancelling_by_a_stopped_run_finishes_its_cancel_without_asking_a_model(queue: _Queue) -> None:
    interrupted = _interrupted_mid_movement(queue)
    queue.cancel_stored(interrupted.job_id)
    assert queue.jobs().get(interrupted.job_id).status is ClassificationJobStatus.CANCELLING

    result = queue.ran(interrupted.job_id)

    assert result.outcome == "cancelled"
    assert _states(queue.jobs().get(interrupted.job_id)) == [ClassificationItemState.CANCELLED] * 3
    assert queue.runtime.service.runs == []


# -- movements that change -------------------------------------------------------------------------------------------------


def test_a_movement_edited_after_enqueue_is_proposed_for_the_revision_the_run_read(queue: _Queue) -> None:
    job = queue.enqueue()
    revision_at_enqueue = movement_revision_id(queue.catalogue().transactions[queue.movements[0]])
    queue.edit_notes(queue.movements[0], "synthetic note added after enqueue")
    revision_now = movement_revision_id(queue.catalogue().transactions[queue.movements[0]])

    queue.ran(job.job_id)

    proposal = queue.jobs().get(job.job_id).items[0].proposal
    assert proposal is not None
    assert revision_now != revision_at_enqueue
    assert proposal.movement_revision_id == revision_now


def test_a_movement_edited_while_the_model_reads_it_leaves_its_proposal_stale(queue: _Queue) -> None:
    job = queue.enqueue()
    read_revision = movement_revision_id(queue.catalogue().transactions[queue.movements[0]])
    queue.answers.while_reading.append(lambda: queue.edit_notes(queue.movements[0], "synthetic note while reading"))

    result = queue.ran(job.job_id)

    assert result.outcome == "settled"
    stored = queue.jobs().get(job.job_id)
    assert _states(stored) == [
        ClassificationItemState.STALE,
        ClassificationItemState.PROPOSED,
        ClassificationItemState.PROPOSED,
    ]
    stale = stored.items[0]
    assert stale.proposal is not None
    assert stale.proposal.movement_revision_id == read_revision
    assert not stale.proposal_is_current(movement_revision_id(queue.catalogue().transactions[queue.movements[0]]))


def test_a_movement_replaced_before_or_while_it_is_read_fails_as_not_found(queue: _Queue) -> None:
    job = queue.enqueue()
    queue.edit_description(queue.movements[0], "synthetic replaced before the run")
    queue.answers.while_reading.append(
        lambda: queue.edit_description(queue.movements[1], "synthetic replaced while reading")
    )

    result = queue.ran(job.job_id)

    assert result.outcome == "settled"
    stored = queue.jobs().get(job.job_id)
    assert _states(stored) == [
        ClassificationItemState.FAILED,
        ClassificationItemState.FAILED,
        ClassificationItemState.PROPOSED,
    ]
    assert _causes(stored)[:2] == [ClassificationItemFailureCause.MOVEMENT_NOT_FOUND] * 2
    assert len(queue.runtime.service.runs) == 2, "a movement that was gone before its read was sent to the model"


# -- refusals ----------------------------------------------------------------------------------------------------------------


def test_a_stored_off_host_consent_that_cannot_be_bound_fails_every_movement_and_refuses_with_both_remedies(
    queue: _Queue,
) -> None:
    job = _stored_job(
        queue,
        lane=ClassificationJobLane(
            provider_id=DEFAULT_LANE.provider_id,
            transport=DEFAULT_LANE.transport,
            model=DEFAULT_LANE.model,
            reads_off_host=True,
        ),
        consent=ClassificationJobConsent(
            scope=ClassificationConsentScope.ONCE, consent_reference="synthetic-grant", granted_at=now()
        ),
    )
    catalogue_before = queue.catalogue()

    detail = _refusal(queue.run(job.job_id), LedgerOffHostConsentRequiredError)

    assert detail.message_key == OFF_HOST_CONSENT_REQUIRED_LOCALE_KEY
    step = detail.next_step
    assert isinstance(step, OperationResolveOffHostConsentStepV1)
    assert [remedy.kind for remedy in step.remedies] == ["authorise_off_host", "switch_to_local_lane"]
    stored = queue.jobs().get(job.job_id)
    assert stored.status is ClassificationJobStatus.SETTLED
    assert _causes(stored) == [ClassificationItemFailureCause.CONSENT_REVOKED] * 3
    assert queue.runtime.service.runs == [], "an off-host read was sent without a bound consent"
    assert queue.catalogue() == catalogue_before


def test_a_lane_that_now_reads_off_host_refuses_at_dispatch_and_fails_every_movement_for_consent(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    answers = _Answers()
    with operation_runtime(tmp_path, None, lane=DEFAULT_LANE, answer=answers) as runtime:
        queue = _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)
        # Stored on the on-host lane the person had picked when it was enqueued.
        job = _stored_job(
            queue,
            lane=ClassificationJobLane(
                provider_id=ON_HOST_LANE.provider_id,
                transport=ON_HOST_LANE.transport,
                model=ON_HOST_LANE.model,
                reads_off_host=False,
            ),
            consent=None,
        )
        detail = _refusal(queue.run(job.job_id), LedgerOffHostConsentRequiredError)
        stored = queue.jobs().get(job.job_id)

    step = detail.next_step
    assert isinstance(step, OperationResolveOffHostConsentStepV1)
    assert stored.status is ClassificationJobStatus.SETTLED
    assert _causes(stored) == [ClassificationItemFailureCause.CONSENT_REQUIRED] * 3


def test_no_reading_model_fails_every_movement_as_unavailable_and_refuses_with_the_step_to_pick_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    answers = _Answers()
    with operation_runtime(tmp_path, ModelRunRefusalCode.NO_SELECTION, lane=ON_HOST_LANE, answer=answers) as runtime:
        queue = _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)
        job = _stored_job(
            queue,
            lane=ClassificationJobLane(
                provider_id=ON_HOST_LANE.provider_id,
                transport=ON_HOST_LANE.transport,
                model=ON_HOST_LANE.model,
                reads_off_host=False,
            ),
            consent=None,
        )
        detail = _refusal(queue.run(job.job_id), PurchaseInvoiceEvidenceReaderError)
        stored = queue.jobs().get(job.job_id)
        runs = list(runtime.service.runs)

    assert isinstance(detail.next_step, OperationChooseReadingModelStepV1)
    assert stored.status is ClassificationJobStatus.SETTLED
    assert _causes(stored) == [ClassificationItemFailureCause.MODEL_UNAVAILABLE] * 3
    assert [item.attempt for item in stored.items] == [1, 1, 1]
    assert runs == []


def test_a_model_that_refuses_each_movement_fails_each_as_lane_refused_and_the_job_settles(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    answers = _Answers()
    with operation_runtime(
        tmp_path, ModelRunRefusalCode.REFUSED_BY_PROVIDER, at_run=True, lane=ON_HOST_LANE, answer=answers
    ) as runtime:
        queue = _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)
        job = queue.enqueue()
        result = queue.ran(job.job_id)
        stored = queue.jobs().get(job.job_id)

    assert result.outcome == "settled"
    assert _causes(stored) == [ClassificationItemFailureCause.LANE_REFUSED] * 3


def test_a_reply_the_classification_parse_does_not_accept_fails_as_an_invalid_response(queue: _Queue) -> None:
    job = queue.enqueue()
    queue.answers.reply = json.dumps({"classification": "NOT_A_CLASSIFICATION", "confidence": "0.5"})

    result = queue.ran(job.job_id)

    assert result.outcome == "settled"
    assert _causes(queue.jobs().get(job.job_id)) == [ClassificationItemFailureCause.INVALID_RESPONSE] * 3


# -- profile isolation -------------------------------------------------------------------------------------------------------


def test_a_run_naming_another_profile_is_refused_before_it_reads_or_writes(queue: _Queue) -> None:
    job = queue.enqueue()

    _refusal(queue.run(job.job_id, profile_id=_OTHER_PROFILE), ProfileAccessRefusedError)

    assert queue.jobs().get(job.job_id) == job
    assert queue.runtime.service.runs == []


def test_a_job_another_profile_store_holds_is_unknown_to_this_run(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    answers = _Answers()
    with operation_runtime(tmp_path / "first", None, lane=ON_HOST_LANE, answer=answers) as runtime:
        first = _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)
        job = first.enqueue()

    with operation_runtime(tmp_path / "second", None, lane=ON_HOST_LANE, answer=answers) as runtime:
        second = _Queue(runtime=runtime, operation=operation, movements=(), answers=answers)
        settled = second.run(job.job_id)
        runs = list(runtime.service.runs)

    _refusal(settled, ClassificationJobUnknownError)
    assert runs == []


def test_running_an_identity_no_job_has_is_refused_as_unknown(queue: _Queue) -> None:
    _refusal(queue.run(sha256_hex(b"no such job")), ClassificationJobUnknownError)
