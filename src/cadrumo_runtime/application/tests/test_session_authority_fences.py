"""Session authority fences, publication receipts and recovery publication retries.

Explicit lifecycle and native-store doubles stand in for the host; ciphertext,
password proof and key verification use their production implementations.
"""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGeneration, SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    OsLockState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
    AutomationDenialReceipt,
)
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.session_retirement import SessionRetirement
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.profile_session import ReceiptBindingRefusal
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AuthorityState,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.automation_lifecycle import AutomationResumeRequest
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome

from ..automation_lifecycle_service import AutomationLifecycleService
from ..session_authority_contracts import SessionAuthorityFacts
from ._session_authority_support import AdmissionOwner, Subject, lifecycle, lock_native_login, session_published

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("resume_before_release", [False, True], ids=["locked", "resumed-generation"])
def test_paused_human_authentication_allows_status_and_cannot_publish_across_profile_lock(
    subject: Subject, resume_before_release: bool
) -> None:
    """Keep real password custody outside unrelated authority work and fence stale candidates."""
    candidate_connection = uuid4()
    entered, release, status_completed, authenticated = Event(), Event(), Event(), Event()

    class PausedAdmissionOwner(AdmissionOwner):
        @override
        @contextmanager
        def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
            if connection_id == candidate_connection:
                entered.set()
                assert release.wait(10)
            with super().authenticate_human(connection_id) as outcome:
                if connection_id == candidate_connection:
                    authenticated.set()
                yield outcome

    owner = PausedAdmissionOwner(subject.enrollment)
    subject.owner = owner
    subject.authority = subject.new_authority()
    owner.connections[candidate_connection] = uuid4()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    initial_generation = owner.current.profile.lock_generation
    initial_bind = owner.human_bind_attempt
    service = lifecycle(subject, human)

    def observe_and_lock() -> tuple[ProfileAccessStatus, AutomationDenialReceipt]:
        status = subject.authority.status(
            connection_id=subject.connection,
            session_id=human.session_id,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
        )
        assert isinstance(status, ProfileAccessStatus)
        assert status.credential_authenticated and status.session_id == human.session_id
        status_completed.set()
        receipt = service.deny(
            AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.PROFILE_LOCK)
        )
        if resume_before_release:
            resumed = service.resume(
                AutomationResumeRequest(
                    request_id=uuid4(),
                    profile_id=human.binding.profile_id,
                    lock_generation=owner.current.profile.lock_generation,
                    grants=frozenset(),
                ),
                password=SecretBytes(PROFILE_INPUT.encode()),
            )
            assert not resumed.reactivated_grants
        return status, receipt

    # Keep joined real password custody active across both authentication threads.
    with portable_password_custody(), ThreadPoolExecutor(max_workers=2) as executor:
        control_context = copy_context()

        def control_work() -> tuple[ProfileAccessStatus, AutomationDenialReceipt]:
            assert entered.wait(10)
            return control_context.run(observe_and_lock)

        admission = executor.submit(
            copy_context().run, subject.authority.admit_human, connection_id=candidate_connection
        )
        control = executor.submit(control_work)
        try:
            assert entered.wait(10)
            assert status_completed.wait(3), "unrelated authority status blocked on password authentication"
            assert not release.is_set()
            _, receipt = control.result(timeout=5)
            assert receipt.access_denied and not receipt.cleanup_pending
            assert owner.current.profile.lock_generation > initial_generation
            assert owner.current.profile.globally_locked is not resume_before_release
            assert not release.is_set() and not admission.done()
        finally:
            release.set()
            # Both original threads settle even when a pre-release assertion fails.
            admission.result(timeout=10)
            control.result(timeout=10)
        candidate = admission.result(timeout=0)

    assert authenticated.is_set()
    assert isinstance(candidate, AccessDenied)
    assert candidate.code is (
        AccessDenialCode.AUTHENTICATION_REQUIRED if resume_before_release else AccessDenialCode.PROFILE_LOCKED
    )
    if resume_before_release:
        assert candidate.sign_in is not None
        assert candidate.sign_in.binding is ReceiptBindingRefusal.GENERATION_CHANGED
    assert owner.human_bind_attempt == initial_bind
    assert owner.human_released and not owner.human_bound and not owner.active
    assert human.session_id in owner.retired
    assert owner.login_calls == 2


