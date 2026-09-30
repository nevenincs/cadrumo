"""Base config auth CLI command surface."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import typer

from ....application.auth.operator_results import AuthLogoutResult, AuthResetResult
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import strict_round_trip
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope, resolve_cli_precondition_action
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion, submitted_operation_error
from .runtime_auth_teardown import run_auth_teardown
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.auth.operator_results import AuthConfigureResult
    from ....application.operator_actions.models import PreconditionVerdict
    from ....core.json_contract import ResolvedPreconditionAction


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


def auth_providers(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List supported authentication providers from the backend catalogue."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.operator import list_operator_auth_providers
    from ....application.auth.output import AuthProviderRow, AuthProvidersResult

    report = list_operator_auth_providers()
    # `label` and `description` are Translatable translation keys, not text.
    # Render both here so the JSON envelope carries the same words the text
    # lines below do rather than the raw dotted key paths.
    providers = [
        AuthProviderRow(
            id=provider.id,
            label=tr(str(provider.label)),
            description=tr(str(provider.description)),
        )
        for provider in report.providers
    ]
    result = AuthProvidersResult(providers=providers)
    rows = [f"{provider.id}\t{provider.label}" for provider in providers]
    emit_envelope(ctx, command="config.auth.providers", result=result, lines=tuple(rows))


def auth_configure(
    ctx: typer.Context,
    provider: str,
    file: Path | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Configure the active authentication provider."""
    _activate_subcommand_output_language(ctx, output_language)
    from .runtime_auth_configure import run_auth_configure

    configure_result = run_auth_configure(ctx, provider=provider, certificate_path=file)
    from ..config_payloads import AuthConfigurePayload as _AuthConfigurePayload

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


class _PreconditionBearingResult(Protocol):
    @property
    def active_profile_precondition_verdict(self) -> PreconditionVerdict | None: ...


def _active_profile_precondition_action(result: _PreconditionBearingResult) -> ResolvedPreconditionAction | None:
    """Resolve the active-profile precondition a read result carries, if any."""
    verdict = result.active_profile_precondition_verdict
    return resolve_cli_precondition_action(verdict) if verdict is not None else None


def auth_status(
    ctx: typer.Context,
    provider: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show the configured local authentication state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ..config_payloads import AuthStatusPayload
    from .runtime_auth_read import cli_auth_read

    result = cli_auth_read(ctx, kind="status", provider=provider, output_language=output_language).status
    if result is None:
        raise _CliRefusedBoundaryError(context={"reason": "invalid_frame"})
    precondition_action = _active_profile_precondition_action(result)
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
    from ..config_payloads import AuthTestPayload
    from .runtime_auth_read import cli_auth_read

    result = cli_auth_read(ctx, kind="test", provider=provider, output_language=output_language).test
    if result is None:
        raise _CliRefusedBoundaryError(context={"reason": "invalid_frame"})
    precondition_action = _active_profile_precondition_action(result)
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
    from ..config_payloads import AuthLoginPayload
    from .runtime_auth_login import run_auth_login

    result = run_auth_login(ctx, provider=provider, fresh=fresh, reset_lock=reset_lock)
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
    completed = run_auth_teardown(
        ctx,
        kind="logout",
        provider=provider,
        all_providers=all_providers,
        result_type=AuthLogoutResult,
    )
    from ..config_payloads import AuthLogoutPayload

    try:
        result = completed.projection
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
    except (typer.Exit, _CliRefusedBoundaryError):
        raise
    except Exception:
        raise _teardown_presentation_error(completed) from None


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
    completed = run_auth_teardown(
        ctx,
        kind="reset",
        provider=provider,
        all_providers=all_providers,
        result_type=AuthResetResult,
    )
    from ..config_payloads import AuthResetPayload

    try:
        result = completed.projection
        payload = strict_round_trip(AuthResetPayload, result)
        emit_envelope(
            ctx,
            command="config.auth.reset",
            result=payload,
            lines=tuple(f"{key}\t{value}" for key, value in result.model_dump(mode="json").items()),
        )
    except (typer.Exit, _CliRefusedBoundaryError):
        raise
    except Exception:
        raise _teardown_presentation_error(completed) from None


def _teardown_presentation_error(
    completed: RegisteredOperationCompletion[AuthLogoutResult] | RegisteredOperationCompletion[AuthResetResult],
) -> _CliRefusedBoundaryError:
    """Keep the settled teardown receipt when local rendering fails."""
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.UNAVAILABLE.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
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
