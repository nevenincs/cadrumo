"""Create declarations through one immutable authenticated runtime session."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.modelo.declarations_calendar import DeclarationsCalendarEntryRefV1
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ....application.modelo.work_create_policy import modelo_work_create_refusal_locale_key
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.public_period import PublicPeriod
from ....application.operations.registry import OperationFrontendProjection
from ....application.operations.schema_identity import OperationSchemaIdentityV1
from ....application.operator_actions.models import DeclaredNextAction
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.workbench_generation_contracts import WorkbenchGenerationV1
from ....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....core.period import Period
from ..declarations.models import CalendarRecoveryHandoffV1, ModeloWorkCreateHandoffV1, ModeloWorkCreateResultV1
from ..operations.runtime_controller import RuntimeOperationController, await_terminal_projection
from .lifecycle import ModeloLifecycleActionUnavailableError


async def _read_terminal_state(
    controller: RuntimeOperationController,
    payload: ModeloWorkCreateRequest,
    subject: str,
    deadline: float,
) -> OperationPublicProjectionV1:
    await controller.start()
    return await await_terminal_projection(
        controller,
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        request_schema=OperationSchemaIdentityV1.from_model(
            schema_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=ModeloWorkCreateRequest,
        ),
        deadline=deadline,
    )


def _admitted_terminal_details(
    state: OperationPublicProjectionV1,
) -> tuple[OperationTerminalCondition, OperationEffect, str | None]:
    condition, refusal_code = state.terminal_condition, state.refusal_ref
    if condition is OperationTerminalCondition.SUCCEEDED:
        return condition, state.effect, refusal_code
    if (
        condition is OperationTerminalCondition.REFUSED
        and refusal_code == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
    ):
        return condition, state.effect, refusal_code
    raise RuntimeFrontendRefusedError(refusal_code or state.failure_error_code or "operation_not_successful")


async def _read_create_projection(
    controller: RuntimeOperationController, state: OperationPublicProjectionV1
) -> ModeloWorkCreateProjection:
    return await controller.read_settled_result(
        state, ModeloWorkCreateProjection, result_version=1, allow_refusal_detail=True
    )


def _result_matches_request(
    result: ModeloWorkCreateProjection,
    payload: ModeloWorkCreateRequest,
    client: RuntimeFrontendClient,
    session_id: UUID,
) -> bool:
    return not (
        result.profile_id != payload.profile_id
        or result.period != payload.period
        or client.profile_id != payload.profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.TUI
    )


def _is_admitted_applicability_refusal(
    outcome: ModeloWorkCreateRefusal,
    payload: ModeloWorkCreateRequest,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_code: str | None,
) -> bool:
    return (
        condition is OperationTerminalCondition.REFUSED
        and refusal_code == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
        and effect is OperationEffect.NONE
        and outcome.modelo == payload.modelo
    )


def _is_valid_create_success(
    outcome: ModeloWorkCreateSuccess,
    payload: ModeloWorkCreateRequest,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_code: str | None,
) -> bool:
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and refusal_code is None
        and effect is (OperationEffect.NONE if outcome.reused else OperationEffect.UPDATED)
        and outcome.unit.modelo == payload.modelo
        and outcome.name_applied is None
        and not outcome.applicability_guard_bypassed
    )


def _validate_create_outcome(
    result: ModeloWorkCreateProjection,
    payload: ModeloWorkCreateRequest,
    controller: RuntimeOperationController,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_code: str | None,
) -> ModeloWorkCreateSuccess:
    outcome = result.outcome
    if isinstance(outcome, ModeloWorkCreateRefusal):
        if not _is_admitted_applicability_refusal(outcome, payload, condition, effect, refusal_code):
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
    if not _is_valid_create_success(outcome, payload, condition, effect, refusal_code):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return outcome


def _refreshed_declaration(refreshed: object, work_unit_id: str) -> DeclarationsWorkspaceDeclarationRefV1 | None:
    declarations = (
        refreshed.declarations.projection.declarations
        if isinstance(refreshed, WorkbenchGenerationV1) and refreshed.declarations.projection is not None
        else ()
    )
    return next((ref for ref in declarations if ref.work_unit_id == work_unit_id), None)


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
        state = await _read_terminal_state(controller, payload, subject, deadline)
        condition, effect, refusal_code = _admitted_terminal_details(state)
        result = await _read_create_projection(controller, state)
        if not _result_matches_request(result, payload, client, session_id):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        outcome = _validate_create_outcome(result, payload, controller, condition, effect, refusal_code)
        refreshed = await asyncio.to_thread(refresh_after_success)
        # The declaration just created or reopened, as the refreshed generation
        # admits it, so the declarations list can open it straight away.
        declaration = _refreshed_declaration(refreshed, outcome.unit.work_unit_id)
        return ModeloWorkCreateResultV1(
            reused=outcome.reused, declaration=declaration, advisory_keys=outcome.advisory_keys
        )
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