@pytest.mark.parametrize("fence", ["lock-resume", "deadline"])
def test_human_candidate_is_retired_when_context_release_overlaps_fresh_fence(subject: Subject, fence: str) -> None:
    candidate_connection = uuid4()
    settled, publish = Event(), Event()

    class SettledCandidateOwner(AdmissionOwner):
        @override
        @contextmanager
        def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
            with super().authenticate_human(connection_id) as outcome:
                yield outcome
            if connection_id == candidate_connection:
                settled.set()
                assert publish.wait(10)

    owner = SettledCandidateOwner(subject.enrollment)
    subject.owner = owner
    subject.authority = subject.new_authority()
    owner.connections[candidate_connection] = uuid4()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    initial_generation = owner.current.profile.lock_generation
    service = lifecycle(subject, human)

    with ThreadPoolExecutor(max_workers=1) as executor:
        admission = executor.submit(
            copy_context().run, subject.authority.admit_human, connection_id=candidate_connection
        )
        try:
            assert settled.wait(10)
            attempted = owner.human_bind_attempt
            assert attempted is not None and attempted != human.session_id
            assert attempted in owner.active
            if fence == "lock-resume":
                receipt = service.deny(
                    AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.PROFILE_LOCK)
                )
                assert receipt.access_denied and not receipt.cleanup_pending
                resumed = service.resume(
                    AutomationResumeRequest(
                        request_id=uuid4(),
                        profile_id=human.binding.profile_id,
                        lock_generation=owner.current.profile.lock_generation,
                        grants=frozenset(),
                    ),
                    password=SecretBytes(PROFILE_INPUT.encode()),
                )
                assert not resumed.reactivated_grants
                assert owner.current.profile.lock_generation > initial_generation
                assert not owner.current.profile.globally_locked
            else:
                subject.advance(41)
            assert not publish.is_set() and not admission.done()
        finally:
            publish.set()
            candidate = admission.result(timeout=10)

    assert isinstance(candidate, AccessDenied)
    assert candidate.code is (
        AccessDenialCode.AUTHENTICATION_REQUIRED if fence == "lock-resume" else AccessDenialCode.SESSION_EXPIRED
    )
    if fence == "lock-resume":
        assert candidate.sign_in is not None
        assert candidate.sign_in.binding is ReceiptBindingRefusal.GENERATION_CHANGED
    assert owner.active == (set() if fence == "lock-resume" else {human.session_id})
    assert owner.retired.count(attempted) == 1
    status = subject.authority.status(
        connection_id=candidate_connection,
        session_id=attempted,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, ProfileAccessStatus)
    assert not status.credential_authenticated and status.session_id is None
    assert status.denial is AccessDenialCode.AUTHENTICATION_REQUIRED


