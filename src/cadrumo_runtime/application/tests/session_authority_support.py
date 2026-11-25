"""Shared synthetic owner, store and recovery doubles for the session authority tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion, revoke_profile_sign_in
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    OsLockState,
    SessionKind,
)
from cadrumo.application.user_profile.automation_enrollment import AdministrationFacts
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.session_retirement import SessionRetirement
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.automation_lifecycle import HumanSignInRevocationResult
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome

from ..automation_lifecycle_service import (
    AutomationLifecycleService,
)
from ..session_authority import ProfileSessionAuthority
from ..session_authority_contracts import SessionAuthorityFacts
from ..session_authority_core import CustodyRecoveryPolicy


class ObservedStore(AutomationControlStore):
    """Capture borrowed-buffer lifetime while preserving real unwrap and wiping."""

    borrowed: bytearray | None = None
    after_unwrap: Callable[[], None] = staticmethod(lambda: None)
    fail_release = False

    @override
    @contextmanager
    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> Generator[bytearray]:
        with super().unlocked(credential=credential, now=now) as material:
            yield material
        if self.fail_release:
            raise RuntimeError("synthetic borrowed material release failure")

    @override
    def unwrap(self, *, credential: SecretBytes, now: UtcInstant) -> bytearray:
        material = super().unwrap(credential=credential, now=now)
        self.borrowed = material
        self.after_unwrap()
        return material


class AdmissionOwner:
    """Synthetic transport, clock and worker host; its login uses real password custody."""

    def __init__(self, subject: AdministrationSubject) -> None:
        self.subject = subject
        self.current = SessionAuthorityFacts(subject.owner.current.profile, subject.owner.current.context)
        self.connections = {self.current.context.connection_id: self.current.context.authenticated_client_id}
        self.guard = subject.owner.guard
        self.active: set[UUID] = set()
        self.activated: list[UUID] = []
        self.activation_attempt: UUID | None = None
        self.retired: list[UUID] = []
        self.login_calls = 0
        self.fail_activation = False
        self.human_bound: set[UUID] = set()
        self.human_released = False
        self.fail_human_bind = False
        self.human_bind_attempt: UUID | None = None
        self.human_login_id = "test-login"
        self.failed_retirements: set[UUID] = set()
        self.fail_human_release = False
        self.refreshed: list[AccessSession] = []
        self.fail_refresh = False
        self.persist_receipt = False
        self.pending_receipts: set[UUID] = set()
        self.receipt_events: list[tuple[str, UUID]] = []
        self.after_capture: Callable[[UUID], None] = lambda _session_id: None
        self.facts_failure: AutomationCustodyError | None = None
        self.lost = False
        self.worker_lost = False

    @contextmanager
    def admission_guard(self) -> Generator[None]:
        with self.guard:
            yield

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        if self.facts_failure is not None:
            raise self.facts_failure
        return SessionAuthorityFacts(
            self.current.profile,
            changed(
                self.current.context,
                connection_id=connection_id,
                authenticated_client_id=self.connections[connection_id],
            ),
        )

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        assert len(dek) == 32 and any(dek)
        assert session.binding == self.current.profile.binding
        self.activation_attempt = session.session_id
        if self.fail_activation:
            raise RuntimeError("synthetic activation failure")
        self.active.add(session.session_id)
        self.activated.append(session.session_id)

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        assert parent.session_id in self.active
        self.active.add(session.session_id)

    def refresh(self, session: AccessSession) -> None:
        assert session.session_id in self.active
        if self.fail_refresh:
            raise RuntimeError("synthetic worker refresh failure")
        self.refreshed.append(session)

    def bind_human(self, session: AccessSession) -> None:
        self.human_bind_attempt = session.session_id
        if self.fail_human_bind:
            raise RuntimeError("synthetic worker preparation failure")
        self.human_bound.add(session.session_id)
        self.active.add(session.session_id)
        if self.persist_receipt:
            self.pending_receipts.add(session.session_id)

    def capture_human_sign_in(self, session_id: UUID) -> bool:
        if session_id not in self.pending_receipts:
            return False
        self.receipt_events.append(("capture", session_id))
        self.after_capture(session_id)
        return True

    def mint_human_receipt(self, session_id: UUID) -> None:
        assert session_id in self.pending_receipts and session_id in self.active
        self.pending_receipts.discard(session_id)
        self.receipt_events.append(("mint", session_id))

    def retire(self, session_id: UUID) -> None:
        if session_id in self.pending_receipts:
            self.pending_receipts.discard(session_id)
            self.receipt_events.append(("discard", session_id))
        self.active.discard(session_id)
        self.retired.append(session_id)
        if session_id in self.failed_retirements:
            raise RuntimeError("synthetic retirement failure")

    @contextmanager
    def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
        self.login_calls += 1
        _, decode = profile_authority_contexts()
        with portable_password_custody():
            outcome = authenticate_profile_for_invocation(
                name=str(self.current.profile.binding.profile_id),
                passphrase_callback=lambda: PROFILE_INPUT,
                profile_decode_context=decode,
                now=self.current.context.now,
            )
        self.human_bound.clear()
        try:
            yield outcome, self.human_login_id
        finally:
            if not self.human_bound:
                reset_test_profile_session()
                self.human_released = True
        if self.fail_human_release:
            raise RuntimeError("synthetic human release failure")

    def human_admission_deadline(self, connection_id: UUID) -> float:
        assert connection_id in self.connections
        return self.current.context.monotonic_now + 40

    @contextmanager
    def prepare_api_admission(self, connection_id: UUID) -> Generator[float]:
        assert connection_id in self.connections
        yield self.current.context.monotonic_now + 30


class Subject:
    def __init__(self, enrollment: AdministrationSubject) -> None:
        self.enrollment = enrollment
        request = uuid4()
        enrollment.service.request(request, enrollment.proposal)
        enrollment.approve(request)
        record = enrollment.store.enrollment_state().requests[0]
        credential = enrollment.owner.delivery.endpoint.possession(record)
        assert credential is not None
        self.credential = credential
        self.store = ObservedStore(
            root=enrollment.store.root, binding=enrollment.store.binding, secrets_store=enrollment.native
        )
        self.owner = AdmissionOwner(enrollment)
        self.authority = self.new_authority()
        self.connection = self.owner.current.context.connection_id

    def new_authority(self) -> ProfileSessionAuthority:
        return ProfileSessionAuthority(
            binding=self.owner.current.profile.binding,
            runtime_boot_id=self.owner.current.context.runtime_boot_id,
            owner=self.owner,
            custody=self.store,
            issuer=CustodyAutomationKeyIssuer(),
        )

    def admit(self) -> AccessSession | AccessDenied:
        return self.authority.admit_api_key(
            connection_id=self.connection,
            target=self.owner.current.profile.binding,
            credential=self.credential,
            scope=self.owner.current.profile.scope,
        )

    def advance(self, seconds: float) -> None:
        context = self.owner.current.context
        self.owner.current = SessionAuthorityFacts(
            self.owner.current.profile,
            changed(
                context, now=context.now + timedelta(seconds=seconds), monotonic_now=context.monotonic_now + seconds
            ),
        )


class LifecycleOwner:
    """Explicit host lock-state observations sharing the admission guard."""

    def __init__(self, subject: Subject, session: AccessSession) -> None:
        self.subject, self.session = subject, session

    def administration_guard(self):
        return self.subject.owner.admission_guard()

    def facts(self) -> AdministrationFacts:
        current = self.subject.owner.current
        return AdministrationFacts(
            profile=current.profile, context=current.context, originating_login_id="test-login", session=self.session
        )

    def revoke_human_sign_in(self) -> HumanSignInRevocationResult:
        deletion = revoke_profile_sign_in(
            SignInGenerationCustody(
                root=self.subject.store.root,
                binding=self.subject.store.binding,
            )
        )
        self.subject.authority.retire_human_sessions()
        return HumanSignInRevocationResult(
            receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
            keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
        )

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        owner = self.subject.owner
        owner.current = SessionAuthorityFacts(
            changed(
                owner.current.profile, lock_generation=generation, globally_locked=locked, automation_enabled=not locked
            ),
            owner.current.context,
        )


def lifecycle(subject: Subject, human: AccessSession) -> AutomationLifecycleService:
    return AutomationLifecycleService(
        custody=subject.store,
        owner=LifecycleOwner(subject, human),
        sessions=subject.authority,
        storage_root=subject.store.root,
    )


def lock_native_login(subject: Subject) -> None:
    before = subject.owner.current.context
    locked = changed(before.login_contexts[0], lock_state=OsLockState.LOCKED)
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile, changed(before, login_contexts=(locked,))
    )


def session_published(subject: Subject, session_id: UUID) -> bool:
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    return isinstance(status, ProfileAccessStatus) and status.credential_authenticated


def attended_tree(subject: Subject) -> tuple[AccessSession, AccessSession, AccessSession, UUID]:
    """An API session, a person's session and the attended child an agent service holds under it."""
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and api.grant_id is not None
    assert isinstance(human, AccessSession)
    recipient = uuid4()
    subject.owner.connections[recipient] = api.client_id
    child = subject.authority.delegate(
        connection_id=subject.connection,
        parent_session_id=human.session_id,
        recipient_connection_id=recipient,
        grant_id=api.grant_id,
        scope=human.scope,
    )
    assert isinstance(child, AccessSession) and child.kind is SessionKind.ATTENDED
    return api, human, child, recipient


