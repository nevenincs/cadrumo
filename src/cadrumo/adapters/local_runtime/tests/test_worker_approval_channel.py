"""Native held-approval publication mechanics; grant policy is an explicit fault port."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from threading import RLock, get_ident
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentReceipt,
    EnrollmentStage,
    EnrollmentTransition,
)
from cadrumo.application.user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
from cadrumo.core.time.clock import now

from ..windows_process import WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from .profile_worker_support import owner_id
from .worker_approval_fixture import Seed
from .worker_completion import wait_file, wait_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows job and pipe custody"),
]


class ApprovalAuthority:
    """Record that publication reenters the exact thread holding the original lock."""

    def __init__(self, seed: Seed) -> None:
        self.seed = seed
        self.guard = RLock()
        self.held_thread: int | None = None
        self.publications = 0
        self.exits = 0

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest) or request != self.seed.request:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        with self.guard:
            self.held_thread = get_ident()
            try:
                yield AccessAllowed(
                    profile_id=request.request.profile_id,
                    session_id=request.session_id,
                    expires_at=now() + timedelta(seconds=25),
                )
            finally:
                self.exits += 1
                self.held_thread = None

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        with self.guard:
            assert self.held_thread == get_ident()
            assert authority == self.seed.request
            assert command.phase == "commit_review"
            self.publications += 1
            if command.binding != self.seed.binding:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if self.publications == 4:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            if self.publications != 1:
                return None
            receipt = EnrollmentReceipt(
                request_id=command.binding.enrollment_request_id,
                profile_id=command.binding.profile_binding.profile_id,
                stage=EnrollmentStage.REQUESTED,
                review_digest=command.binding.review_digest,
                grant_id=uuid4(),
                key_id=None,
                credential_reference=None,
            )
            return EnrollmentTransition(receipt=receipt, published=False)


def test_held_commit_publication_reenters_owner_and_known_refusals_release(tmp_path: Path) -> None:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(), installation_id=uuid4(), os_owner_id=owner_id(), custody_generation=1, dek_epoch=uuid4()
        ),
    )
    binding = RuntimeApprovalBinding(
        worker_id=identity.worker_id,
        runtime_boot_id=identity.runtime_boot_id,
        profile_binding=identity.binding,
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        enrollment_request_id=uuid4(),
        review_digest="b" * 64,
    )
    request = WorkerAuthorizationRequest(
        request_id=uuid4(),
        connection_id=binding.connection_id,
        session_id=binding.session_id,
        operation_id=binding.operation_id,
        request=OperationAccessRequest(
            profile_id=identity.binding.profile_id,
            definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
            action=AccessAction.COMMIT,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
            definition_contract_digest="c" * 64,
            actions=frozenset({AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )
    seed = Seed(identity=identity, request=request, binding=binding, parent_pid=os.getpid())
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    scope = WindowsProcessScope()
    servers: list[WorkerAuthorizationServer] = []
    try:
        process = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo.adapters.local_runtime.tests.worker_approval_fixture", str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        wait_file(tmp_path / "worker.pid", process)
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        assert worker_pid in scope.active_process_ids()
        authority = ApprovalAuthority(seed)
        server = WorkerAuthorizationServer(
            identity=identity,
            root=tmp_path,
            process_id=worker_pid,
            owns_process=lambda pid: pid in scope.active_process_ids(),
            contain=scope.terminate,
            owner=authority,
        )
        servers.append(server)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        assert wait_process(process) == 0, (tmp_path / "failure").read_text(encoding="ascii")
        assert (tmp_path / "done").is_file()
        assert authority.publications == 5
        assert authority.exits == 5
        server.require_healthy()
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle(timeout=6)
