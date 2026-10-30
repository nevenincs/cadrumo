"""The worker loop answers its control channel while an operation door waits on custody.

Custody is real, over a real profile capsule, and so are the operation host
and the control dispatcher. Only the parent's ends are stand-ins: requests
arrive from a local queue and replies land in memory. Custody waits either on a
held capsule read or on another thread holding its lock; the loop must answer
the control channel before that wait ends.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from typing import Literal, cast
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.master_key import active_session, profile_worker_custody
from cadrumo.adapters.persistence.storage.master_key.profile_worker_binding import ProfileWorkerBindingOwner
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.master_key.tests.capsule_read_support import (
    HELD_READ_WAIT_SECONDS,
    HeldCapsuleRead,
    republish_capsule_commit,
)
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.operations.models import new_operation_id
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerControlRequest, ProfileWorkerRequest

from ...adapters.tests.profile_worker_support import lease, worker_profiles
from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.worker_transport import WorkerChannel
from .. import worker_service
from ..operation_host import ProfileWorkerOperationHost
from ..profile_login import ProfileWorkerHumanLogin

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ANSWER_SECONDS = 2.0


class _ParentEnd:
    """The parent's end of the control pipe: which reply kinds the worker wrote, as each arrives."""

    def __init__(self) -> None:
        self.activity, self.status = Event(), Event()

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > 0
        if b'"kind":"activity"' in payload:
            self.activity.set()
        if b'"kind":"status"' in payload:
            self.status.set()


@contextmanager
def _worker(tmp_path: Path) -> Generator[tuple[ProfileWorkerCustody, AccessSession, ProfileWorkerOperationHost]]:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles, pytest.MonkeyPatch.context() as patch:
        root, ((identity, key), _) = profiles
        # The worker's binding is single-assignment for its process, and this test's process lives on.
        isolated = ProfileWorkerBindingOwner()
        patch.setattr(profile_worker_custody, "profile_worker_binding", isolated)
        patch.setattr(active_session, "profile_worker_binding", isolated)
        with override_settings(cadrumo_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id)):
            custody = ProfileWorkerCustody(identity, storage_root=root)
            session = lease(identity)
            custody.install(session, bytearray(key))
            host = ProfileWorkerOperationHost(
                custody,
                authorization=WorkerAuthorizationClient(identity=identity, root=root, parent_pid=os.getpid()),
            )
            try:
                yield custody, session, host
            finally:
                custody.close()


async def _serve_control(
    custody: ProfileWorkerCustody,
    host: ProfileWorkerOperationHost,
    parent: _ParentEnd,
    requests: asyncio.Queue[ProfileWorkerRequest | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def receive(*_arguments: object, **_keywords: object) -> ProfileWorkerRequest:
        request = await requests.get()
        if request is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return request

    monkeypatch.setattr(worker_service._worker_requests, "receive", receive)
    context = worker_service._WorkerControl(
        channel=cast(WorkerChannel, parent),
        custody=custody,
        human=cast(ProfileWorkerHumanLogin, object()),
        operations=host,
        uploads=cast(worker_service.WorkerSubmissionStaging, object()),
        failed=asyncio.Event(),
        operation_release=cast(worker_service._worker_cleanup.WorkerRelease[OperationDrainResult], object()),
        upload_release=cast(worker_service._worker_cleanup.WorkerRelease[None], object()),
        changed=asyncio.Event(),
    )
    with ThreadPoolExecutor(max_workers=1) as input_executor, pytest.raises(RefusalError):
        await worker_service._serve_control_requests(context, input_executor)


def _control(action: Literal["activity", "status"]) -> ProfileWorkerRequest:
    return ProfileWorkerRequest(root=ProfileWorkerControlRequest(action=action, request_id=uuid4()))


def test_control_is_answered_while_an_operation_door_waits_on_a_held_capsule_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _worker(tmp_path) as (custody, session, host):
        read = HeldCapsuleRead(fail_held=True)
        monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)
        republish_capsule_commit(custody.identity.binding.profile_id, root=custody.root)
        parent = _ParentEnd()
        answered_while_held: list[bool] = []

        def release_after_answers() -> None:
            try:
                assert read.entered.wait(HELD_READ_WAIT_SECONDS)
                answered_while_held.append(
                    parent.activity.wait(_ANSWER_SECONDS) and parent.status.wait(_ANSWER_SECONDS)
                )
            finally:
                read.release.set()

        async def exercise() -> None:
            requests: asyncio.Queue[ProfileWorkerRequest | None] = asyncio.Queue()
            serving = asyncio.create_task(_serve_control(custody, host, parent, requests, monkeypatch))
            releaser = Thread(target=release_after_answers, name="synthetic-capsule-release")
            releaser.start()
            try:
                door = asyncio.create_task(
                    host.resume(new_operation_id(), session.session_id, frontend=OperationFrontendProjection.CLI)
                )
                # The door's own read is the held one; the status read that follows runs unheld.
                assert await asyncio.to_thread(read.entered.wait, HELD_READ_WAIT_SECONDS)
                for request in (_control("activity"), _control("status"), None):
                    await requests.put(request)
                with pytest.raises(AutomationCustodyError) as refused:
                    await door
                # The held read failed once released: the door refuses and custody closes, as before.
                assert refused.value.reason is AutomationCustodyCode.INVALID
                await serving
            finally:
                await asyncio.to_thread(releaser.join, HELD_READ_WAIT_SECONDS)

        asyncio.run(exercise())
        assert answered_while_held == [True], "the control channel waited for a capsule read"
        assert custody.live_sessions() == ()


def test_control_is_answered_while_another_thread_holds_the_custody_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _worker(tmp_path) as (custody, session, host):
        parent = _ParentEnd()
        holding, answered_while_held = Event(), list[bool]()

        def waiting_clock() -> UtcInstant:
            # Only the holder's entry waits; every later entry reads the real clock.
            custody.clock = now
            holding.set()
            answered_while_held.append(parent.activity.wait(_ANSWER_SECONDS))
            return now()

        custody.clock = waiting_clock
        holder = Thread(target=custody.seconds_until_expiry, name="synthetic-custody-holder")
        holder.start()
        assert holding.wait(HELD_READ_WAIT_SECONDS)

        async def exercise() -> None:
            requests: asyncio.Queue[ProfileWorkerRequest | None] = asyncio.Queue()
            serving = asyncio.create_task(_serve_control(custody, host, parent, requests, monkeypatch))
            door = asyncio.create_task(
                host.resume(new_operation_id(), uuid4(), frontend=OperationFrontendProjection.CLI)
            )
            # Let the door reach its custody wait before the parent asks for activity.
            await asyncio.sleep(0.1)
            for request in (_control("activity"), None):
                await requests.put(request)
            with pytest.raises(AutomationCustodyError) as refused:
                await door
            assert refused.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
            await serving

        try:
            asyncio.run(exercise())
        finally:
            holder.join(HELD_READ_WAIT_SECONDS)
        assert answered_while_held == [True], "the control channel waited for the custody lock"
        assert custody.require(session.session_id) == session
