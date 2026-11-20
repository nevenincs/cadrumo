"""Off-host consent of ledger classification jobs, and the apply of accepted proposals, through the real operations.

Every operation runs through the production registry, the real supervisor,
journal and encrypted operand store, inside an enrolled profile whose jobs,
movements and consent ledger are stored by the production encrypted
repositories. The model boundary is the agent service behind the operation's
execution authority: a recording stand-in that resolves one lane, answers each
run with a scripted reply and, as the real service does, refuses a run whose
consent does not admit the lane. A test that reads off this computer opens the
deployment's opt-in and the profile's own eligibility, the standing bars every
grant is checked against.

A grant is the person's: once, for the agent session, or until revoked. Each
read on its strength is recorded in the consent ledger by the revision of the
movement it sends, never by the movement's text.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.model_runs import ModelRunBody, ModelRunLane

from ...adapters.outbound.llm.tests.model_run_support import DEFAULT_LANE, ON_HOST_LANE
from ...adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ...adapters.persistence.profile.classification_jobs import ClassificationJobRepositoryAdapter
from ...adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.ledger.classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
    LedgerClassifyJobAcceptedProposal,
    LedgerClassifyJobApplyRefusal,
    LedgerClassifyJobApplyRequest,
    LedgerClassifyJobApplyResult,
    LedgerClassifyJobAuthoriseRequest,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobConsentGrant,
    LedgerClassifyJobEnqueueRequest,
    LedgerClassifyJobRevokeConsentRequest,
    LedgerClassifyJobRunRequest,
    LedgerClassifyJobRunResult,
)
from ...application.ledger.classification_job_errors import (
    ClassificationJobConsentNotNeededError,
    ClassificationJobLaneChangedError,
    ClassificationJobStaleRevisionError,
)
from ...application.ledger.classification_job_run import movement_revision_id
from ...application.ledger.evidence_errors import LedgerOffHostConsentRequiredError
from ...application.ledger.manual_update import update_manual_transaction_fields
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.operations.error_detail import OperationErrorDetailV1
from ...application.operations.next_step import OperationResolveOffHostConsentStepV1
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.capabilities import ServiceCapability
from ...core.config import override_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationTerminalCondition
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.evidence_consent.record import EvidenceConsentLedgerEntry, EvidenceConsentRecordKind
from ...domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import TransactionCatalogue
from ...domain.user_profile.values import UserProfileFact
from ..ledger_action_composition import compose_ledger_action_ports
from .dependency_operation_gating_support import OperationRuntime, SettledOperation, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OTHER_PROFILE = UUID("0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0")
_DESCRIPTION = "synthetic consent row 8c41"
"""The movements' own text: what the model reads, so it must never reach a consent record, a result or a log."""
_REPLY = json.dumps({"classification": "BUSINESS", "confidence": "0.85", "reason": "synthetic office supplies"})
_MIXED_REPLY = json.dumps({"classification": "MIXED", "confidence": "0.7", "reason": "synthetic shared phone"})
_OTHER_OFF_HOST_LANE = ModelRunLane(
    provider_id=DEFAULT_LANE.provider_id, transport=DEFAULT_LANE.transport, model="example-model-2", reads_off_host=True
)


@dataclass
class _Answers:
    reply: str = _REPLY

    def __call__(self, body: ModelRunBody) -> str:
        del body
        return self.reply


