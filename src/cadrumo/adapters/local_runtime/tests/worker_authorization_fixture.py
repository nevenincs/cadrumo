"""Expendable native child for authorization-channel death and expiry proofs."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorizationRequest
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from ..worker_authorization_client import WorkerAuthorizationClient


class Seed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    request: WorkerAuthorizationRequest
    parent_pid: int
    mode: Literal["release", "disconnect", "expire", "deny", "cancel"]


async def exercise(root: Path, seed: Seed) -> int:
    candidate = root / "worker.pid.pending"
    candidate.write_text(str(os.getpid()), encoding="ascii")
    candidate.replace(root / "worker.pid")
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    deadline = time.monotonic() + 10
    if seed.mode == "cancel":
        while not (root / "listening").exists():
            if time.monotonic() >= deadline:
                return 2
            await asyncio.sleep(0.01)

        async def cancelled_body() -> None:
            async with client.guard(seed.request):
                (root / "inside").write_text("forbidden", encoding="ascii")

        attempt = asyncio.create_task(cancelled_body())
        while not (root / "authorizing").exists():
            if time.monotonic() >= deadline:
                return 2
            await asyncio.sleep(0.01)
        attempt.cancel()
        await asyncio.sleep(0.02)
        attempt.cancel()
        (root / "grant").write_text("1", encoding="ascii")
        try:
            await attempt
        except asyncio.CancelledError:
            (root / "cancelled").write_text("1", encoding="ascii")
            return 0
        return 3
    while True:
        try:
            async with client.guard(seed.request):
                child = subprocess.Popen(
                    [sys.executable, "-I", "-c", "import time; time.sleep(15)"],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                (root / "descendant").write_text(str(child.pid), encoding="ascii")
                (root / "inside").write_text("1", encoding="ascii")
                while not (root / "release").exists():
                    await asyncio.sleep(0.01)
                if seed.mode == "disconnect":
                    os._exit(4)
                child.terminate()
                child.wait(timeout=3)
            (root / "done").write_text("1", encoding="ascii")
            return 0
        except ProfileAccessRefusedError:
            (root / "denied").write_text("1", encoding="ascii")
            return 0
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                (root / "refusal").write_text(error.reason.value, encoding="ascii")
                return 2
            await asyncio.sleep(0.02)


if __name__ == "__main__":
    root = Path(sys.argv[1])
    seed = Seed.model_validate_json((root / "seed.json").read_bytes())
    raise SystemExit(asyncio.run(exercise(root, seed)))
