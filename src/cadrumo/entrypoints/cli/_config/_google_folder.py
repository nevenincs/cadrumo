"""Google Drive folder command registration for ``aeat config google``."""

from __future__ import annotations

from collections.abc import Callable

import typer

from ....adapters.outbound.google import (
    DriveConfig,
    GoogleAuthError,
    load_drive_config,
    resolve_active_profile,
    save_drive_config,
)
from ....core.i18n import tr
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError
from ._execution_policies import GOOGLE_READ, GOOGLE_WRITE, declare_metadata_group
from ._google_payloads import GoogleFolderGetResult, GoogleFolderSetResult

_GoogleRefusal = Callable[[GoogleAuthError], CliRefusedBoundaryError]

folder_app = typer.Typer(
    name="folder",
    help=tr("cli.config.google.folder.help"),
    no_args_is_help=True,
)


def register_google_folder_commands(google_app: typer.Typer, *, google_refusal: _GoogleRefusal) -> None:
    """Register Google Drive root-folder commands."""

    @folder_app.command("set", help=tr("cli.config.google.folder.set_help"))
    @command_execution_policy(GOOGLE_WRITE)
    def google_folder_set(
        ctx: typer.Context,
        folder_id: str = typer.Argument(..., help=tr("cli.config.google.folder.folder_id_help")),
    ) -> None:
        """Persist the Drive root folder id under the active profile."""
        try:
            active = resolve_active_profile()
        except GoogleAuthError as exc:
            raise google_refusal(exc) from exc

        config = DriveConfig(root_folder_id=folder_id.strip())
        save_drive_config(active, config)
        folder_set_result = GoogleFolderSetResult(profile=active, root_folder_id=config.root_folder_id)
        _emit_envelope(
            ctx,
            command="config.google.folder.set",
            result=folder_set_result,
            lines=(
                "operation\tconfig.google.folder.set",
                f"profile\t{active}",
                f"root_folder_id\t{config.root_folder_id}",
            ),
        )

    @folder_app.command("get", help=tr("cli.config.google.folder.get_help"))
    @command_execution_policy(GOOGLE_READ)
    def google_folder_get(
        ctx: typer.Context,
    ) -> None:
        """Show the persisted Drive root folder id for the active profile."""
        try:
            active = resolve_active_profile()
        except GoogleAuthError as exc:
            raise google_refusal(exc) from exc

        config = load_drive_config(active)
        folder_get_result = GoogleFolderGetResult(
            profile=active,
            configured=config is not None,
            root_folder_id=config.root_folder_id if config is not None else None,
        )
        _emit_envelope(
            ctx,
            command="config.google.folder.get",
            result=folder_get_result,
            lines=(
                "operation\tconfig.google.folder.get",
                f"profile\t{active}",
                f"configured\t{config is not None}",
                f"root_folder_id\t{config.root_folder_id if config is not None else '<unset>'}",
            ),
        )

    google_app.add_typer(folder_app, name="folder")


declare_metadata_group(folder_app)
