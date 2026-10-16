"""Authenticated person activity through the installed runtime authority."""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError, resolve_login_target
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.external_constants import OutputLanguage
from cadrumo_client.commands.custody_payloads import ConfigActivityResult
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .presentation import activate_subcommand_output_language, emit_envelope
from .profile_admission import _raise_frontend_refusal, _session_refusal_key, runtime_root_context


def config_activity(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """Resume existing human proof and record activity without prompting or minting."""
    activate_subcommand_output_language(ctx, output_language)
    profile = runtime_root_context(ctx).profile
    if profile is None:
        bucket_id = observe_active_profile_pointer().bucket_id
    else:
        target = resolve_login_target(profile)
        bucket_id = str(target.bucket_id)
        ctx.find_root().ensure_object(dict)["cadrumo.runtime.profile_label"] = target.label
    if bucket_id is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    from cadrumo_client.commands.profile_binding import subscribe_profile_notices
    from cadrumo_client.transport.installed_client import open_installed_client

    client = asyncio.run(open_installed_client(profile_id=UUID(bucket_id), frontend=OperationFrontendProjection.CLI))
    try:
        subscribe_profile_notices(ctx, client)
        client.resume_receipt()
        client.note_activity()
    except ProfileReceiptRefusedError as error:
        raise CliRefusedBoundaryError(
            translated_message=_session_refusal_key(error.reason, error.binding),
            context={"reason": error.reason.value},
        ) from None
    except FrontendRefusedError as error:
        _raise_frontend_refusal(error)
    finally:
        client.close()
    emit_envelope(
        ctx,
        command="config.activity",
        result=ConfigActivityResult(activity_recorded=True),
        lines=("activity_recorded\ttrue",),
    )


__all__ = ["config_activity"]
