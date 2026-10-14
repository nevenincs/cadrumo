"""Non-authoritative observation of the selected profile's sign-in state."""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import resolve_login_target
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.external_constants import OutputLanguage
from cadrumo_client.commands.custody_payloads import ConfigSignInStatusResult
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatus

from .presentation import activate_subcommand_output_language, emit_envelope
from .profile_admission import runtime_root_context


def config_sign_in_status(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """Observe sign-in presence without borrowing proof or extending the session."""
    activate_subcommand_output_language(ctx, output_language)

    profile = runtime_root_context(ctx).profile
    if profile is None:
        captured = observe_active_profile_pointer()
        bucket_id = captured.bucket_id
    else:
        target = resolve_login_target(profile)
        bucket_id = str(target.bucket_id)
        root_state = ctx.find_root().ensure_object(dict)
        root_state["cadrumo.runtime.profile_label"] = target.label
    status = SignInStatus(presence=SignInPresence.ABSENT)
    if bucket_id is not None:
        from cadrumo_client.commands.profile_binding import subscribe_profile_notices
        from cadrumo_client.transport.installed_client import open_installed_client

        client = asyncio.run(
            open_installed_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI)
        )
        try:
            subscribe_profile_notices(ctx, client)
            status = client.sign_in_status().status
        finally:
            client.close()
    result = ConfigSignInStatusResult(profile_id=bucket_id, status=status)
    emit_envelope(
        ctx,
        command="config.sign-in-status",
        result=result,
        lines=(
            f"presence\t{status.presence.value}",
            f"idle_deadline\t{status.idle_deadline.isoformat() if status.idle_deadline is not None else '<none>'}",
            "absolute_deadline\t"
            f"{status.absolute_deadline.isoformat() if status.absolute_deadline is not None else '<none>'}",
        ),
    )


__all__ = ["config_sign_in_status"]
