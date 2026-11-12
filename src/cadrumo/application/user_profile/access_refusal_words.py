"""Locale keys for the words served with each profile access refusal.

Every refusal reason has its own plain sentence in the error catalogue, so an
operator never sees the raw reason token. The mapping is spelled out so each key
is a literal the locale tooling can read, and a test proves it covers the whole
closed vocabulary.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.access_refusals import AccessDenialCode

_REFUSAL_LOCALE_KEYS: Final[dict[AccessDenialCode, str]] = {
    AccessDenialCode.AUTHENTICATION_REQUIRED: "errors.refused.profile_access_authentication_required",
    AccessDenialCode.PROFILE_MISMATCH: "errors.refused.profile_access_profile_mismatch",
    AccessDenialCode.CUSTODY_CHANGED: "errors.refused.profile_access_custody_changed",
    AccessDenialCode.PROFILE_LOCKED: "errors.refused.profile_access_profile_locked",
    AccessDenialCode.AUTOMATION_SUSPENDED: "errors.refused.profile_access_automation_suspended",
    AccessDenialCode.SESSION_INACTIVE: "errors.refused.profile_access_session_inactive",
    AccessDenialCode.SESSION_EXPIRED: "errors.refused.profile_access_session_expired",
    AccessDenialCode.CONNECTION_MISMATCH: "errors.refused.profile_access_connection_mismatch",
    AccessDenialCode.CLIENT_MISMATCH: "errors.refused.profile_access_client_mismatch",
    AccessDenialCode.RUNTIME_CHANGED: "errors.refused.profile_access_runtime_changed",
    AccessDenialCode.CLOCK_INVALID: "errors.refused.profile_access_clock_invalid",
    AccessDenialCode.PARENT_INVALID: "errors.refused.profile_access_parent_invalid",
    AccessDenialCode.PRIVILEGE_EXPANSION: "errors.refused.profile_access_privilege_expansion",
    AccessDenialCode.GRANT_INACTIVE: "errors.refused.profile_access_grant_inactive",
    AccessDenialCode.GRANT_EXPIRED: "errors.refused.profile_access_grant_expired",
    AccessDenialCode.KEY_INACTIVE: "errors.refused.profile_access_key_inactive",
    AccessDenialCode.KEY_EXPIRED: "errors.refused.profile_access_key_expired",
    AccessDenialCode.OS_SESSION_UNAVAILABLE: "errors.refused.profile_access_os_session_unavailable",
    AccessDenialCode.OS_LOCKED: "errors.refused.profile_access_os_locked",
    AccessDenialCode.STORAGE_UNAVAILABLE: "errors.refused.profile_access_storage_unavailable",
    AccessDenialCode.CUSTODY_UNAVAILABLE: "errors.refused.profile_access_custody_unavailable",
    AccessDenialCode.CUSTODY_RECOVERING: "errors.refused.profile_access_custody_recovering",
    AccessDenialCode.OPERATION_UNAVAILABLE: "errors.refused.profile_access_operation_unavailable",
    AccessDenialCode.SUBJECT_BUSY: "errors.refused.profile_access_subject_busy",
    AccessDenialCode.FRONTEND_DENIED: "errors.refused.profile_access_frontend_denied",
    AccessDenialCode.OPERATION_DENIED: "errors.refused.profile_access_operation_denied",
    AccessDenialCode.DISCLOSURE_DENIED: "errors.refused.profile_access_disclosure_denied",
    AccessDenialCode.PERIOD_DENIED: "errors.refused.profile_access_period_denied",
    AccessDenialCode.BACKEND_UNAVAILABLE: "errors.refused.profile_access_backend_unavailable",
    AccessDenialCode.AUTHORITY_UNAVAILABLE: "errors.refused.profile_access_authority_unavailable",
    AccessDenialCode.PROVIDER_REQUIRED: "errors.refused.profile_access_provider_required",
    AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED: "errors.refused.profile_access_response_authority_required",
    AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED: "errors.refused.profile_access_transaction_authority_required",
    AccessDenialCode.HUMAN_AUTHORITY_REQUIRED: "errors.refused.profile_access_human_authority_required",
    AccessDenialCode.FRESH_PASSWORD_REQUIRED: "errors.refused.profile_access_fresh_password_required",
    AccessDenialCode.ADMINISTRATION_DENIED: "errors.refused.profile_access_administration_denied",
    AccessDenialCode.PERSON_ACT_REQUIRED: "errors.refused.profile_access_person_act_required",
}


def access_refusal_message_key(reason: AccessDenialCode | str) -> str:
    """Return the locale key whose words explain ``reason``.

    A value outside the closed vocabulary reads as the generic operation refusal,
    so an unknown token is never shown to the operator.
    """
    try:
        known = AccessDenialCode(reason)
    except ValueError:
        known = AccessDenialCode.OPERATION_DENIED
    return _REFUSAL_LOCALE_KEYS[known]


__all__ = ["access_refusal_message_key"]
