"""Exact-profile registered worker bridge for human Google configuration leaves."""

from __future__ import annotations

from typing import cast

import typer
from pydantic import BaseModel

from ....adapters.outbound.google.errors import GoogleAuthError
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleLoginRequest,
)
from ....core.operations import profile_operation_subject
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import run_registered_operation
from .google_configuration_contract_map import GOOGLE_REQUEST_OPERATIONS
from .google_configuration_projection import google_success_projection
from .google_configuration_receipt_correlation import correlate_google_completion
from .google_configuration_refusals import google_invalid_frame
from .google_errors import google_refusal


def run_google_configuration[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    result_type: type[ProjectionT],
) -> ProjectionT:
    """Run one typed request and correlate its complete projection to the actual receipt."""
    client = bound_profile_client(ctx)
    request_contract = GOOGLE_REQUEST_OPERATIONS.get(type(request))
    if (
        request_contract is None
        or request_contract[1] is not result_type
        or getattr(request, "profile_id", None) != client.profile_id
    ):
        google_invalid_frame(operation_id="config.google.invalid")
    definition_id, expected_projection_type = request_contract

    if isinstance(request, GoogleLoginRequest) and not request.refresh_only:
        from .runtime_google_consent import login_google_with_runtime

        try:
            completed = login_google_with_runtime(client, request, timeout=420)
        except GoogleAuthError as error:
            raise google_refusal(error) from None
    else:
        completed = run_registered_operation(
            client,
            request,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=GoogleConfigurationOutcome,
            request_version=1,
            result_version=1,
            timeout=120,
            allow_refusal_detail=True,
        )
    correlate_google_completion(
        client,
        request,
        completed,
        definition_id=definition_id,
        expected_projection_type=expected_projection_type,
    )
    result = google_success_projection(completed, definition_id, expected_projection_type)
    return cast("ProjectionT", result)
