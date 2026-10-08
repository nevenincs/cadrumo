"""Native approval phases use a separate protected proof frame and retire lost work."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes, ValidationError

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
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
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.application.user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID

from .. import worker_authorization
from ..windows_process import WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from .profile_worker_support import owner_id
from .worker_approval_phase_fixture import PhaseSeed
from .worker_completion import wait_file, wait_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows job and pipe custody"),
]

_PROOF = b"synthetic-test-proof"


class PhaseAuthority:
    """Explicit test owner: phases never enter a COMMIT guard or publish grants."""

    def __init__(self, seed: PhaseSeed, root: Path) -> None:
        self.seed, self.root = seed, root
        self.guard = RLock()
        self.authorize_calls = 0
        self.preflights: list[UUID] = []
        self.phase_calls: list[tuple[UUID, str]] = []
        self.proof_count = 0

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        self.authorize_calls += 1
        raise AssertionError("an approval phase cannot acquire a COMMIT permit")
        yield  # pragma: no cover

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        assert request.binding == self.seed.request.binding
        assert request.request.action is AccessAction.START
        assert request.policy.requires_human
        self.preflights.append(request.request_id)
        if request.request_id == self.seed.denied_id:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        assert self.guard.acquire(blocking=False)
        self.guard.release()
        self.phase_calls.append((request.request_id, request.phase))
        if request.phase == "close":
            if request.request_id in {self.seed.denied_id, self.seed.failed_id, self.seed.lost_id}:
                marker = {
                    self.seed.denied_id: "denied_closed",
                    self.seed.failed_id: "failed_closed",
                    self.seed.lost_id: "lost_closed",
                }[request.request_id]
                (self.root / marker).write_text("1", encoding="ascii")
            return None
        if request.phase == "prepare":
            assert password is not None
            assert password.get_secret_value() == _PROOF
            self.proof_count += 1
            if request.request_id == self.seed.failed_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROVIDER_REQUIRED)
            if request.request_id == self.seed.lost_id:
                (self.root / "lost_phase_done").write_text("1", encoding="ascii")
            return None
        assert password is None
        if request.phase == "inspect_recipient":
            return True
        return None

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def test_approval_phase_schema_rejects_wrong_action_and_mismatched_binding() -> None:
    profile_id = uuid4()
    binding = RuntimeApprovalBinding(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        profile_binding=ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        enrollment_request_id=uuid4(),
        review_digest="b" * 64,
    )
    request = OperationAccessRequest(
        profile_id=profile_id,
        definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
        action=AccessAction.START,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset(),
        period_independent=True,
        destination_id=uuid4(),
    )
    policy = OperationAccessPolicy(
        definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
        definition_contract_digest="c" * 64,
        actions=frozenset({AccessAction.START, AccessAction.COMMIT}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
        requires_human=True,
    )
    valid = WorkerApprovalRequest(
        request_id=uuid4(),
        connection_id=binding.connection_id,
        session_id=binding.session_id,
        binding=binding,
        request=request,
        policy=policy,
        phase="prepare",
    )
    with pytest.raises(ValidationError):
        WorkerApprovalRequest.model_validate(
            valid.model_copy(
                update={"request": request.model_copy(update={"action": AccessAction.COMMIT})}
            ).model_dump()
        )
    with pytest.raises(ValidationError):
        WorkerApprovalRequest.model_validate(valid.model_copy(update={"connection_id": uuid4()}).model_dump())


@pytest.mark.parametrize("refuse_lost_proof", [False, True])
def test_protected_approval_phase_preflight_and_lost_result_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refuse_lost_proof: bool
) -> None:
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
    definition = AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
    request = WorkerApprovalRequest(
        request_id=uuid4(),
        connection_id=binding.connection_id,
        session_id=binding.session_id,
        binding=binding,
        request=OperationAccessRequest(
            profile_id=identity.binding.profile_id,
            definition_id=definition,
            action=AccessAction.START,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=definition,
            definition_contract_digest="c" * 64,
            actions=frozenset({AccessAction.START, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
        phase="prepare",
    )
    seed = PhaseSeed(
        identity=identity,
        request=request,
        parent_pid=os.getpid(),
        denied_id=uuid4(),
        failed_id=uuid4(),
        lost_id=uuid4(),
    )
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    scope = WindowsProcessScope()
    servers: list[WorkerAuthorizationServer] = []
    try:
        process = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo.adapters.local_runtime.tests.worker_approval_phase_fixture", str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        wait_file(tmp_path / "worker.pid", process)
        worker_pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        assert worker_pid in scope.active_process_ids()
        authority = PhaseAuthority(seed, tmp_path)
        refused_proofs: list[UUID] = []
        if refuse_lost_proof:
            read_secret = worker_authorization.read_secret

            @contextmanager
            def read_proof(channel: RuntimeByteChannel, *, deadline: float) -> Generator[bytearray]:
                with read_secret(channel, deadline=deadline) as proof:
                    if authority.preflights[-1] == seed.lost_id:
                        refused_proofs.append(seed.lost_id)
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    yield proof

            monkeypatch.setattr(worker_authorization, "read_secret", read_proof)
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
        result = wait_process(process)
        if refuse_lost_proof:
            assert result == 6
            assert (tmp_path / "failure").read_text(encoding="ascii") == "AssertionError"
            assert (tmp_path / "lost_closed").is_file()
            assert not (tmp_path / "lost_phase_done").exists()
            assert not (tmp_path / "done").exists()
            assert refused_proofs == [seed.lost_id]
            assert authority.proof_count == 2
            assert (seed.lost_id, "prepare") not in authority.phase_calls
        else:
            assert result == 0, (tmp_path / "failure").read_text(encoding="ascii")
            assert (tmp_path / "done").is_file()
            assert authority.proof_count == 3  # successful, refused, and lost-result proof
        assert authority.authorize_calls == 0
        assert (seed.denied_id, "prepare") not in authority.phase_calls
        for request_id in (seed.denied_id, seed.failed_id, seed.lost_id):
            assert (request_id, "close") in authority.phase_calls
        server.require_healthy()
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle(timeout=6)
    assert not scope.active_process_ids()
