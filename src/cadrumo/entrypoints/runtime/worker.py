"""Installed profile worker: native parent verification precedes all private custody."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from contextlib import ExitStack, suppress
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from ...adapters.local_runtime.framing import VerifiedRuntimeConnection, read_document, read_secret, write_document
from ...adapters.local_runtime.profile_worker import worker_operation_namespace
from ...adapters.local_runtime.windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint
from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseRequest,
    ProfileWorkerObservation,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationContract,
    ProfileWorkerOperationReceipt,
    ProfileWorkerOperationRequest,
    ProfileWorkerPasswordOutcome,
    ProfileWorkerRefusal,
    ProfileWorkerRequest,
    ProfileWorkerResumeRequest,
    ProfileWorkerRetireRequest,
    ProfileWorkerStatus,
    ProfileWorkerSubmission,
    ProfileWorkerSubmitRequest,
)
from ...application.user_profile.access_contracts import AccessAction
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from .operation_host import ProfileWorkerOperationHost
from .profile_login import ProfileWorkerHumanLogin


async def _receive(channel: WindowsRuntimeChannel, failed: asyncio.Event) -> ProfileWorkerRequest:
    def read() -> ProfileWorkerRequest:
        return read_document(channel, ProfileWorkerRequest, deadline=time.monotonic() + 5)

    while not failed.is_set():
        if channel.read_ready():
            return await await_cancellation_complete(asyncio.to_thread(read), task_name="profile-worker-read")
        await asyncio.sleep(0.02)
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


async def _operate(
    channel: WindowsRuntimeChannel, operations: ProfileWorkerOperationHost, failed: asyncio.Event
) -> None:
    try:
        while True:
            request = (await _receive(channel, failed)).root
            try:
                if isinstance(request, ProfileWorkerSubmitRequest):
                    submitted = await operations.submit_payload(
                        session_id=request.session_id,
                        frontend=request.frontend,
                        definition_id=request.definition_id,
                        subject_ref=request.subject_ref,
                        payload_json=request.payload_json,
                        idempotency_key=request.idempotency_key,
                    )
                    async with operations.release(
                        request.session_id, submitted.receipt.operation_id, request.frontend, AccessAction.SUBMIT
                    ) as release:
                        write_document(
                            channel,
                            ProfileWorkerSubmission(
                                identity=operations.custody.identity,
                                request_id=request.request_id,
                                receipt=submitted.receipt,
                                release=release,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                    continue
                elif isinstance(request, ProfileWorkerOperationRequest | ProfileWorkerResumeRequest):
                    if isinstance(request, ProfileWorkerResumeRequest):
                        operation_id = await operations.resume(
                            request.operation_id, request.session_id, frontend=request.frontend
                        )
                        action = AccessAction.RESUME
                    else:
                        operation_id = await operations.start(request.operation_id, request.session_id)
                        action = AccessAction.START
                    async with operations.release(
                        request.session_id, operation_id, request.frontend, action
                    ) as release:
                        write_document(
                            channel,
                            ProfileWorkerOperationReceipt(
                                identity=operations.custody.identity,
                                request_id=request.request_id,
                                operation_id=operation_id,
                                release=release,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                    continue
                elif isinstance(request, ProfileWorkerObserveRequest):
                    async with operations.observe(
                        request.session_id, request.observation, frontend=request.frontend
                    ) as (observation, release):
                        write_document(
                            channel,
                            ProfileWorkerObservation(
                                identity=operations.custody.identity,
                                request_id=request.request_id,
                                observation=observation,
                                release=release,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                    continue
                else:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                result = ProfileWorkerRefusal(
                    identity=operations.custody.identity,
                    request_id=request.request_id,
                    reason=AutomationCustodyCode.INVALID if isinstance(refusal, ValidationError) else refusal.reason,
                )
            write_document(channel, result, deadline=time.monotonic() + 5)
    except Exception:
        failed.set()
        raise


async def _serve(
    channel: WindowsRuntimeChannel,
    operation_channel: WindowsRuntimeChannel,
    custody: ProfileWorkerCustody,
    human: ProfileWorkerHumanLogin,
    operations: ProfileWorkerOperationHost,
) -> None:
    stop, failed = asyncio.Event(), asyncio.Event()

    async def expire() -> None:
        while not stop.is_set():
            await asyncio.sleep(0.1)
            try:
                await asyncio.to_thread(custody.expire)
                await asyncio.to_thread(human.expire)
            except Exception:
                failed.set()
                return

    expiry = asyncio.create_task(expire(), name="profile-custody-expiry")
    executing = asyncio.create_task(_operate(operation_channel, operations, failed), name="profile-operation-requests")
    try:
        while not failed.is_set():
            request = (await _receive(channel, failed)).root
            if failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            try:
                if isinstance(request, ProfileWorkerLeaseRequest):
                    if request.action == "install":
                        with read_secret(channel, deadline=time.monotonic() + 5) as secret:
                            custody.install(request.lease, secret)
                    elif request.action == "refresh":
                        custody.refresh(request.lease)
                    else:
                        custody.share(request.lease)
                elif isinstance(request, ProfileWorkerRetireRequest):
                    custody.retire(request.session_id)
                elif isinstance(request, ProfileWorkerHumanBindingRequest):
                    human.bind(request.candidate_id, request.lease)
                elif isinstance(
                    request,
                    ProfileWorkerSubmitRequest
                    | ProfileWorkerOperationRequest
                    | ProfileWorkerObserveRequest
                    | ProfileWorkerResumeRequest,
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                elif isinstance(request, ProfileWorkerContractRequest):
                    contract = operations.contract(request.session_id, request.definition_id)
                    write_document(
                        channel,
                        ProfileWorkerOperationContract(
                            identity=custody.identity,
                            request_id=request.request_id,
                            contract=contract,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif request.action == "password":
                    with read_secret(channel, deadline=time.monotonic() + 5) as secret:
                        candidate, login = human.authenticate(secret)
                    write_document(
                        channel,
                        ProfileWorkerPasswordOutcome(
                            identity=custody.identity,
                            request_id=request.request_id,
                            candidate_id=candidate,
                            login=login,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif request.action == "cancel_password":
                    human.close()
                elif request.action == "stop":
                    await operations.close()
                    human.close()
                    custody.close()
                result = ProfileWorkerStatus(
                    identity=custody.identity, request_id=request.request_id, sessions=custody.live_sessions()
                )
                write_document(channel, result, deadline=time.monotonic() + 5)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                write_document(
                    channel,
                    ProfileWorkerRefusal(
                        identity=custody.identity,
                        request_id=request.request_id,
                        reason=AutomationCustodyCode.INVALID
                        if isinstance(refusal, ValidationError)
                        else refusal.reason,
                    ),
                    deadline=time.monotonic() + 5,
                )
            if request.action == "stop":
                return
    finally:
        stop.set()
        executing.cancel()
        await await_cancellation_complete(expiry, task_name="profile-custody-expiry-stop")
        try:
            try:
                with suppress(asyncio.CancelledError):
                    await executing
            finally:
                await operations.close()
        finally:
            human.close()
            custody.close()


def run(arguments: list[str] | None = None) -> int:
    """Admit only an exact native runtime parent and a contained current-cohort worker."""
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--worker-id", required=True, type=UUID)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--expected-version", required=True)
    options = parser.parse_args(arguments)
    if sys.platform != "win32" or not sys.flags.isolated:
        return 2
    channel = None
    operation_channel = None
    custody = None
    try:
        if options.expected_version != version("cadrumo"):
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        endpoint = WindowsRuntimeEndpoint(storage_root=options.storage_root, worker_namespace=options.worker_id)
        channel = endpoint.connect()
        if channel.peer.process_id != options.parent_pid:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        deadline = time.monotonic() + 10
        connection = VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(
                product_version=options.expected_version, storage_identity=endpoint.storage_identity
            ),
            deadline=deadline,
        )
        identity = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
        if (
            identity.worker_id != options.worker_id
            or identity.runtime_boot_id != connection.hello.boot_id
            or identity.binding.os_owner_id != channel.peer.os_owner_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        custody = ProfileWorkerCustody(identity, storage_root=options.storage_root)
        write_document(channel, identity, deadline=deadline)
        operation_endpoint = WindowsRuntimeEndpoint(
            storage_root=options.storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        operation_channel = operation_endpoint.connect()
        if operation_channel.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        deadline = time.monotonic() + 10
        verified = VerifiedRuntimeConnection(
            operation_channel,
            expected=RuntimeClientHello(
                product_version=options.expected_version, storage_identity=operation_endpoint.storage_identity
            ),
            deadline=deadline,
        )
        if (
            verified.hello.boot_id != identity.runtime_boot_id
            or read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        write_document(operation_channel, identity, deadline=deadline)
        with ExitStack() as composition:
            composition.enter_context(
                override_settings(
                    cadrumo_local_storage_root=options.storage_root,
                    cadrumo_active_profile=str(identity.binding.profile_id),
                )
            )
            composition.enter_context(composed_profile_persistence_ports())
            operations = ProfileWorkerOperationHost(
                custody,
                authorization=WorkerAuthorizationClient(
                    identity=identity, root=options.storage_root, parent_pid=options.parent_pid
                ),
            )
            human = ProfileWorkerHumanLogin(custody, decode=operations.profile_decode_context)
            asyncio.run(_serve(channel, operation_channel, custody, human, operations))
        return 0
    except (RuntimeRefusalError, AutomationCustodyError):
        return 2
    finally:
        if custody is not None:
            custody.close()
        if channel is not None:
            channel.close()
        if operation_channel is not None:
            operation_channel.close()


if __name__ == "__main__":
    raise SystemExit(run())
