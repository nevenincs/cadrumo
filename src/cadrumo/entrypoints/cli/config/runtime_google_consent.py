"""Exact human terminal acknowledgement for the registered Google consent flow."""

from __future__ import annotations

import time
from uuid import uuid4

from ....adapters.local_runtime.frontend_client import (
    RuntimeFrontendClient,
    frontend_failure_code,
)
from ....adapters.outbound.google.errors import GoogleAuthNonInteractiveError
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleLoginRequest,
)
from ....core.operations import (
    OperationLifecycle,
    profile_operation_subject,
)
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import submitted_operation_error
from .google_consent_admission import admit_google_consent_connection, admit_google_consent_contract
from .google_consent_exchange import google_consent_exchange, google_consent_remaining
from .google_consent_observation import (
    observe_google_consent,
    read_google_consent_result,
    require_google_consent_settlement,
    start_google_consent,
)
from .google_consent_review import review_google_consent_once


def login_google_with_runtime(
    client: RuntimeFrontendClient,
    request: GoogleLoginRequest,
    *,
    timeout: float = 420,
) -> RegisteredOperationCompletion[GoogleConfigurationOutcome]:
    """Review this human terminal and wait for canonical browser consent settlement."""
    deadline, profile_id, session_id = admit_google_consent_connection(client, request, timeout)
    contract = client.contract(GOOGLE_LOGIN_OPERATION_DEFINITION_ID, deadline=deadline)
    expected_result, payload_json = admit_google_consent_contract(client, request, contract)
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = google_consent_exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=subject_ref,
            payload_json=payload_json,
        ),
        deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    condition = None
    effect = None
    refusal_code = None
    reviewed: tuple[str, int] | None = None
    try:
        start_google_consent(client, profile_id, session_id, submitted, operation_id, deadline)
        while True:
            state = observe_google_consent(
                client, profile_id, session_id, operation_id, subject_ref, contract, deadline
            )
            condition, effect, refusal_code = state.terminal_condition, state.effect, state.refusal_ref
            if state.lifecycle is OperationLifecycle.TERMINAL:
                break
            if state.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
                reviewed = review_google_consent_once(
                    state, reviewed, client, profile_id, session_id, request, contract, deadline
                )
            time.sleep(min(0.02, google_consent_remaining(deadline)))
        condition = require_google_consent_settlement(operation_id, state, condition, effect, refusal_code, contract)
        projection = read_google_consent_result(
            client, profile_id, session_id, operation_id, state, contract, expected_result, deadline
        )
        return RegisteredOperationCompletion(
            operation_id=operation_id,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )
    except (CliRefusedBoundaryError, GoogleAuthNonInteractiveError):
        raise
    except Exception as error:
        code = frontend_failure_code(error)
        raise submitted_operation_error(
            operation_id, code, terminal_condition=condition, effect=effect, refusal_code=refusal_code
        ) from None
