"""A client-held receipt key proves a fresh human session over native transport."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import keyring
import pytest
from keyring.errors import KeyringError, PasswordDeleteError

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_custody
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt_crypto import profile_session_login_binding
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGeneration, SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from cadrumo.application.runtime.session_events import RuntimeSessionEvent
from cadrumo.application.runtime.sign_in import (
    RuntimeHumanSignedOut,
    RuntimeSignInStatusReply,
    RuntimeSignInStatusRequest,
    SignInPresence,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessSession, OsLockState
from cadrumo.application.user_profile.login_session import (
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
    borrow_profile_receipt_key,
)
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.tests.in_memory_keyring import IN_MEMORY_KEYRING, InMemoryKeyring

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from ..session_owner import ProfileWorkerSessionOwner
from .test_profile_connections import LoginObservation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _login(
    client: VerifiedRuntimeConnection,
    profile_id: UUID,
    method: str,
    secret: bytearray,
    *,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    persist_receipt: bool = False,
) -> RuntimeProfileStatus | RuntimeAccessRefusal:
    request = RuntimeProfileLogin.model_validate(
        {
            "request_id": uuid4(),
            "profile_id": profile_id,
            "method": method,
            "frontend": frontend,
            "persist_receipt": persist_receipt,
        }
    )
    # Match the cold registry-publication budget used by the native admission suite.
    result = client.login(request, secret, deadline=time.monotonic() + 75)
    assert secret == bytes(len(secret))
    return result


def _session(client: VerifiedRuntimeConnection, profile_id: UUID, session_id: UUID, action: str):
    request = RuntimeSessionRequest.model_validate(
        {"action": action, "request_id": uuid4(), "profile_id": profile_id, "session_id": session_id}
    )
    return client.session(request, deadline=time.monotonic() + 5)


@pytest.mark.parametrize("revocation", ["sign_out", "positive_lock"])
def test_receipt_proof_reenters_without_password_or_api_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revocation: str
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    prior_keyring = keyring.get_keyring()
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", IN_MEMORY_KEYRING)
    store = InMemoryKeyring()
    keyring.set_keyring(store)
    # The backend's priority was fixed when collection imported it, before the
    # selection above, so the receipt writer's usability probe would refuse it.
    # Hand the writer the same selected store directly.
    monkeypatch.setattr(receipt_custody, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))
    try:
        with administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as enrollment:
            request_id = uuid4()
            enrollment.service.request(request_id, enrollment.proposal)
            enrollment.approve(request_id)
            record = enrollment.store.enrollment_state().requests[0]
            api_credential = enrollment.owner.delivery.endpoint.possession(record)
            assert api_credential is not None
            profile_id = enrollment.store.binding.profile_id
            close_active_bucket_session()
            native_login = LoginObservation(owner_id())
            # The worker's own publication step, run in this process so the
            # receipt key lands in this process's keyring: it binds the
            # receipt to the native login the runtime observes below.
            _, decode = profile_authority_contexts()
            with authenticate_profile_candidate(
                bucket_id=profile_id, passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
            ) as candidate:
                assert candidate.persist_acceleration_receipt(
                    login_id=native_login.login_id,
                    binding=enrollment.store.binding,
                    sign_in=SignInGenerationCustody(root=root, binding=enrollment.store.binding).establish().current,
                )
            receipt_path = profile_session_path(storage_root=root, profile_id=profile_id)
            original_receipt = receipt_path.read_bytes()
            receipt_metadata = json.loads(original_receipt)
            assert receipt_metadata["login_binding"] == profile_session_login_binding(
                profile_id=profile_id,
                session_id=UUID(receipt_metadata["session_id"]),
                login_id=native_login.login_id,
            )
            receipt_expiry = min(
                datetime.fromisoformat(receipt_metadata["idle_deadline"]),
                datetime.fromisoformat(receipt_metadata["absolute_deadline"]),
            )

            stop, boot = Event(), uuid4()
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: native_login,
                secret_store=lambda: enrollment.native,
            )
            profiles.prepare_registry()
            server = RetainedRuntimeTransportServer(
                endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
            )
            clients: list[VerifiedRuntimeConnection] = []
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert server.ready.wait(3)
                    api, human, stranger, invalid_api, invalid_receipt, invalid_mcp = (
                        _connect(endpoint) for _ in range(6)
                    )
                    clients.extend((api, human, stranger, invalid_api, invalid_receipt, invalid_mcp))
                    presence = human.sign_in_status(
                        RuntimeSignInStatusRequest(request_id=uuid4(), profile_id=profile_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(presence, RuntimeSignInStatusReply)
                    assert presence.status.presence is SignInPresence.PRESENT
                    assert not profiles._profiles  # Observation must not start a worker.
                    assert receipt_path.read_bytes() == original_receipt
                    invalid_api_reply = _login(
                        invalid_api, profile_id, "api_key", bytearray(b"x" * 32), persist_receipt=True
                    )
                    invalid_receipt_reply = _login(
                        invalid_receipt, profile_id, "receipt", bytearray(b"x" * 32), persist_receipt=True
                    )
                    invalid_mcp_reply = _login(
                        invalid_mcp,
                        profile_id,
                        "password",
                        bytearray(PROFILE_INPUT.encode()),
                        frontend=OperationFrontendProjection.MCP,
                        persist_receipt=True,
                    )
                    for denied in (invalid_api_reply, invalid_receipt_reply, invalid_mcp_reply):
                        assert isinstance(denied, RuntimeAccessRefusal)
                        assert denied.code is RuntimeRefusalCode.INVALID_FRAME
                    for method in ("password", "receipt"):
                        mcp_human = _login(
                            invalid_mcp,
                            profile_id,
                            method,
                            bytearray(b"nonsecret-rejected-before-delivery"),
                            frontend=OperationFrontendProjection.MCP,
                        )
                        assert isinstance(mcp_human, RuntimeAccessRefusal)
                        assert mcp_human.code is RuntimeRefusalCode.INVALID_FRAME
                    admitted_api = _login(api, profile_id, "api_key", bytearray(api_credential.get_secret_value()))
                    assert isinstance(admitted_api, RuntimeProfileStatus) and admitted_api.status.session_id is not None
                    assert admitted_api.human_login is None
                    api_id = admitted_api.status.session_id

                    # A copied session UUID and a frontend label cannot stand in for the receipt key.
                    copied = _session(stranger, profile_id, api_id, "session_status")
                    assert isinstance(copied, RuntimeAccessRefusal)
                    wrong = bytearray(b"\x00" * 32)
                    with borrow_profile_receipt_key(bucket_id=profile_id) as proof:
                        assert bytes(proof) != bytes(wrong)
                        denied = _login(human, profile_id, "receipt", wrong)
                        assert isinstance(denied, RuntimeAccessRefusal)
                        assert receipt_path.read_bytes() == original_receipt
                        accepted = _login(human, profile_id, "receipt", proof)
                        assert isinstance(accepted, RuntimeProfileStatus), accepted
                    assert proof == bytes(32)
                    first_human_id = accepted.status.session_id
                    assert first_human_id is not None and first_human_id != api_id
                    assert accepted.status.session_expires_at == receipt_expiry
                    assert accepted.human_login is not None
                    assert accepted.human_login.resumed and accepted.human_login.session_persisted
                    assert accepted.human_login.authenticated_at == datetime.fromisoformat(
                        receipt_metadata["issued_at"]
                    )
                    assert accepted.human_login.idle_deadline == datetime.fromisoformat(
                        receipt_metadata["idle_deadline"]
                    )
                    assert accepted.human_login.absolute_deadline == datetime.fromisoformat(
                        receipt_metadata["absolute_deadline"]
                    )
                    assert receipt_path.read_bytes() == original_receipt
                    assert isinstance(_session(api, profile_id, api_id, "session_status"), RuntimeProfileStatus)

                    locked = _session(human, profile_id, first_human_id, "session_lock")
                    assert isinstance(locked, RuntimeSessionsLocked) and locked.session_ids == (first_human_id,)
                    assert isinstance(
                        _session(stranger, profile_id, first_human_id, "session_status"), RuntimeAccessRefusal
                    )
                    with borrow_profile_receipt_key(bucket_id=profile_id) as fresh_proof:
                        second = _login(stranger, profile_id, "receipt", fresh_proof)
                        assert isinstance(second, RuntimeProfileStatus), second
                    assert fresh_proof == bytes(32)
                    second_human_id = second.status.session_id
                    assert second_human_id is not None and second_human_id != first_human_id
                    retired_notice = Event()
                    stranger.subscribe_session_events(
                        lambda event: (
                            retired_notice.set()
                            if isinstance(event, RuntimeSessionEvent) and event.session_id == second_human_id
                            else None
                        )
                    )
                    assert second.status.session_expires_at == accepted.status.session_expires_at
                    assert second.human_login == accepted.human_login
                    assert receipt_path.read_bytes() == original_receipt
                    assert isinstance(_session(api, profile_id, api_id, "session_status"), RuntimeProfileStatus)

                    host = profiles._profiles[profile_id]
                    with host.guard:
                        native_login.lock_state = OsLockState.UNKNOWN
                        assert host.observe_human_lock_down() == ()
                        assert receipt_path.read_bytes() == original_receipt
                        native_login.lock_state = OsLockState.UNLOCKED
                        original_logins = host._logins
                        unrelated = LoginObservation(owner_id(), login_id="other-login", lock_state=OsLockState.LOCKED)
                        host._logins = lambda: (unrelated,)
                        try:
                            assert host.observe_human_lock_down() == ()
                            assert receipt_path.read_bytes() == original_receipt
                        finally:
                            host._logins = original_logins
                    with borrow_profile_receipt_key(bucket_id=profile_id) as stale_proof:
                        if revocation == "sign_out":
                            revoked = _session(stranger, profile_id, second_human_id, "human_sign_out")
                            assert isinstance(revoked, RuntimeHumanSignedOut), revoked
                            assert second_human_id in revoked.session_ids
                            assert revoked.receipt_removed and revoked.keychain_removed
                            assert revoked.automation_enabled is True
                        else:
                            with host.guard:
                                native_login.lock_state = OsLockState.LOCKED
                                retired = host.observe_human_lock_down()
                                assert second_human_id in retired
                                assert host.observe_human_lock_down() == ()
                                profiles._retired(retired)
                                native_login.lock_state = OsLockState.UNLOCKED
                        assert retired_notice.wait(5), "idle client must receive retirement on its verified stream"
                        assert not receipt_path.exists()
                        stale = _login(human, profile_id, "receipt", stale_proof)
                        assert isinstance(stale, RuntimeAccessRefusal)
                        assert stale.sign_in is not None and stale.sign_in.reason == "absent"
                    assert isinstance(_session(api, profile_id, api_id, "session_status"), RuntimeProfileStatus)
                    absent = human.sign_in_status(
                        RuntimeSignInStatusRequest(request_id=uuid4(), profile_id=profile_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(absent, RuntimeSignInStatusReply)
                    assert absent.status.presence is SignInPresence.ABSENT

                    stranger.close()
                    replacement = _connect(endpoint)
                    clients.append(replacement)
                    assert isinstance(
                        _session(replacement, profile_id, second_human_id, "session_status"), RuntimeAccessRefusal
                    )
                    # An API-authenticated connection has no human upgrade by session identity or frontend alone.
                    api_upgrade = _login(api, profile_id, "receipt", bytearray(b"\x00" * 32))
                    assert isinstance(api_upgrade, RuntimeAccessRefusal)
                finally:
                    for client in clients:
                        client.close()
                    stop.set()
                    running.result(timeout=15)
                    endpoint.close()
    finally:
        keyring.set_keyring(prior_keyring)


_KEYCHAIN_WORKER = """
# The real profile worker, given a usable keychain. The OS credential store
# refuses this logon session, and the worker environment drops PYTHON*
# variables, so the receipt writer is handed an in-process store instead.
from keyring.errors import KeyringError, PasswordDeleteError

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt
from cadrumo.entrypoints.runtime.worker import run
from cadrumo.tests.in_memory_keyring import InMemoryKeyring

