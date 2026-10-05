"""Reconstruct canonical Google human errors from the closed owning refusal."""

from __future__ import annotations

from ....application.operations.models import OperationId
from ....application.user_profile.google_configuration_operation_contracts import GoogleConfigurationExportDisabledError
from ....application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationRefusalProjection,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..storage import errors as storage_errors
from ..storage.errors import OutboundStorageError
from . import errors as google_errors
from .errors import GoogleAuthError

GOOGLE_CONFIGURATION_ERROR_TYPES: tuple[
    type[GoogleAuthError | OutboundStorageError | GoogleConfigurationExportDisabledError], ...
] = (
    google_errors.GoogleAuthError,
    google_errors.GoogleAuthValidationError,
    google_errors.GoogleAuthClientMetadataUnavailableError,
    google_errors.GoogleAuthClientRevokedError,
    google_errors.GoogleAuthRevokedError,
    google_errors.GoogleAuthExpiredError,
    google_errors.GoogleAuthScopeInsufficientError,
    google_errors.GoogleAuthNetworkError,
    google_errors.GoogleAuthLoopbackBindError,
    google_errors.GoogleAuthBrowserOpenError,
    google_errors.GoogleAuthNonInteractiveError,
    google_errors.GoogleAuthKeychainLockedError,
    google_errors.GoogleAuthProfileUnboundError,
    storage_errors.OutboundStorageError,
    storage_errors.OutboundStorageValidationError,
    storage_errors.OutboundStorageNotFoundError,
    storage_errors.OutboundStorageConflictError,
    storage_errors.OutboundStoragePermissionError,
    storage_errors.OutboundStoragePathTooLongError,
    storage_errors.OutboundStorageQuotaError,
    storage_errors.OutboundStorageNetworkError,
    storage_errors.OutboundStorageIntegrityError,
    storage_errors.OutboundStorageUnavailableError,
    GoogleConfigurationExportDisabledError,
)


def google_configuration_refusal_error(
    refusal: GoogleConfigurationRefusalProjection,
    *,
    operation_id: OperationId,
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
    refusal_code: str,
) -> CadrumoError:
    """Rehydrate the original declared human failure and attach actual receipt coordinates."""
    refusal = GoogleConfigurationRefusalProjection.model_validate(refusal.model_dump(mode="python"), strict=True)
    if not _google_refusal_receipt_is_closed(terminal_condition, refusal_code):
        raise ValueError("Google refusal requires its authoritative refusal receipt")
    error_type = _google_refusal_constructor(refusal)
    if error_type is None:
        raise ValueError("Google refusal code has no canonical presentation constructor")
    context = refusal.facts.presentation_context()
    context.update(
        {
            "operation_id": str(operation_id),
            "effect": effect.value,
            "terminal_condition": terminal_condition.value,
            "refusal_code": refusal_code,
        }
    )
    if error_type is GoogleConfigurationExportDisabledError:
        return GoogleConfigurationExportDisabledError(translated_message=refusal.message_key, context=context)
    verdict = refusal.verdict.to_verdict() if refusal.verdict is not None else None
    if error_type is google_errors.GoogleAuthScopeInsufficientError and refusal.message_key.endswith("scope_missing"):
        if not refusal.facts.missing_scopes or refusal.facts.account_email is None:
            raise ValueError("Google scope refusal requires its canonical missing scope facts")
        return google_errors.GoogleAuthScopeInsufficientError(
            translated_message=refusal.message_key,
            context=context,
            precondition_verdict=verdict,
            scope_failure=google_errors.GoogleScopeFailure(
                missing_scopes=refusal.facts.missing_scopes,
                account_email=refusal.facts.account_email,
            ),
        )
    if issubclass(error_type, (GoogleAuthError, OutboundStorageError)):
        return error_type(translated_message=refusal.message_key, context=context, precondition_verdict=verdict)
    raise ValueError("Google refusal constructor does not carry canonical preconditions")


__all__ = ["GOOGLE_CONFIGURATION_ERROR_TYPES", "google_configuration_refusal_error"]


def _google_refusal_receipt_is_closed(terminal_condition: OperationTerminalCondition, refusal_code: str) -> bool:
    """Require the authoritative refused terminal receipt before reconstructing a human error."""
    return not (
        terminal_condition is not OperationTerminalCondition.REFUSED
        or refusal_code != GOOGLE_CONFIGURATION_REFUSAL_CODE
    )


def _google_refusal_constructor(
    refusal: GoogleConfigurationRefusalProjection,
) -> type[GoogleAuthError | OutboundStorageError | GoogleConfigurationExportDisabledError] | None:
    """Select the declared owning constructor for the exact provider code."""
    return next((item for item in GOOGLE_CONFIGURATION_ERROR_TYPES if item.code.code == refusal.provider_code), None)
