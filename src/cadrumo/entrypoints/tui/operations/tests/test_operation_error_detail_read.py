"""The TUI reads a stopped operation's recorded detail under its own schema identity."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, NoReturn, cast
from uuid import UUID

import pytest

from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from .....application.modelo.calculation_operation import (
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from .....application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from .....application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from .....application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.operations.registry import OperationPublicContractSetV1, OperationPublicDefinitionContractV1
from .....core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..controller_port import OperationErrorDetailPort

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION = "c" * 64
_NOW = datetime(2026, 10, 2, tzinfo=UTC)
_REFUSAL_CODE = "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"
_MESSAGE_KEY = "aggregation.grouping.errors.unsupported_modelo"


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_modelo_work_calculate_definition(
        calculation_action_ports_factory=_unavailable,
        attachment_store_factory=_unavailable,
    )
    return build_modelo_work_calculate_registration(definition).contract


def _detail() -> OperationErrorDetailV1:
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key=_MESSAGE_KEY,
        context=(
            OperationErrorContextEntryV1(key="aggregator_label", value="probe"),
            OperationErrorContextEntryV1(key="modelo", value="111"),
        ),
    )


def _projection(
    contract: OperationPublicDefinitionContractV1, condition: OperationTerminalCondition
) -> OperationPublicProjectionV1:
    return OperationPublicProjectionV1(
        operation_id=_OPERATION,
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref="b" * 64,
        revision=3,
        anchor_cursor=1,
        definition_contract=contract,
        contract_set_digest=OperationPublicContractSetV1.build((contract,)).contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref="e" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=_REFUSAL_CODE if condition is OperationTerminalCondition.REFUSED else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )


class _DetailWire:
    """An explicit transport port that serves one recorded detail document."""

    profile_id = _PROFILE
    session_id = _SESSION
    frontend = OperationFrontendProjection.TUI

    def __init__(self, contract: OperationPublicDefinitionContractV1) -> None:
        self.contract = contract
        self.reads: list[OperationResultProjectionRequestV1] = []

    def read_result_document(
        self, request: OperationResultProjectionRequestV1, *, deadline: float | None = None
    ) -> dict[str, Any]:
        assert deadline is not None
        self.reads.append(request)
        return json.loads(
            OperationResultProjectionSuccessV1[OperationErrorDetailV1](
                result_schema=operation_error_detail_schema(),
                definition_contract_digest=self.contract.definition_contract_digest,
                projection=_detail(),
            ).model_dump_json()
        )


def _controller(wire: _DetailWire) -> OperationController:
    return OperationController(client=cast(FrontendClient, wire), operation_id=_OPERATION, session_id=_SESSION)


def test_the_runtime_controller_reads_a_refused_operations_recorded_detail() -> None:
    """A refused operation's detail is read under its own schema identity and validated."""
    contract = _contract()
    wire = _DetailWire(contract)
    controller = _controller(wire)

    assert isinstance(controller, OperationErrorDetailPort)
    detail = asyncio.run(controller.settled_error_detail(_projection(contract, OperationTerminalCondition.REFUSED)))

    assert detail == _detail()
    assert [read.result_schema for read in wire.reads] == [operation_error_detail_schema()]


def test_a_succeeded_operation_is_never_asked_for_error_detail() -> None:
    """Only a refused or failed terminal can carry detail, so nothing else is read."""
    contract = _contract()
    wire = _DetailWire(contract)

    detail = asyncio.run(
        _controller(wire).settled_error_detail(_projection(contract, OperationTerminalCondition.SUCCEEDED))
    )

    assert detail is None
    assert wire.reads == []
