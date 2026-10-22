"""Expendable contained worker that asks its owner to start the runtime server over one held COMMIT channel."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_runtime.adapters.worker_authorization_client import WorkerAuthorizationClient
from cadrumo_runtime.adapters.worker_authorization_connections import WorkerAuthorizationConnections
from cadrumo_runtime.adapters.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorizationPermit,
    WorkerAuthorizationRequest,
    WorkerServerStart,
    WorkerServerStarted,
)


class Seed(BaseModel):
    """The worker identity and the exact authority request the runtime side of the test expects."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    request: WorkerAuthorizationRequest
    parent_pid: int


async def exercise(root: Path, seed: Seed) -> int:
    """Ask once under a held fence, record the answer, and show a second ask on the same fence is refused."""
    pending_pid = root / "worker.pid.pending"
    pending_pid.write_text(str(os.getpid()), encoding="ascii")
    pending_pid.replace(root / "worker.pid")
    while not (root / "listening").exists():
        await asyncio.sleep(0.01)
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    try:
        async with client.guard(seed.request) as lease:
            process_id = lease.start_runtime_server()
            try:
                lease.start_runtime_server()
            except RefusalError as error:
                if error.reason is not RefusalCode.INVALID_FRAME:
                    return 3
            else:
                return 4
    except BaseException as error:
        (root / "failure").write_text(type(error).__name__, encoding="ascii")
        return 6
    (root / "started.json").write_text(json.dumps({"server": process_id}), encoding="utf-8")
    return 0


class _UncheckedLease(WorkerAuthorizationLease):
    """A worker that skips its own lease's server-start check, so only its owner's check stands."""

    def send_unchecked_start(self) -> WorkerServerStarted:
        channel, permit = self._channel, self._permit
        if channel is None or not isinstance(permit, WorkerAuthorizationPermit):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        command = WorkerServerStart(request_id=self.request.request_id, permit_id=permit.permit_id, command_id=uuid4())
        write_document(channel, command, deadline=exchange_deadline())
        return read_document(channel, WorkerServerStarted, deadline=exchange_deadline())


def exercise_unchecked(root: Path, seed: Seed) -> int:
    """Hold the fence and send the start instruction without the lease's check; record what came back."""
    pending_pid = root / "worker.pid.pending"
    pending_pid.write_text(str(os.getpid()), encoding="ascii")
    pending_pid.replace(root / "worker.pid")
    while not (root / "listening").exists():
        time.sleep(0.01)
    lease = _UncheckedLease(
        connections=WorkerAuthorizationConnections(identity=seed.identity, root=root, parent_pid=seed.parent_pid),
        request=seed.request,
    )
    try:
        lease.acquire()
        reply = lease.send_unchecked_start()
    except BaseException as error:
        (root / "failure").write_text(type(error).__name__, encoding="ascii")
        return 6
    (root / "started.json").write_text(json.dumps({"server": reply.process_id}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    fixture_root = Path(sys.argv[1])
    fixture_seed = Seed.model_validate_json((fixture_root / "seed.json").read_bytes())
    if sys.argv[2:] == ["unchecked"]:
        raise SystemExit(exercise_unchecked(fixture_root, fixture_seed))
    raise SystemExit(asyncio.run(exercise(fixture_root, fixture_seed)))
