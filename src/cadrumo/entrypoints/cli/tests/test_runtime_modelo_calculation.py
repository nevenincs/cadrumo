"""The registered calculation CLI keeps strict contract and uncertain identity."""

from __future__ import annotations

from typing import NoReturn, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    Modelo349RectificacionRowWireV1,
    ModeloWorkCalculateRequest,
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from cadrumo.entrypoints.cli._modelo_cli_support import parse_calculation_wire_row_spec
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.runtime_modelo_calculation import run_modelo_work_calculation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_modelo_work_calculate_definition(
        calculation_action_ports_factory=_unavailable,
        attachment_store_factory=_unavailable,
    )
    return build_modelo_work_calculate_registration(definition).contract


class _InterruptedClient(RuntimeFrontendClient):
    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self._frontend = OperationFrontendProjection.CLI
        self.requests: list[RuntimeOperationRequest] = []
        self.wrong_contract = False

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID and deadline > 0
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
                receipt=OperationSubmissionReceiptV1(operation_id="a" * 64, secret_requirement=None),
            )
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def test_calculation_retains_operation_id_after_submit_when_control_is_lost() -> None:
    client = _InterruptedClient()
    with pytest.raises(CliRefusedBoundaryError) as refused:
        run_modelo_work_calculation(client, ModeloWorkCalculateRequest(work_unit_id="b" * 64, actor="operator"))
    assert isinstance(client.requests[0], RuntimeOperationSubmit)
    assert refused.value.context == {
        "operation_id": "a" * 64,
        "effect": "unknown",
        "reason": RuntimeRefusalCode.CONNECTION_CLOSED.value,
    }


def test_calculation_wrong_contract_refuses_before_submit() -> None:
    client = _InterruptedClient()
    client.wrong_contract = True
    with pytest.raises(RuntimeRefusalError, match=RuntimeRefusalCode.INVALID_FRAME.value):
        run_modelo_work_calculation(client, ModeloWorkCalculateRequest(work_unit_id="b" * 64, actor="operator"))
    assert client.requests == []


def test_private_rows_over_old_frame_limit_retain_operation_id_after_control_loss() -> None:
    client = _InterruptedClient()
    overrides = tuple(ModeloCalculationOverride(key=f"casilla-{index}", value="9" * 32) for index in range(1800))
    request = ModeloWorkCalculateRequest(
        work_unit_id="b" * 64,
        actor="operator",
        inputs=ModeloCalculationInputFieldsV1(casilla_overrides=overrides),
    )
    assert len(request.model_dump_json()) > 60_000
    with pytest.raises(CliRefusedBoundaryError) as refused:
        run_modelo_work_calculation(client, request)
    assert isinstance(client.requests[0], RuntimeOperationSubmit)
    assert refused.value.context == {
        "operation_id": "a" * 64,
        "effect": "unknown",
        "reason": RuntimeRefusalCode.CONNECTION_CLOSED.value,
    }
    assert "9999" not in str(refused.value)


def test_over_limit_private_rows_refuse_before_transport_or_exception_echo() -> None:
    client = _InterruptedClient()
    overrides = tuple(ModeloCalculationOverride(key=f"casilla-{index}", value="9" * 3500) for index in range(4800))
    request = ModeloWorkCalculateRequest(
        work_unit_id="b" * 64,
        actor="operator",
        inputs=ModeloCalculationInputFieldsV1(casilla_overrides=overrides),
    )
    assert len(request.model_dump_json().encode("utf-8")) > SUBMISSION_PAYLOAD_MAX_BYTES
    with pytest.raises(RuntimeRefusalError, match=RuntimeRefusalCode.INVALID_FRAME.value) as refused:
        run_modelo_work_calculation(client, request)
    assert "9999" not in str(refused.value)
    assert client.requests == []


def test_m349_rectification_row_parses_without_local_registry_or_profile_authority() -> None:
    row = parse_calculation_wire_row_spec(
        'rectificacion codigo_pais=DE nif_comunitario=DE123456789 razon_social="EU trader" '
        "clave_operacion=E ejercicio=2025 periodo=4T base_rectificada=25.00 base_anterior=30.00"
    )
    assert isinstance(row, Modelo349RectificacionRowWireV1)
    assert row.codigo_pais == "DE"
    assert row.periodo == "4T"
