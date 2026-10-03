"""Registered automation effects reflect actual encrypted custody transitions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, SecretBytes

from cadrumo.adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    NOW,
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.application.operations.authorization import OperationExecutionAuthority
from cadrumo.application.operations.composition import OperationComposedServices, compose_operation_services
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationSecureReferenceStore
from cadrumo.application.user_profile.access_contracts import AccessAction, AuthorityState
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentControlState,
    EnrollmentReceipt,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_execution import ThreadedAutomationAdministration
from cadrumo.application.user_profile.automation_operations import (
    AutomationAdministrationExecutor,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _services(
    subject: AdministrationSubject,
    authority_operation: PinnedAuthorityOperation,
    *,
    execution_authority: OperationExecutionAuthority | None = None,
) -> tuple[OperationComposedServices, OperationJournalRepository, OperationSecureReferenceStore]:
    registry = build_production_operation_registry(
        automation_administration_factory=lambda _context, _profile: ThreadedAutomationAdministration(subject.service)
    )
    journal = OperationJournalRepository(storage_root=subject.store.root / "operations")
    operands = operation_secure_reference_repository()
    services = compose_operation_services(
        registry=registry,
        authority_operation=authority_operation,
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=subject.store.root / "operations"),
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: NOW,
        lease_duration=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=5),
        cleanup_timeout=timedelta(seconds=20),
        financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(
            root=subject.store.root / "financial"
        ),
        execution_authority=execution_authority,
    )
    return services, journal, operands


async def _invoke(
    services: OperationComposedServices,
    journal: OperationJournalRepository,
    operands: OperationSecureReferenceStore,
    subject: AdministrationSubject,
    *,
    action: str,
    request_id: UUID,
    secret: bytes | None = None,
    review_digest: str | None = None,
) -> tuple[OperationEffect, EnrollmentReceipt]:
    submitted = await services.submission.submit(
        OperationRequest(
            definition_id=f"user-profile.automation-{action}",
            subject_ref=profile_operation_subject(str(subject.store.binding.profile_id)),
            payload=AutomationOperationRequest(
                profile_id=subject.store.binding.profile_id,
                request_id=request_id,
                review_digest=review_digest,
            ),
        ),
        actor_ref="operator:synthetic-human",
    )
    requirement = submitted.receipt.secret_requirement
    if requirement is not None:
        assert secret is not None
        buffer = bytearray(secret)
        await services.submission.submit_secret(requirement, buffer)
        assert buffer == bytearray(len(secret))
    else:
        assert secret is None
    await services.submission.start(submitted.receipt.operation_id)
    await asyncio.wait_for(services.submission.settled(submitted.receipt.operation_id), timeout=20)
    settled = await journal.load(submitted.receipt.operation_id)
    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED, settled
    assert settled.terminal_receipt is not None
    assert settled.terminal_receipt.result_ref is not None
    receipt = await operands.resolve(settled.terminal_receipt.result_ref, EnrollmentReceipt)
    assert receipt.request_id == request_id
    assert receipt.profile_id == subject.store.binding.profile_id
    return settled.effect, receipt


def test_registered_request_and_decline_retries_keep_encrypted_receipt_and_none_effect(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with administration_subject(tmp_path) as subject:
        services, journal, operands = _services(subject, authority_operation)

        async def run() -> None:
            try:
                request_id = uuid4()
                proposal = subject.proposal.model_dump_json().encode()
                first_effect, first = await _invoke(
                    services, journal, operands, subject, action="request", request_id=request_id, secret=proposal
                )
                assert first_effect is OperationEffect.UPDATED
                assert first.stage is EnrollmentStage.REQUESTED
                requested_revision = subject.store.enrollment_state().revision

                repeated_effect, repeated = await _invoke(
                    services, journal, operands, subject, action="request", request_id=request_id, secret=proposal
                )
                assert repeated_effect is OperationEffect.NONE
                assert repeated == first
                assert subject.store.enrollment_state().revision == requested_revision

                declined_effect, declined = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="decline",
                    request_id=request_id,
                    review_digest=first.review_digest,
                )
                assert declined_effect is OperationEffect.UPDATED
                assert declined.stage is EnrollmentStage.DECLINED
                declined_revision = subject.store.enrollment_state().revision

                repeated_effect, repeated = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="decline",
                    request_id=request_id,
                    review_digest=declined.review_digest,
                )
                assert repeated_effect is OperationEffect.NONE
                assert repeated == declined
                assert subject.store.enrollment_state().revision == declined_revision
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_registered_approve_retry_keeps_activated_receipt_without_second_delivery(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with administration_subject(tmp_path) as subject:
        services, journal, operands = _services(subject, authority_operation)

        async def run() -> None:
            try:
                request_id = uuid4()
                _, requested = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="request",
                    request_id=request_id,
                    secret=subject.proposal.model_dump_json().encode(),
                )
                first_effect, approved = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="approve",
                    request_id=request_id,
                    secret=PROFILE_INPUT.encode(),
                    review_digest=requested.review_digest,
                )
                assert first_effect is OperationEffect.UPDATED
                assert approved.stage is EnrollmentStage.COMPLETE
                assert subject.owner.delivery.deliveries == 1
                approved_revision = subject.store.enrollment_state().revision

                repeated_effect, repeated = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="approve",
                    request_id=request_id,
                    secret=PROFILE_INPUT.encode(),
                    review_digest=approved.review_digest,
                )
                assert repeated_effect is OperationEffect.NONE
                assert repeated == approved
                assert subject.store.enrollment_state().revision == approved_revision
                assert subject.owner.delivery.deliveries == 1
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_post_publication_failure_keeps_unknown_effect_and_committed_record(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed acknowledgement after real custody publication cannot imply rollback."""
    with administration_subject(tmp_path) as subject:
        services, journal, _operands = _services(subject, authority_operation)
        original_publish = subject.store.publish_enrollment

        def publish_then_fail(state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
            original_publish(state, fresh_dek=fresh_dek)
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

        async def run() -> None:
            try:
                request_id = uuid4()
                submitted = await services.submission.submit(
                    OperationRequest(
                        definition_id="user-profile.automation-request",
                        subject_ref=profile_operation_subject(str(subject.store.binding.profile_id)),
                        payload=AutomationOperationRequest(
                            profile_id=subject.store.binding.profile_id, request_id=request_id
                        ),
                    ),
                    actor_ref="operator:synthetic-human",
                )
                requirement = submitted.receipt.secret_requirement
                assert requirement is not None
                secret = bytearray(subject.proposal.model_dump_json().encode())
                await services.submission.submit_secret(requirement, secret)
                assert secret == bytearray(len(secret))
                await services.submission.start(submitted.receipt.operation_id)
                await asyncio.wait_for(services.submission.settled(submitted.receipt.operation_id), timeout=20)
                settled = await journal.load(submitted.receipt.operation_id)
                assert settled.terminal_condition is OperationTerminalCondition.REFUSED
                assert settled.effect is OperationEffect.UNKNOWN
                assert settled.terminal_receipt is not None
                assert settled.terminal_receipt.result_ref is None
                state = subject.store.enrollment_state()
                assert state.revision == 1
                assert tuple(item.request_id for item in state.requests) == (request_id,)
            finally:
                await services.shutdown()

        with monkeypatch.context() as local_patch:
            local_patch.setattr(subject.store, "publish_enrollment", publish_then_fail)
            asyncio.run(run())


def test_failed_delivery_after_candidate_publication_stays_unknown_until_retry_activates(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A durable pending candidate is not a completed approval effect."""
    with administration_subject(tmp_path) as subject:
        services, journal, operands = _services(subject, authority_operation)

        def fail_after_delivery() -> None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

        async def run() -> None:
            try:
                request_id = uuid4()
                _, requested = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="request",
                    request_id=request_id,
                    secret=subject.proposal.model_dump_json().encode(),
                )
                subject.owner.delivery.after_delivery = fail_after_delivery
                submitted = await services.submission.submit(
                    OperationRequest(
                        definition_id="user-profile.automation-approve",
                        subject_ref=profile_operation_subject(str(subject.store.binding.profile_id)),
                        payload=AutomationOperationRequest(
                            profile_id=subject.store.binding.profile_id,
                            request_id=request_id,
                            review_digest=requested.review_digest,
                        ),
                    ),
                    actor_ref="operator:synthetic-human",
                )
                requirement = submitted.receipt.secret_requirement
                assert requirement is not None
                password = bytearray(PROFILE_INPUT.encode())
                await services.submission.submit_secret(requirement, password)
                assert password == bytearray(len(PROFILE_INPUT.encode()))
                await services.submission.start(submitted.receipt.operation_id)
                await asyncio.wait_for(services.submission.settled(submitted.receipt.operation_id), timeout=20)
                failed = await journal.load(submitted.receipt.operation_id)
                assert failed.terminal_condition is OperationTerminalCondition.REFUSED
                assert failed.effect is OperationEffect.UNKNOWN
                assert failed.terminal_receipt is not None and failed.terminal_receipt.result_ref is None
                pending = subject.store.enrollment_state()
                assert len(pending.requests) == len(pending.grants) == 1
                assert pending.requests[0].stage is EnrollmentStage.CANDIDATE
                candidate_id = pending.requests[0].candidate_key_id
                assert candidate_id is not None
                assert pending.grants[0].grant.state is AuthorityState.PENDING
                assert len(pending.grants[0].keys) == 1
                assert pending.grants[0].keys[0].key.key_id == candidate_id
                assert pending.grants[0].keys[0].key.state is AuthorityState.PENDING
                assert subject.owner.delivery.deliveries == 1

                subject.owner.delivery.after_delivery = lambda: None
                effect, approved = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="approve",
                    request_id=request_id,
                    secret=PROFILE_INPUT.encode(),
                    review_digest=requested.review_digest,
                )
                assert effect is OperationEffect.UPDATED
                assert approved.stage is EnrollmentStage.COMPLETE
                assert approved.key_id == candidate_id
                assert subject.owner.delivery.deliveries == 1
            finally:
                await services.shutdown()

        asyncio.run(run())


class _CommitWitness:
    def __init__(self) -> None:
        self.active = False
        self.entries = 0

    async def require[Payload: BaseModel](
        self, *, identity: OperationIdentity, request: OperationRequest[Payload], action: AccessAction
    ) -> None:
        assert identity.definition_id == request.definition_id
        assert action in {AccessAction.SUBMIT, AccessAction.START}

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        assert identity.operation_id
        assert not self.active
        self.active = True
        self.entries += 1
        try:
            yield
        finally:
            self.active = False


def test_registered_approval_delivers_outside_commit_but_publishes_inside_it(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    with administration_subject(tmp_path) as subject:
        witness = _CommitWitness()
        services, journal, operands = _services(subject, authority_operation, execution_authority=witness)
        original_publish = subject.store.publish_enrollment
        publications = 0

        def guarded_publish(state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
            nonlocal publications
            assert witness.active
            publications += 1
            return original_publish(state, fresh_dek=fresh_dek)

        def delivery_outside_commit() -> None:
            assert not witness.active

        subject.owner.delivery.before_delivery = delivery_outside_commit
        subject.owner.delivery.after_possession = delivery_outside_commit

        async def run() -> None:
            try:
                request_id = uuid4()
                _, requested = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="request",
                    request_id=request_id,
                    secret=subject.proposal.model_dump_json().encode(),
                )
                effect, approved = await _invoke(
                    services,
                    journal,
                    operands,
                    subject,
                    action="approve",
                    request_id=request_id,
                    secret=PROFILE_INPUT.encode(),
                    review_digest=requested.review_digest,
                )
                assert effect is OperationEffect.UPDATED
                assert approved.stage is EnrollmentStage.COMPLETE
            finally:
                await services.shutdown()

        with monkeypatch.context() as local_patch:
            local_patch.setattr(subject.store, "publish_enrollment", guarded_publish)
            asyncio.run(run())
        assert publications >= 3
        assert witness.entries >= publications
        assert subject.owner.delivery.deliveries == 1
        assert not witness.active


class _CancellationWitness:
    """Observe the executor's section lifetime while an actual store write blocks."""

    def __init__(self) -> None:
        self.active = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        assert not self.active
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _EffectWitness:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        assert phase_code == "user-profile.automation-request.execute"

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _SecretWitness:
    def __init__(self, secret: bytes) -> None:
        self.buffer = bytearray(secret)

    @asynccontextmanager
    async def consume(self) -> AsyncGenerator[memoryview]:
        view = memoryview(self.buffer)
        try:
            yield view
        finally:
            view.release()
            self.buffer[:] = b"\x00" * len(self.buffer)


class _RecordingOperands:
    def __init__(self, store: OperationSecureReferenceStore) -> None:
        self.store = store
        self.references: list[str] = []

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        reference = await self.store.put(operand, written_at=written_at)
        self.references.append(reference)
        return reference


def test_cancelling_executor_owner_during_real_publication_keeps_section_until_receipt_is_stored(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cancellation-complete child owns publication, effect and encrypted receipt."""
    with administration_subject(tmp_path) as subject:
        entered, release = Event(), Event()
        original_publish = subject.store.publish_enrollment

        def blocked_publish(state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
            entered.set()
            assert release.wait(timeout=20)
            return original_publish(state, fresh_dek=fresh_dek)

        request_id = uuid4()
        payload = AutomationOperationRequest(profile_id=subject.store.binding.profile_id, request_id=request_id)
        request = OperationRequest(
            definition_id="user-profile.automation-request",
            subject_ref=profile_operation_subject(str(payload.profile_id)),
            payload=payload,
        )
        cancellation, events = _CancellationWitness(), _EffectWitness()
        secret = _SecretWitness(subject.proposal.model_dump_json().encode())
        encrypted = operation_secure_reference_repository()
        operands = _RecordingOperands(encrypted)
        context = cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=request.definition_id,
                    subject_ref=request.subject_ref,
                ),
                authority_operation=authority_operation,
                cancellation=cancellation,
                events=events,
                ephemeral_secret=secret,
                operands=operands,
            ),
        )
        executor = AutomationAdministrationExecutor(
            lambda _context, _profile: ThreadedAutomationAdministration(subject.service)
        )

        async def run() -> None:
            task = asyncio.create_task(executor.execute(request, context))
            try:
                assert await asyncio.to_thread(entered.wait, 10)
                assert cancellation.active
                assert events.effects == [OperationEffect.UNKNOWN]
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done()
                assert cancellation.active
                assert subject.store.enrollment_state().revision == 0
            finally:
                release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=20)
            assert not cancellation.active
            assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
            assert secret.buffer == bytearray(len(secret.buffer))
            assert len(operands.references) == 1
            receipt = await encrypted.resolve(operands.references[0], EnrollmentReceipt)
            assert receipt.request_id == request_id
            assert receipt.stage is EnrollmentStage.REQUESTED
            assert subject.store.enrollment_state().revision == 1

        with monkeypatch.context() as local_patch:
            local_patch.setattr(subject.store, "publish_enrollment", blocked_publish)
            asyncio.run(run())
