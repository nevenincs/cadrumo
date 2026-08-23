"""Result schemas owned only by the Google Drive folder command family."""

from __future__ import annotations

from ....core.json_contract import OutputSchema, register_schema


@register_schema("config.google.folder.set")
class GoogleFolderSetResult(OutputSchema):
    """Persisted Drive-root selection returned by ``folder set``."""

    operation: str = "config.google.folder.set"
    profile: str
    root_folder_id: str


@register_schema("config.google.folder.get")
class GoogleFolderGetResult(OutputSchema):
    """Current optional Drive-root selection returned by ``folder get``."""

    operation: str = "config.google.folder.get"
    profile: str
    configured: bool
    root_folder_id: str | None = None


__all__ = ["GoogleFolderGetResult", "GoogleFolderSetResult"]