@dataclass(frozen=True)
class _Queue:
    """One enrolled profile, its stored movements, its job repository and its consent ledger."""

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

    def consent_entries(self) -> tuple[EvidenceConsentLedgerEntry, ...]:
        return EvidenceConsentLedger().load_entries()

    def entries_of(self, kind: EvidenceConsentRecordKind) -> list[EvidenceConsentLedgerEntry]:
        return [entry for entry in self.consent_entries() if entry.record_kind is kind]

    def catalogue(self) -> TransactionCatalogue:
        return compose_ledger_action_ports(
            bucket_id=str(self.profile_id), operation=self.operation
        ).transaction_repository.load()

    def settle(self, definition_id: str, payload: BaseModel, result_type: type[BaseModel]) -> SettledOperation:
        return self.runtime.settle(definition_id, payload, result_type)

    def enqueue(
        self, consent: LedgerClassifyJobConsentGrant | None = None, *, profile_id: UUID | None = None
    ) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
            LedgerClassifyJobEnqueueRequest(
                profile_id=profile_id or self.profile_id,
                scope=ClassificationJobScopeKind.SELECTION,
                movement_ids=self.movements,
                consent=consent,
            ),
            LedgerClassifyJobChangeResult,
        )

    def enqueued(self, consent: LedgerClassifyJobConsentGrant | None = None) -> ClassificationJob:
        settled = self.enqueue(consent)
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        assert isinstance(settled.published, LedgerClassifyJobChangeResult)
        return self.jobs().get(settled.published.job.job_id)

    def run(self, job_id: str) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
            LedgerClassifyJobRunRequest(profile_id=self.profile_id, job_id=job_id),
            LedgerClassifyJobRunResult,
        )

    def ran(self, job_id: str) -> ClassificationJob:
        settled = self.run(job_id)
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        return self.jobs().get(job_id)

    def authorise(
        self, job: ClassificationJob, grant: LedgerClassifyJobConsentGrant, *, expected_revision: int | None = None
    ) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
            LedgerClassifyJobAuthoriseRequest(
                profile_id=self.profile_id,
                job_id=job.job_id,
                expected_revision=job.revision if expected_revision is None else expected_revision,
                consent=grant,
            ),
            LedgerClassifyJobChangeResult,
        )

    def revoke(self, job: ClassificationJob) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
            LedgerClassifyJobRevokeConsentRequest(
                profile_id=self.profile_id, job_id=job.job_id, expected_revision=job.revision
            ),
            LedgerClassifyJobChangeResult,
        )

    def apply(
        self,
        job: ClassificationJob,
        accepted: tuple[LedgerClassifyJobAcceptedProposal, ...],
        *,
        expected_revision: int | None = None,
        profile_id: UUID | None = None,
    ) -> SettledOperation:
        return self.runtime.settle(
            LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID,
            LedgerClassifyJobApplyRequest(
                profile_id=profile_id or self.profile_id,
                job_id=job.job_id,
                expected_revision=job.revision if expected_revision is None else expected_revision,
                accepted=accepted,
            ),
            LedgerClassifyJobApplyResult,
        )

    def applied(
        self, job: ClassificationJob, accepted: tuple[LedgerClassifyJobAcceptedProposal, ...]
    ) -> LedgerClassifyJobApplyResult:
        settled = self.apply(job, accepted)
        assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
        assert isinstance(settled.published, LedgerClassifyJobApplyResult)
        assert _DESCRIPTION not in settled.published.model_dump_json(), "an apply published a movement's text"
        return settled.published

    def edit_notes(self, movement_id: str, notes: str) -> None:
        update_manual_transaction_fields(
            bucket_id=str(self.profile_id),
            transaction_id=movement_id,
            patch=ManualLedgerTransactionPatch(notes=notes),
            actor="classification-consent-test",
            source_command="synthetic edit",
            ports=compose_ledger_action_ports(bucket_id=str(self.profile_id), operation=self.operation),
        )

    def sign_in_again(self) -> None:
        """Move the open profile session to a new opening instant, as a new sign-in for the same key does."""
        session = current_active_bucket_session()
        assert session is not None
        session.retarget_lifetime(
            opened_at=session.opened_at + timedelta(seconds=1), idle_minutes=30, deadline=session.absolute_deadline
        )


def _seed(runtime: OperationRuntime, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    ports = compose_ledger_action_ports(bucket_id=str(runtime.profile_id), operation=operation)
    year = now().year - 1
    return tuple(
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(runtime.profile_id),
                booked_date=booked,
                amount=Decimal("31.40") + index,
                direction=TransactionDirection.OUTGOING,
                description=f"{_DESCRIPTION} {index}",
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                actor="classification-consent-test",
            ),
            ports=ports,
            occurred_at=now(),
        ).ref.transaction_id
        for index, booked in enumerate((date(year, 3, 4), date(year, 6, 11), date(year, 9, 23)))
    )


def _grant(scope: ClassificationConsentScope, lane: ModelRunLane = DEFAULT_LANE) -> LedgerClassifyJobConsentGrant:
    return LedgerClassifyJobConsentGrant(
        scope=scope, provider_id=lane.provider_id, connection=lane.transport, model=lane.model
    )


