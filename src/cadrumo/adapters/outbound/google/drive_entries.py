"""Shared ownership marker for app-managed Google Drive entries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

OWNERSHIP_KEY: Final[str] = "cadrumo_vault_app"
OWNERSHIP_VALUE: Final[Literal["cadrumo"]] = "cadrumo"


def is_app_owned(app_properties: Mapping[str, Any]) -> bool:
    """Return whether ``appProperties`` carries this application's ownership marker."""
    marker = app_properties.get(OWNERSHIP_KEY)
    return isinstance(marker, str) and marker == OWNERSHIP_VALUE


__all__ = ["OWNERSHIP_KEY", "OWNERSHIP_VALUE", "is_app_owned"]
