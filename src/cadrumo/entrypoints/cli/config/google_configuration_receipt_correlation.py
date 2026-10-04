"""Canonical Google receipt correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationFrontendProjection
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleFolderSetRequest,
    GoogleFolderViewRequest,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleRegisterRequest,
    GoogleStatusRequest,
)
from ....application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
)
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame
from .google_configuration_request_correlation import correlate_google_request


def correlate_success_receipt(
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
    outcome: GoogleConfigurationOutcome,
    client: RuntimeFrontendClient,
    request: BaseModel,
    definition_id: str,
    expected_projection_type: type[BaseModel],
) -> BaseModel:
    """Correlate success receipt."""
    result = outcome.result
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or outcome.refusal is not None
        or result is None
        or type(result) is not expected_projection_type
        or result.profile_id != client.profile_id
        or completed.effect not in google_success_effects(request, result)
    ):
        google_invalid_frame(operation_id=definition_id, completed=completed)
    return result


def correlate_refusal_receipt(
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
    outcome: GoogleConfigurationOutcome,
    client: RuntimeFrontendClient,
    definition_id: str,
) -> None:
    """Require a truthful refusal receipt and its exact-profile public detail."""
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code != GOOGLE_CONFIGURATION_REFUSAL_CODE
        or outcome.result is not None
        or outcome.refusal is None
        or outcome.refusal.profile_id != client.profile_id
        or completed.effect not in {OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
    ):
        google_invalid_frame(operation_id=definition_id, completed=completed)


def correlate_google_completion(
    client: RuntimeFrontendClient,
    request: BaseModel,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
    *,
    definition_id: str,
    expected_projection_type: type[BaseModel],
) -> None:
    """Require exact profile, request class, registered operation, and truthful effect."""
    outcome = completed.projection
    if (
        completed.terminal_condition not in {OperationTerminalCondition.SUCCEEDED, OperationTerminalCondition.REFUSED}
        or outcome.profile_id != client.profile_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        google_invalid_frame(operation_id=definition_id, completed=completed)
    if outcome.outcome == "refused":
        correlate_refusal_receipt(completed, outcome, client, definition_id)
        return
    result = correlate_success_receipt(completed, outcome, client, request, definition_id, expected_projection_type)
    correlate_google_request(request, result, client, completed)


def google_success_effects(request: BaseModel, result: BaseModel) -> frozenset[OperationEffect]:
    """Admit only the effects permitted by this exact successful Google action."""
    if isinstance(request, (GoogleFolderSetRequest, GoogleRegisterRequest)):
        return frozenset({OperationEffect.UPDATED})
    if isinstance(request, (GoogleFolderViewRequest, GoogleStatusRequest)):
        return frozenset({OperationEffect.NONE})
    if isinstance(request, GoogleLoginRequest):
        return frozenset({OperationEffect.NONE if request.refresh_only else OperationEffect.UPDATED})
    if isinstance(request, GoogleLogoutRequest) and isinstance(result, GoogleLogoutProjection):
        return logout_effects(result)
    if isinstance(request, GoogleProbeRequest) and isinstance(result, GoogleProbeProjection):
        return frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
    return frozenset[OperationEffect]()


def logout_effects(result: GoogleLogoutProjection) -> frozenset[OperationEffect]:
    """Report an update exactly when stored token or metadata was removed."""
    return frozenset(
        {OperationEffect.UPDATED if result.token_removed or result.metadata_removed else OperationEffect.NONE}
    )
