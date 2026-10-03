"""Transient approval custody around real encrypted enrollment publication."""

from __future__ import annotations

from collections.abc import Iterator
from contextvars import copy_context
from pathlib import Path
from threading import Event, Thread
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    NOW,
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.approval_sessions import APPROVAL_SESSION_LIMIT, RuntimeApprovalSessions
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import ACCESS_LEASE_MAXIMUM, AuthorityState
from cadrumo.application.user_profile.automation_administration_service import AutomationAdministrationService
from cadrumo.application.user_profile.automation_approval_session import ApprovalSession
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentReceipt, EnrollmentStage
from cadrumo.core.identity.digest import ContentDigest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[AdministrationSubject]:
    with administration_subject(tmp_path) as result:
        yield result


def _setup(
    subject: AdministrationSubject,
    *,
    clock: list[float] | None = None,
    service: AutomationAdministrationService | None = None,
) -> tuple[RuntimeApprovalSessions, RuntimeApprovalBinding, EnrollmentReceipt]:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    requester = subject.owner.requesting
    session = subject.owner.current.session
    assert session is not None
    worker = ProfileWorkerIdentity(
        worker_id=uuid4(), runtime_boot_id=requester.runtime_boot_id, binding=subject.store.binding
    )
    binding = RuntimeApprovalBinding(
        worker_id=worker.worker_id,
        runtime_boot_id=worker.runtime_boot_id,
        profile_binding=worker.binding,
        connection_id=requester.connection_id,
        session_id=session.session_id,
        operation_id="a" * 64,
        enrollment_request_id=receipt.request_id,
        review_digest=receipt.review_digest,
    )
    manager = RuntimeApprovalSessions(
        worker=worker,
        service=lambda _binding: service or subject.service,
        clock=(lambda: clock[0]) if clock is not None else (lambda: 0.0),
    )
    return manager, binding, receipt


def _prepare(manager: RuntimeApprovalSessions, binding: RuntimeApprovalBinding) -> None:
    manager.prepare(binding, SecretBytes(PROFILE_INPUT.encode()))


def _complete(manager: RuntimeApprovalSessions, binding: RuntimeApprovalBinding) -> EnrollmentReceipt:
    assert manager.commit_review(binding) is None
    assert manager.inspect_recipient(binding)
    candidate = manager.publish_candidate(binding)
    assert candidate.published and candidate.receipt.stage is EnrollmentStage.CANDIDATE
    manager.deliver_and_verify(binding)
    active = manager.activate(binding)
    assert active.published and active.receipt.stage is EnrollmentStage.COMPLETE
    return active.receipt


def test_exact_session_completes_real_grant_and_releases_proof(subject: AdministrationSubject) -> None:
    manager, binding, _ = _setup(subject)
    _prepare(manager, binding)
    receipt = _complete(manager, binding)
    record = subject.store.enrollment_state().requests[0]
    credential = subject.owner.delivery.endpoint.possession(record)
    assert credential is not None
    assert receipt.key_id == record.candidate_key_id
    assert subject.store.snapshot().keys[0].state is AuthorityState.ACTIVE
    assert len(subject.store.unwrap(credential=credential, now=NOW)) == 32
    manager.retire(binding)
    assert manager.close() == 0
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.activate(binding)


def test_only_original_invocation_can_adopt_proof(subject: AdministrationSubject) -> None:
    manager, binding, receipt = _setup(subject)
    _prepare(manager, binding)
    alternatives = (
        changed(binding, worker_id=uuid4()),
        changed(binding, runtime_boot_id=uuid4()),
        changed(binding, profile_binding=changed(binding.profile_binding, profile_id=uuid4())),
        changed(binding, connection_id=uuid4()),
        changed(binding, session_id=uuid4()),
        changed(binding, operation_id="b" * 64),
        changed(binding, enrollment_request_id=uuid4()),
        changed(binding, review_digest="f" * 64),
    )
    for other in alternatives:
        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
            manager.commit_review(other)
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.retire(changed(binding, session_id=uuid4()))
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.prepare(changed(binding, worker_id=uuid4(), operation_id="c" * 64), SecretBytes(PROFILE_INPUT.encode()))
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CONFLICT):
        manager.prepare(
            changed(binding, review_digest="f" * 64, operation_id="d" * 64), SecretBytes(PROFILE_INPUT.encode())
        )
    assert subject.store.enrollment_state().requests[0].request_id == receipt.request_id
    assert _complete(manager, binding).request_id == receipt.request_id
    assert manager.close() == 0


