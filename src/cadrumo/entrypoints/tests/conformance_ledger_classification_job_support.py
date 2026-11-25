"""Ledger classification jobs through the real supervisor matrix.

Each job read or change runs against a job stored through the production
encrypted repository. The enqueue meets a runtime with no model-run authority,
so its lane lookup is refused as an unreachable reader before anything is
stored. The run meets the same unreachable reader at its first movement, fails
every movement as unavailable, settles the job and refuses with the reader's
refusal; no ledger fact is written. An authorise meets the same unreachable
lane lookup and records nothing. A revoke on a job that reads on this computer
is refused as needing no consent. An apply writes the one proposal the person
accepted through the reviewed classification path and marks it applied.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...adapters.persistence.profile.classification_jobs import ClassificationJobRepositoryAdapter
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.ledger.classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
    LedgerClassifyJobAcceptedProposal,
    LedgerClassifyJobApplyRequest,
    LedgerClassifyJobApplyResult,
    LedgerClassifyJobAuthoriseRequest,
    LedgerClassifyJobCancelRequest,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobConsentGrant,
    LedgerClassifyJobDismissRequest,
    LedgerClassifyJobEnqueueRequest,
    LedgerClassifyJobListRequest,
    LedgerClassifyJobListResult,
    LedgerClassifyJobProjection,
    LedgerClassifyJobReadRequest,
    LedgerClassifyJobReadResult,
    LedgerClassifyJobRetryRequest,
    LedgerClassifyJobRevokeConsentRequest,
    LedgerClassifyJobRunRequest,
)
from ...application.ledger.classification_job_errors import ClassificationJobConsentNotNeededError
from ...application.ledger.classification_job_run import movement_revision_id
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
    ClassificationProposal,
)
from ...domain.transactions.enums import BusinessClassification
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import ledger_action_ports, ledger_unchanged_verifier, seed_manual_transaction

#: A synthetic on-host lane: the stored job only names it, nothing reads with it here.
_LANE = ClassificationJobLane(
    provider_id="conformance-local", transport="local", model="conformance-model", reads_off_host=False
)


def _jobs(context: ConformanceFamilyContext) -> ClassificationJobRepositoryAdapter:
    bucket_id = str(context.profile_id)
    return ClassificationJobRepositoryAdapter(
        objects=secure_object_repository_for_bucket(bucket_id), bucket_id=bucket_id
    )


def _stored_job(context: ConformanceFamilyContext, *, failed: bool) -> ClassificationJob:
    """Store a queued job over two seeded movements, finished with the second one failed when ``failed``."""
    movements = tuple(
        seed_manual_transaction(
            context,
            booked_date=date(filing_year_envelope().horizon, 4, day),
            amount=Decimal("12.50"),
            description="classification job row",
        )
        for day in (7, 8)
    )
    jobs = _jobs(context)
    job = ClassificationJob.enqueue(
        bucket_id=str(context.profile_id),
        scope=ClassificationJobScope(kind=ClassificationJobScopeKind.SELECTION),
        movement_ids=movements,
        lane=_LANE,
        consent=None,
        at=now(),
    )
    jobs.create(job)
    if not failed:
        return job
    running = job.successor(
        at=now(),
        status=ClassificationJobStatus.RUNNING,
        items=tuple(item.transitioned(ClassificationItemState.RUNNING) for item in job.items),
    )
    jobs.update(running)
    first, second = running.items
    settled = running.successor(
        at=now(),
        status=ClassificationJobStatus.SETTLED,
        items=(
            first.transitioned(ClassificationItemState.FAILED, failure_cause=ClassificationItemFailureCause.TIMED_OUT),
            second.transitioned(
                ClassificationItemState.FAILED, failure_cause=ClassificationItemFailureCause.INVALID_RESPONSE
            ),
        ),
    )
    jobs.update(settled)
    return settled


def _prepare_enqueue(context: ConformanceFamilyContext) -> ConformancePreparation:
    movement = seed_manual_transaction(
        context,
        booked_date=date(filing_year_envelope().horizon, 4, 2),
        amount=Decimal("9.90"),
        description="classification job enqueue row",
    )
    ledger_unchanged = ledger_unchanged_verifier(context)

    def verify(outcome: ConformanceOutcome) -> None:
        ledger_unchanged(outcome)
        assert _jobs(context).list_jobs() == ()

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobEnqueueRequest(
            profile_id=context.profile_id, scope=ClassificationJobScopeKind.SINGLE, movement_ids=(movement,)
        ),
        verify=verify,
    )


def _prepare_read(context: ConformanceFamilyContext) -> ConformancePreparation:
    job = _stored_job(context, failed=True)
    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobReadRequest(profile_id=context.profile_id, job_id=job.job_id),
        expected_result=LedgerClassifyJobReadResult(
            profile_id=context.profile_id, job=LedgerClassifyJobProjection.from_job(job)
        ),
    )


def _prepare_list(context: ConformanceFamilyContext) -> ConformancePreparation:
    job = _stored_job(context, failed=False)

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(LedgerClassifyJobListResult)
        assert result.profile_id == context.profile_id
        assert result.jobs == (LedgerClassifyJobProjection.from_job(job),)
        assert result.more is False

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobListRequest(profile_id=context.profile_id),
        verify=verify,
    )


def _prepare_change(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    # A cancel needs a job not yet finished; a retry and a dismiss need a finished one.
    job = _stored_job(context, failed=definition_id != LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID)
    expected: dict[str, tuple[str, ClassificationJobStatus, ClassificationItemState]] = {
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID: (
            "cancelled",
            ClassificationJobStatus.CANCELLED,
            ClassificationItemState.CANCELLED,
        ),
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID: (
            "retried",
            ClassificationJobStatus.QUEUED,
            ClassificationItemState.PENDING,
        ),
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID: (
            "dismissed",
            ClassificationJobStatus.DISMISSED,
            ClassificationItemState.FAILED,
        ),
    }
    outcome_word, status, item_state = expected[definition_id]
    request_type = {
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID: LedgerClassifyJobCancelRequest,
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID: LedgerClassifyJobRetryRequest,
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID: LedgerClassifyJobDismissRequest,
    }[definition_id]

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(LedgerClassifyJobChangeResult)
        assert result.profile_id == context.profile_id
        assert (result.outcome, result.job.status, result.job.revision) == (outcome_word, status, job.revision + 1)
        assert {item.state for item in result.job.items} == {item_state}
        stored = _jobs(context).get(job.job_id)
        assert (stored.status, stored.revision) == (status, job.revision + 1)

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        request_type(profile_id=context.profile_id, job_id=job.job_id, expected_revision=job.revision),
        verify=verify,
    )


def _prepare_run(context: ConformanceFamilyContext) -> ConformancePreparation:
    job = _stored_job(context, failed=False)
    ledger_unchanged = ledger_unchanged_verifier(context)

    def verify(outcome: ConformanceOutcome) -> None:
        ledger_unchanged(outcome)
        stored = _jobs(context).get(job.job_id)
        assert stored.status is ClassificationJobStatus.SETTLED
        assert {item.failure_cause for item in stored.items} == {ClassificationItemFailureCause.MODEL_UNAVAILABLE}

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobRunRequest(profile_id=context.profile_id, job_id=job.job_id),
        verify=verify,
    )


def _prepare_authorise(context: ConformanceFamilyContext) -> ConformancePreparation:
    job = _stored_job(context, failed=False)
    ledger_unchanged = ledger_unchanged_verifier(context)

    def verify(outcome: ConformanceOutcome) -> None:
        ledger_unchanged(outcome)
        assert _jobs(context).get(job.job_id) == job

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobAuthoriseRequest(
            profile_id=context.profile_id,
            job_id=job.job_id,
            expected_revision=job.revision,
            consent=LedgerClassifyJobConsentGrant(
                scope=ClassificationConsentScope.ONCE,
                provider_id="conformance-remote",
                connection="api",
                model="conformance-remote-model",
            ),
        ),
        verify=verify,
    )


def _prepare_revoke_consent(context: ConformanceFamilyContext) -> ConformancePreparation:
    job = _stored_job(context, failed=False)

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        assert _jobs(context).get(job.job_id) == job

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobRevokeConsentRequest(
            profile_id=context.profile_id, job_id=job.job_id, expected_revision=job.revision
        ),
        verify=verify,
    )


def _prepare_apply(context: ConformanceFamilyContext) -> ConformancePreparation:
    """Store a settled job whose single movement holds a personal proposal bound to its current revision."""
    movement = seed_manual_transaction(
        context,
        booked_date=date(filing_year_envelope().horizon, 4, 9),
        amount=Decimal("7.30"),
        description="classification job apply row",
    )
    transaction = ledger_action_ports(context).transaction_repository.load().transactions[movement]
    jobs = _jobs(context)
    job = ClassificationJob.enqueue(
        bucket_id=str(context.profile_id),
        scope=ClassificationJobScope(kind=ClassificationJobScopeKind.SINGLE),
        movement_ids=(movement,),
        lane=_LANE,
        consent=None,
        at=now(),
    )
    jobs.create(job)
    running = job.successor(
        at=now(),
        status=ClassificationJobStatus.RUNNING,
        items=tuple(item.transitioned(ClassificationItemState.RUNNING) for item in job.items),
    )
    jobs.update(running)
    revision = movement_revision_id(transaction)
    settled = running.successor(
        at=now(),
        status=ClassificationJobStatus.SETTLED,
        items=tuple(
            item.transitioned(
                ClassificationItemState.PROPOSED,
                proposal=ClassificationProposal(
                    movement_revision_id=revision,
                    classification=BusinessClassification.PERSONAL,
                    confidence=Decimal("0.9"),
                    provenance="llm:local-text:conformance-model",
                    proposed_at=now(),
                ),
            )
            for item in running.items
        ),
    )
    jobs.update(settled)

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(LedgerClassifyJobApplyResult)
        assert [(item.movement_id, item.outcome) for item in result.items] == [(movement, "applied")]
        stored = _jobs(context).get(job.job_id)
        assert [item.state for item in stored.items] == [ClassificationItemState.APPLIED]
        applied = ledger_action_ports(context).transaction_repository.load().transactions[movement]
        assert applied.business_classification is BusinessClassification.PERSONAL

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerClassifyJobApplyRequest(
            profile_id=context.profile_id,
            job_id=job.job_id,
            expected_revision=settled.revision,
            accepted=(LedgerClassifyJobAcceptedProposal(movement_id=movement, movement_revision_id=revision),),
        ),
        verify=verify,
    )


_PREPARE = {
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID: _prepare_enqueue,
    LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID: _prepare_read,
    LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID: _prepare_list,
    LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID: _prepare_change,
    LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID: _prepare_change,
    LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID: _prepare_change,
    LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID: _prepare_run,
    LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID: _prepare_authorise,
    LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID: _prepare_revoke_consent,
    LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID: _prepare_apply,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARE.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no classification job conformance scenario for {context.definition.definition_id}")
    return prepare(context)


# With no model-run authority the lane lookup finds the agent service unreachable,
# which the composition raises as the reader refusal. ledger_llm_composition.py
# `resolve_reading_lane`.
_READER_UNAVAILABLE_REFUSAL = get_registered_error_code(PurchaseInvoiceEvidenceReaderError).code


def _succeeded(definition_id: str, effect: OperationEffect) -> RegisteredExecutorConformanceCase:
    return RegisteredExecutorConformanceCase(
        definition_id, OperationTerminalCondition.SUCCEEDED, effect, (definition_id,)
    )


LEDGER_CLASSIFICATION_JOB_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,),
            expected_refusal_ref=_READER_UNAVAILABLE_REFUSAL,
        ),
        _succeeded(LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID, OperationEffect.NONE),
        _succeeded(LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID, OperationEffect.NONE),
        _succeeded(LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID, OperationEffect.UPDATED),
        _succeeded(LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID, OperationEffect.UPDATED),
        _succeeded(LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID, OperationEffect.UPDATED),
        RegisteredExecutorConformanceCase(
            LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.UPDATED,
            (LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,),
            expected_refusal_ref=_READER_UNAVAILABLE_REFUSAL,
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,),
            expected_refusal_ref=_READER_UNAVAILABLE_REFUSAL,
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,),
            expected_refusal_ref=get_registered_error_code(ClassificationJobConsentNotNeededError).code,
        ),
        _succeeded(LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID, OperationEffect.UPDATED),
    ),
    prepare=_prepare,
)