@pytest.mark.parametrize("fence", ["profile-lock", "lock-resume", "client-change", "deadline"])
def test_api_preparation_allows_status_and_cannot_publish_across_a_fresh_fence(subject: Subject, fence: str) -> None:
    candidate_connection = uuid4()
    entered, release, status_completed = Event(), Event(), Event()

    class PausedApiOwner(AdmissionOwner):
        @override
        @contextmanager
        def prepare_api_admission(self, connection_id: UUID) -> Generator[float]:
            with super().prepare_api_admission(connection_id) as deadline:
                if connection_id == candidate_connection:
                    entered.set()
                    assert release.wait(10)
                yield deadline
            if connection_id == candidate_connection and fence == "deadline":
                subject.advance(31)

    owner = PausedApiOwner(subject.enrollment)
    subject.owner = owner
    subject.authority = subject.new_authority()
    owner.connections[candidate_connection] = owner.current.context.authenticated_client_id
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    initial_generation = owner.current.profile.lock_generation
    original_grant = subject.store.snapshot().grants[0].grant_id
    service = lifecycle(subject, human)

    def observe_and_fence() -> ProfileAccessStatus:
        status = subject.authority.status(
            connection_id=subject.connection,
            session_id=human.session_id,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
        )
        assert isinstance(status, ProfileAccessStatus)
        assert status.credential_authenticated and status.session_id == human.session_id
        status_completed.set()
        if fence in {"profile-lock", "lock-resume"}:
            receipt = service.deny(
                AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.PROFILE_LOCK)
            )
            assert receipt.access_denied and not receipt.cleanup_pending
            if fence == "lock-resume":
                resumed = service.resume(
                    AutomationResumeRequest(
                        request_id=uuid4(),
                        profile_id=human.binding.profile_id,
                        lock_generation=owner.current.profile.lock_generation,
                        grants=frozenset({original_grant}),
                    ),
                    password=SecretBytes(PROFILE_INPUT.encode()),
                )
                assert resumed.reactivated_grants == frozenset({original_grant})
                assert subject.store.snapshot().grants[0].state is AuthorityState.ACTIVE
            assert owner.current.profile.lock_generation > initial_generation
            assert owner.current.profile.globally_locked is (fence == "profile-lock")
        elif fence == "client-change":
            with owner.admission_guard():
                owner.connections[candidate_connection] = uuid4()
        return status

    def admit() -> AccessSession | AccessDenied:
        return subject.authority.admit_api_key(
            connection_id=candidate_connection,
            target=owner.current.profile.binding,
            credential=subject.credential,
            scope=owner.current.profile.scope,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        control_context = copy_context()

        def control_work() -> ProfileAccessStatus:
            assert entered.wait(10)
            return control_context.run(observe_and_fence)

        admission = executor.submit(copy_context().run, admit)
        control = executor.submit(control_work)
        try:
            assert entered.wait(10)
            assert status_completed.wait(3), "unrelated authority status blocked on API preparation"
            assert not release.is_set()
            status = control.result(timeout=5)
            assert status.credential_authenticated
            assert not release.is_set() and not admission.done()
        finally:
            release.set()
            admission.result(timeout=10)
            control.result(timeout=10)
        candidate = admission.result(timeout=0)

    assert isinstance(candidate, AccessDenied)
    expected = {
        "profile-lock": AccessDenialCode.PROFILE_LOCKED,
        "lock-resume": AccessDenialCode.PROFILE_LOCKED,
        "client-change": AccessDenialCode.CLIENT_MISMATCH,
        "deadline": AccessDenialCode.SESSION_EXPIRED,
    }
    assert candidate.code is expected[fence]
    assert owner.active == (set() if fence in {"profile-lock", "lock-resume"} else {human.session_id})
    if fence == "deadline":
        attempted = owner.activation_attempt
        assert attempted is not None
        assert owner.activated == [attempted] and owner.retired.count(attempted) == 1
        assert subject.store.borrowed == bytearray(32)
    else:
        assert owner.activation_attempt is None and not owner.activated
        assert subject.store.borrowed is None


@pytest.mark.asyncio
async def test_api_preparation_exit_failure_preserves_primary_and_retryable_installed_candidate(
    subject: Subject,
) -> None:
    primary = RuntimeError("synthetic original API preparation exit failure")

    class FailedPreparationOwner(AdmissionOwner):
        @override
        @contextmanager
        def prepare_api_admission(self, connection_id: UUID) -> Generator[float]:
            with super().prepare_api_admission(connection_id) as deadline:
                yield deadline
            raise primary

        @override
        def activate(self, session: AccessSession, dek: bytearray) -> None:
            super().activate(session, dek)
            self.failed_retirements.add(session.session_id)

    owner = FailedPreparationOwner(subject.enrollment)
    subject.owner = owner
    subject.authority = subject.new_authority()
    with pytest.raises(RuntimeError) as refused:
        subject.admit()
    assert refused.value is primary
    attempted = owner.activation_attempt
    assert attempted is not None and owner.activated == [attempted]
    assert not owner.active and subject.store.borrowed == bytearray(32)
    assert owner.retired.count(attempted) == 1
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    with pytest.raises(AsyncResourceCleanupError) as incomplete:
        await cleanup.retry_cleanup()
    assert owner.retired.count(attempted) == 2
    owner.failed_retirements.clear()
    await incomplete.value.retry_cleanup()
    assert owner.retired.count(attempted) == 3
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=attempted,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, ProfileAccessStatus)
    assert not status.credential_authenticated and status.session_id is None
    assert status.denial is AccessDenialCode.AUTHENTICATION_REQUIRED
    await subject.authority.close()
    assert owner.retired.count(attempted) == 3


