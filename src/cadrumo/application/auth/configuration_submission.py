"""One public operation journey for CLI and TUI authentication selection."""

from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.error_codes import get_registered_error_code_by_code
from ...core.errors.hierarchy import CoreValidationError, InternalInvariantError
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ..operations.composition import OperationComposedServices
from ..operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ..operations.models import OperationRequest
from .configuration_result import AuthConfigurePublicResultV1
from .operation_definitions import AUTH_CONFIGURE_OPERATION_DEFINITION_ID, AuthConfigureOperationRequest


async def submit_auth_configuration(
    request: AuthConfigureOperationRequest,
    *,
    services: OperationComposedServices,
) -> AuthConfigurePublicResultV1:
    """Submit, settle, observe and resolve only through public platform ports."""
    submitted = await services.submission.submit(
        OperationRequest(
            definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(require_active_bucket_id()),
            payload=request,
        ),
        actor_ref="operator:auth-configure",
    )
    await services.submission.start(submitted.receipt.operation_id)
    await services.submission.settled(submitted.receipt.operation_id)
    observed = await services.observation.observe(
        OperationObservationRequestV1(
            operation_id=submitted.receipt.operation_id,
            after_cursor=0,
            page_limit=64,
        )
    )
    if not isinstance(observed, OperationObservationSuccessV1):
        raise InternalInvariantError("authentication configuration observation is unavailable")
    projection = observed.projection
    code = projection.refusal_ref or projection.failure_error_code
    if code is not None:
        metadata = get_registered_error_code_by_code(code)
        # Never rethrow a private executor exception or reconstruct its context.
        # Both frontends see the same registered metadata and opaque reference.
        raise CoreValidationError(
            translated_message=metadata.message_key,
            context={"error_code": code, "diagnostic_ref": projection.diagnostic_ref or ""},
        )
    if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise InternalInvariantError("authentication configuration did not settle successfully")
    result_schema = projection.definition_contract.result_schema
    if result_schema is None:
        raise InternalInvariantError("authentication configuration has no public result schema")
    resolved = await services.result.resolve(
        OperationResultProjectionRequestV1(
            operation_id=projection.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=projection.definition_contract.definition_contract_digest,
            result_schema=result_schema,
        ),
        AuthConfigurePublicResultV1,
    )
    if not isinstance(resolved, OperationResultProjectionSuccessV1) or not isinstance(
        resolved.projection,
        AuthConfigurePublicResultV1,
    ):
        raise InternalInvariantError("authentication configuration public result is unavailable")
    return resolved.projection
