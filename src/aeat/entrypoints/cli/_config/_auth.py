"""Base config auth CLI command surface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import click
import typer
import typer._click.types as typer_click_types

from ....application.auth import known_auth_provider_ids as _known_auth_provider_ids
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

auth_app = typer.Typer(name="auth", help=tr("cli.config.auth.help"), no_args_is_help=True)

# CAST-RATIONALE-AUTH-PROVIDER-CHOICE: typer vendors its own copy of click, so
# click.Choice is a click.types.ParamType while typer.Option's click_type expects
# typer._click.types.ParamType. They are the same object at runtime (the vendored
# click), so the cast only bridges the static type duality — no Any escape.
_AUTH_PROVIDER_CHOICE: typer_click_types.ParamType = cast(
    typer_click_types.ParamType, click.Choice(_known_auth_provider_ids())
)


@auth_app.command("providers", help=tr("cli.config.auth.providers_help"))
def auth_providers(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List supported authentication providers from the backend catalogue."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import list_operator_auth_providers
    from .._config_payloads import AuthProvidersResult

    report = list_operator_auth_providers()
    result = AuthProvidersResult(providers=report.model_dump(mode="json")["providers"])
    rows: list[str] = []
    for provider in report.providers:
        if provider.implemented:
            status_token = tr("cli.config.auth.providers.status_implemented")
        else:
            status_token = (
                f"{tr('cli.config.auth.providers.status_reserved')}"
                f" ({tr('cli.config.auth.providers.status_unavailable_gloss')})"
            )
        rows.append(f"{provider.id}\t{status_token}\t{tr(str(provider.label))}")
    _emit_envelope(ctx, command="config.auth.providers", result=result, lines=tuple(rows))


@auth_app.command("configure", help=tr("cli.config.auth.configure_help"))
def auth_configure(
    ctx: typer.Context,
    provider: str = typer.Option(
        ...,
        "--provider",
        click_type=_AUTH_PROVIDER_CHOICE,
        help=tr("cli.config.auth.provider_help"),
    ),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.config.auth.file_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Configure the active authentication provider."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        AuthProviderReservedError,
        configure_operator_auth,
    )

    try:
        result = configure_operator_auth(provider, certificate_path=file)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider},
        ) from exc
    except AuthProviderReservedError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.reserved_provider",
            context={"provider": provider},
        ) from exc
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    from .._config_payloads import AuthConfigurePayload as _AuthConfigurePayload

    configure_result = result
    auth_configure_payload = _AuthConfigurePayload.from_result(configure_result)
    lines = [
        f"provider\t{configure_result.provider}",
        f"file\t{configure_result.file}",
        f"status\t{'configured' if configure_result.complete else 'incomplete'}",
        f"active_profile\t{configure_result.active_profile}",
    ]
    if not configure_result.complete:
        lines.append(f"incomplete_reason\t{configure_result.incomplete_reason}")
    if configure_result.provider == "clave_movil":
        lines.extend(
            (
                f"profile_tax_id\t{'present' if configure_result.profile_tax_id_present else 'missing'}",
                f"clave_identity\t{'present' if configure_result.provider_identity_present else 'missing'}",
                f"identity_alignment\t{configure_result.identity_alignment}",
            )
        )
        if configure_result.identity_alignment_detail:
            lines.append(f"identity_alignment_detail\t{configure_result.identity_alignment_detail}")
    lines.append(f"next_action\t{configure_result.next_action}")
    _emit_envelope(ctx, command="config.auth.configure", result=auth_configure_payload, lines=lines)


@auth_app.command("status", help=tr("cli.config.auth.status_help"))
def auth_status(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=_AUTH_PROVIDER_CHOICE),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Show the configured local authentication state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import inspect_operator_auth
    from .._config_payloads import AuthStatusPayload

    try:
        result = inspect_operator_auth(provider)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    payload = result.model_dump(mode="json")
    envelope_result = AuthStatusPayload.model_validate(payload)
    _emit_envelope(
        ctx,
        command="config.auth.status",
        result=envelope_result,
        lines=tuple(f"{key}\t{value}" for key, value in payload.items()),
    )


@auth_app.command("test", help=tr("cli.config.auth.test_help"))
def auth_test(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=_AUTH_PROVIDER_CHOICE),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Render auth readiness through the application-owned auth state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import AuthProviderReservedError, test_operator_auth
    from .._config_payloads import AuthTestPayload

    try:
        result = test_operator_auth(provider)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    except AuthProviderReservedError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.reserved_provider",
            context={"provider": provider or ""},
        ) from exc
    payload = result.model_dump(mode="json")
    envelope_result = AuthTestPayload.model_validate(payload)
    _emit_envelope(
        ctx,
        command="config.auth.test",
        result=envelope_result,
        lines=tuple(f"{key}\t{value}" for key, value in payload.items()),
    )


@auth_app.command("login", help=tr("cli.config.auth.login_help"))
def auth_login(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=_AUTH_PROVIDER_CHOICE),
    fresh: bool = typer.Option(False, "--fresh", help=tr("cli.config.auth.login_fresh_help")),
    reset_lock: bool = typer.Option(False, "--reset-lock", help=tr("cli.config.auth.login_reset_lock_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Acquire or verify a live AEAT session through the configured provider."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthLoginNotEnabledError,
        AuthLoginPreconditionError,
        AuthProviderReservedError,
        login_operator_auth,
    )
    from .._config_payloads import AuthLoginPayload

    try:
        result = asyncio.run(login_operator_auth(provider, fresh=fresh, reset_lock=reset_lock))
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    except AuthProviderReservedError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.reserved_provider",
            context={"provider": provider or ""},
        ) from exc
    except (AuthLoginNotEnabledError, AuthLoginPreconditionError) as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    payload = result.model_dump(mode="json")
    envelope_result = AuthLoginPayload.model_validate(payload)
    _emit_envelope(
        ctx,
        command="config.auth.login",
        result=envelope_result,
        lines=tuple(f"{key}\t{value}" for key, value in payload.items()),
    )


@auth_app.command("clear", help=tr("cli.config.auth.clear_help"))
def auth_clear(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", click_type=_AUTH_PROVIDER_CHOICE),
    all_providers: bool = typer.Option(False, "--all", help=tr("cli.config.auth.clear_all_help")),
    sessions: bool = typer.Option(False, "--sessions", help=tr("cli.config.auth.clear_sessions_help")),
    locks: bool = typer.Option(False, "--locks", help=tr("cli.config.auth.clear_locks_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Clear local auth metadata, persisted sessions, and auth locks."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import AuthProviderReservedError, clear_operator_auth

    try:
        result = clear_operator_auth(provider=provider, all_providers=all_providers, sessions=sessions, locks=locks)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    except AuthProviderReservedError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.reserved_provider",
            context={"provider": provider or ""},
        ) from exc
    from .._config_payloads import AuthClearPayload

    clear_result = AuthClearPayload.from_result(result)
    _emit_envelope(
        ctx,
        command="config.auth.clear",
        result=clear_result,
        lines=(
            f"removed_sessions\t{result.removed_sessions}",
            f"cleared_workflow_state\t{result.cleared_workflow_state}",
            f"cleared_locks\t{result.cleared_locks}",
        ),
    )
