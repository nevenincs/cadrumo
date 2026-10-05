"""A single-phase definition names itself as its only phase and is interrupted on owner loss."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ....core.models import STRICT_FROZEN_CONFIG
from ..capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operation_definition import OperationDefinition, build_single_phase_definition
from ..owner import OperationExecutorContext
from ..registry import OperationFrontendProjection, OperationReconciliationPolicy

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFINITION_ID = "test.single-phase"


class _Request(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    name: str


class _Result(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    name: str


class _Executor:
    async def execute(self, request: object, context: OperationExecutorContext) -> str | None:
        del request, context
        return None


def _definition(*, executor: object | None = None, public_error_detail: bool = False) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=_DEFINITION_ID,
        request_type=_Request,
        result_type=_Result,
        executor_type=_Executor,
        build=(lambda: executor) if executor is not None else _Executor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
        public_error_detail=public_error_detail,
    )


def test_definition_declares_its_own_id_as_the_sole_phase() -> None:
    definition = _definition()

    assert definition.definition_id == _DEFINITION_ID
    assert definition.phase_codes == (_DEFINITION_ID,)
    assert definition.interaction_kinds == frozenset()
    assert definition.reconciliation_policy is OperationReconciliationPolicy.INTERRUPT
    assert definition.capabilities is RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.TUI})
    assert definition.request_type is _Request
    assert definition.result_type is _Result


def test_definition_builds_the_declared_executor_and_nothing_else() -> None:
    executor = _Executor()

    assert _definition(executor=executor).executor_factory.create() is executor
    with pytest.raises(TypeError):
        _definition(executor=object()).executor_factory.create()


def test_optional_declarations_default_closed_and_pass_through_when_given() -> None:
    assert _definition().public_error_detail is False
    assert _definition(public_error_detail=True).public_error_detail is True


def test_definition_refuses_an_unregistered_error_detail_declaration_without_a_result_model() -> None:
    with pytest.raises(ValidationError):
        build_single_phase_definition(
            definition_id=_DEFINITION_ID,
            request_type=_Request,
            result_type=None,
            executor_type=_Executor,
            build=_Executor,
            capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
            permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
            refusal_detail_codes=frozenset({"REFUSED_TEST"}),
        )
