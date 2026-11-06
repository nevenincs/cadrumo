"""Native lifecycle controls preserve human authority and exact profile custody."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo_client.contracts.access_management import (
    AutomationDenied,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
    SessionInventory,
    SessionInventoryReply,
)
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileLogin, ProfileStatus, SessionRequest
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .served_runtime import SyntheticLogin, admit_session, connect_verified

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def login(
    connection: VerifiedConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "api_key"],
    proof: bytes,
) -> ProfileStatus | AccessRefusal:
    secret = bytearray(proof)
    reply = connection.login(
        ProfileLogin(
            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI, method=method
        ),
        secret,
        deadline=exchange_deadline(),
    )
    assert secret == bytes(len(proof))
    return reply


def _seed_two_grants(subject: AdministrationSubject) -> tuple[tuple[UUID, UUID, bytes], tuple[UUID, UUID, bytes]]:
    """Use real canonical request, proof, publish and client possession twice."""
    issued: list[tuple[UUID, UUID, bytes]] = []
    for _ in range(2):
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        receipt = subject.approve(request_id)
        record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
        key = subject.owner.delivery.endpoint.possession(record)
        assert receipt.key_id is not None and key is not None
        issued.append((receipt.grant_id, receipt.key_id, key.get_secret_value()))
    return issued[0], issued[1]


@dataclass(frozen=True)
class _Access:
    subject: AdministrationSubject
    endpoint: WindowsEndpoint
    profile_id: UUID
    selected_grant: UUID
    selected_key: UUID
    selected_secret: bytes
    held_grant: UUID
    held_key: UUID
    held_secret: bytes
    human: VerifiedConnection
    api: VerifiedConnection
    stale: VerifiedConnection
    recovery: VerifiedConnection


def _admit_and_inspect_sessions(access: _Access) -> tuple[UUID, UUID]:
    profile_id = access.profile_id
    human_id = admit_session(access.human, profile_id, method="password", proof=PROFILE_INPUT.encode())
    api_id = admit_session(access.api, profile_id, method="api_key", proof=access.selected_secret)
    inventory = access.human.session_inventory(
        SessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=human_id),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(inventory, SessionInventoryReply)
    assert {human_id, api_id} <= {item.session_id for item in inventory.sessions}
    api_inventory = access.api.session_inventory(
        SessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=api_id),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(api_inventory, AccessRefusal)
    return human_id, api_id


def _lock_profile(access: _Access, human_id: UUID) -> tuple[int, int]:
    profile_id, subject = access.profile_id, access.subject
    old = access.stale.recovery_prepare(
        ProfileRecoveryPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(old, ProfileRecoveryPrepared)
    assert not old.globally_locked

    locked = access.human.deny_automation(
        AutomationDeny(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=human_id,
            kind=AutomationDenialKind.PROFILE_LOCK,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(locked, AutomationDenied)
    assert locked.receipt.access_denied
    assert locked.receipt.profile_lock_generation is not None
    generation = locked.receipt.profile_lock_generation
    assert generation > old.lock_generation
    assert subject.store.profile_lock_state().globally_locked
    assert all(grant.state is AuthorityState.SUSPENDED for grant in subject.store.snapshot().grants)
    return old.lock_generation, generation


def _refuse_stale_resume(access: _Access, old_lock_generation: int, generation: int) -> None:
    profile_id = access.profile_id
    stale_password = bytearray(PROFILE_INPUT.encode())
    stale_reply = access.stale.resume_profile(
        ProfileResume(
            request_id=uuid4(),
            profile_id=profile_id,
            frontend=OperationFrontendProjection.CLI,
            lock_generation=old_lock_generation,
            grants=frozenset({access.selected_grant}),
        ),
        stale_password,
        deadline=time.monotonic() + 5,
    )
    assert stale_password == bytes(len(PROFILE_INPUT.encode()))
    assert isinstance(stale_reply, AccessRefusal)
    assert stale_reply.code is AutomationCustodyCode.CONFLICT

    prepared = access.recovery.recovery_prepare(
        ProfileRecoveryPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prepared, ProfileRecoveryPrepared)
    assert prepared.globally_locked and prepared.lock_generation == generation


def _resume_selected_grant(access: _Access, generation: int) -> None:
    profile_id, subject, recovery = access.profile_id, access.subject, access.recovery
    sign_in = SignInGenerationCustody(root=subject.store.root, binding=subject.store.binding)
    before_sign_in = sign_in.observe().current
    assert before_sign_in is not None
    wrong_password = bytearray(b"wrong-synthetic-password")
    wrong = recovery.resume_profile(
        ProfileResume(
            request_id=uuid4(),
            profile_id=profile_id,
            frontend=OperationFrontendProjection.CLI,
            lock_generation=generation,
            grants=frozenset({access.selected_grant}),
        ),
        wrong_password,
        deadline=exchange_deadline(),
    )
    assert wrong_password == bytes(len(b"wrong-synthetic-password"))
    assert isinstance(wrong, AccessRefusal)
    assert sign_in.observe().current == before_sign_in
    assert subject.store.profile_lock_state().globally_locked

    password = bytearray(PROFILE_INPUT.encode())
    resumed = recovery.resume_profile(
        ProfileResume(
            request_id=uuid4(),
            profile_id=profile_id,
            frontend=OperationFrontendProjection.CLI,
            lock_generation=generation,
            grants=frozenset({access.selected_grant}),
        ),
        password,
        deadline=exchange_deadline(),
    )
    assert password == bytes(len(PROFILE_INPUT.encode()))
    assert isinstance(resumed, ProfileResumed)
    assert resumed.receipt.human_sign_in_revocation is not None
    after_sign_in = sign_in.observe().current
    assert after_sign_in is not None and after_sign_in.generation == before_sign_in.generation + 1
    assert resumed.receipt.reactivated_grants == frozenset({access.selected_grant})
    assert not subject.store.profile_lock_state().globally_locked
    grants = {grant.grant_id: grant for grant in subject.store.snapshot().grants}
    keys = {key.key_id: key for key in subject.store.snapshot().keys}
    assert grants[access.selected_grant].state is AuthorityState.ACTIVE
    assert keys[access.selected_key].state is AuthorityState.ACTIVE
    assert grants[access.held_grant].state is AuthorityState.SUSPENDED
    assert keys[access.held_key].state is AuthorityState.SUSPENDED


def _revoke_selected_key(access: _Access, api_id: UUID) -> None:
    profile_id, subject = access.profile_id, access.subject
    prior_api = access.api.session(
        SessionRequest(action="session_status", request_id=uuid4(), profile_id=profile_id, session_id=api_id),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prior_api, AccessRefusal)
    renewed_human, renewed_api, held_api = (
        connect_verified(access.endpoint),
        connect_verified(access.endpoint),
        connect_verified(access.endpoint),
    )
    try:
        renewed_human_id = admit_session(renewed_human, profile_id, method="password", proof=PROFILE_INPUT.encode())
        renewed_api_id = admit_session(renewed_api, profile_id, method="api_key", proof=access.selected_secret)
        assert isinstance(login(held_api, profile_id, method="api_key", proof=access.held_secret), AccessRefusal)

        revoked = renewed_human.deny_automation(
            AutomationDeny(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=renewed_human_id,
                kind=AutomationDenialKind.KEY,
                target_id=access.selected_key,
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(revoked, AutomationDenied)
        assert revoked.receipt.access_denied
        keys_after_revoke = {key.key_id: key for key in subject.store.snapshot().keys}
        assert keys_after_revoke[access.selected_key].state is AuthorityState.REVOKED
        fenced = renewed_api.session(
            SessionRequest(
                action="session_status",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=renewed_api_id,
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(fenced, AccessRefusal)
        surviving = renewed_human.session(
            SessionRequest(
                action="session_status",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=renewed_human_id,
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(surviving, ProfileStatus)
    finally:
        renewed_human.close()
        renewed_api.close()
        held_api.close()


def test_native_human_lock_resume_selected_grant_and_revoke_key(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        (selected_grant, selected_key, selected_secret), (held_grant, held_key, held_secret) = _seed_two_grants(subject)
        profile_id = subject.store.binding.profile_id
        assert selected_grant != held_grant and selected_key != held_key
        close_active_bucket_session()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: SyntheticLogin("native-access-management-test-login"),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                human, api, stale, recovery = (
                    connect_verified(endpoint),
                    connect_verified(endpoint),
                    connect_verified(endpoint),
                    connect_verified(endpoint),
                )
                try:
                    access = _Access(
                        subject,
                        endpoint,
                        profile_id,
                        selected_grant,
                        selected_key,
                        selected_secret,
                        held_grant,
                        held_key,
                        held_secret,
                        human,
                        api,
                        stale,
                        recovery,
                    )
                    human_id, api_id = _admit_and_inspect_sessions(access)
                    old_lock_generation, generation = _lock_profile(access, human_id)
                    _refuse_stale_resume(access, old_lock_generation, generation)
                    _resume_selected_grant(access, generation)
                    _revoke_selected_key(access, api_id)
                finally:
                    human.close()
                    api.close()
                    stale.close()
                    recovery.close()
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
