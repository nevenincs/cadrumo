"""The CLI modelo client retains an admitted operation's uncertain identity."""

from __future__ import annotations

from typing import override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.modelo.revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionRequest,
    build_modelo_work_revision_definition,
    build_modelo_work_revision_registration,
)
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundle
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.runtime_modelo_verification import read_modelo_work_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _contract() -> OperationPublicDefinitionContractV1:
    def unavailable_repositories(
        _profile_id: str, *, operation: PinnedAuthorityOperation
    ) -> VerificationRepositoryBundle:
        raise AssertionError("public contract construction must not open profile repositories")

    definition = build_modelo_work_revision_definition(unavailable_repositories)
    return build_modelo_work_revision_registration(definition, unavailable_repositories).contract


class _InterruptedClient(RuntimeFrontendClient):
    """Return one real typed receipt, then lose only the control exchange."""

    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self._frontend = OperationFrontendProjection.CLI
        self.operation_id = "a" * 64
        self.requests: list[RuntimeOperationRequest] = []
        self.wrong_contract = False

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == MODELO_WORK_REVISION_OPERATION_DEFINITION_ID and deadline > 0
        contract = _contract()
        return contract.model_copy(update={"definition_id": "modelo.work.other"}) if self.wrong_contract else contract

    @override
    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0
        self.requests.append(request)
        if isinstance(request, RuntimeOperationSubmit):
            assert request.profile_id == self.profile_id and request.session_id == self.session_id
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                receipt=OperationSubmissionReceiptV1(operation_id=self.operation_id, secret_requirement=None),
            )
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def test_revision_read_retains_submitted_identity_when_control_connection_is_lost() -> None:
    client = _InterruptedClient()
    with pytest.raises(CliRefusedBoundaryError) as refused:
        read_modelo_work_revision(client, ModeloWorkRevisionRequest(profile_id=client.profile_id))
    assert isinstance(client.requests[0], RuntimeOperationSubmit)
    assert refused.value.context == {
        "operation_id": client.operation_id,
        "effect": "unknown",
        "reason": RuntimeRefusalCode.CONNECTION_CLOSED.value,
    }


def test_wrong_public_contract_refuses_before_submission() -> None:
    client = _InterruptedClient()
    client.wrong_contract = True
    with pytest.raises(RuntimeRefusalError, match=RuntimeRefusalCode.INVALID_FRAME.value):
        read_modelo_work_revision(client, ModeloWorkRevisionRequest(profile_id=client.profile_id))
    assert client.requests == []


def test_foreign_profile_cannot_be_selected_on_the_borrowed_connection() -> None:
    client = _InterruptedClient()
    with pytest.raises(RuntimeRefusalError, match=RuntimeRefusalCode.INVALID_FRAME.value):
        read_modelo_work_revision(client, ModeloWorkRevisionRequest(profile_id=uuid4()))
    assert client.requests == []
