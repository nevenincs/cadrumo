"""Synthetic custody and trusted lifecycle/transport doubles for administration integration."""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    Availability,
    LoginEligibility,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.automation_administration_service import AutomationAdministrationService
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AdministrationFacts,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentRecord,
    EnrollmentRequester,
    ProtectedEnrollmentRecipient,
)
from cadrumo.application.user_profile.login_session import logout_active_profile
from cadrumo.application.user_profile.registration import register_profile_with_credentials

NOW = datetime(2026, 9, 26, tzinfo=UTC)
PROFILE_INPUT = "synthetic-enrollment-password"


def changed[T: BaseModel](model: T, **values: object) -> T:
    """Revalidate every altered test fact."""
    model_type = model.__class__
    return model_type.model_validate({**{name: getattr(model, name) for name in model_type.model_fields}, **values})


class DeliveryFaults:
    """Client-side endpoint with explicit failure points, not native platform evidence."""

    def __init__(self, endpoint: NativeEnrollmentRecipient) -> None:
        self.endpoint = endpoint
        self.before_delivery: Callable[[], None] = lambda: None
        self.after_delivery: Callable[[], None] = lambda: None
        self.after_possession: Callable[[], None] = lambda: None
        self.wrong_possession: SecretBytes | None = None
        self.deliveries = 0

    def deliver(self, request: EnrollmentRecord, secret: SecretBytes) -> None:
        self.before_delivery()
        self.endpoint.deliver(request, secret)
        self.deliveries += 1
        self.after_delivery()

    def possession(self, request: EnrollmentRecord) -> SecretBytes | None:
        value = self.wrong_possession or self.endpoint.possession(request)
        self.after_possession()
        return value


class TestAdministrationOwner:
    """Test-owned provenance; agent proposal fields cannot modify these observations."""

    __test__ = False

    def __init__(self, facts: AdministrationFacts, requester: EnrollmentRequester, delivery: DeliveryFaults) -> None:
        self.current = facts
        self.requesting = requester
        self.delivery = delivery
        self.connected = True
        self.guard = RLock()

    def facts(self) -> AdministrationFacts:
        return self.current

    def requester(self) -> EnrollmentRequester:
        return self.requesting

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        if requester != self.requesting or not self.connected:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return self.delivery

    @contextmanager
    def administration_guard(self) -> Iterator[None]:
        with self.guard:
            yield


@dataclass
class AdministrationSubject:
    service: AutomationAdministrationService
    owner: TestAdministrationOwner
    store: AutomationControlStore
    native: MemoryNativePort
    client_native: MemoryNativePort
    proposal: EnrollmentProposal

    def approve(self, request_id: UUID):
        from cadrumo.application.user_profile.automation_administration import enrollment_review_digest

        record = next(item for item in self.store.enrollment_state().requests if item.request_id == request_id)
        return self.service.approve(
            request_id, review_digest=enrollment_review_digest(record), password=SecretBytes(PROFILE_INPUT.encode())
        ).receipt


@contextmanager
def administration_subject(
    tmp_path: Path,
    *,
    os_owner_id: str = "synthetic-owner",
    installation_id: UUID | None = None,
    profile_label: str = "Enrollment tests",
) -> Iterator[AdministrationSubject]:
    """Use a real encrypted profile; only native store and OS/transport observations are doubled."""
    create, decode = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = register_profile_with_credentials(
            label=profile_label,
            passphrase=PROFILE_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        material = load_committed_profile_password_material(UUID(result.profile_id))
        binding = ProfileAccessBinding(
            profile_id=UUID(result.profile_id),
            installation_id=installation_id or uuid4(),
            os_owner_id=os_owner_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(material.envelope.dek_epoch)),
        )
        scope = AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )
        requester = EnrollmentRequester(
            runtime_boot_id=uuid4(), connection_id=uuid4(), client_id=uuid4(), destination_id=uuid4()
        )
        profile = ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=scope,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        )
        context = AccessEvaluationContext(
            now=NOW,
            monotonic_now=10.0,
            clock_rollback_detected=False,
            runtime_boot_id=requester.runtime_boot_id,
            connection_id=requester.connection_id,
            authenticated_client_id=requester.client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="test-login",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    locked=False,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        )
        session = AccessSession(
            session_id=uuid4(),
            binding=binding,
            profile_lock_generation=0,
            runtime_boot_id=requester.runtime_boot_id,
            connection_id=requester.connection_id,
            client_id=requester.client_id,
            kind=SessionKind.HUMAN,
            originating_login_id="test-login",
            state=SessionState.ACTIVE,
            scope=scope,
            issued_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            issued_monotonic=10.0,
        )
        native, client_native = MemoryNativePort(), MemoryNativePort()
        delivery = DeliveryFaults(NativeEnrollmentRecipient(requester=requester, secrets_store=client_native))
        owner = TestAdministrationOwner(
            AdministrationFacts(profile=profile, context=context, originating_login_id="test-login", session=session),
            requester,
            delivery,
        )
        store = AutomationControlStore(root=material.capsule_path.parent.parent, binding=binding, secrets_store=native)
        service = AutomationAdministrationService(
            custody=store, owner=owner, issuer=CustodyAutomationKeyIssuer(), storage_root=store.root
        )
        proposal = EnrollmentProposal(
            kind=EnrollmentKind.ENROLL,
            scope=scope,
            expires_at=NOW + timedelta(days=365),
            key_expires_at=NOW + timedelta(days=100),
            unattended=True,
            allow_os_lock=False,
        )
        try:
            yield AdministrationSubject(service, owner, store, native, client_native, proposal)
        finally:
            logout_active_profile()
