"""A saved sign-in still proves the person to a fresh worker after the worker that held it was lost.

The runtime, the native transport, the session authority, the profile workers
and the stored sign-in are real. The worker is lost by terminating its process;
the runtime learns of the loss through its own health check.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.application.modelo.query_read_operation import MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.operation_access import OperationContract, OperationContractReply
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _worker_serves(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> object:
    """Ask for an operation contract: a call only a worker holding the session's custody answers."""
    return connection.operation(
        OperationContract(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=session_id,
            definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        ),
        deadline=exchange_deadline(),
    )


def _terminate_worker(runtime: StoredSignInRuntime) -> UUID:
    """Terminate the profile worker's process from outside the runtime and return the lost worker's id."""
    host = runtime.profiles._profiles[runtime.profile_id]
    worker = host.owner._worker
    assert worker is not None
    os.kill(worker._process.pid, signal.SIGTERM)
    return worker.identity.worker_id


def test_a_fresh_worker_accepts_the_saved_sign_in_after_the_worker_that_held_it_was_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        person = runtime.connect()
        admitted = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(admitted, ProfileStatus), admitted
        first = admitted.status.session_id
        assert first is not None
        assert isinstance(_worker_serves(runtime, person, first), OperationContractReply)
        stored = runtime.stored_sign_in()
        assert stored is not None

        lost_worker = _terminate_worker(runtime)
        deadline = time.monotonic() + 30
        while (lost := runtime.profiles._profiles.get(runtime.profile_id)) is not None and not lost.owner.lost:
            # Any use observes the worker's health; the terminated process is a positive loss.
            refused = _worker_serves(runtime, person, first)
            assert isinstance(refused, AccessRefusal), refused
            assert time.monotonic() < deadline, "the runtime never observed the terminated worker"
            time.sleep(0.05)
        while runtime.profile_id in runtime.profiles._profiles:
            # The lifecycle pass contains and forgets the lost incarnation.
            assert time.monotonic() < deadline, "the runtime never released the lost worker's host"
            time.sleep(0.05)
        assert runtime.stored_sign_in() == stored

        resumed = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(resumed, ProfileStatus), resumed
        session_id = resumed.status.session_id
        assert session_id is not None
        host = runtime.profiles._profiles[runtime.profile_id]
        assert not host.owner.lost
        replacement = host.owner._worker
        assert replacement is not None and replacement.identity.worker_id != lost_worker
        assert resumed.human_login is not None and resumed.human_login.resumed
        assert isinstance(_worker_serves(runtime, person, session_id), OperationContractReply)
