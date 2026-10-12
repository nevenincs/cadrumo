"""Installation acts over the real native transport, with the real recovery enrolment behind one of them."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.installation_client import (
    RuntimeInstallationClient,
    installation_passphrase_document,
)
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_LOG_TAIL_MAX_LINES,
    InstallationAct,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    RuntimeRecoveryEnrollReply,
    RuntimeRecoveryEnrollRequest,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_recovery_material,
    unlock_profile_custody_recovery,
)
from cadrumo.application.user_profile.recovery_custody import profile_recovery_status
from cadrumo.core.storage_taxonomy import StorageArea

from ..profile_connections import RuntimeProfileConnections
from .installation_runtime import FAULT_TEXT, LOG_LINES, InstallationLogin, serving_installation_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_UNHELD_CODE = "a-code-nobody-was-given"


@contextmanager
def _running_runtime(tmp_path: Path, login: InstallationLogin) -> Iterator[tuple[WindowsRuntimeEndpoint, Path]]:
    """Serve a storage root that holds no profile, yielding its endpoint and root."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    with serving_installation_runtime(endpoint, root, login):
        yield endpoint, root


@contextmanager
def _running_runtime_with_profile(
    tmp_path: Path, login: InstallationLogin
) -> Iterator[tuple[WindowsRuntimeEndpoint, Path, UUID, RuntimeProfileConnections]]:
    """Serve a storage root that holds one real encrypted profile, yielding that profile too."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        close_active_bucket_session()
        with serving_installation_runtime(endpoint, root, login, secret_store=lambda: subject.native) as service:
            yield endpoint, root, subject.store.binding.profile_id, service


def _client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


def _login() -> InstallationLogin:
    return InstallationLogin(owner=owner_id())


def test_acts_settle_over_the_native_transport_and_a_large_reply_arrives_whole(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cli = OperationFrontendProjection.CLI
    caplog.set_level(logging.DEBUG)

    with _running_runtime(tmp_path, _login()) as (endpoint, root), _client(endpoint) as client:
        checked = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=cli), RuntimeStorageCheckReply)
        tailed = client.perform(
            RuntimeRepairLogsRequest(request_id=uuid4(), frontend=cli, lines=INSTALLATION_LOG_TAIL_MAX_LINES),
            RuntimeRepairLogsReply,
        )
        refused = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=cli, area=StorageArea.CACHE),
            RuntimeStorageReclaimReply,
        )
        failed = client.perform(RuntimeStorageInitRequest(request_id=uuid4(), frontend=cli), RuntimeStorageInitReply)
        with pytest.raises(RuntimeFrontendRefusedError) as unavailable:
            client.perform(
                RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=cli), RuntimeStorageInventoryReply
            )
        # The connection outlives a refusal and a failure: the next act is served on it.
        again = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=cli), RuntimeStorageCheckReply)

    assert isinstance(checked, RuntimeStorageCheckReply)
    assert checked.storage_root == str(root)
    assert isinstance(tailed, RuntimeRepairLogsReply)
    assert tailed.lines == LOG_LINES
    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.STORAGE_RECLAIM
    assert refused.detail.context_mapping()["entry_count"] == "3"
    assert isinstance(failed, RuntimeInstallationFailed)
    assert FAULT_TEXT not in failed.model_dump_json()
    assert FAULT_TEXT not in caplog.text
    assert unavailable.value.reason == "operation_unavailable"
    assert isinstance(again, RuntimeStorageCheckReply)


def test_a_locked_login_is_refused_over_the_native_transport_until_it_is_unlocked(tmp_path: Path) -> None:
    login = InstallationLogin(owner=owner_id(), lock_state=OsLockState.LOCKED)
    request = RuntimeStorageCheckRequest(request_id=uuid4(), frontend=OperationFrontendProjection.TUI)

    with _running_runtime(tmp_path, login) as (endpoint, _root), _client(endpoint) as client:
        with pytest.raises(RuntimeFrontendRefusedError) as locked:
            client.perform(request, RuntimeStorageCheckReply)
        login.lock_state = OsLockState.UNLOCKED
        unlocked = client.perform(request.model_copy(update={"request_id": uuid4()}), RuntimeStorageCheckReply)

    assert locked.value.reason == "needs_user"
    assert isinstance(unlocked, RuntimeStorageCheckReply)


def test_every_frontend_gets_the_same_answer_from_the_running_runtime(tmp_path: Path) -> None:
    answers: dict[OperationFrontendProjection, dict[str, object]] = {}

    with _running_runtime(tmp_path, _login()) as (endpoint, _root):
        for frontend in (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI):
            with _client(endpoint) as client:
                reply = client.perform(
                    RuntimeStorageCheckRequest(request_id=uuid4(), frontend=frontend), RuntimeStorageCheckReply
                )
                answers[frontend] = reply.model_dump(mode="json", exclude={"request_id", "connection_id"})

    assert len(answers) == 2
    assert answers[OperationFrontendProjection.CLI] == answers[OperationFrontendProjection.TUI]


def test_the_client_refuses_to_send_an_act_outside_its_contract(tmp_path: Path) -> None:
    cli = OperationFrontendProjection.CLI

    with _running_runtime(tmp_path, _login()) as (endpoint, _root), _client(endpoint) as client:
        unasked = bytearray(b"an-unasked-for-frame")
        with pytest.raises(RuntimeRefusalError) as wrong_reply:
            client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=cli), RuntimeStorageInitReply)
        with pytest.raises(RuntimeRefusalError) as unasked_secret:
            client.perform(
                RuntimeStorageCheckRequest(request_id=uuid4(), frontend=cli), RuntimeStorageCheckReply, secret=unasked
            )
        with pytest.raises(RuntimeRefusalError) as missing_secret:
            client.perform(
                RuntimeRecoveryEnrollRequest(request_id=uuid4(), frontend=cli, profile_id=uuid4()),
                RuntimeRecoveryEnrollReply,
            )
        served = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=cli), RuntimeStorageCheckReply)

    for refusal in (wrong_reply, unasked_secret, missing_secret):
        assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert not any(unasked)
    assert isinstance(served, RuntimeStorageCheckReply)


def test_recovery_enrolment_takes_the_passphrase_in_and_hands_the_code_out_and_back(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    held: list[str] = []
    exclusion_while_held: list[str | None] = []
    reserved_while_held: list[set[UUID]] = []
    passphrase = bytearray(PROFILE_INPUT, "utf-8")
    caplog.set_level(logging.DEBUG)

    def hold(delivered: bytearray) -> SecretBytes:
        held.append(delivered.decode("utf-8"))
        exclusion_while_held.append(service._drain_guard._owner_role)
        reserved_while_held.append(set(service._custody_mutations))
        return SecretBytes(bytes(delivered))

    with (
        _running_runtime_with_profile(tmp_path, _login()) as (endpoint, root, profile, service),
        _client(endpoint) as client,
    ):
        document = installation_passphrase_document(passphrase)
        reply = client.perform(
            RuntimeRecoveryEnrollRequest(
                request_id=uuid4(), frontend=OperationFrontendProjection.CLI, profile_id=profile
            ),
            RuntimeRecoveryEnrollReply,
            secret=document,
            hold_secret=hold,
        )
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled
        # The code the client holds is the one the installed wrapper opens under.
        unlock_profile_custody_recovery(
            load_profile_custody_recovery_material(profile, root=root), recovery_secret=held[0]
        )

    assert isinstance(reply, RuntimeRecoveryEnrollReply)
    assert (reply.profile_id, reply.enrolled, reply.changed) == (str(profile), True, True)
    assert enrolled
    assert len(held) == 1
    # While the person copies the code down the act lends the lifecycle exclusion back, so
    # polling and shutdown are not held up, and keeps the profile fenced.
    assert exclusion_while_held != ["delete"]
    assert reserved_while_held == [{profile}]
    assert service._custody_mutations == set()
    assert not any(passphrase) and not any(document)
    for private in (PROFILE_INPUT, held[0]):
        assert private not in reply.model_dump_json()
        assert private not in caplog.text
        assert all(private not in repr(record.__dict__) for record in caplog.records)


@pytest.mark.parametrize("case", ["wrong-read-back", "declined", "wrong-passphrase"])
def test_recovery_enrolment_installs_nothing_unless_the_passphrase_and_the_read_back_both_hold(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, case: str
) -> None:
    delivered_codes: list[str] = []
    supplied = "not-the-profile-passphrase" if case == "wrong-passphrase" else PROFILE_INPUT
    caplog.set_level(logging.DEBUG)

    def hold(delivered: bytearray) -> SecretBytes | None:
        delivered_codes.append(delivered.decode("utf-8"))
        return None if case == "declined" else SecretBytes(_UNHELD_CODE.encode())

    with (
        _running_runtime_with_profile(tmp_path, _login()) as (endpoint, root, profile, service),
        _client(endpoint) as client,
    ):
        request = RuntimeRecoveryEnrollRequest(
            request_id=uuid4(), frontend=OperationFrontendProjection.TUI, profile_id=profile
        )
        secret = installation_passphrase_document(bytearray(supplied, "utf-8"))
        if case == "declined":
            with pytest.raises(RuntimeFrontendRefusedError) as declined:
                client.perform(request, RuntimeRecoveryEnrollReply, secret=secret, hold_secret=hold)
            settled = declined.value.reason
        else:
            reply = client.perform(request, RuntimeRecoveryEnrollReply, secret=secret, hold_secret=hold)
            assert isinstance(reply, RuntimeInstallationRefused)
            assert reply.act is InstallationAct.RECOVERY_ENROLL
            settled = reply.model_dump_json()
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled

    assert not enrolled
    assert service._custody_mutations == set()
    assert service._drain_guard._owner is None
    assert len(delivered_codes) == (0 if case == "wrong-passphrase" else 1)
    if case == "declined":
        assert settled == "missing"
    if case == "wrong-read-back":
        assert "recovery_possession_mismatch" in settled
    for private in (supplied, *delivered_codes, _UNHELD_CODE):
        assert private not in settled
        assert private not in caplog.text
