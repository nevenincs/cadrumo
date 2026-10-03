"""Configure the profile's AEAT authentication through one exact TUI runtime session.

The profile manager's provider and Cl@ve Móvil route fields are saved by the
same registered operation the CLI's ``config auth configure`` submits, so both
frontends record the same supervised configuration, honour the same profile
baseline and read the same redacted result.
"""

from __future__ import annotations

import asyncio
import time

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from ....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from ....application.operations.registry import OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.errors.error_codes import declared_error_codes_by_qualname
from ....core.errors.hierarchy import RecordedRegisteredError
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ..operations.runtime_controller import RuntimeOperationController, await_terminal_projection

_TIMEOUT_SECONDS = 120.0


def _settlement_error(code: str, operation_id: object) -> Exception:
    """Carry a catalogued code's registered metadata; any other code stays a plain runtime refusal."""
    if any(error_code.code == code for error_code in declared_error_codes_by_qualname().values()):
        return RecordedRegisteredError(code, context={"operation_id": str(operation_id)})
    return RuntimeFrontendRefusedError(code)


async def _configure(
    client: RuntimeFrontendClient, request: AuthConfigureOperationRequest
) -> AuthConfigurePublicResultV2:
    session_id = client.session_id
    subject_ref = profile_operation_subject(str(client.profile_id))
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    controller = await RuntimeOperationController.submit(
        client,
        definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=request,
        deadline=deadline,
        expected_session_id=session_id,
    )
    await controller.start()
    state = await await_terminal_projection(
        controller,
        definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        request_schema=OperationSchemaIdentityV1.from_model(
            schema_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=AuthConfigureOperationRequest,
        ),
        deadline=deadline,
    )
    if state.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        # The registered refusal or failure code is the public fact; the
        # executor's private exception never crosses the runtime boundary.
        raise _settlement_error(
            state.refusal_ref
            or state.failure_error_code
            or (state.terminal_condition.value if state.terminal_condition is not None else "unknown"),
            controller.operation_id,
        )
    result = await controller.read_settled_result(state, AuthConfigurePublicResultV2, result_version=2)
    if (
        result.profile_id != client.profile_id
        or result.provider is not request.provider
        or state.effect is not (OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
        or client.session_id != session_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return result


def configure_runtime_auth(
    client: RuntimeFrontendClient, request: AuthConfigureOperationRequest
) -> AuthConfigurePublicResultV2:
    """Submit and settle one configuration; call from a worker thread, never the UI loop."""
    return asyncio.run(_configure(client, request))


__all__ = ["configure_runtime_auth"]
