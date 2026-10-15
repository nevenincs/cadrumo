"""Shared profile admission for commands backed by the local runtime."""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.profile_preconditions import (
    profile_password_channel_failure_verdict,
    profile_session_failure_verdict,
)
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.i18n.render import tr
from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from cadrumo_client.commands.errors import CliRefusedBoundaryError, attach_cli_policy_verdict
from cadrumo_client.commands.profile_authentication import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
    parsed_root_profile_source,
)
from cadrumo_client.commands.profile_authentication_notice import stage_profile_session_not_persisted_notice
from cadrumo_client.commands.profile_binding import bind_profile_client, subscribe_profile_notices
from cadrumo_client.commands.secure_input import (
    ProfileSecretSelection,
    prompt_secret_no_echo,
    read_profile_secret_payload,
    terminal_can_prompt_for_secrets,
)
from cadrumo_client.transport.credentials import open_installed_credential_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client


def require_automation_change_credential_reference(ctx: typer.Context) -> UUID:
    """Return only the exact protected reference admitted for own-grant change."""
    source = parsed_root_profile_source(ctx)
    if source.method is not ProfileAuthenticationMethod.API_KEY or source.credential_reference is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.automation_change_credential_ref_required"
        )
    return source.credential_reference


def _password(client: FrontendClient, *, selection: ProfileSecretSelection | None) -> None:
    from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode

    if selection is None:
        secret = bytearray(prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt")).encode("utf-8"))
    else:
        payload = read_profile_secret_payload(ProfileAuthenticationSecrets, selection=selection)
        try:
            if not isinstance(payload, ProfileAuthenticationSecrets):
                raise InternalInvariantError("root secret model returned an unexpected payload type")
            if payload.profile_passphrase is None:
                raise CliRefusedBoundaryError(
                    translated_message="cli.config.custody.errors.profile_secrets_method_mismatch"
                )
            secret = bytearray(payload.profile_passphrase.get_secret_value().encode("utf-8"))
        finally:
            del payload
    try:
        if not secret:
            raise CliRefusedBoundaryError(
                AutomationCustodyCode.CREDENTIAL_REJECTED.value,
                context={"reason": AutomationCustodyCode.CREDENTIAL_REJECTED.value},
                translated_message="application.user_profile.errors.profile_authentication_refused",
            )
        admitted = client.login_password(secret)
    except FrontendRefusedError as error:
        if error.reason != AutomationCustodyCode.CREDENTIAL_REJECTED.value:
            raise
        raise CliRefusedBoundaryError(
            error.reason,
            context=error.context,
            translated_message="application.user_profile.errors.profile_authentication_refused",
        ) from None
    finally:
        secret[:] = bytes(len(secret))
    if admitted.human_login is None or not admitted.human_login.session_persisted:
        stage_profile_session_not_persisted_notice()


def _api_key(client: FrontendClient, *, selection: ProfileSecretSelection) -> None:
    payload = read_profile_secret_payload(ProfileAuthenticationSecrets, selection=selection)
    try:
        if not isinstance(payload, ProfileAuthenticationSecrets):
            raise InternalInvariantError("root secret model returned an unexpected payload type")
        if payload.api_key is None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.profile_secrets_method_mismatch"
            )
        secret = bytearray(payload.api_key.get_secret_value().encode("utf-8"))
    finally:
        del payload
    try:
        client.login_api_key(secret)
    finally:
        secret[:] = bytes(len(secret))


def _authenticate(
    ctx: typer.Context,
    client: FrontendClient,
    *,
    root_selection: ProfileSecretSelection | None,
    profile_label: str | None,
    method: ProfileAuthenticationMethod,
) -> None:
    if method is ProfileAuthenticationMethod.API_KEY:
        if root_selection is None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.profile_secrets_api_key_requires_channel"
            )
        _api_key(client, selection=root_selection)
        return
    if root_selection is not None:
        _password(client, selection=root_selection)
        return
    # A live sign-in on this OS login admits every client, attached to a terminal or not.
    try:
        client.resume_receipt()
    except ProfileReceiptRefusedError as error:
        refusal = error.reason
        if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            if terminal_can_prompt_for_secrets():
                _password(client, selection=None)
                return
            raise attach_cli_policy_verdict(
                CliRefusedBoundaryError(
                    translated_message="cli.config.custody.errors.profile_passphrase_channel_absent"
                ),
                verdict=profile_password_channel_failure_verdict(profile_name=profile_label or str(client.profile_id)),
            ) from None
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message=_session_refusal_translation_key(refusal, error.binding),
                context=_session_refusal_context(refusal, error.binding),
            ),
            verdict=profile_session_failure_verdict(refusal, profile_name=profile_label or str(client.profile_id)),
        ) from None


