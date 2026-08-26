"""Result schemas owned only by the Google Drive folder command family."""

from __future__ import annotations

from ....core.json_contract import OutputSchema


class GoogleFolderSetResult(OutputSchema):
    """Persisted Drive-root selection returned by ``folder set``."""

    operation: str = "config.google.folder.set"
    profile: str
    root_folder_id: str


class GoogleFolderViewResult(OutputSchema):
    """Current optional Drive-root selection returned by ``folder view``."""

    operation: str = "config.google.folder.view"
    profile: str
    configured: bool
    root_folder_id: str | None = None


__all__ = ["GoogleFolderSetResult", "GoogleFolderViewResult"]
