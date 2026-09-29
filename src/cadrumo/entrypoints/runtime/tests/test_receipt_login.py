"""A client-held receipt key proves a fresh human session over native transport."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import keyring
import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
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
from cadrumo.application.user_profile.login_session import borrow_profile_receipt_key, login_profile
from cadrumo.tests.in_memory_keyring import IN_MEMORY_KEYRING, InMemoryKeyring

from ..profile_connections import RuntimeProfileConnections
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
    result = client.login(request, secret, deadline=time.monotonic() + 20)
    assert secret == bytes(len(secret))
    return result


def _session(client: VerifiedRuntimeConnection, profile_id: UUID, session_id: UUID, action: str):
    request = RuntimeSessionRequest.model_validate(
        {"action": action, "request_id": uuid4(), "profile_id": profile_id, "session_id": session_id}
    )
    return client.session(request, deadline=time.monotonic() + 5)


def test_receipt_proof_reenters_without_password_or_api_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    prior_keyring = keyring.get_keyring()
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", IN_MEMORY_KEYRING)
    keyring.set_keyring(InMemoryKeyring())
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
            _, decode = profile_authority_contexts()
            minted = login_profile(
                name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
            )
            assert minted.session_persisted
            close_active_bucket_session()
            receipt_path = profile_session_path(storage_root=root, profile_id=profile_id)
            original_receipt = receipt_path.read_bytes()
            receipt_metadata = json.loads(original_receipt)
            receipt_expiry = min(
                datetime.fromisoformat(receipt_metadata["idle_deadline"]),
                datetime.fromisoformat(receipt_metadata["absolute_deadline"]),
            )

            stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: native_login,
                secret_store=lambda: enrollment.native,
            )
            server = RuntimeTransportServer(
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
                    assert second.status.session_expires_at == accepted.status.session_expires_at
                    assert second.human_login == accepted.human_login
                    assert receipt_path.read_bytes() == original_receipt
                    assert isinstance(_session(api, profile_id, api_id, "session_status"), RuntimeProfileStatus)

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
