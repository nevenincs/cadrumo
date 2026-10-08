"""Expendable native worker for one held approval-publication channel."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorizationRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from ..worker_authorization_client import WorkerAuthorizationClient


class Seed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    request: WorkerAuthorizationRequest
    binding: RuntimeApprovalBinding
    parent_pid: int


async def exercise(root: Path, seed: Seed) -> int:
    pending_pid = root / "worker.pid.pending"
    pending_pid.write_text(str(os.getpid()), encoding="ascii")
    pending_pid.replace(root / "worker.pid")
    while not (root / "listening").exists():
        await asyncio.sleep(0.01)
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    try:
        async with client.guard(seed.request) as lease:
            receipt = lease.publish_approval(seed.binding, "commit_review")
            assert receipt is not None
            assert receipt.receipt.request_id == seed.binding.enrollment_request_id
            assert receipt.receipt.review_digest == seed.binding.review_digest
            assert receipt.receipt.stage is EnrollmentStage.REQUESTED
            assert not receipt.published
            try:
                lease.publish_approval(seed.binding, "commit_review")
            except RuntimeRefusalError as error:
                assert error.reason is RuntimeRefusalCode.INVALID_FRAME
            else:
                return 3
        async with client.guard(seed.request) as lease:
            assert lease.publish_approval(seed.binding, "commit_review") is None
        altered = seed.binding.model_copy(
            update={"profile_binding": seed.binding.profile_binding.model_copy(update={"profile_id": uuid4()})}
        )
        async with client.guard(seed.request) as lease:
            try:
                lease.publish_approval(altered, "commit_review")
            except ProfileAccessRefusedError as error:
                assert error.reason is AccessDenialCode.PROFILE_MISMATCH
            else:
                return 4
        async with client.guard(seed.request) as lease:
            try:
                lease.publish_approval(seed.binding, "commit_review")
            except ProfileAccessRefusedError as error:
                assert error.reason is AccessDenialCode.SESSION_INACTIVE
            else:
                return 5
        async with client.guard(seed.request) as lease:
            assert lease.publish_approval(seed.binding, "commit_review") is None
    except BaseException as error:
        (root / "failure").write_text(type(error).__name__, encoding="ascii")
        return 6
    (root / "done").write_text("1", encoding="ascii")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1])
    seed = Seed.model_validate_json((root / "seed.json").read_bytes())
    raise SystemExit(asyncio.run(exercise(root, seed)))
