"""Create declarations through one immutable authenticated runtime session."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.modelo.declarations_calendar import DeclarationsCalendarEntryRefV1
from ....application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
)
from ....application.modelo.work_create_policy import modelo_work_create_refusal_locale_key
from ....application.operations.frontend_requests import OperationObservationRefusalV1, OperationObservationSuccessV1
from ....application.operations.public_period import PublicPeriod
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.operator_actions.models import DeclaredNextAction
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....core.period import Period
from ..declarations.models import CalendarRecoveryHandoffV1, ModeloWorkCreateHandoffV1, ModeloWorkCreateResultV1
from ..operations.runtime_controller import RuntimeOperationController
from .lifecycle import ModeloLifecycleActionUnavailableError


async def _create(
    client: RuntimeFrontendClient,
    payload: ModeloWorkCreateRequest,
    session_id: UUID,
    refresh_after_success: Callable[[], object],
) -> ModeloWorkCreateResultV1:
    deadline = time.monotonic() + 120
    subject = profile_operation_subject(str(payload.profile_id))
    controller = await RuntimeOperationController.submit(
        client,
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=payload,
        expected_session_id=session_id,
        deadline=deadline,
    )
    condition: OperationTerminalCondition | None = None
    effect = OperationEffect.UNKNOWN
    refusal_code: str | None = None
    try:
        await controller.start()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            observed = await controller.observe(0, page_limit=1)
            if isinstance(observed, OperationObservationRefusalV1):
                raise RuntimeFrontendRefusedError(observed.code.value)
            if not isinstance(observed, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            state = observed.projection
            if (
                state.operation_id != controller.operation_id
                or state.definition_id != MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
                or state.subject_ref != subject
                or state.definition_contract.request_schema
                != OperationSchemaIdentityV1.from_model(
                    schema_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID + ".request",
                    schema_version=1,
                    model_type=ModeloWorkCreateRequest,
                )
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if state.lifecycle is OperationLifecycle.TERMINAL:
                condition, effect, refusal_code = state.terminal_condition, state.effect, state.refusal_ref
                break
            await asyncio.sleep(min(0.05, remaining))
        if condition is not OperationTerminalCondition.SUCCEEDED and not (
            condition is OperationTerminalCondition.REFUSED
            and refusal_code == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
        ):
            raise RuntimeFrontendRefusedError(refusal_code or state.failure_error_code or "operation_not_successful")
        result = await controller.read_settled_result(
            state, ModeloWorkCreateProjection, result_version=1, allow_refusal_detail=True
        )
        if (
            result.profile_id != payload.profile_id
            or result.period != payload.period
            or client.profile_id != payload.profile_id
            or client.session_id != session_id
            or client.frontend is not OperationFrontendProjection.TUI
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        outcome = result.outcome
        if isinstance(outcome, ModeloWorkCreateRefusal):
            if (
                condition is not OperationTerminalCondition.REFUSED
                or refusal_code != MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
                or effect is not OperationEffect.NONE
                or outcome.modelo != payload.modelo
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            raise ModeloLifecycleActionUnavailableError(
                translated_message="tui.declarations.work_create.refusal.not_applicable",
                context={
                    "modelo": outcome.modelo,
                    "reason": outcome.reason,
                    "operation_id": str(controller.operation_id),
                    "terminal_condition": condition.value,
                    "effect": effect.value,
                    "refusal_code": refusal_code,
                },
            )
        if (
            condition is not OperationTerminalCondition.SUCCEEDED
            or refusal_code is not None
            or effect is not (OperationEffect.NONE if outcome.reused else OperationEffect.UPDATED)
            or outcome.unit.modelo != payload.modelo
            or outcome.name_applied is not None
            or outcome.applicability_guard_bypassed
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        await asyncio.to_thread(refresh_after_success)
        return ModeloWorkCreateResultV1(reused=outcome.reused, advisory_keys=outcome.advisory_keys)
    except Exception as error:
        if (
            isinstance(error, ModeloLifecycleActionUnavailableError)
            and error.context is not None
            and error.context.get("operation_id") == str(controller.operation_id)
        ):
            raise
        code = (
            error.reason.value
            if isinstance(error, RuntimeRefusalError)
            else error.reason
            if isinstance(error, RuntimeFrontendRefusedError)
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        raise ModeloLifecycleActionUnavailableError(
            code,
            context={
                "operation_id": str(controller.operation_id),
                "terminal_condition": condition.value if condition is not None else "unknown",
                "effect": effect.value,
                "refusal_code": refusal_code,
            },
        ) from None


def compose_runtime_work_create_handoff(
    client: RuntimeFrontendClient,
    *,
    refresh_after_success: Callable[[], object],
) -> ModeloWorkCreateHandoffV1:
    """Retain the originating profile and session for the declarations form."""
    if client.frontend is not OperationFrontendProjection.TUI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    profile_id, session_id = client.profile_id, client.session_id

    def create(modelo: str, filing_year: int, period: Period, /) -> ModeloWorkCreateResultV1:
        if client.profile_id != profile_id or client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if not FILING_YEAR_MIN <= filing_year <= FILING_YEAR_MAX:
            raise ModeloLifecycleActionUnavailableError(translated_message="tui.declarations.work_create.refusal.year")
        if period.filing_year != filing_year:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="tui.declarations.work_create.refusal.period"
            )
        if locale_key := modelo_work_create_refusal_locale_key(modelo):
            raise ModeloLifecycleActionUnavailableError(
                translated_message=locale_key, context={"modelo": modelo.strip()}
            )
        payload = ModeloWorkCreateRequest(
            profile_id=profile_id,
            modelo=modelo.strip(),
            period=PublicPeriod.from_period(period),
            actor="operator:tui-modelo",
        )
        return asyncio.run(_create(client, payload, session_id, refresh_after_success))

    return create


def compose_runtime_calendar_create_handoff(create: ModeloWorkCreateHandoffV1) -> CalendarRecoveryHandoffV1:
    """Use the same declaration operation for a prevalidated calendar address."""

    def recover(action: DeclaredNextAction, entry: DeclarationsCalendarEntryRefV1, /) -> None:
        if action.action.action_id != "operator.modelo.work.create":
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        create(str(entry.modelo), entry.filing_year, entry.period)

    return recover