_store = InMemoryKeyring()
acceleration_receipt._keyring = lambda: (_store, KeyringError, PasswordDeleteError)
raise SystemExit(run())
"""


def test_password_login_mints_its_receipt_only_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    worker_script = tmp_path / "keychain_worker.py"
    worker_script.write_text(_KEYCHAIN_WORKER, encoding="utf-8")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    store = InMemoryKeyring()
    # Storage teardown deletes receipts through this process's writer.
    monkeypatch.setattr(receipt_custody, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))
    after_bind: list[Callable[[], None]] = []
    after_capture: list[Callable[[], object]] = []
    captured: list[SignInGeneration | None] = []
    bind_human = ProfileWorkerSessionOwner.bind_human
    capture_human_sign_in = ProfileWorkerSessionOwner.capture_human_sign_in

    def bind_then_fault(owner: ProfileWorkerSessionOwner, session: AccessSession) -> None:
        bind_human(owner, session)
        while after_bind:
            after_bind.pop()()

    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        profile_id = enrollment.store.binding.profile_id
        sign_in = SignInGenerationCustody(root=root, binding=enrollment.store.binding)
        receipt_path = profile_session_path(storage_root=root, profile_id=profile_id)

        def capture_then_fault(owner: ProfileWorkerSessionOwner, session_id: UUID) -> bool:
            # Publication precedes the capture, and nothing is minted before either.
            assert not receipt_path.exists()
            pending = capture_human_sign_in(owner, session_id)
            captured.append(sign_in.observe().current)
            while after_capture:
                after_capture.pop()()
            return pending

        monkeypatch.setattr(ProfileWorkerSessionOwner, "bind_human", bind_then_fault)
        monkeypatch.setattr(ProfileWorkerSessionOwner, "capture_human_sign_in", capture_then_fault)
        close_active_bucket_session()
        native_login = LoginObservation(owner_id())

        def lock_login() -> None:
            native_login.lock_state = OsLockState.LOCKED

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
            worker_script=worker_script,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[VerifiedRuntimeConnection] = []

        def password_login() -> RuntimeProfileStatus | RuntimeAccessRefusal:
            client = _connect(endpoint)
            clients.append(client)
            return _login(client, profile_id, "password", bytearray(PROFILE_INPUT.encode()), persist_receipt=True)

        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)

                # Publication refused after binding: no capture, no receipt.
                after_bind.append(lock_login)
                refused = password_login()
                assert isinstance(refused, RuntimeAccessRefusal), refused
                assert captured == [] and not receipt_path.exists()
                assert sign_in.observe().current is None
                native_login.lock_state = OsLockState.UNLOCKED

                # Retired between publication and mint: the generation exists, the receipt does not.
                after_capture.append(lock_login)
                retired = password_login()
                assert isinstance(retired, RuntimeAccessRefusal), retired
                assert len(captured) == 1 and captured[0] is not None
                assert not receipt_path.exists()
                native_login.lock_state = OsLockState.UNLOCKED

                # A sign-out generation advance between publication and mint: the session
                # stays published, but no receipt carries the revoked generation.
                after_capture.append(sign_in.advance)
                advanced = password_login()
                assert isinstance(advanced, RuntimeProfileStatus), advanced
                assert advanced.human_login is not None and not advanced.human_login.session_persisted
                assert not receipt_path.exists()
                assert sign_in.observe().current != captured[-1]

                minted = password_login()
                assert isinstance(minted, RuntimeProfileStatus), minted
                assert minted.human_login is not None and minted.human_login.session_persisted
                stamped = captured[-1]
                assert stamped is not None and sign_in.observe().current == stamped
                metadata = json.loads(receipt_path.read_bytes())
                assert metadata["sign_in_lineage"] == str(stamped.lineage)
                assert metadata["sign_in_generation"] == stamped.generation
                assert metadata["login_binding"] == profile_session_login_binding(
                    profile_id=profile_id,
                    session_id=UUID(metadata["session_id"]),
                    login_id=native_login.login_id,
                )
                session_id = minted.status.session_id
                assert session_id is not None
                assert isinstance(_session(clients[-1], profile_id, session_id, "session_status"), RuntimeProfileStatus)
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=15)
                endpoint.close()


@pytest.mark.parametrize("case", ["login_mismatch", "generation_changed"])
def test_a_receipt_bound_elsewhere_is_refused_typed_and_deleted_by_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    worker_script = tmp_path / "keychain_worker.py"
    worker_script.write_text(_KEYCHAIN_WORKER, encoding="utf-8")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    # The client's proof store. The worker runs with its own, so a keychain
    # half that survives here shows this process deleted nothing.
    store = InMemoryKeyring()
    monkeypatch.setattr(receipt_custody, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        profile_id = enrollment.store.binding.profile_id
        sign_in = SignInGenerationCustody(root=root, binding=enrollment.store.binding)
        close_active_bucket_session()
        native_login = LoginObservation(owner_id())
        _, decode = profile_authority_contexts()
        with authenticate_profile_candidate(
            bucket_id=profile_id, passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
        ) as candidate:
            assert candidate.persist_acceleration_receipt(
                login_id="another-desktop-login" if case == "login_mismatch" else native_login.login_id,
                binding=enrollment.store.binding,
                sign_in=sign_in.establish().current,
            )
        if case == "generation_changed":
            sign_in.advance()
        receipt_path = profile_session_path(storage_root=root, profile_id=profile_id)
        session_id = json.loads(receipt_path.read_bytes())["session_id"]
        account = (receipt_custody.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{profile_id}:{session_id}")
        assert store.get_password(*account) is not None

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
            worker_script=worker_script,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            clients: list[RuntimeFrontendClient] = []
            try:
                assert server.ready.wait(3)
                client = RuntimeFrontendClient(
                    _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                )
                clients.append(client)
                with pytest.raises(ProfileReceiptRefusedError) as refused:
                    client.resume_receipt()
                # The runtime's typed denial reaches the client as a receipt refusal.
                assert refused.value.reason is ProfileSessionRefusalReason.ABSENT
                assert refused.value.binding is not None and refused.value.binding.value == case
                cause = refused.value.__cause__
                assert isinstance(cause, RuntimeFrontendRefusedError)
                assert cause.reason == AccessDenialCode.AUTHENTICATION_REQUIRED.value
                # The worker deleted the receipt; the client deleted nothing.
                assert not receipt_path.exists()
                assert store.get_password(*account) is not None
            finally:
                for opened in clients:
                    opened.close()
                stop.set()
                running.result(timeout=15)
                endpoint.close()