def test_revocation_serializes_against_material_release_and_retires_the_winning_admission(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    unwrapped, release, revoking = Event(), Event(), Event()

    def pause() -> None:
        unwrapped.set()
        assert release.wait(10)

    def revoke() -> AutomationDenialReceipt:
        revoking.set()
        return service.deny(AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.ALL))

    subject.store.after_unwrap = pause
    with ThreadPoolExecutor(max_workers=2) as executor:
        admission = executor.submit(copy_context().run, subject.admit)
        try:
            assert unwrapped.wait(10)
            denial = executor.submit(copy_context().run, revoke)
            assert revoking.wait(10)
            assert not denial.done()
        finally:
            release.set()
        admitted = admission.result(timeout=10)
        assert isinstance(admitted, AccessSession)
        result = denial.result(timeout=10)
    assert isinstance(result, AutomationDenialReceipt)
    assert result.access_denied and not result.cleanup_pending
    assert subject.owner.active == {human.session_id}
    assert admitted.session_id in subject.owner.retired
    assert isinstance(subject.admit(), AccessDenied)


def test_operation_guard_orders_revocation_and_never_enters_after_denial(subject: Subject) -> None:
    """Exercise the real grant/store authority fence, without claiming a domain commit."""
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    definitions = build_user_profile_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions, public_registrations=build_user_profile_operation_registrations(definitions)
    )
    definition_id = "user-profile.field-mutation"
    request = OperationAccessRequest(
        profile_id=api.binding.profile_id,
        definition_id=definition_id,
        action=AccessAction.COMMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset(),
        period_independent=True,
        destination_id=uuid4(),
    )
    policy = OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=registry.lookup_public_contract(definition_id).definition_contract_digest,
        actions=frozenset({AccessAction.COMMIT}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )
    entered, release, revoking = Event(), Event(), Event()
    effects: list[str] = []

    def guarded() -> None:
        with subject.authority.operation_guard(
            connection_id=subject.connection,
            session_id=api.session_id,
            request=request,
            policy=policy,
            registry=registry,
        ):
            entered.set()
            assert release.wait(10)
            effects.append("protected body completed")

    def deny() -> AutomationDenialReceipt:
        revoking.set()
        return service.deny(AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.ALL))

    with ThreadPoolExecutor(max_workers=2) as executor:
        operation = executor.submit(copy_context().run, guarded)
        try:
            assert entered.wait(10)
            denial = executor.submit(copy_context().run, deny)
            assert revoking.wait(10)
            assert not denial.done()
        finally:
            release.set()
        operation.result(timeout=10)
        denial_receipt = denial.result(timeout=10)
        assert isinstance(denial_receipt, AutomationDenialReceipt)
        assert denial_receipt.access_denied
    with (
        pytest.raises(ProfileAccessRefusedError),
        subject.authority.operation_guard(
            connection_id=subject.connection,
            session_id=api.session_id,
            request=request,
            policy=policy,
            registry=registry,
        ),
    ):
        effects.append("forbidden body")
    assert effects == ["protected body completed"]


def test_requested_receipt_is_minted_after_publication_under_the_guard(subject: Subject) -> None:
    subject.owner.persist_receipt = True
    published_at_capture: list[bool] = []
    guarded_at_capture: list[bool] = []

    def acquired_elsewhere() -> bool:
        acquired = subject.owner.guard.acquire(blocking=False)
        if acquired:
            subject.owner.guard.release()
        return acquired

    def observe_capture(session_id: UUID) -> None:
        published_at_capture.append(session_published(subject, session_id))
        # Another thread cannot take the admission guard while the capture runs.
        with ThreadPoolExecutor(max_workers=1) as executor:
            guarded_at_capture.append(not executor.submit(acquired_elsewhere).result())

    subject.owner.after_capture = observe_capture
    human = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(human, AccessSession)
    assert subject.owner.receipt_events == [("capture", human.session_id), ("mint", human.session_id)]
    assert published_at_capture == [True] and guarded_at_capture == [True]
    assert session_published(subject, human.session_id)


