"""Canonical google consent admission stages for the human terminal."""

from __future__ import annotations

import math
import time
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from ....application.user_profile.google_configuration_operation import (
    GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING,
    GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING,
)
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleLoginRequest,
)


def admit_google_consent_connection(
    client: RuntimeFrontendClient, request: GoogleLoginRequest, timeout: float
) -> tuple[float, UUID, UUID]:
    """Admit google consent connection."""
    if request.refresh_only or not math.isfinite(timeout) or not 0 < timeout <= 420:
        raise ValueError("Google browser consent requires a finite timeout of at most 420 seconds")
    deadline = time.monotonic() + timeout
    profile_id, session_id = client.profile_id, client.session_id
    if request.profile_id != profile_id or client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return deadline, profile_id, session_id


def admit_google_consent_contract(
    client: RuntimeFrontendClient, request: GoogleLoginRequest, contract: OperationPublicDefinitionContractV1
) -> tuple[OperationSchemaIdentityV1, str]:
    """Admit google consent contract."""
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".request",
        schema_version=1,
        model_type=GoogleLoginRequest,
    )
    expected_result = OperationSchemaIdentityV1.from_model(
        schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".result",
        schema_version=1,
        model_type=GoogleConfigurationOutcome,
    )
    if (
        contract.definition_id != GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or contract.review_projection_schema != GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING.identity
        or contract.interaction_response_schema != GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING.identity
        or client.frontend not in contract.permitted_frontends
        or contract.ephemeral_secret_required
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    payload_json = request.model_dump_json()
    if len(payload_json.encode("utf-8")) > SUBMISSION_PAYLOAD_MAX_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return expected_result, payload_json
