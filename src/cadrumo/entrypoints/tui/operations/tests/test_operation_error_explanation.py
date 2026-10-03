"""The TUI reads a stopped operation's recorded detail and says the executor's own message."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, NoReturn, cast
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from cadrumo.application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.tui.operations.controller_port import OperationErrorDetailPort
from cadrumo.entrypoints.tui.operations.refusal_explanation import operation_error_explanation
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

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


def _controller(wire: _DetailWire) -> RuntimeOperationController:
    return RuntimeOperationController(
        client=cast(RuntimeFrontendClient, wire), operation_id=_OPERATION, session_id=_SESSION
    )


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


def test_the_explanation_is_the_registered_message_with_its_recorded_context() -> None:
    """The operator reads the same sentence the in-process refusal would have rendered."""
    expected = resolve_error_message(
        RecordedRegisteredError(
            _REFUSAL_CODE,
            context={"aggregator_label": "probe", "modelo": "111"},
            translated_message=_MESSAGE_KEY,
        )
    )

    assert operation_error_explanation(_detail()) == expected
    assert operation_error_explanation(None) is None


def test_a_record_fault_has_no_message_of_its_own() -> None:
    """An internal record fault keeps the generic failure wording the modal already shows."""
    fault = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.RECORD_VALIDATION,
        error_code=None,
        message_key=None,
        context=(OperationErrorContextEntryV1(key="failing_record", value="BucketEvent"),),
    )

    assert operation_error_explanation(fault) is None