def test_login_without_a_receipt_request_captures_nothing(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(human, AccessSession)
    assert subject.owner.receipt_events == []


def test_refused_publication_leaves_no_receipt(subject: Subject) -> None:
    subject.owner.persist_receipt = True

    class LockingOwner(AdmissionOwner):
        @override
        def bind_human(self, session: AccessSession) -> None:
            super().bind_human(session)
            lock_native_login(subject)

    owner = LockingOwner(subject.enrollment)
    owner.persist_receipt = True
    subject.owner = owner
    subject.authority = subject.new_authority()

    result = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(result, AccessDenied)
    attempted = owner.human_bind_attempt
    assert attempted is not None
    assert owner.receipt_events == [("discard", attempted)]
    assert not owner.pending_receipts and attempted in owner.retired


def test_session_retired_before_mint_leaves_no_receipt(subject: Subject) -> None:
    subject.owner.persist_receipt = True
    subject.owner.after_capture = lambda _session_id: lock_native_login(subject)

    result = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(result, AccessDenied)
    attempted = subject.owner.human_bind_attempt
    assert attempted is not None
    assert subject.owner.receipt_events == [("capture", attempted), ("discard", attempted)]
    assert not subject.owner.pending_receipts and attempted not in subject.owner.active


def test_failed_mint_retires_the_published_session(subject: Subject) -> None:
    subject.owner.persist_receipt = True

    class FailingMintOwner(AdmissionOwner):
        @override
        def mint_human_receipt(self, session_id: UUID) -> None:
            raise RuntimeError("synthetic receipt mint failure")

    owner = FailingMintOwner(subject.enrollment)
    owner.persist_receipt = True
    subject.owner = owner
    subject.authority = subject.new_authority()

    with pytest.raises(RuntimeError, match="synthetic receipt mint failure"):
        subject.authority.admit_human(connection_id=subject.connection)

    attempted = owner.human_bind_attempt
    assert attempted is not None
    assert owner.receipt_events == [("capture", attempted), ("discard", attempted)]
    assert not owner.active and not session_published(subject, attempted)


def test_human_sign_out_retires_human_access_but_keeps_api_session(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    api = subject.admit()
    assert isinstance(api, AccessSession)
    retired = subject.authority.retire_human_sessions()
    assert human.session_id in retired
    assert api.session_id not in retired
    assert not session_published(subject, human.session_id)
    assert api.session_id in subject.owner.active


def test_retirement_event_commits_once_even_when_physical_cleanup_needs_retry(subject: Subject) -> None:
    from cadrumo.application.user_profile.session_retirement import SessionRetirementKind

    events: list[SessionRetirement] = []
    subject.authority._retired = events.append
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    subject.owner.failed_retirements.add(human.session_id)
    with pytest.raises(ExceptionGroup):
        subject.authority.retire_human_sessions()
    assert not session_published(subject, human.session_id)
    assert len(events) == 1
    assert events[0].session_id == human.session_id
    assert events[0].kind is SessionRetirementKind.SIGNED_OUT
    subject.owner.failed_retirements.clear()
    subject.authority.revalidate_sessions()
    assert len(events) == 1
    assert human.session_id not in subject.owner.active


def test_sign_out_between_binding_and_publication_refuses_candidate(subject: Subject) -> None:
    class SigningOutOwner(AdmissionOwner):
        @override
        @contextmanager
        def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
            with super().authenticate_human(connection_id) as proof:
                yield proof
            subject.authority.retire_human_sessions()

    owner = SigningOutOwner(subject.enrollment)
    owner.persist_receipt = True
    subject.owner = owner
    subject.authority = subject.new_authority()
    result = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(result, AccessDenied)
    assert not owner.active and not owner.pending_receipts
    assert all(event != "mint" for event, _ in owner.receipt_events)


@pytest.mark.parametrize("refusal", ["unknown-login", "missing-grant"])
def test_refused_profile_recovery_preserves_sign_in_generation(subject: Subject, refusal: str) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    service.deny(
        AutomationDenial(
            request_id=uuid4(),
            binding=subject.store.binding,
            kind=AutomationDenialKind.PROFILE_LOCK,
        )
    )
    sign_in = SignInGenerationCustody(root=subject.store.root, binding=subject.store.binding)
    before = sign_in.establish().current
    facts = subject.owner.current
    if refusal == "unknown-login":
        subject.owner.current = SessionAuthorityFacts(
            facts.profile,
            changed(
                facts.context,
                login_contexts=tuple(
                    changed(login, lock_state=OsLockState.UNKNOWN) for login in facts.context.login_contexts
                ),
            ),
        )
    selection = AutomationResumeRequest(
        request_id=uuid4(),
        profile_id=subject.store.binding.profile_id,
        lock_generation=facts.profile.lock_generation,
        grants=frozenset({uuid4()}) if refusal == "missing-grant" else frozenset(),
    )
    with pytest.raises(AutomationCustodyError):
        service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    assert sign_in.observe().current == before
    assert subject.store.profile_lock_state().globally_locked


def _locked_for_recovery(
    subject: Subject, *, selected_grants: bool
) -> tuple[AutomationLifecycleService, SignInGenerationCustody, SignInGeneration, AutomationResumeRequest]:
    """Lock the profile with one admitted API grant and return the service, generation custody and resume request."""
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and api.grant_id is not None
    assert isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    service.deny(
        AutomationDenial(request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.PROFILE_LOCK)
    )
    generation = SignInGenerationCustody(root=subject.store.root, binding=subject.store.binding)
    before = generation.establish().current
    selection = AutomationResumeRequest(
        request_id=uuid4(),
        profile_id=subject.store.binding.profile_id,
        lock_generation=subject.owner.current.profile.lock_generation,
        grants=frozenset({api.grant_id}) if selected_grants else frozenset(),
    )
    return service, generation, before, selection


@pytest.mark.parametrize("selected_grants", [False, True], ids=["human-only", "selected-automation"])
def test_failed_recovery_publication_keeps_revocation_and_allows_retry(
    subject: Subject, monkeypatch: pytest.MonkeyPatch, selected_grants: bool
) -> None:
    service, generation, before, selection = _locked_for_recovery(subject, selected_grants=selected_grants)

    def refuse_publication(*_args: object, **_kwargs: object) -> None:
        # Inject at the existing custody publication boundary, after the real
        # password proof and durable revocation; never replace their owners.
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)

    with monkeypatch.context() as patch:
        patch.setattr(
            type(subject.store), "publish_enrollment" if selected_grants else "unlock_profile", refuse_publication
        )
        with pytest.raises(AutomationCustodyError):
            service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    revoked = generation.observe().current
    assert revoked is not None and revoked.generation == before.generation + 1
    assert subject.store.profile_lock_state().globally_locked
    assert not subject.owner.active
    assert isinstance(subject.admit(), AccessDenied)

    recovered = service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    retried = generation.observe().current
    assert retried is not None and retried.generation == revoked.generation + 1
    assert recovered.reactivated_grants == selection.grants
    assert recovered.human_sign_in_revocation is not None
    assert not subject.store.profile_lock_state().globally_locked


@pytest.mark.parametrize("retry_observation", ["published", "wrong-generation", "revoked-grant", "revoked-key"])
def test_recovery_retries_after_grants_publish_but_unlock_fails(
    subject: Subject, monkeypatch: pytest.MonkeyPatch, retry_observation: str
) -> None:
    service, generation, before, selection = _locked_for_recovery(subject, selected_grants=True)

    def refuse_unlock(*_args: object, **_kwargs: object) -> None:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)

    with monkeypatch.context() as patch:
        patch.setattr(type(subject.store), "unlock_profile", refuse_unlock)
        with pytest.raises(AutomationCustodyError):
            service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    published = subject.store.enrollment_state()
    assert published.grants[0].grant.state is AuthorityState.ACTIVE
    assert subject.store.profile_lock_state().globally_locked
    assert isinstance(subject.admit(), AccessDenied)

    if retry_observation != "published":
        entry = published.grants[0]
        if retry_observation == "wrong-generation":
            invalid = changed(entry, grant=changed(entry.grant, profile_lock_generation=selection.lock_generation + 1))
        elif retry_observation == "revoked-grant":
            invalid = changed(entry, grant=changed(entry.grant, state=AuthorityState.REVOKED))
        else:
            invalid = changed(
                entry,
                keys=tuple(changed(item, key=changed(item.key, state=AuthorityState.REVOKED)) for item in entry.keys),
            )
        # Fault only the returned control observation. Proof, local lock and
        # generation remain real; changed/revoked authority must not be revived.
        with monkeypatch.context() as patch:
            patch.setattr(type(subject.store), "enrollment_state", lambda _store: changed(published, grants=(invalid,)))
            with pytest.raises(AutomationCustodyError):
                service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
        refused = generation.observe().current
        assert refused is not None and refused.generation == before.generation + 1
        assert subject.store.profile_lock_state().globally_locked

    recovered = service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    after = generation.observe().current
    assert after is not None and after.generation == before.generation + 2
    assert recovered.reactivated_grants == selection.grants
    assert subject.store.enrollment_state().grants == published.grants
    assert not subject.store.profile_lock_state().globally_locked
    assert isinstance(subject.admit(), AccessSession)