def test_failed_and_out_of_order_phases_drop_owned_proof(subject: AdministrationSubject) -> None:
    manager, binding, _ = _setup(subject)
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.prepare(binding, SecretBytes(b"wrong-password"))
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.commit_review(binding)
    _prepare(manager, binding)
    with pytest.raises(ValueError, match="out of order"):
        manager.activate(binding)
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.commit_review(binding)
    assert subject.store.snapshot().grants == ()
    assert manager.close() == 0


def test_expiry_and_capacity_fence_later_phases(subject: AdministrationSubject) -> None:
    clock = [0.0]
    manager, binding, _ = _setup(subject, clock=clock)
    _prepare(manager, binding)
    clock[0] = ACCESS_LEASE_MAXIMUM.total_seconds() + 1
    manager.expire()
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        manager.commit_review(binding)
    assert manager.close() == 0

    second, binding, _ = _setup(subject)
    for index in range(APPROVAL_SESSION_LIMIT):
        _prepare(second, changed(binding, operation_id=f"{index + 1:064x}"))
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.UNAVAILABLE):
        _prepare(second, changed(binding, operation_id="f" * 64))
    assert second.close() == 0


def test_retire_waits_for_real_password_proof_to_settle(subject: AdministrationSubject) -> None:
    entered, release = Event(), Event()
    actual: list[ApprovalSession] = []

    class GatedApproval(ApprovalSession):
        @override
        def prepare(self, password: SecretBytes) -> None:
            super().prepare(password)
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test proof gate was not released")

    class GatedService(AutomationAdministrationService):
        @override
        def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> ApprovalSession:
            session = GatedApproval(self, request_id=request_id, review_digest=review_digest)
            actual.append(session)
            return session

    gated_service = GatedService(
        custody=subject.store,
        owner=subject.owner,
        issuer=subject.service.issuer,
        storage_root=subject.store.root,
    )
    manager, binding, _ = _setup(subject, service=gated_service)
    outcomes: list[BaseException] = []

    def prepare() -> None:
        try:
            _prepare(manager, binding)
        except BaseException as error:
            outcomes.append(error)

    authority_context = copy_context()
    thread = Thread(target=lambda: authority_context.run(prepare))
    thread.start()
    try:
        assert entered.wait(10)
        manager.retire(binding)
        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
            manager.commit_review(binding)
        assert manager.close() == 1
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive() and outcomes == []
    assert manager.close() == 0
    with pytest.raises(ValueError, match="closed"):
        actual[0].commit_review()


def test_close_waits_for_real_recipient_callback_and_keeps_candidate_pending(subject: AdministrationSubject) -> None:
    manager, binding, _ = _setup(subject)
    _prepare(manager, binding)
    assert manager.commit_review(binding) is None
    assert manager.inspect_recipient(binding)
    candidate = manager.publish_candidate(binding)
    entered, release = Event(), Event()

    def hold_delivery() -> None:
        entered.set()
        if not release.wait(10):
            raise TimeoutError("test recipient gate was not released")

    subject.owner.delivery.before_delivery = hold_delivery
    outcomes: list[BaseException] = []

    def deliver() -> None:
        try:
            manager.deliver_and_verify(binding)
        except BaseException as error:
            outcomes.append(error)

    thread = Thread(target=deliver)
    thread.start()
    try:
        assert entered.wait(10)
        assert manager.close() == 1
        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
            manager.activate(binding)
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive() and outcomes == []
    assert manager.close() == 0
    record = subject.store.enrollment_state().requests[0]
    assert record.candidate_key_id == candidate.receipt.key_id
    assert subject.store.snapshot().keys[0].state is AuthorityState.PENDING