@pytest.fixture
def answers() -> _Answers:
    return _Answers()


@pytest.fixture
def off_host(tmp_path: Path, operation: PinnedAuthorityOperation, answers: _Answers) -> Iterator[_Queue]:
    """A profile the agent reads for off this computer, with the deployment and the profile admitting it."""
    with operation_runtime(tmp_path, None, lane=DEFAULT_LANE, answer=answers) as runtime:
        upsert_test_profile_facts(
            runtime.profile_id,
            (UserProfileFact(path=ServiceCapability.CLOUD_EVIDENCE_UPLOAD.schema_path, value=True),),
        )
        with override_settings(cadrumo_evidence_cloud_upload_permitted=True):
            yield _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)


@pytest.fixture
def on_host(tmp_path: Path, operation: PinnedAuthorityOperation, answers: _Answers) -> Iterator[_Queue]:
    with operation_runtime(tmp_path, None, lane=ON_HOST_LANE, answer=answers) as runtime:
        yield _Queue(runtime=runtime, operation=operation, movements=_seed(runtime, operation), answers=answers)


def _refusal(settled: SettledOperation, error_type: type[Exception]) -> OperationErrorDetailV1:
    assert settled.condition is OperationTerminalCondition.REFUSED, settled
    detail = settled.published
    assert isinstance(detail, OperationErrorDetailV1), settled
    assert detail.error_code == get_registered_error_code(error_type).code
    assert _DESCRIPTION not in detail.model_dump_json(), "a refusal published a movement's text"
    return detail


def _causes(job: ClassificationJob) -> list[ClassificationItemFailureCause | None]:
    return [item.failure_cause for item in job.items]


def _states(job: ClassificationJob) -> list[ClassificationItemState]:
    return [item.state for item in job.items]


def _accepted(job: ClassificationJob, index: int, business_pct: str | None = None) -> LedgerClassifyJobAcceptedProposal:
    item = job.items[index]
    assert item.proposal is not None
    return LedgerClassifyJobAcceptedProposal(
        movement_id=item.movement_id,
        movement_revision_id=item.proposal.movement_revision_id,
        business_pct=business_pct,
    )


# -- grants at enqueue -----------------------------------------------------------------------------------------------------