async def retry_incomplete_cleanup_then_close(
    subject: Subject, owner: AdmissionOwner, cleanup: AsyncResourceCleanupError, attempted: UUID
) -> None:
    """Retry a failed candidate retirement twice, then show the status is unauthenticated and close retires nothing more."""
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


class RecoveryClock:
    """The monotonic clock that measures only the recovery window and the repeat-loss interval."""

    def __init__(self) -> None:
        self.now = 5_000.0

    def __call__(self) -> float:
        return self.now


class Recovery:
    """An authority whose positive worker loss suspends leases under a fresh, empty owner."""

    def __init__(self, subject: Subject) -> None:
        self.subject = subject
        self.clock = RecoveryClock()
        self.retired: list[SessionRetirement] = []
        self.suspended: list[tuple[AccessSession, ...]] = []
        self.rebound: list[tuple[AccessSession, ...]] = []
        subject.authority = ProfileSessionAuthority(
            binding=subject.owner.current.profile.binding,
            runtime_boot_id=subject.owner.current.context.runtime_boot_id,
            owner=subject.owner,
            custody=subject.store,
            issuer=CustodyAutomationKeyIssuer(),
            retired=self.retired.append,
            replace_lost_owner=self._replace_lost_owner,
            suspended=self.suspended.append,
            rebound=self.rebound.append,
            recovery=CustodyRecoveryPolicy(monotonic=self.clock),
        )

    def _replace_lost_owner(self) -> AdmissionOwner:
        # The fresh incarnation holds no custody of any lease.
        owner = self.subject.owner
        owner.worker_lost = False
        owner.active.clear()
        owner.human_bound.clear()
        return owner

    def lose_worker(self) -> tuple[UUID, ...]:
        self.subject.owner.worker_lost = True
        return self.subject.authority.revalidate_sessions()

    def status(self, session: AccessSession) -> ProfileAccessStatus | AccessDenied:
        return self.subject.authority.status(
            connection_id=session.connection_id,
            session_id=session.session_id,
            published_authority=Availability.UNAVAILABLE,
            provider=Availability.NOT_REQUIRED,
        )

    def live(self, session: AccessSession) -> bool:
        status = self.status(session)
        return (
            isinstance(status, ProfileAccessStatus)
            and status.denial is None
            and status.session_id == session.session_id
            and status.credential_authenticated
        )


def read_guard(subject: Subject, session: AccessSession) -> AbstractContextManager[object]:
    definitions = build_user_profile_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions, public_registrations=build_user_profile_operation_registrations(definitions)
    )
    definition_id = "user-profile.field-mutation"
    return subject.authority.operation_guard(
        connection_id=session.connection_id,
        session_id=session.session_id,
        request=OperationAccessRequest(
            profile_id=session.binding.profile_id,
            definition_id=definition_id,
            action=AccessAction.COMMIT,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
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
        ),
        registry=registry,
    )
