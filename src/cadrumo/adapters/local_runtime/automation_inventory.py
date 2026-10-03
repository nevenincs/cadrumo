"""Read one human automation inventory through its registered runtime operation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from uuid import UUID, uuid4

from pydantic import ValidationError

from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import bounded_deadline_after
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.automation_enrollment import AutomationInventoryProjection
from ...application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient
from .frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code
from .operation_run_error_context import operation_run_error_context
from .operation_settlement import (
    PinnedConnection,
    read_settled_result_bytes,
    start_and_await_terminal,
    submit_operation,
)


@dataclass(frozen=True, slots=True)
class AutomationInventoryCompletion:
    """One complete current-consent projection and its canonical operation ID."""

    operation_id: OperationId
    projection: AutomationInventoryProjection


class AutomationInventoryReadError(CadrumoError):
    """Retain a submitted operation's identity without inventing its outcome."""

    def __init__(
        self,
        *,
        operation_id: OperationId,
        code: str,
        terminal_condition: OperationTerminalCondition | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        """Keep only a validated terminal witness or an explicit unknown effect."""
        self.operation_id = operation_id
        self.reason = code
        self._terminal_condition = terminal_condition
        self._effect = effect
        super().__init__(
            code,
            context=operation_run_error_context(
                code=code,
                operation_id=operation_id,
                terminal_condition=terminal_condition,
                effect=effect,
            ),
        )

    @property
    def terminal_condition(self) -> OperationTerminalCondition | None:
        """Return a condition only when canonical observation supplied it."""
        return self._terminal_condition

    @property
    def effect(self) -> OperationEffect | None:
        """Keep an unobserved effect distinct from the public unknown marker."""
        return self._effect


@cache
def _contract() -> OperationPublicDefinitionContractV1:
    definition = next(
        item
        for item in build_automation_operation_definitions()
        if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    )
    registration = build_automation_operation_registrations((definition,))[0]
    if registration.contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return registration.contract


def _exact_profile(projection: AutomationInventoryProjection, profile_id: UUID) -> bool:
    return (
        all(item.profile_id == profile_id for item in projection.grants)
        and all(item.profile_id == profile_id for item in projection.keys)
        and all(item.receipt.profile_id == profile_id for item in projection.requests)
    )


def read_automation_inventory(client: RuntimeFrontendClient, *, timeout: float = 60) -> AutomationInventoryCompletion:
    """Return only a settled, exact-profile public inventory under human authority.

    A timeout or refusal after submission carries its operation ID. An observed
    terminal condition/effect is included only when canonical observation
    supplied it; no acknowledgement is treated as a completed read.
    """
    deadline, pinned, contract, subject_ref = _automation_inventory_contract(client, timeout)
    profile_id = pinned.profile_id
    submitted = submit_operation(
        client,
        pinned,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        payload_json=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()).model_dump_json(),
        deadline=deadline,
    )
    operation_id = submitted.receipt.operation_id
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        state = start_and_await_terminal(
            client, pinned, operation_id, contract=contract, subject_ref=subject_ref, deadline=deadline
        )
        condition, effect = state.terminal_condition, state.effect
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise AutomationInventoryReadError(
                operation_id=operation_id,
                code=state.refusal_ref
                or state.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        if effect is not OperationEffect.NONE:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        projection = _read_inventory_projection(client, pinned, operation_id, state, contract, deadline)
        return AutomationInventoryCompletion(operation_id=operation_id, projection=projection)
    except AutomationInventoryReadError:
        raise
    except Exception as error:
        code = frontend_failure_code(error)
    # Leave the exception handler before constructing the public error. A
    # malformed private result must not remain in its exception chain.
    raise AutomationInventoryReadError(
        operation_id=operation_id,
        code=code,
        terminal_condition=condition,
        effect=effect,
    )


__all__ = ["AutomationInventoryCompletion", "AutomationInventoryReadError", "read_automation_inventory"]


def _automation_inventory_contract(
    client: RuntimeFrontendClient, timeout: float
) -> tuple[float, PinnedConnection, OperationPublicDefinitionContractV1, str]:
    """Pin the human frontend and exact automation inventory contract before submission."""
    if client.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
        raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
    deadline = bounded_deadline_after(timeout, subject="automation inventory")
    pinned = PinnedConnection.of(client)
    profile_id = pinned.profile_id
    contract = client.contract(AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID, deadline=deadline)
    if contract != _contract() or contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = profile_operation_subject(str(profile_id))
    return deadline, pinned, contract, subject_ref


def _read_inventory_projection(
    client: RuntimeFrontendClient,
    pinned: PinnedConnection,
    operation_id: OperationId,
    state: OperationPublicProjectionV1,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> AutomationInventoryProjection:
    """Validate the complete exact-profile inventory under the retained connection."""
    profile_id = pinned.profile_id
    pinned.require_held(client)
    encoded = read_settled_result_bytes(client, operation_id, state, contract, deadline=deadline)
    try:
        result = OperationResultProjectionSuccessV1[AutomationInventoryProjection].model_validate_json(encoded)
    except ValidationError:
        result = None
    if result is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if (
        result.result_schema != contract.result_schema
        or result.definition_contract_digest != contract.definition_contract_digest
        or not _exact_profile(result.projection, profile_id)
        or not pinned.holds(client)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return result.projection
