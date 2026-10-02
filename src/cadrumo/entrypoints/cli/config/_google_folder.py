"""Google Drive folder commands backed by the registered worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
)
from ..common import emit_envelope
from ..runtime_profile_binding import bound_profile_client
from ._google_folder_payloads import GoogleFolderSetResult, GoogleFolderViewResult
from .runtime_google_configuration import run_google_configuration

if TYPE_CHECKING:
    import typer


def google_folder_set(ctx: typer.Context, folder_id: str) -> None:
    """Persist a Drive root folder for the invocation's authenticated profile."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleFolderSetRequest(profile_id=client.profile_id, folder_id=folder_id),
        result_type=GoogleFolderSetProjection,
    )
    profile = str(projection.profile_id)
    result = GoogleFolderSetResult(profile=profile, root_folder_id=projection.root_folder_id)
    emit_envelope(
        ctx,
        command="config.google.folder.set",
        result=result,
        lines=(
            "operation\tconfig.google.folder.set",
            f"profile\t{profile}",
            f"root_folder_id\t{projection.root_folder_id}",
        ),
    )


def google_folder_view(ctx: typer.Context) -> None:
    """Show the persisted Drive root folder for the invocation's profile."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleFolderViewRequest(profile_id=client.profile_id),
        result_type=GoogleFolderViewProjection,
    )
    profile = str(projection.profile_id)
    result = GoogleFolderViewResult(
        profile=profile,
        configured=projection.configured,
        root_folder_id=projection.root_folder_id,
    )
    emit_envelope(
        ctx,
        command="config.google.folder.view",
        result=result,
        lines=(
            "operation\tconfig.google.folder.view",
            f"profile\t{profile}",
            f"configured\t{projection.configured}",
            f"root_folder_id\t{projection.root_folder_id if projection.root_folder_id is not None else '<unset>'}",
        ),
    )


__all__ = ["google_folder_set", "google_folder_view"]
