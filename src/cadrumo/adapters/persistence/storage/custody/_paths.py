"""Taxonomy-backed paths for one immutable profile capsule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final
from uuid import UUID

from .....core import StorageCategory, bucket_scoped_storage_path

if TYPE_CHECKING:
    from .....core.config import Settings


_PROFILE_CUSTODY_CATEGORIES: Final[frozenset[StorageCategory]] = frozenset(
    {
        StorageCategory.PROFILE_CAPSULE_CUSTODY,
        StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE,
        StorageCategory.PROFILE_CAPSULE_RECOVERY_ENVELOPE,
        StorageCategory.PROFILE_CAPSULE_DATA,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
    },
)


def profile_custody_path(
    profile_id: UUID,
    category: StorageCategory,
    *,
    settings: Settings | None = None,
) -> Path:
    """Resolve one current-format custody artifact beneath ``profile_id``."""
    if category not in _PROFILE_CUSTODY_CATEGORIES:
        raise ValueError(f"storage category {category.value!r} is not a profile-custody artifact")
    return bucket_scoped_storage_path(category, str(profile_id), settings=settings)


__all__ = ["profile_custody_path"]