def test_a_once_grant_is_recorded_for_its_job_and_lane_and_each_read_is_recorded_by_the_revision_it_sends(
    off_host: _Queue, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    revisions = {movement_revision_id(off_host.catalogue().transactions[movement]) for movement in off_host.movements}

    job = off_host.enqueued(_grant(ClassificationConsentScope.ONCE))
    stored = off_host.ran(job.job_id)

    assert job.consent is not None
    assert job.consent.scope is ClassificationConsentScope.ONCE
    (granted,) = off_host.entries_of(EvidenceConsentRecordKind.GRANT)
    assert granted.grant is not None
    assert (granted.grant.grant_id, granted.grant.job_id) == (job.consent.consent_reference, job.job_id)
    assert (granted.provider, granted.grant.transport, granted.model, granted.grant.task_kind) == (
        DEFAULT_LANE.provider_id,
        DEFAULT_LANE.transport,
        DEFAULT_LANE.model,
        "classification",
    )
    assert _states(stored) == [ClassificationItemState.PROPOSED] * 3
    dispatches = off_host.entries_of(EvidenceConsentRecordKind.DISPATCH)
    assert {entry.evidence_content_address for entry in dispatches} == revisions
    assert len(off_host.runtime.service.runs) == 3
    for entry in off_host.consent_entries():
        assert _DESCRIPTION not in entry.model_dump_json(), "a consent record carries a movement's text"
    assert _DESCRIPTION not in caplog.text, "a log line carries a movement's text"


def test_a_once_grant_covers_no_other_job(off_host: _Queue) -> None:
    first = off_host.enqueued(_grant(ClassificationConsentScope.ONCE))

    refused = off_host.enqueue()

    detail = _refusal(refused, LedgerOffHostConsentRequiredError)
    assert isinstance(detail.next_step, OperationResolveOffHostConsentStepV1)
    assert off_host.jobs().list_jobs() == (first,), "a job was stored on another job's once grant"


def test_a_session_grant_covers_later_jobs_until_the_profile_signs_in_again(off_host: _Queue) -> None:
    first = off_host.enqueued(_grant(ClassificationConsentScope.AGENT_SESSION))
    second = off_host.enqueued()
    assert first.consent is not None
    assert second.consent == first.consent, "a later enqueue did not take the session's grant"

    off_host.sign_in_again()
    settled = off_host.run(second.job_id)

    detail = _refusal(settled, LedgerOffHostConsentRequiredError)
    assert isinstance(detail.next_step, OperationResolveOffHostConsentStepV1)
    stored = off_host.jobs().get(second.job_id)
    assert _causes(stored) == [ClassificationItemFailureCause.CONSENT_EXPIRED] * 3
    assert off_host.runtime.service.runs == [], "a read was sent on a session grant from an earlier sign-in"
    _refusal(off_host.enqueue(), LedgerOffHostConsentRequiredError)


def test_a_remembered_grant_outlasts_a_new_sign_in_and_covers_later_jobs(off_host: _Queue) -> None:
    off_host.enqueued(_grant(ClassificationConsentScope.REMEMBERED))
    off_host.sign_in_again()

    later = off_host.enqueued()
    stored = off_host.ran(later.job_id)

    assert later.consent is not None
    assert later.consent.scope is ClassificationConsentScope.REMEMBERED
    assert _states(stored) == [ClassificationItemState.PROPOSED] * 3


def test_a_grant_for_another_lane_than_the_agent_reads_with_is_refused_and_records_nothing(off_host: _Queue) -> None:
    detail = _refusal(
        off_host.enqueue(_grant(ClassificationConsentScope.ONCE, _OTHER_OFF_HOST_LANE)),
        ClassificationJobLaneChangedError,
    )

    assert ("model", DEFAULT_LANE.model) in {(entry.key, entry.value) for entry in detail.context}
    assert off_host.jobs().list_jobs() == ()
    assert off_host.consent_entries() == ()


def test_a_grant_the_deployment_does_not_admit_is_refused_and_records_nothing(off_host: _Queue) -> None:
    with override_settings(cadrumo_evidence_cloud_upload_permitted=False):
        settled = off_host.enqueue(_grant(ClassificationConsentScope.REMEMBERED))

    detail = _refusal(settled, LedgerOffHostConsentRequiredError)
    assert isinstance(detail.next_step, OperationResolveOffHostConsentStepV1)
    assert off_host.jobs().list_jobs() == ()
    assert off_host.consent_entries() == ()


def test_a_grant_for_a_lane_that_reads_on_this_computer_is_refused_as_not_needed(on_host: _Queue) -> None:
    _refusal(
        on_host.enqueue(_grant(ClassificationConsentScope.ONCE, ON_HOST_LANE)), ClassificationJobConsentNotNeededError
    )

    assert on_host.jobs().list_jobs() == ()


# -- revocation and lane changes at dispatch ----------------------------------------------------------------------------------


def test_a_revoked_grant_fails_every_movement_still_to_ask_and_sends_nothing(off_host: _Queue) -> None:
    job = off_host.enqueued(_grant(ClassificationConsentScope.REMEMBERED))

    revoked = off_host.revoke(job)
    assert revoked.condition is OperationTerminalCondition.SUCCEEDED, revoked
    (revocation,) = off_host.entries_of(EvidenceConsentRecordKind.REVOCATION)
    assert job.consent is not None
    assert revocation.revoked_grant_id == job.consent.consent_reference
    settled = off_host.run(job.job_id)

    detail = _refusal(settled, LedgerOffHostConsentRequiredError)
    assert isinstance(detail.next_step, OperationResolveOffHostConsentStepV1)
    assert _causes(off_host.jobs().get(job.job_id)) == [ClassificationItemFailureCause.CONSENT_REVOKED] * 3
    assert off_host.runtime.service.runs == []
    _refusal(off_host.enqueue(), LedgerOffHostConsentRequiredError)


def test_a_lane_changed_after_the_grant_refuses_the_run_without_reading_on_the_new_lane(off_host: _Queue) -> None:
    job = off_host.enqueued(_grant(ClassificationConsentScope.REMEMBERED))
    off_host.runtime.service.serve_lane(_OTHER_OFF_HOST_LANE)

    detail = _refusal(off_host.run(job.job_id), ClassificationJobLaneChangedError)

    assert ("model", _OTHER_OFF_HOST_LANE.model) in {(entry.key, entry.value) for entry in detail.context}
    assert _causes(off_host.jobs().get(job.job_id)) == [ClassificationItemFailureCause.LANE_CHANGED] * 3
    assert off_host.runtime.service.runs == []
    assert off_host.entries_of(EvidenceConsentRecordKind.DISPATCH) == []


# -- authorise --------------------------------------------------------------------------------------------------------------


def test_authorising_a_job_failed_for_its_lane_binds_it_to_the_new_lane_and_asks_again(off_host: _Queue) -> None:
    job = off_host.enqueued(_grant(ClassificationConsentScope.ONCE))
    off_host.runtime.service.serve_lane(_OTHER_OFF_HOST_LANE)
    _refusal(off_host.run(job.job_id), ClassificationJobLaneChangedError)
    failed = off_host.jobs().get(job.job_id)

    settled = off_host.authorise(failed, _grant(ClassificationConsentScope.ONCE, _OTHER_OFF_HOST_LANE))

    assert settled.condition is OperationTerminalCondition.SUCCEEDED, settled
    assert isinstance(settled.published, LedgerClassifyJobChangeResult)
    assert settled.published.outcome == "authorised"
    authorised = off_host.jobs().get(job.job_id)
    assert authorised.revision == failed.revision + 1
    assert (authorised.status, authorised.lane.model) == (ClassificationJobStatus.QUEUED, _OTHER_OFF_HOST_LANE.model)
    assert _states(authorised) == [ClassificationItemState.PENDING] * 3
    assert authorised.consent is not None and failed.consent is not None
    assert authorised.consent.consent_reference != failed.consent.consent_reference
    assert _states(off_host.ran(job.job_id)) == [ClassificationItemState.PROPOSED] * 3
    assert {header.consent is not None for header, _body in off_host.runtime.service.runs} == {True}


def test_an_authorise_at_a_revision_the_job_has_moved_past_is_refused_and_records_no_grant(off_host: _Queue) -> None:
    job = off_host.enqueued(_grant(ClassificationConsentScope.ONCE))
    off_host.revoke(job)
    off_host.run(job.job_id)
    entries_before = off_host.consent_entries()
    stored = off_host.jobs().get(job.job_id)

    settled = off_host.authorise(stored, _grant(ClassificationConsentScope.ONCE), expected_revision=job.revision)

    _refusal(settled, ClassificationJobStaleRevisionError)
    assert off_host.jobs().get(job.job_id) == stored
    assert off_host.consent_entries() == entries_before


def test_authorising_a_job_on_a_lane_that_reads_on_this_computer_is_refused_as_not_needed(on_host: _Queue) -> None:
    job = on_host.enqueued()

    _refusal(
        on_host.authorise(job, _grant(ClassificationConsentScope.ONCE, ON_HOST_LANE)),
        ClassificationJobConsentNotNeededError,
    )

    assert on_host.jobs().get(job.job_id) == job


# -- apply --------------------------------------------------------------------------------------------------------------------


def test_a_run_applies_nothing_and_an_apply_writes_only_the_accepted_proposals(on_host: _Queue) -> None:
    catalogue_before = on_host.catalogue()
    job = on_host.ran(on_host.enqueued().job_id)
    assert on_host.catalogue() == catalogue_before, "a run applied a proposal"

    result = on_host.applied(job, (_accepted(job, 0), _accepted(job, 2)))

    assert [(item.movement_id, item.outcome) for item in result.items] == [
        (job.items[0].movement_id, "applied"),
        (job.items[2].movement_id, "applied"),
    ]
    stored = on_host.jobs().get(job.job_id)
    assert _states(stored) == [
        ClassificationItemState.APPLIED,
        ClassificationItemState.PROPOSED,
        ClassificationItemState.APPLIED,
    ]
    assert result.job.revision == stored.revision == job.revision + 1
    catalogue = on_host.catalogue().transactions
    assert [catalogue[movement].business_classification for movement in on_host.movements] == [
        BusinessClassification.BUSINESS,
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.BUSINESS,
    ]
    proposal = job.items[0].proposal
    assert proposal is not None
    assert catalogue[on_host.movements[0]].classified_by == proposal.provenance


def test_an_accepted_proposal_whose_movement_changed_is_refused_as_stale_and_marked_stale(on_host: _Queue) -> None:
    job = on_host.ran(on_host.enqueued().job_id)
    on_host.edit_notes(on_host.movements[1], "synthetic note after the proposal")

    result = on_host.applied(job, (_accepted(job, 0), _accepted(job, 1)))

    assert [(item.outcome, item.refusal) for item in result.items] == [
        ("applied", None),
        ("refused", LedgerClassifyJobApplyRefusal.STALE),
    ]
    stored = on_host.jobs().get(job.job_id)
    assert _states(stored)[:2] == [ClassificationItemState.APPLIED, ClassificationItemState.STALE]
    movement = on_host.catalogue().transactions[on_host.movements[1]]
    assert movement.business_classification is BusinessClassification.NOT_YET_PROCESSED


def test_an_applied_proposal_is_not_applied_twice(on_host: _Queue) -> None:
    job = on_host.ran(on_host.enqueued().job_id)
    on_host.applied(job, (_accepted(job, 0),))
    stored = on_host.jobs().get(job.job_id)
    catalogue = on_host.catalogue()

    result = on_host.applied(stored, (_accepted(job, 0),))

    assert [(item.outcome, item.refusal) for item in result.items] == [
        ("refused", LedgerClassifyJobApplyRefusal.NOT_PROPOSED)
    ]
    assert on_host.catalogue() == catalogue


def test_a_mixed_proposal_needs_the_persons_business_share(on_host: _Queue) -> None:
    on_host.answers.reply = _MIXED_REPLY
    job = on_host.ran(on_host.enqueued().job_id)

    result = on_host.applied(job, (_accepted(job, 0), _accepted(job, 1, business_pct="0.4")))

    assert [(item.outcome, item.refusal) for item in result.items] == [
        ("refused", LedgerClassifyJobApplyRefusal.BUSINESS_PCT_REQUIRED),
        ("applied", None),
    ]
    movement = on_host.catalogue().transactions[on_host.movements[1]]
    assert (movement.business_classification, movement.business_pct) == (BusinessClassification.MIXED, Decimal("0.4"))


def test_an_apply_at_a_stale_job_revision_is_refused_and_writes_nothing(on_host: _Queue) -> None:
    job = on_host.ran(on_host.enqueued().job_id)
    catalogue = on_host.catalogue()

    _refusal(
        on_host.apply(job, (_accepted(job, 0),), expected_revision=job.revision - 1),
        ClassificationJobStaleRevisionError,
    )

    assert on_host.catalogue() == catalogue
    assert on_host.jobs().get(job.job_id) == job


# -- profile isolation ---------------------------------------------------------------------------------------------------------


def test_consent_and_apply_operations_naming_another_profile_are_refused_before_they_read_or_write(
    off_host: _Queue,
) -> None:
    job = off_host.enqueued(_grant(ClassificationConsentScope.ONCE))
    entries = off_host.consent_entries()
    catalogue = off_host.catalogue()

    _refusal(
        off_host.enqueue(_grant(ClassificationConsentScope.REMEMBERED), profile_id=_OTHER_PROFILE),
        ProfileAccessRefusedError,
    )
    _refusal(
        off_host.settle(
            LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
            LedgerClassifyJobAuthoriseRequest(
                profile_id=_OTHER_PROFILE,
                job_id=job.job_id,
                expected_revision=job.revision,
                consent=_grant(ClassificationConsentScope.REMEMBERED),
            ),
            LedgerClassifyJobChangeResult,
        ),
        ProfileAccessRefusedError,
    )
    _refusal(
        off_host.settle(
            LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
            LedgerClassifyJobRevokeConsentRequest(
                profile_id=_OTHER_PROFILE, job_id=job.job_id, expected_revision=job.revision
            ),
            LedgerClassifyJobChangeResult,
        ),
        ProfileAccessRefusedError,
    )
    foreign_accept = LedgerClassifyJobAcceptedProposal(
        movement_id=job.items[0].movement_id,
        movement_revision_id=movement_revision_id(catalogue.transactions[job.items[0].movement_id]),
    )
    _refusal(off_host.apply(job, (foreign_accept,), profile_id=_OTHER_PROFILE), ProfileAccessRefusedError)

    assert off_host.consent_entries() == entries
    assert off_host.jobs().list_jobs() == (job,)
    assert off_host.catalogue() == catalogue
