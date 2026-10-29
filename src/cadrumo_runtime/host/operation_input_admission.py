"""Validation and admission of registered operation inputs."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo.application.operations.models import (
    OperationRequest,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.request_faults import registered_error_fault, request_faults
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

if TYPE_CHECKING:
    from cadrumo.application.operations.composition import OperationSubmission
    from cadrumo.application.operations.registry import (
        OperationFrontendProjection,
    )

    from .operation_host import ProfileWorkerOperationHost


@contextmanager
def _refusing_what_its_readers_refuse() -> Generator[None]:
    """Answer whatever refuses a caller's document while it is read as an invalid request that says why.

    Every frontend is told what the validator said, as the command line shows
    it. A validator can also refuse with a registered error the model does not
    wrap: that is the same refusal, with the error's code and message, and it
    must not end the worker that every session of the profile shares.
    """
    try:
        yield
    except ValidationError as refused:
        faults = request_faults(refused)
        raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
    except (AutomationCustodyError, ProfileAccessRefusedError):
        raise
    except CadrumoError as refused:
        faults = (registered_error_fault(refused),)
        raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
    except (ValueError, TypeError, RecursionError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None


async def submit_financial_input(
    host: ProfileWorkerOperationHost,
    *,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    definition_id: str,
    subject_ref: str,
    input_json: str,
) -> OperationSubmission:
    """Convert volatile human input before binding or journaling the safe request."""
    from cadrumo.application.modelo.edit_operator_input import (
        PreparedModeloEditOperand,
        prepare_modelo_edit_operand,
    )
    from cadrumo.application.operations.financial_operand_contract import OperationFinancialOperandRefusedError

    await host.composed_off_loop()
    contract = await await_cancellation_complete(
        asyncio.to_thread(host.contract, session_id, definition_id), task_name="profile-financial-input-contract"
    )
    if contract.transient_financial_operand is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

    def prepare() -> PreparedModeloEditOperand:
        # A fault of the operand is a validator's message and never the operand ithost.
        with _refusing_what_its_readers_refuse(), host.governed():
            return prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=host.custody.identity.binding.profile_id,
                subject_ref=subject_ref,
                input_json=input_json,
            )

    prepared = await await_cancellation_complete(
        asyncio.to_thread(prepare), task_name="profile-financial-input-prepare"
    )
    input_json = ""

    async def transfer() -> OperationSubmission:
        try:
            submitted = await host.submit(
                session_id=session_id,
                frontend=frontend,
                request=OperationRequest(
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    payload=prepared.request,
                    idempotency_key=None,
                ),
            )
            operand = prepared.operand
            if operand is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            supervisor = host.composed().submission.supervisor
            try:
                await supervisor.bind_typed_financial_operand(submitted.receipt.operation_id, operand)
            except OperationFinancialOperandRefusedError as refused:
                await supervisor.refuse_unstarted_financial_input(submitted.receipt.operation_id)
                faults = (registered_error_fault(refused),)
                raise AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=faults) from None
            finally:
                del operand
            return submitted
        finally:
            prepared.release()

    return await await_cancellation_complete(transfer(), task_name="profile-financial-operand-admission")


async def submit_payload(
    host: ProfileWorkerOperationHost,
    *,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    definition_id: str,
    subject_ref: str,
    payload_json: str,
    idempotency_key: str | None = None,
) -> OperationSubmission:
    """Decode through the exact registered model after exact-profile custody."""
    await host.composed_off_loop()

    def decode() -> BaseModel:
        # Custody and a registered model's validators both run here, never on the service loop.
        host.contract(session_id, definition_id)
        execution = host.execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        with _refusing_what_its_readers_refuse(), host.governed():
            return execution.registry.decode_request_payload(definition_id, payload_json)

    payload = await await_cancellation_complete(asyncio.to_thread(decode), task_name="profile-payload-decode")
    return await host.submit(
        session_id=session_id,
        frontend=frontend,
        request=OperationRequest(
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            idempotency_key=idempotency_key,
        ),
    )
