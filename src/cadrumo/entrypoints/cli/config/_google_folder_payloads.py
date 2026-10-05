"""Result schemas owned only by the Google Drive folder command family.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

from ....core.json_contract import OutputSchema


class GoogleFolderViewResult(OutputSchema):
    """The Drive root folder created for the profile, as returned by ``folder view``."""

    operation: str = "config.google.folder.view"
    profile: str
    configured: bool
    root_folder_id: str | None = None


__all__ = ["GoogleFolderViewResult"]
