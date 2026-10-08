"""Expendable native worker for approval proof-frame and cleanup ordering."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes

from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorizationReply
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalReady, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from ..framing import VerifiedRuntimeConnection
from ..runtime_frame_io import read_document, write_document, write_secret
from ..windows import WindowsRuntimeEndpoint
from ..worker_authorization import worker_authorization_namespace
from ..worker_authorization_client import WorkerAuthorizationClient

_PROOF = b"synthetic-test-proof"


class PhaseSeed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    request: WorkerApprovalRequest
    parent_pid: int
    denied_id: UUID
    failed_id: UUID
    lost_id: UUID


def _request(seed: PhaseSeed, phase: str, request_id: UUID | None = None) -> WorkerApprovalRequest:
    return seed.request.model_copy(update={"request_id": request_id or uuid4(), "phase": phase})


async def _wait_file(path: Path) -> None:
    while not path.exists():
        await asyncio.sleep(0.01)


def _lose_result(root: Path, seed: PhaseSeed) -> None:
    """Send one real protected proof and close before consuming its result/ack."""
    endpoint = WindowsRuntimeEndpoint(
        storage_root=root, worker_namespace=worker_authorization_namespace(seed.identity.worker_id)
    )
    with ExitStack() as resources:
        resources.callback(endpoint.close)
        channel = endpoint.connect(timeout=5)
        resources.callback(channel.close)
        assert channel.peer.process_id == seed.parent_pid
        assert channel.peer.os_owner_id == seed.identity.binding.os_owner_id
        deadline = time.monotonic() + 15
        verified = VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
            deadline=deadline,
        )
        assert verified.hello.boot_id == seed.identity.runtime_boot_id
        request = _request(seed, "prepare", seed.lost_id)
        write_document(channel, request, deadline=deadline)
        ready = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
        assert isinstance(ready, WorkerApprovalReady)
        assert ready.request_id == request.request_id
        write_secret(channel, bytearray(_PROOF), deadline=deadline)
        while not (root / "lost_phase_done").exists():
            if (root / "lost_closed").exists():
                assert (root / "lost_phase_done").exists(), (
                    "approval phase closed before lost-result preparation completed"
                )
            time.sleep(0.01)


async def exercise(root: Path, seed: PhaseSeed) -> int:
    (root / "worker.pid").write_text(str(os.getpid()), encoding="ascii")
    await _wait_file(root / "listening")
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    try:
        try:
            await client.approval_phase(_request(seed, "prepare", seed.denied_id), SecretBytes(_PROOF))
        except ProfileAccessRefusedError as error:
            assert error.reason is AccessDenialCode.SESSION_INACTIVE
        else:
            return 3
        await _wait_file(root / "denied_closed")
        assert await client.approval_phase(_request(seed, "prepare"), SecretBytes(_PROOF)) is None
        assert await client.approval_phase(_request(seed, "inspect_recipient")) is True
        assert await client.approval_phase(_request(seed, "deliver_and_verify")) is None
        assert await client.approval_phase(_request(seed, "close")) is None
        try:
            await client.approval_phase(_request(seed, "prepare"))
        except RuntimeRefusalError as error:
            assert error.reason is RuntimeRefusalCode.INVALID_FRAME
        else:
            return 4
        try:
            await client.approval_phase(_request(seed, "prepare", seed.failed_id), SecretBytes(_PROOF))
        except ProfileAccessRefusedError as error:
            assert error.reason is AccessDenialCode.PROVIDER_REQUIRED
        else:
            return 5
        await _wait_file(root / "failed_closed")
        await asyncio.to_thread(_lose_result, root, seed)
        await _wait_file(root / "lost_closed")
        assert await client.approval_phase(_request(seed, "inspect_recipient")) is True
    except BaseException as error:
        (root / "failure").write_text(type(error).__name__, encoding="ascii")
        return 6
    (root / "done").write_text("1", encoding="ascii")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1])
    seed = PhaseSeed.model_validate_json((root / "seed.json").read_bytes())
    raise SystemExit(asyncio.run(exercise(root, seed)))
