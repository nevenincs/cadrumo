"""Authenticate one runtime-owned command against its exact profile target."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError, resolve_login_target
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import clear_output_language_cache, tr
from cadrumo.core.output_rendering import OutputFormat
from cadrumo.core.profile_session import ProfileSessionRefusalReason as ReceiptRefusalReason
from cadrumo.core.profile_session import ReceiptBindingRefusal
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_authentication import ProfileAuthenticationMethod, ProfileAuthenticationSecrets
from cadrumo_client.commands.secure_input import (
    ProfileSecretSelection,
    prompt_secret_no_echo,
    read_profile_secret_payload,
    select_profile_secret_channel,
    terminal_can_prompt_for_secrets,
)
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

if TYPE_CHECKING:
    from cadrumo_client.commands.spec import CommandSpec
    from cadrumo_client.transport.frontend_client import FrontendClient


@dataclass(frozen=True, slots=True)
class RuntimeProfileAuthenticationSource:
    """Parsed, non-secret root profile-authentication choices for one invocation."""

    selection: ProfileSecretSelection | None
    method: ProfileAuthenticationMethod
    credential_reference: UUID | None

    @property
    def supplied(self) -> bool:
        """Return whether non-default profile authentication input was supplied."""
        return (
            self.selection is not None
            or self.credential_reference is not None
            or self.method is not ProfileAuthenticationMethod.PASSWORD
        )


@dataclass(frozen=True, slots=True)
class RuntimeCommandContext:
    """Typed output, profile and admission policy attached to the root invocation."""

    output_format: OutputFormat
    output_language: OutputLanguage | None
    profile: str | None
    profile_source: RuntimeProfileAuthenticationSource
    quiet: bool
    verbose: bool
    debug: bool


_ROOT_CONTEXT_KEY = "cadrumo.runtime.command_context"


def bind_runtime_root_context(
    ctx: typer.Context,
    *,
    language: OutputLanguage | None,
    profile: str | None,
    profile_secrets_stdin: bool,
    profile_secrets_fd: int | None,
    profile_auth_method: str,
    profile_credential_ref: UUID | None,
    format_: OutputFormat,
    quiet: bool,
    verbose: bool,
    debug: bool,
) -> RuntimeCommandContext:
    """Validate and attach the typed root options used by runtime commands."""
    normalized_format = format_
    normalized_language = language
    try:
        method = ProfileAuthenticationMethod(profile_auth_method)
    except ValueError:
        _refuse("profile_auth_method_invalid")
    selection = select_profile_secret_channel(
        profile_secrets_stdin=profile_secrets_stdin,
        profile_secrets_fd=profile_secrets_fd,
    )
    source = RuntimeProfileAuthenticationSource(selection, method, profile_credential_ref)
    if sum((quiet, verbose, debug)) > 1:
        raise CliRefusedBoundaryError(translated_message="cli.log_levels.errors.flags_mutually_exclusive")
    command_context = RuntimeCommandContext(
        output_format=normalized_format,
        output_language=normalized_language,
        profile=profile,
        profile_source=source,
        quiet=quiet,
        verbose=verbose,
        debug=debug,
    )
    root = ctx.find_root()
    state = root.ensure_object(dict)
    state[_ROOT_CONTEXT_KEY] = command_context
    state["format_"] = normalized_format
    state["format"] = normalized_format
    state["language"] = normalized_language
    state["profile_override"] = profile
    root.params["format_"] = normalized_format
    root.params["language"] = normalized_language
    if normalized_language is not None:
        root.with_resource(override_settings(cadrumo_output_language=normalized_language))
        clear_output_language_cache()
    if quiet or verbose or debug:
        from logging import DEBUG, ERROR, INFO

        from cadrumo.core.logging import set_log_level

        set_log_level(DEBUG if debug else INFO if verbose else ERROR)
    return command_context


def runtime_root_context(ctx: typer.Context) -> RuntimeCommandContext:
    """Return the validated root context bound before command dispatch."""
    state = ctx.find_root().ensure_object(dict)
    value = state.get(_ROOT_CONTEXT_KEY)
    if not isinstance(value, RuntimeCommandContext):
        raise InternalInvariantError("runtime root command context was not bound")
    return value


def _refuse(key: str) -> NoReturn:
    raise CliRefusedBoundaryError(translated_message=f"cli.config.custody.errors.{key}")


def _root_profile_source(
    ctx: typer.Context,
) -> tuple[ProfileSecretSelection | None, ProfileAuthenticationMethod, UUID | None]:
    source = runtime_root_context(ctx).profile_source
    return source.selection, source.method, source.credential_reference


def _profile_id(ctx: typer.Context) -> tuple[UUID, str | None]:
    raw = runtime_root_context(ctx).profile
    if raw is not None:
        if not isinstance(raw, str) or not raw.strip():
            raise CliRefusedBoundaryError(translated_message="errors.refused.refused_profile_not_found")
        pointer = resolve_login_target(raw.strip())
        profile_id = UUID(str(pointer.bucket_id))
        ctx.find_root().ensure_object(dict)["cadrumo.runtime.profile_label"] = pointer.label
        return profile_id, pointer.label
    active = resolve_active_bucket_id()
    if active is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(active)
    label = None if pointer is None else pointer.label
    ctx.find_root().ensure_object(dict)["cadrumo.runtime.profile_label"] = label
    return UUID(active), label


def _password(
    client: FrontendClient,
    *,
    selection: ProfileSecretSelection | None,
    ctx: typer.Context,
) -> None:
    if selection is None:
        secret = bytearray(prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt")).encode("utf-8"))
    else:
        payload = read_profile_secret_payload(ProfileAuthenticationSecrets, selection=selection)
        try:
            if payload.profile_passphrase is None:
                _refuse("profile_secrets_method_mismatch")
            secret = bytearray(payload.profile_passphrase.get_secret_value().encode("utf-8"))
        finally:
            del payload
    try:
        admitted = client.login_password(secret)
    finally:
        secret[:] = bytes(len(secret))
    if admitted.human_login is None or not admitted.human_login.session_persisted:
        from cadrumo.core.json_contract import Notice, NoticeSeverity

        state = ctx.find_root().ensure_object(dict)
        state.setdefault("cadrumo.runtime.notices", []).append(
            Notice(
                code="config.login.session_not_persisted",
                severity=NoticeSeverity.WARNING,
                message=tr("cli.config.login.notices.session_invocation_scoped"),
            )
        )


def _api_key(client: FrontendClient, *, selection: ProfileSecretSelection) -> None:
    payload = read_profile_secret_payload(ProfileAuthenticationSecrets, selection=selection)
    try:
        if payload.api_key is None:
            _refuse("profile_secrets_method_mismatch")
        secret = bytearray(payload.api_key.get_secret_value().encode("utf-8"))
    finally:
        del payload
    try:
        client.login_api_key(secret)
    finally:
        secret[:] = bytes(len(secret))


def _session_refusal_key(
    refusal: ReceiptRefusalReason,
    binding: ReceiptBindingRefusal | None = None,
) -> str:
    if binding is ReceiptBindingRefusal.LOGIN_MISMATCH:
        return "cli.config.errors.profile_session_login_mismatch"
    if binding is ReceiptBindingRefusal.GENERATION_CHANGED:
        return "cli.config.errors.profile_session_signed_out"
    if binding is not None:
        return "cli.config.errors.profile_session_unreadable"
    if refusal is ReceiptRefusalReason.CUSTODY_CHANGED:
        return "cli.config.errors.profile_session_custody_changed"
    if refusal is ReceiptRefusalReason.SCHEMA_VERSION_MISMATCH:
        return "cli.config.errors.profile_session_outdated"
    if refusal in {ReceiptRefusalReason.MALFORMED, ReceiptRefusalReason.TAMPERED}:
        return "cli.config.errors.profile_session_unreadable"
    if refusal is ReceiptRefusalReason.KEYRING_UNAVAILABLE:
        return "errors.auth.auth_storage_keyring_unavailable"
    if refusal in {ReceiptRefusalReason.ABSENT, ReceiptRefusalReason.KEYCHAIN_ENTRY_MISSING}:
        return "cli.config.errors.profile_session_absent"
    return "cli.config.errors.profile_session_expired"


def _raise_frontend_refusal(error: FrontendRefusedError) -> None:
    sign_in = error.sign_in
    translated_message = None
    if sign_in is not None and sign_in.reason == "throttled":
        translated_message = "errors.refused.refused_profile_login_throttled"
    elif sign_in is not None and isinstance(sign_in.reason, ReceiptRefusalReason):
        translated_message = _session_refusal_key(sign_in.reason, sign_in.binding)
    raise CliRefusedBoundaryError(error.reason, context=error.context, translated_message=translated_message) from None


def _authenticate(
    ctx: typer.Context,
    client: FrontendClient,
    *,
    selection: ProfileSecretSelection | None,
    method: ProfileAuthenticationMethod,
) -> None:
    if method is ProfileAuthenticationMethod.API_KEY:
        if selection is None:
            _refuse("profile_secrets_api_key_requires_channel")
        _api_key(client, selection=selection)
        return
    if selection is not None:
        _password(client, selection=selection, ctx=ctx)
        return
    try:
        client.resume_receipt()
    except ProfileReceiptRefusedError as error:
        if error.reason is ReceiptRefusalReason.KEYRING_UNAVAILABLE and terminal_can_prompt_for_secrets():
            _password(client, selection=None, ctx=ctx)
            return
        key = _session_refusal_key(error.reason, error.binding)
        raise CliRefusedBoundaryError(
            translated_message=key,
            context={
                "reason": error.reason.value,
                **({"sign_in_binding": error.binding.value} if error.binding is not None else {}),
            },
        ) from None
    except FrontendRefusedError as error:
        _raise_frontend_refusal(error)


def _bind_target(ctx: typer.Context, profile_id: UUID) -> None:
    ctx.find_root().ensure_object(dict)["cadrumo.runtime.profile_id"] = profile_id
    ctx.with_resource(override_settings(cadrumo_active_profile=str(profile_id)))


def _open_authenticated_profile(
    ctx: typer.Context,
    profile_id: UUID,
    *,
    selection: ProfileSecretSelection | None,
    method: ProfileAuthenticationMethod,
    credential_reference: UUID | None,
) -> None:
    from cadrumo_client.commands.profile_binding import bind_profile_client, subscribe_profile_notices
    from cadrumo_client.transport.credentials import open_installed_credential_client
    from cadrumo_client.transport.installed_client import open_installed_client

    if credential_reference is not None:
        if selection is not None:
            _refuse("profile_credential_ref_conflict")
        if method is not ProfileAuthenticationMethod.API_KEY:
            _refuse("profile_credential_ref_requires_api_key")
        client = asyncio.run(
            open_installed_credential_client(
                profile_id=profile_id,
                credential_reference=credential_reference,
                frontend=OperationFrontendProjection.CLI,
                on_connected=lambda connected: subscribe_profile_notices(ctx, connected),
            )
        )
    else:
        client = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        subscribe_profile_notices(ctx, client)
        if credential_reference is None:
            _authenticate(
                ctx,
                client,
                selection=selection,
                method=method,
            )
        _bind_target(ctx, profile_id)
        if credential_reference is not None:
            ctx.find_root().ensure_object(dict)["credential_reference"] = credential_reference
        bind_profile_client(ctx, client, profile_id=profile_id)
    except FrontendRefusedError as error:
        client.close()
        _raise_frontend_refusal(error)
    except BaseException:
        client.close()
        raise


def _open_recovery_profile(ctx: typer.Context, profile_id: UUID) -> None:
    from cadrumo_client.commands.profile_binding import bind_profile_client
    from cadrumo_client.transport.installed_client import open_installed_client

    client = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        _bind_target(ctx, profile_id)
        bind_profile_client(ctx, client, profile_id=profile_id)
    except BaseException:
        client.close()
        raise


def _root_profile_options_are_supplied(ctx: typer.Context) -> bool:
    return runtime_root_context(ctx).profile_source.supplied


def preflight_runtime_command(ctx: typer.Context, spec: CommandSpec, arguments: dict[str, object]) -> None:
    """Bind a command's exact profile before its handler starts, using the declared posture."""
    if spec.kind.value != "leaf":
        return
    selection, method, credential_reference = _root_profile_source(ctx)
    if spec.key in {"config_auth_providers", "config_auth_apoderado_scopes_list", "config_sign_in_status"}:
        if _root_profile_options_are_supplied(ctx):
            _refuse("profile_secrets_inapplicable")
        return
    posture = spec.profile_authentication
    target_is_self_authenticating = posture is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    if spec.key == "config_profile_resume":
        if selection is not None or credential_reference is not None:
            _refuse("profile_secrets_inapplicable")
        profile_id, _ = _profile_id(ctx)
        _open_recovery_profile(ctx, profile_id)
        return
    if spec.machine_secret is not None:
        from cadrumo_client.commands.secure_input import MachineSecretChannel, select_machine_secret_channel

        secrets_fd = arguments.get("secrets_fd")
        if secrets_fd is not None and type(secrets_fd) is not int:
            raise CliRefusedBoundaryError(translated_message="errors.refused.refused_cli_validation_boundary")
        leaf = select_machine_secret_channel(
            secrets_stdin=bool(arguments.get("secrets_stdin", False)),
            secrets_fd=secrets_fd,
        )
        if selection is not None and leaf is not None:
            root_descriptor = 0 if selection.descriptor is None else selection.descriptor
            leaf_descriptor = 0 if leaf.channel is MachineSecretChannel.STDIN else leaf.descriptor
            if root_descriptor == leaf_descriptor:
                _refuse("profile_secrets_stdin_collision" if root_descriptor == 0 else "profile_secrets_fd_collision")
    if target_is_self_authenticating:
        if _root_profile_options_are_supplied(ctx):
            _refuse("profile_secrets_inapplicable")
        if runtime_root_context(ctx).profile is not None:
            profile_id, _ = _profile_id(ctx)
            _bind_target(ctx, profile_id)
        return
    profile_required = bool(spec.policy.capabilities & {"profile-custody", "encrypted-facts"})
    if not profile_required:
        if _root_profile_options_are_supplied(ctx):
            _refuse("profile_secrets_inapplicable")
        return
    if method is ProfileAuthenticationMethod.API_KEY and selection is None and credential_reference is None:
        _refuse("profile_secrets_api_key_requires_channel")
    if credential_reference is not None and posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
        _refuse("profile_credential_ref_inapplicable")
    profile_id, _label = _profile_id(ctx)
    _open_authenticated_profile(
        ctx,
        profile_id,
        selection=selection,
        method=method,
        credential_reference=credential_reference,
    )


__all__ = [
    "RuntimeCommandContext",
    "RuntimeProfileAuthenticationSource",
    "bind_runtime_root_context",
    "preflight_runtime_command",
    "runtime_root_context",
]
