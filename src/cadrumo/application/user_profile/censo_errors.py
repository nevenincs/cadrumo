"""Narrow exceptions for the 036 censo application service.

``CensoSyncError`` is the base for censo-derived application failures
surfaced through the ``config profile`` verb tree.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class CensoSyncError(CadrumoError):
    """Base for every 036 censo application failure."""


__all__ = [
    "CensoSyncError",
]
