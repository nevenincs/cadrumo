"""Base config auth CLI command surface."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import strict_round_trip
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope, resolve_cli_precondition_action
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.auth.operator_results import AuthConfigureResult


def _auth_configure_lines(configure_result: AuthConfigureResult) -> list[str]:
    """Render the operator text dump for a completed auth configure.

    Cl@ve Móvil is the only provider that binds a taxpayer identity, so its
    three identity lines (and the alignment detail, when the backend states
    one) are emitted for that provider alone.
    """
    lines = [
        f"provider\t{configure_result.provider}",
        f"file\t{configure_result.file}",
        f"status\t{'configured' if configure_result.complete else 'incomplete'}",
    ]
    if not configure_result.complete:
        lines.append(f"incomplete_reason\t{configure_result.incomplete_reason}")
    if configure_result.provider != "clave_movil":
        return lines
    lines.extend(
        (
            f"profile_tax_id\t{'present' if configure_result.profile_tax_id_present else 'missing'}",
            f"clave_identity\t{'present' if configure_result.provider_identity_present else 'missing'}",
            f"identity_alignment\t{configure_result.identity_alignment}",
        ),
    )
    if configure_result.identity_alignment_detail:
        lines.append(f"identity_alignment_detail\t{configure_result.identity_alignment_detail}")
    return lines


def _run_provider_auth_operation[AuthResultT](
    operation: Callable[..., AuthResultT],
    *,
    provider: str | None,
    all_providers: bool,
) -> AuthResultT:
    """Run a provider-scoped auth operation, mapping backend refusals to CLI boundaries.

    ``logout`` and ``reset`` share the exact refusal fan-out: an unknown provider,
    no active bucket, a missing custody session, an operation-scope conflict, and an
    unconfigured provider each map to the same translated boundary message for both
    verbs.

    The custody-session refusal is mapped separately from the scope conflict on
    purpose. Collapsing the two would render "choose either --provider or --all"
    at an operator whose real remedy is ``aeat config login`` for the target
    profile — an instruction that cannot resolve the refusal it answers.
    """
    from ....application.auth.operator_results import (
        AuthConfigureNoActiveBucketError,
        AuthOperationRequiresCustodySessionError,
        AuthOperationScopeConflictError,
        AuthProviderNotConfiguredError,
    )

    try:
        return operation(provider=provider, all_providers=all_providers)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthOperationRequiresCustodySessionError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="application.auth.operator.errors.requires_custody_session",
            context=exc.context,
        ) from exc
    except AuthOperationScopeConflictError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="application.auth.operator.errors.scope_conflict",
        ) from exc
    except AuthProviderNotConfiguredError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="application.auth.operator.errors.provider_not_configured",
        ) from exc


def auth_providers(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List supported authentication providers from the backend catalogue."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import list_operator_auth_providers
    from ..config_payloads import AuthProvidersResult

    report = list_operator_auth_providers()
    result = AuthProvidersResult(providers=list(report.providers))
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
    emit_envelope(ctx, command="config.auth.providers", result=result, lines=tuple(rows))


def auth_configure(
    ctx: typer.Context,
    provider: str,
    file: Path | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Configure the active authentication provider."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import configure_operator_auth
    from ....application.auth.operator_results import AuthConfigureNoActiveBucketError, AuthProviderReservedError

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
    from ..config_payloads import AuthConfigurePayload as _AuthConfigurePayload

    configure_result = result
    precondition_action = (
        resolve_cli_precondition_action(configure_result.precondition_verdict)
        if configure_result.precondition_verdict is not None
        else None
    )
    auth_configure_payload = _AuthConfigurePayload.from_result(
        configure_result,
        precondition_action=precondition_action,
    )
    lines = _auth_configure_lines(configure_result)
    lines.extend(precondition_action_lines(precondition_action))
    emit_envelope(ctx, command="config.auth.configure", result=auth_configure_payload, lines=lines)


def auth_status(
    ctx: typer.Context,
    provider: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show the configured local authentication state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import inspect_operator_auth
    from ..config_payloads import AuthStatusPayload

    try:
        result = inspect_operator_auth(provider)
    except KeyError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider or ""},
        ) from exc
    precondition_action = (
        resolve_cli_precondition_action(result.active_profile_precondition_verdict)
        if result.active_profile_precondition_verdict is not None
        else None
    )
    envelope_result = AuthStatusPayload.from_result(
        result,
        active_profile_precondition_action=precondition_action,
    )
    payload = envelope_result.model_dump(mode="json")
    emit_envelope(
        ctx,
        command="config.auth.status",
        result=envelope_result,
        lines=(
            _auth_status_summary_line(payload),
            *(f"{key}\t{value}" for key, value in payload.items() if key != "active_profile_precondition_action"),
            *precondition_action_lines(precondition_action),
        ),
    )


def _auth_status_summary_line(payload: dict[str, object]) -> str:
    """Return the localised operator verdict prepended to the status dump.

    The tab-separated ``key`` / ``value`` lines mirror the JSON envelope and key
    on stable field identifiers (``configured``, ``authenticated``,
    ``available``, …), so they are deliberately kept as machine identifiers
    rather than localised. This verdict line is the operator-facing prose that
    the ``--language`` / ``--output-language`` flag localises, so the flag has a
    visible effect on the ``status`` output.
    """
    if payload.get("authenticated") and payload.get("available"):
        return tr(
            "cli.config.auth.status_summary_ready",
        )
    if payload.get("configured"):
        return tr(
            "cli.config.auth.status_summary_configured",
        )
    return tr(
        "cli.config.auth.status_summary_unconfigured",
    )


def auth_test(
    ctx: typer.Context,
    provider: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Render auth readiness through the application-owned auth state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import test_operator_auth
    from ....application.auth.operator_results import AuthProviderReservedError
    from ..config_payloads import AuthTestPayload

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
    precondition_action = (
        resolve_cli_precondition_action(result.active_profile_precondition_verdict)
        if result.active_profile_precondition_verdict is not None
        else None
    )
    envelope_result = AuthTestPayload.from_test_result(
        result,
        active_profile_precondition_action=precondition_action,
    )
    payload = envelope_result.model_dump(mode="json")
    emit_envelope(
        ctx,
        command="config.auth.test",
        result=envelope_result,
        lines=(
            *(f"{key}\t{value}" for key, value in payload.items() if key != "active_profile_precondition_action"),
            *precondition_action_lines(precondition_action),
        ),
    )


def auth_login(
    ctx: typer.Context,
    provider: str | None = None,
    fresh: bool = False,
    reset_lock: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Acquire or verify a live AEAT session through the configured provider."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import login_operator_auth
    from ....application.auth.operator_results import AuthProviderReservedError
    from ..config_payloads import AuthLoginPayload

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
    payload = result.model_dump(mode="json")
    envelope_result = AuthLoginPayload.model_validate_json(result.model_dump_json())
    emit_envelope(
        ctx,
        command="config.auth.login",
        result=envelope_result,
        lines=tuple(f"{key}\t{value}" for key, value in payload.items()),
    )


def auth_logout(
    ctx: typer.Context,
    provider: str | None = None,
    all_providers: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Terminate local auth sessions without removing provider configuration."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import logout_operator_auth

    result = _run_provider_auth_operation(
        logout_operator_auth,
        provider=provider,
        all_providers=all_providers,
    )
    from ..config_payloads import AuthLogoutPayload

    payload = strict_round_trip(AuthLogoutPayload, result)
    emit_envelope(
        ctx,
        command="config.auth.logout",
        result=payload,
        lines=(
            f"bucket_id\t{result.bucket_id}",
            f"providers\t{','.join(result.providers)}",
            f"removed_sessions\t{result.removed_sessions}",
            f"cleared_session_state\t{result.cleared_session_state}",
        ),
    )


def auth_reset(
    ctx: typer.Context,
    provider: str | None = None,
    all_providers: bool = False,
    yes: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove local auth configuration and persisted provider state."""
    _activate_subcommand_output_language(ctx, output_language)
    if not yes:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.reset_requires_yes",
        )
    from ....application.auth.operator import reset_operator_auth

    result = _run_provider_auth_operation(
        reset_operator_auth,
        provider=provider,
        all_providers=all_providers,
    )
    from ..config_payloads import AuthResetPayload

    payload = strict_round_trip(AuthResetPayload, result)
    emit_envelope(
        ctx,
        command="config.auth.reset",
        result=payload,
        lines=tuple(f"{key}\t{value}" for key, value in result.model_dump(mode="json").items()),
    )


__all__ = [
    "auth_configure",
    "auth_login",
    "auth_logout",
    "auth_providers",
    "auth_reset",
    "auth_status",
    "auth_test",
]
