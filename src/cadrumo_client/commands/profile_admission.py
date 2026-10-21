"""Shared profile admission for commands backed by the local runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.profile_preconditions import (
    profile_password_channel_failure_verdict,
    profile_session_failure_verdict,
)
from cadrumo.core.config import override_settings
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.i18n.render import tr
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_client.commands import profile_selection
from cadrumo_client.commands.errors import CliRefusedBoundaryError, attach_cli_policy_verdict
from cadrumo_client.commands.profile_authentication import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
)
from cadrumo_client.commands.profile_authentication_notice import stage_profile_session_not_persisted_notice
from cadrumo_client.commands.profile_binding import bind_profile_client, subscribe_profile_notices
from cadrumo_client.commands.secure_input import (
    ProfileSecretSelection,
    prompt_secret_no_echo,
    read_profile_secret_payload,
    terminal_can_prompt_for_secrets,
)
from cadrumo_client.commands.sign_in_refusal_projection import (
    raise_connection_refusal,
    session_refusal_context,
    session_refusal_translation_key,
)
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.credentials import open_installed_credential_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client


def _password(
    client: FrontendClient, *, selection: ProfileSecretSelection | None, not_persisted: Callable[[], None]
) -> None:
    from cadrumo_client.contracts.automation_codes import AutomationCustodyCode

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
        not_persisted()


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


def authenticate_profile_client(
    client: FrontendClient,
    *,
    root_selection: ProfileSecretSelection | None,
    profile_label: str | None,
    method: ProfileAuthenticationMethod,
    not_persisted: Callable[[], None] = stage_profile_session_not_persisted_notice,
) -> None:
    """Admit ``client``'s profile by its live sign-in, a password or a key, presented only to the runtime.

    This is the one admission door of every command, whichever executable
    runs it. A key needs its secret channel. A password given on the root
    secret channel is presented as given. Otherwise the live sign-in on this
    OS login is resumed, and only when this process cannot use the keychain
    is a password asked for at a terminal. Every refusal keeps the runtime's
    typed reason. ``not_persisted`` reports a password sign-in the runtime
    kept for this invocation only, in the calling executable's notice channel.
    """
    if method is ProfileAuthenticationMethod.API_KEY:
        if root_selection is None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.profile_secrets_api_key_requires_channel"
            )
        _api_key(client, selection=root_selection)
        return
    if root_selection is not None:
        _password(client, selection=root_selection, not_persisted=not_persisted)
        return
    # A live sign-in on this OS login admits every client, attached to a terminal or not.
    try:
        client.resume_receipt()
        # An interactive command is person input. Background helpers and
        # redirected invocations may resume, but must not keep a login alive.
        # The runtime still verifies the peer and the live human session.
        if terminal_can_prompt_for_secrets():
            client.note_activity()
    except ProfileReceiptRefusedError as error:
        refusal = error.reason
        if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            if terminal_can_prompt_for_secrets():
                _password(client, selection=None, not_persisted=not_persisted)
                return
            raise attach_cli_policy_verdict(
                CliRefusedBoundaryError(
                    translated_message="cli.config.custody.errors.profile_passphrase_channel_absent"
                ),
                verdict=profile_password_channel_failure_verdict(profile_name=profile_label or str(client.profile_id)),
            ) from None
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message=session_refusal_translation_key(refusal, error.binding),
                context=session_refusal_context(refusal, error.binding),
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
    bucket_id = target_bucket_id or profile_selection.command_profile_id()
    if bucket_id is None:
        if root_selection is not None or credential_reference is not None:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_missing_target")
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    profile_label = target_profile_label
    if profile_label is None and credential_reference is None:
        target = profile_selection.runtime_login_target(bucket_id)
        if target is not None:
            profile_label = target.label
    if credential_reference is not None:
        client = _open_profile_credential_client(bucket_id, credential_reference, root_selection, method, ctx)
    else:
        client = asyncio.run(
            open_installed_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI)
        )
    try:
        if credential_reference is None:
            subscribe_profile_notices(ctx, client)
            authenticate_profile_client(
                client, root_selection=root_selection, profile_label=profile_label, method=method
            )
        bind_profile_target(ctx, bucket_id=bucket_id)
        bind_profile_client(ctx, client, profile_id=UUID(bucket_id))
    except FrontendRefusedError as error:
        client.close()
        raise_connection_refusal(error)
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


__all__ = [
    "activate_profile",
    "authenticate_profile_client",
    "bind_profile_target",
]
