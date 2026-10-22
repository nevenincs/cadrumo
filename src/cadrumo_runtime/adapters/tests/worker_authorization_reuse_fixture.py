"""Expendable native worker that drives several exchanges over its pooled authorization connections."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Awaitable
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
)

from ..worker_authorization import worker_authorization_namespace
from ..worker_authorization_client import WorkerAuthorizationClient
from ..worker_transport import worker_endpoint

type Mode = Literal[
    "reuse",
    "check",
    "revoke",
    "frame",
    "timeout",
    "secret",
    "cancel",
    "incarnation",
    "stop",
    "idle_loss",
    "permit_loss",
    "foreign_peer",
    "abandoned_handshake",
    "idle_close",
]


class ReuseSeed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    request: WorkerAuthorizationRequest
    parent_pid: int
    mode: Mode
    denied_session: UUID
    paused_session: UUID


def _wait(root: Path, name: str) -> None:
    while not (root / name).exists():
        time.sleep(0.01)


def _mark(root: Path, name: str, text: str = "1") -> None:
    pending = root / f"{name}.pending"
    pending.write_text(text, encoding="ascii")
    pending.replace(root / name)


def _request(seed: ReuseSeed, action: AccessAction, *, session: UUID | None = None) -> WorkerAuthorizationRequest:
    """A fresh request for one exchange; nothing but its id and action differs between exchanges."""
    return seed.request.model_copy(
        update={
            "request_id": uuid4(),
            "session_id": session or seed.request.session_id,
            "request": seed.request.request.model_copy(update={"action": action}),
        }
    )


async def _stage(client: WorkerAuthorizationClient, seed: ReuseSeed) -> None:
    async with client.guard(_request(seed, AccessAction.START)):
        pass


async def _refused(root: Path, name: str, attempt: Awaitable[None]) -> None:
    """Record how an exchange that must fail was refused."""
    try:
        await attempt
    except ProfileAccessRefusedError as error:
        _mark(root, name, f"access:{error.reason.value}")
        return
    except RefusalError as error:
        _mark(root, name, f"refusal:{error.reason.value}")
        return
    _mark(root, name, "allowed")


async def _model_run(client: WorkerAuthorizationClient, seed: ReuseSeed, answer_seconds: float) -> None:
    async with client.guard(_request(seed, AccessAction.START)) as lease:
        await asyncio.to_thread(lease.model_run, "text_extraction", None, bytearray(), answer_seconds=answer_seconds)


async def _frame_fault(client: WorkerAuthorizationClient) -> None:
    """Send the runtime a frame no exchange starts with, as a broken worker would."""
    channel = client.connections.checkout(time.monotonic() + 5)
    try:
        write_document(channel, WorkerAuthorizationAcknowledgement(request_id=uuid4()), deadline=time.monotonic() + 5)
        read_document(channel, WorkerAuthorizationReply, deadline=time.monotonic() + 5)
    finally:
        client.connections.checkin(channel, reusable=False)


async def _cancelled_stage(root: Path, client: WorkerAuthorizationClient, seed: ReuseSeed) -> None:
    async def body() -> None:
        async with client.guard(_request(seed, AccessAction.START, session=seed.paused_session)):
            _mark(root, "inside_cancelled")

    attempt = asyncio.create_task(body())
    while not (root / "authorizing").exists():
        await asyncio.sleep(0.01)
    attempt.cancel()
    _mark(root, "grant")
    try:
        await attempt
    except asyncio.CancelledError:
        _mark(root, "cancelled")


async def exercise(root: Path, seed: ReuseSeed) -> int:
    _mark(root, "worker.pid", str(os.getpid()))
    _wait(root, "listening")
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    mode = seed.mode
    await _stage(client, seed)
    if mode == "reuse":
        await client.check(_request(seed, AccessAction.START))
        client.operations_advanced(("c" * 64,))
        await _stage(client, seed)
    elif mode == "check":
        await _refused(
            root, "check_refused", client.check(_request(seed, AccessAction.START, session=seed.denied_session))
        )
        async with client.guard(_request(seed, AccessAction.COMMIT)):
            _mark(root, "commit_held")
            _wait(root, "commit_probed")
        await client.check(_request(seed, AccessAction.START))
        _mark(root, "checked")
        _wait(root, "check_probed")
    elif mode == "revoke":
        _mark(root, "first")
        _wait(root, "revoked")
        await _refused(root, "second", _stage(client, seed))
    elif mode == "frame":
        await _refused(root, "fault", _frame_fault(client))
        await _stage(client, seed)
    elif mode in {"timeout", "secret"}:
        await _refused(root, "fault", _model_run(client, seed, 1.0 if mode == "timeout" else 30.0))
        await _stage(client, seed)
    elif mode == "cancel":
        await _cancelled_stage(root, client, seed)
        await _stage(client, seed)
    elif mode in {"incarnation", "stop"}:
        # A second stage first, so the connection left idle is one already reused.
        await _stage(client, seed)
        _mark(root, "idle")
        _wait(root, "changed")
        await _refused(root, "second", _stage(client, seed))
    elif mode == "idle_loss":
        await _stage(client, seed)
        _mark(root, "opened", str(client.connections.opened))
        os._exit(0)
    elif mode == "foreign_peer":
        _mark(root, "idle")
        _wait(root, "changed")
        await _stage(client, seed)
    elif mode == "abandoned_handshake":
        # The exact worker connects and closes before its hello, as a checkout past its deadline would.
        endpoint = worker_endpoint(
            storage_root=root, worker_namespace=worker_authorization_namespace(seed.identity.worker_id)
        )
        try:
            endpoint.connect(timeout=5).close()
        finally:
            endpoint.close()
        _mark(root, "idle")
        _wait(root, "changed")
        await _stage(client, seed)
    elif mode == "idle_close":
        await _stage(client, seed)
        # The live worker closes its idle, already reused connection.
        client.close()
        _mark(root, "idle")
        _wait(root, "changed")
        client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
        await _stage(client, seed)
    else:
        async with client.guard(_request(seed, AccessAction.COMMIT)):
            _mark(root, "opened", str(client.connections.opened))
            os._exit(4)
    _mark(root, "opened", str(client.connections.opened))
    client.close()
    return 0


if __name__ == "__main__":
    fixture_root = Path(sys.argv[1])
    fixture_seed = ReuseSeed.model_validate_json((fixture_root / "seed.json").read_bytes())
    raise SystemExit(asyncio.run(exercise(fixture_root, fixture_seed)))
