"""An old prepared enrollment cannot survive a real profile lock cycle."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import RLock
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimePeer
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepared
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import AdministrationFacts
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo.application.user_profile.automation_lifecycle_service import (
    AutomationLifecycleService,
    AutomationResumeRequest,
)
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.runtime.enrollment_offer import RuntimeEnrollmentOffer
from cadrumo.entrypoints.runtime.profile_host import ProfileConnection, RuntimeProfileHost

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Login:
    """A stable test-owned OS observation; lock changes come from real custody."""

    login_id = "prepared-enrollment-test-login"

    def __init__(self, os_owner_id: str) -> None:
        self.os_owner_id = os_owner_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Keep the same live login while the profile lock changes."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.os_owner_id,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


class _ResumeOwner:
    """Expose the fixture's real password provenance to the lifecycle service."""

    def __init__(self, subject: AdministrationSubject) -> None:
        self.subject = subject
        self.guard = RLock()

    @contextmanager
    def administration_guard(self) -> Iterator[None]:
        """Fence one canonical resume against this test's custody transition."""
        with self.guard:
            yield

    def facts(self) -> AdministrationFacts:
        """Return the current test-owned human login facts."""
        return self.subject.owner.current

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        """Mirror the committed local lock into the trusted host observation."""
        facts = self.subject.owner.current
        self.subject.owner.current = changed(
            facts,
            profile=changed(
                facts.profile,
                lock_generation=generation,
                globally_locked=locked,
                automation_enabled=not locked,
            ),
        )


def test_prepared_offer_refuses_after_canonical_lock_and_password_resume(tmp_path: Path) -> None:
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        grant_id = subject.approve(request_id).grant_id
        assert subject.store.enrollment_state().automation_enabled

        boot, connection_id, client_id = uuid4(), uuid4(), uuid4()
        context = RuntimeConnectionContext(
            connection_id,
            boot,
            RuntimePeer(os_owner_id=subject.store.binding.os_owner_id, process_id=1234),
        )
        login = _Login(context.peer.os_owner_id)
        connection = ProfileConnection(
            context,
            login,
            client_id,
            subject.store.binding.profile_id,
            OperationFrontendProjection.MCP,
            method="enrollment",
        )
        host = RuntimeProfileHost(
            store=subject.store,
            runtime_boot_id=boot,
            registry=build_production_operation_registry(),
            connected=lambda _identity: connection,
            logins=lambda: (login,),
            admitting=lambda: True,
        )
        initial = subject.store.profile_lock_state()
        prepared = RuntimeEnrollmentPrepared(
            request_id=uuid4(),
            runtime_boot_id=boot,
            connection_id=connection_id,
            enrollment_request_id=uuid4(),
            client_id=client_id,
            destination_id=client_id,
            profile_binding=subject.store.binding,
            expires_at=now() + timedelta(minutes=5),
        )
        offer = RuntimeEnrollmentOffer(
            prepared=prepared,
            connection=connection,
            host=host,
            deadline=time.monotonic() + 300,
            admitting=lambda: True,
            lock_generation=initial.generation,
        )
        offer.require_live()

        denied = subject.store.deny(
            AutomationDenial(request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.PROFILE_LOCK)
        )
        assert denied.access_denied and not denied.cleanup_pending
        locked = subject.store.profile_lock_state()
        assert locked.globally_locked and locked.generation > initial.generation
        owner = _ResumeOwner(subject)
        owner.set_profile_lock(generation=locked.generation, locked=True)
        service = AutomationLifecycleService(
            custody=subject.store, owner=owner, sessions=host.authority, storage_root=subject.store.root
        )
        resumed = service.resume(
            AutomationResumeRequest(
                request_id=uuid4(),
                profile_id=subject.store.binding.profile_id,
                lock_generation=locked.generation,
                grants=frozenset({grant_id}),
            ),
            password=SecretBytes(PROFILE_INPUT.encode()),
        )
        assert resumed.reactivated_grants == frozenset({grant_id})
        current = subject.store.profile_lock_state()
        assert current.generation == locked.generation and not current.globally_locked
        assert subject.store.enrollment_state().automation_enabled
        assert now() < prepared.expires_at
        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.NEEDS_USER):
            offer.require_live()
        replace(offer, lock_generation=current.generation).require_live()
