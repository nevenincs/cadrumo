"""CLI admission for private commands hosted by the shared local runtime."""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID

import typer

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ...adapters.persistence.storage.errors import KeyringUnavailableError
from ...application.operations.registry import OperationFrontendProjection
from ...application.profile_preconditions import profile_session_failure_verdict
from ...application.user_profile.login_session import ProfileReceiptRefusedError
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.profile_session import ProfileSessionRefusalReason
from ._profile_authentication_contract import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
    ProfileSecretSourceOptions,
    root_profile_secret_model,
)
from ._profile_authentication_notice import stage_profile_session_not_persisted_notice
from ._profile_session_gate import bind_profile_target, session_refusal_translation_key
from .common import attach_cli_policy_verdict, no_active_profile_refusal, requested_cli_leaf
from .config.secure_input import (
    ProfileSecretSelection,
    prompt_secret_no_echo,
    read_profile_secret_payload,
    terminal_can_prompt_for_secrets,
)
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import bind_profile_client


def parsed_root_profile_source(ctx: typer.Context) -> ProfileSecretSourceOptions:
    """Read the one parsed root authentication selection for this invocation."""
    value = cast("dict[str, object]", ctx.find_root().ensure_object(dict)).get("profile_secret_source")
    if value is None:
        return ProfileSecretSourceOptions()
    if not isinstance(value, ProfileSecretSourceOptions):
        raise TypeError("root profile-secret source has an invalid type")
    return value


def require_automation_change_credential_reference(ctx: typer.Context) -> UUID:
    """Return only the exact protected reference admitted for own-grant change."""
    source = parsed_root_profile_source(ctx)
    if source.method is not ProfileAuthenticationMethod.API_KEY or source.credential_reference is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.automation_change_credential_ref_required"
        )
    return source.credential_reference


def _password(client: RuntimeFrontendClient, *, selection: ProfileSecretSelection | None) -> None:
    if selection is None:
        secret = bytearray(prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt")).encode("utf-8"))
    else:
        payload = read_profile_secret_payload(root_profile_secret_model(), selection=selection)
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
        admitted = client.login_password(secret)
    finally:
        secret[:] = bytes(len(secret))
    if admitted.human_login is None or not admitted.human_login.session_persisted:
        stage_profile_session_not_persisted_notice()


def _api_key(client: RuntimeFrontendClient, *, selection: ProfileSecretSelection) -> None:
    payload = read_profile_secret_payload(root_profile_secret_model(), selection=selection)
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
    client: RuntimeFrontendClient,
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
    try:
        client.resume_receipt()
    except ProfileReceiptRefusedError as error:
        if root_selection is not None:
            _password(client, selection=root_selection)
            return
        refusal = error.reason
        if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            if terminal_can_prompt_for_secrets():
                _password(client, selection=None)
                return
            raise KeyringUnavailableError("OS keychain is unavailable for profile-session acceleration") from None
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message=session_refusal_translation_key(refusal), context={"reason": refusal.value}
            ),
            verdict=profile_session_failure_verdict(refusal, profile_name=profile_label or str(client.profile_id)),
            requested_leaf=requested_cli_leaf(ctx),
        ) from None
    if root_selection is not None:
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_unused")


def activate_runtime_profile(
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
        raise no_active_profile_refusal()
    if credential_reference is not None:
        client = _open_profile_credential_client(bucket_id, credential_reference, root_selection, method)
    else:
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI)
        )
    try:
        if credential_reference is None:
            _authenticate(ctx, client, root_selection=root_selection, profile_label=target_profile_label, method=method)
        bind_profile_target(ctx, bucket_id=bucket_id)
        bind_profile_client(ctx, client, profile_id=UUID(bucket_id))
    except RuntimeFrontendRefusedError as error:
        client.close()
        raise CliRefusedBoundaryError(error.reason, context={"reason": error.reason}) from None
    except BaseException:
        client.close()
        raise


def activate_runtime_recovery(
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
        raise no_active_profile_refusal()
    client = asyncio.run(
        open_installed_runtime_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI)
    )
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
) -> RuntimeFrontendClient:
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
        )
    )
    return client
