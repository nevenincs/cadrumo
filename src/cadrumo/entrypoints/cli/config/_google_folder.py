"""Google Drive folder commands backed by the registered worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleFolderOrganizeRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
)
from ..common import emit_envelope
from ..runtime_profile_binding import bound_profile_client
from ._google_folder_payloads import GoogleFolderOrganizeResult, GoogleFolderViewResult
from .runtime_google_configuration import run_google_configuration

if TYPE_CHECKING:
    import typer


def google_folder_view(ctx: typer.Context) -> None:
    """Show the Drive root folder created for the invocation's profile."""
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


def google_folder_organize(ctx: typer.Context) -> None:
    """Place the exact recorded profile root inside the Cadrumo folder."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleFolderOrganizeRequest(profile_id=client.profile_id),
        result_type=GoogleFolderViewProjection,
    )
    # The operation succeeds only after the exact root's placement is checked.
    if projection.root_folder_id is None:
        from .google_configuration_refusals import google_invalid_frame

        google_invalid_frame(operation_id="config.google.folder.organize")
    result = GoogleFolderOrganizeResult(
        profile=str(projection.profile_id),
        configured=projection.configured,
        root_folder_id=projection.root_folder_id,
    )
    emit_envelope(
        ctx,
        command="config.google.folder.organize",
        result=result,
        lines=(
            "operation\tconfig.google.folder.organize",
            f"profile\t{projection.profile_id}",
            f"root_folder_id\t{projection.root_folder_id}",
        ),
    )


__all__ = ["google_folder_organize", "google_folder_view"]
