"""Expendable contained worker that asks its owner to start the runtime server over one held COMMIT channel."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.adapters.worker_authorization_client import WorkerAuthorizationClient
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorizationRequest


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


if __name__ == "__main__":
    fixture_root = Path(sys.argv[1])
    fixture_seed = Seed.model_validate_json((fixture_root / "seed.json").read_bytes())
    raise SystemExit(asyncio.run(exercise(fixture_root, fixture_seed)))
