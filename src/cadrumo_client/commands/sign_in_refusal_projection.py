"""Typed sign-in refusal diagnostics shared by command admission and renderers."""

from __future__ import annotations

from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal

from ..transport.frontend_client_contracts import FrontendRefusedError
from .errors import CliRefusedBoundaryError


def session_refusal_translation_key(
    refusal: ProfileSessionRefusalReason,
    binding: ReceiptBindingRefusal | None = None,
) -> str:
    """Choose the diagnostic for a typed receipt refusal."""
    if binding is ReceiptBindingRefusal.LOGIN_MISMATCH:
        return "cli.config.errors.profile_session_login_mismatch"
    if binding is ReceiptBindingRefusal.GENERATION_CHANGED:
        return "cli.config.errors.profile_session_signed_out"
    if binding is not None:
        return "cli.config.errors.profile_session_unreadable"
    if refusal is ProfileSessionRefusalReason.CUSTODY_CHANGED:
        return "cli.config.errors.profile_session_custody_changed"
    if refusal is ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH:
        return "cli.config.errors.profile_session_outdated"
    if refusal in {ProfileSessionRefusalReason.MALFORMED, ProfileSessionRefusalReason.TAMPERED}:
        return "cli.config.errors.profile_session_unreadable"
    if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
        return "errors.auth.auth_storage_keyring_unavailable"
    if refusal in {ProfileSessionRefusalReason.ABSENT, ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING}:
        return "cli.config.errors.profile_session_absent"
    return "cli.config.errors.profile_session_expired"


def session_refusal_context(
    refusal: ProfileSessionRefusalReason,
    binding: ReceiptBindingRefusal | None = None,
) -> dict[str, object]:
    """Preserve receipt refusal facts in the command error context."""
    context: dict[str, object] = {"reason": (binding or refusal).value, "sign_in_reason": refusal.value}
    if binding is not None:
        context["sign_in_binding"] = binding.value
    return context


def raise_connection_refusal(error: FrontendRefusedError) -> None:
    """Project a wire admission refusal into its operator-facing boundary error."""
    from cadrumo_client.contracts.access_refusals import AccessDenialCode

    sign_in = error.sign_in
    key: str | None = None
    if sign_in is not None and sign_in.reason == "throttled":
        key = "errors.refused.refused_profile_login_throttled"
    elif sign_in is not None and isinstance(sign_in.reason, ProfileSessionRefusalReason):
        key = session_refusal_translation_key(sign_in.reason, sign_in.binding)
    elif error.reason == AccessDenialCode.PROFILE_LOCKED.value:
        key = "errors.refused.profile_locked"
    raise CliRefusedBoundaryError(error.reason, context=error.context, translated_message=key) from None