def activate_profile(
    ctx: typer.Context,
    *,
    target_bucket_id: str | None,
    target_profile_label: str | None,
    root_selection: ProfileSecretSelection | None,
    method: ProfileAuthenticationMethod = ProfileAuthenticationMethod.PASSWORD,
    credential_reference: UUID | None = None,
) -> None:
    """Prove one exact profile through native IPC without opening local custody.

    Parsed dispatch selects the migrated registered leaves. An ambient
    selection supplies a target, never authentication.
    """
    bucket_id = target_bucket_id or resolve_active_bucket_id()
    if bucket_id is None:
        if root_selection is not None or credential_reference is not None:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_missing_target")
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    profile_label = target_profile_label
    if profile_label is None and credential_reference is None:
        from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

        pointer = read_profile_bucket_by_id(bucket_id)
        if pointer is not None:
            profile_label = pointer.label
    if credential_reference is not None:
        client = _open_profile_credential_client(bucket_id, credential_reference, root_selection, method, ctx)
    else:
        client = asyncio.run(
            open_installed_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI)
        )
    try:
        if credential_reference is None:
            subscribe_profile_notices(ctx, client)
            _authenticate(ctx, client, root_selection=root_selection, profile_label=profile_label, method=method)
        bind_profile_target(ctx, bucket_id=bucket_id)
        bind_profile_client(ctx, client, profile_id=UUID(bucket_id))
    except FrontendRefusedError as error:
        client.close()
        _raise_connection_refusal(error)
    except BaseException:
        client.close()
        raise


def activate_profile_recovery(
    ctx: typer.Context,
    *,
    target_bucket_id: str | None,
    root_selection: ProfileSecretSelection | None,
) -> None:
    """Bind a fresh exact-profile native connection for separate recovery proof.

    The resume leaf owns its one-shot password payload. Root authentication
    would create a different session journey and is therefore inapplicable.
    """
    if root_selection is not None:
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_inapplicable")
    bucket_id = target_bucket_id or resolve_active_bucket_id()
    if bucket_id is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    client = asyncio.run(open_installed_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI))
    try:
        bind_profile_target(ctx, bucket_id=bucket_id)
        bind_profile_client(ctx, client, profile_id=UUID(bucket_id))
    except BaseException:
        client.close()
        raise


def _open_profile_credential_client(
    bucket_id: str,
    credential_reference: UUID,
    root_selection: ProfileSecretSelection | None,
    method: ProfileAuthenticationMethod,
    ctx: typer.Context,
) -> FrontendClient:
    """Refuse conflicting credential inputs before opening the installed credential connection."""
    if root_selection is not None:
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_credential_ref_conflict")
    if method is not ProfileAuthenticationMethod.API_KEY:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.profile_credential_ref_requires_api_key"
        )
    client = asyncio.run(
        open_installed_credential_client(
            profile_id=UUID(bucket_id),
            credential_reference=credential_reference,
            frontend=OperationFrontendProjection.CLI,
            on_connected=lambda client: subscribe_profile_notices(ctx, client),
        )
    )
    return client


def bind_profile_target(ctx: typer.Context, *, bucket_id: str) -> None:
    """Bind one proven profile target as the invocation's storage route."""
    ctx.with_resource(override_settings(cadrumo_active_profile=bucket_id))


def _session_refusal_translation_key(
    refusal: ProfileSessionRefusalReason,
    binding: ReceiptBindingRefusal | None = None,
) -> str:
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


def _session_refusal_context(
    refusal: ProfileSessionRefusalReason,
    binding: ReceiptBindingRefusal | None = None,
) -> dict[str, object]:
    context: dict[str, object] = {"reason": (binding or refusal).value, "sign_in_reason": refusal.value}
    if binding is not None:
        context["sign_in_binding"] = binding.value
    return context


def _raise_connection_refusal(error: FrontendRefusedError) -> None:
    from cadrumo.application.user_profile.access_contracts import AccessDenialCode

    sign_in = error.sign_in
    key: str | None = None
    if sign_in is not None and sign_in.reason == "throttled":
        key = "errors.refused.refused_profile_login_throttled"
    elif sign_in is not None and isinstance(sign_in.reason, ProfileSessionRefusalReason):
        key = _session_refusal_translation_key(sign_in.reason, sign_in.binding)
    elif error.reason == AccessDenialCode.PROFILE_LOCKED.value:
        key = "errors.refused.profile_locked"
    raise CliRefusedBoundaryError(error.reason, context=error.context, translated_message=key) from None


__all__ = [
    "activate_profile",
    "activate_profile_recovery",
    "bind_profile_target",
    "require_automation_change_credential_reference",
]
