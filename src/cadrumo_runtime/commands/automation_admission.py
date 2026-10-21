"""Admission facts for runtime-owned automation credential changes."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError


def require_automation_change_credential_reference(ctx: typer.Context) -> UUID:
    """Return only the exact protected reference admitted for own-grant change."""
    value = ctx.find_root().ensure_object(dict).get("credential_reference")
    if not isinstance(value, UUID):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.automation_change_credential_ref_required"
        )
    return value


__all__ = ["require_automation_change_credential_reference"]
