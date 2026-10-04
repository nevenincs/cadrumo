"""Native lifecycle controls preserve human authority and exact profile custody."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
)
from cadrumo.application.user_profile.access_contracts import (
    AuthorityState,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "native-access-management-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _login(
    connection: VerifiedRuntimeConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "api_key"],
    proof: bytes,
) -> RuntimeProfileStatus | RuntimeAccessRefusal:
    secret = bytearray(proof)
    reply = connection.login(
        RuntimeProfileLogin(
            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI, method=method
        ),
        secret,
        deadline=time.monotonic() + 25,
    )
    assert secret == bytes(len(proof))
    return reply


def _admit(
    connection: VerifiedRuntimeConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "api_key"],
    proof: bytes,
) -> UUID:
    reply = _login(connection, profile_id, method=method, proof=proof)
    assert isinstance(reply, RuntimeProfileStatus)
    assert reply.status.session_id is not None
    return reply.status.session_id


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


def test_native_human_lock_resume_selected_grant_and_revoke_key(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
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
            capture_login=lambda _channel: _LoginObservation(),
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
                    _connect(endpoint),
                    _connect(endpoint),
                    _connect(endpoint),
                    _connect(endpoint),
                )
                try:
                    human_id = _admit(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                    api_id = _admit(api, profile_id, method="api_key", proof=selected_secret)
                    inventory = human.session_inventory(
                        RuntimeSessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=human_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(inventory, RuntimeSessionInventoryReply)
                    assert {human_id, api_id} <= {item.session_id for item in inventory.sessions}
                    api_inventory = api.session_inventory(
                        RuntimeSessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=api_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(api_inventory, RuntimeAccessRefusal)

                    old = stale.recovery_prepare(
                        RuntimeProfileRecoveryPrepare(
                            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(old, RuntimeProfileRecoveryPrepared)
                    assert not old.globally_locked

                    locked = human.deny_automation(
                        RuntimeAutomationDeny(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            kind=AutomationDenialKind.PROFILE_LOCK,
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(locked, RuntimeAutomationDenied)
                    assert locked.receipt.access_denied
                    assert locked.receipt.profile_lock_generation is not None
                    generation = locked.receipt.profile_lock_generation
                    assert generation > old.lock_generation
                    assert subject.store.profile_lock_state().globally_locked
                    assert all(grant.state is AuthorityState.SUSPENDED for grant in subject.store.snapshot().grants)

                    stale_password = bytearray(PROFILE_INPUT.encode())
                    stale_reply = stale.resume_profile(
                        RuntimeProfileResume(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            frontend=OperationFrontendProjection.CLI,
                            lock_generation=old.lock_generation,
                            grants=frozenset({selected_grant}),
                        ),
                        stale_password,
                        deadline=time.monotonic() + 5,
                    )
                    assert stale_password == bytes(len(PROFILE_INPUT.encode()))
                    assert isinstance(stale_reply, RuntimeAccessRefusal)
                    assert stale_reply.code is AutomationCustodyCode.CONFLICT

                    prepared = recovery.recovery_prepare(
                        RuntimeProfileRecoveryPrepare(
                            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(prepared, RuntimeProfileRecoveryPrepared)
                    assert prepared.globally_locked and prepared.lock_generation == generation

                    wrong_password = bytearray(b"wrong-synthetic-password")
                    wrong = recovery.resume_profile(
                        RuntimeProfileResume(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            frontend=OperationFrontendProjection.CLI,
                            lock_generation=generation,
                            grants=frozenset({selected_grant}),
                        ),
                        wrong_password,
                        deadline=time.monotonic() + 25,
                    )
                    assert wrong_password == bytes(len(b"wrong-synthetic-password"))
                    assert isinstance(wrong, RuntimeAccessRefusal)
                    assert subject.store.profile_lock_state().globally_locked

                    password = bytearray(PROFILE_INPUT.encode())
                    resumed = recovery.resume_profile(
                        RuntimeProfileResume(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            frontend=OperationFrontendProjection.CLI,
                            lock_generation=generation,
                            grants=frozenset({selected_grant}),
                        ),
                        password,
                        deadline=time.monotonic() + 25,
                    )
                    assert password == bytes(len(PROFILE_INPUT.encode()))
                    assert isinstance(resumed, RuntimeProfileResumed)
                    assert resumed.receipt.reactivated_grants == frozenset({selected_grant})
                    assert not subject.store.profile_lock_state().globally_locked
                    grants = {grant.grant_id: grant for grant in subject.store.snapshot().grants}
                    keys = {key.key_id: key for key in subject.store.snapshot().keys}
                    assert grants[selected_grant].state is AuthorityState.ACTIVE
                    assert keys[selected_key].state is AuthorityState.ACTIVE
                    assert grants[held_grant].state is AuthorityState.SUSPENDED
                    assert keys[held_key].state is AuthorityState.SUSPENDED

                    prior_api = api.session(
                        RuntimeSessionRequest(
                            action="session_status", request_id=uuid4(), profile_id=profile_id, session_id=api_id
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(prior_api, RuntimeAccessRefusal)
                    renewed_human, renewed_api, held_api = (
                        _connect(endpoint),
                        _connect(endpoint),
                        _connect(endpoint),
                    )
                    try:
                        renewed_human_id = _admit(
                            renewed_human, profile_id, method="password", proof=PROFILE_INPUT.encode()
                        )
                        renewed_api_id = _admit(renewed_api, profile_id, method="api_key", proof=selected_secret)
                        assert isinstance(
                            _login(held_api, profile_id, method="api_key", proof=held_secret), RuntimeAccessRefusal
                        )

                        revoked = renewed_human.deny_automation(
                            RuntimeAutomationDeny(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=renewed_human_id,
                                kind=AutomationDenialKind.KEY,
                                target_id=selected_key,
                            ),
                            deadline=time.monotonic() + 10,
                        )
                        assert isinstance(revoked, RuntimeAutomationDenied)
                        assert revoked.receipt.access_denied
                        keys_after_revoke = {key.key_id: key for key in subject.store.snapshot().keys}
                        assert keys_after_revoke[selected_key].state is AuthorityState.REVOKED
                        fenced = renewed_api.session(
                            RuntimeSessionRequest(
                                action="session_status",
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=renewed_api_id,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(fenced, RuntimeAccessRefusal)
                        surviving = renewed_human.session(
                            RuntimeSessionRequest(
                                action="session_status",
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=renewed_human_id,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(surviving, RuntimeProfileStatus)
                    finally:
                        renewed_human.close()
                        renewed_api.close()
                        held_api.close()
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
