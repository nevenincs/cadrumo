"""Google Drive folder command registration for ``aeat config google``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....adapters.outbound.google import (
    DriveConfig,
    GoogleAuthError,
    load_drive_config,
    resolve_active_profile,
    save_drive_config,
)
from .._common import _emit_envelope
from ._google_errors import _google_refusal
from ._google_folder_payloads import GoogleFolderGetResult, GoogleFolderSetResult

if TYPE_CHECKING:
    import typer


def google_folder_set(ctx: typer.Context, folder_id: str) -> None:
    """Persist the Drive root folder id under the active profile."""
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc
    config = DriveConfig(root_folder_id=folder_id.strip())
    save_drive_config(active, config)
    result = GoogleFolderSetResult(profile=active, root_folder_id=config.root_folder_id)
    _emit_envelope(
        ctx,
        command="config.google.folder.set",
        result=result,
        lines=(
            "operation\tconfig.google.folder.set",
            f"profile\t{active}",
            f"root_folder_id\t{config.root_folder_id}",
        ),
    )


def google_folder_get(ctx: typer.Context) -> None:
    """Show the persisted Drive root folder id for the active profile."""
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc
    config = load_drive_config(active)
    result = GoogleFolderGetResult(
        profile=active,
        configured=config is not None,
        root_folder_id=config.root_folder_id if config is not None else None,
    )
    _emit_envelope(
        ctx,
        command="config.google.folder.get",
        result=result,
        lines=(
            "operation\tconfig.google.folder.get",
            f"profile\t{active}",
            f"configured\t{config is not None}",
            f"root_folder_id\t{config.root_folder_id if config is not None else '<unset>'}",
        ),
    )


__all__ = ["google_folder_get", "google_folder_set"]
