"""Error-code rows for the profile proof attempt lifecycle."""

from ..error_codes import ErrorCategory, ErrorCode

PROFILE_PROOF_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    (
        "cadrumo.application.user_profile.proof_cancellation.ProfileProofCancelledError",
        ErrorCode(
            code="REFUSED_PROFILE_PROOF_CANCELLED",
            category=ErrorCategory.REFUSED,
            message_key="application.user_profile.errors.profile_proof_cancelled",
            retryable=False,
            runbook_id=None,
        ),
    ),
)
