"""Human Google login, status, and logout commands owned by the runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.application.user_profile.google_configuration_operation_contracts import (
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from cadrumo_client.commands.google_configuration import run_google_configuration
from cadrumo_client.commands.google_payloads import GoogleLoginResult, GoogleLogoutResult, GoogleStatusResult
from cadrumo_client.commands.profile_binding import bound_profile_client

from .presentation import emit_envelope

if TYPE_CHECKING:
    import typer


def google_login(ctx: typer.Context) -> None:
    """Run the worker's human-consented login flow."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleLoginRequest(profile_id=client.profile_id),
        result_type=GoogleLoginProjection,
    )
    profile = str(projection.profile_id)
    typed = GoogleLoginResult(
        profile=profile,
        account_email=projection.account_email,
        granted_scopes=list(projection.granted_scopes),
        root_folder_id=projection.root_folder_id,
    )
    emit_envelope(
        ctx,
        command="config.google.login",
        result=typed,
        lines=(
            "operation\tconfig.google.login",
            f"profile\t{profile}",
            f"account_email\t{projection.account_email}",
            f"root_folder_id\t{projection.root_folder_id}",
            *tuple(f"scope\t{scope}" for scope in projection.granted_scopes),
        ),
    )


def _google_status_result(projection: GoogleStatusProjection) -> GoogleStatusResult:
    return GoogleStatusResult(
        profile=str(projection.profile_id),
        session_present=projection.session_present,
        account_email=projection.account_email,
        granted_scopes=list(projection.granted_scopes),
        issued_at=projection.issued_at,
    )


def _google_status_lines(projection: GoogleStatusProjection) -> tuple[str, ...]:
    lines = [
        "operation\tconfig.google.status",
        f"profile\t{projection.profile_id}",
        f"session_present\t{projection.session_present}",
    ]
    if projection.session_present:
        lines.extend(
            (
                f"account_email\t{projection.account_email}",
                f"issued_at\t{projection.issued_at}",
                *tuple(f"scope\t{scope}" for scope in projection.granted_scopes),
            ),
        )
    return tuple(lines)


def google_status(ctx: typer.Context) -> None:
    """Report non-secret session metadata from the worker."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleStatusRequest(profile_id=client.profile_id),
        result_type=GoogleStatusProjection,
    )
    emit_envelope(
        ctx,
        command="config.google.status",
        result=_google_status_result(projection),
        lines=_google_status_lines(projection),
    )


def google_logout(ctx: typer.Context) -> None:
    """Clear session records through the worker."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleLogoutRequest(profile_id=client.profile_id),
        result_type=GoogleLogoutProjection,
    )
    profile = str(projection.profile_id)
    result = GoogleLogoutResult(
        profile=profile,
        token_removed=projection.token_removed,
        metadata_removed=projection.metadata_removed,
    )
    emit_envelope(
        ctx,
        command="config.google.logout",
        result=result,
        lines=(
            "operation\tconfig.google.logout",
            f"profile\t{profile}",
            f"token_removed\t{projection.token_removed}",
            f"metadata_removed\t{projection.metadata_removed}",
        ),
    )


__all__ = ["google_login", "google_logout", "google_status"]
