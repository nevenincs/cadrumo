"""Locate the historical handover leaf excluded from operation journal enrollment."""

from __future__ import annotations

from pathlib import Path

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location

_HANDOVER_JOURNAL_FILENAME = "profile-login-handover.v2.json"


def handover_journal_path(storage_root: Path) -> Path:
    """Retain the known historical journal location without accepting new handovers."""
    return (
        storage_root / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path() / _HANDOVER_JOURNAL_FILENAME
    )


__all__ = ["handover_journal_path"]
