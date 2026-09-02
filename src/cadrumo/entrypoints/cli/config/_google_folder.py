"""Google Drive folder behavior handlers for ``aeat config google``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....adapters.outbound.google.active_profile import resolve_active_profile
from ....adapters.outbound.google.errors import GoogleAuthError
from ....adapters.outbound.google.records import DriveConfig
from ....adapters.outbound.google.session_store import load_drive_config, save_drive_config
from .._common import emit_envelope
from ._google_folder_payloads import GoogleFolderSetResult, GoogleFolderViewResult
from .google_errors import google_refusal

if TYPE_CHECKING:
    import typer


def google_folder_set(ctx: typer.Context, folder_id: str) -> None:
    """Persist the Drive root folder id under the active profile."""
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise google_refusal(exc) from exc
    config = DriveConfig(root_folder_id=folder_id.strip())
    save_drive_config(active, config)
    result = GoogleFolderSetResult(profile=active, root_folder_id=config.root_folder_id)
    emit_envelope(
        ctx,
        command="config.google.folder.set",
        result=result,
        lines=(
            "operation\tconfig.google.folder.set",
            f"profile\t{active}",
            f"root_folder_id\t{config.root_folder_id}",
        ),
    )


def google_folder_view(ctx: typer.Context) -> None:
    """Show the persisted Drive root folder id for the active profile."""
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise google_refusal(exc) from exc
    config = load_drive_config(active)
    result = GoogleFolderViewResult(
        profile=active,
        configured=config is not None,
        root_folder_id=config.root_folder_id if config is not None else None,
    )
    emit_envelope(
        ctx,
        command="config.google.folder.view",
        result=result,
        lines=(
            "operation\tconfig.google.folder.view",
            f"profile\t{active}",
            f"configured\t{config is not None}",
            f"root_folder_id\t{config.root_folder_id if config is not None else '<unset>'}",
        ),
    )


__all__ = ["google_folder_set", "google_folder_view"]
