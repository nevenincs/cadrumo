"""The browsers folder Cadrumo hands Playwright for its browser automation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..core.config import Settings, load_settings
from ..core.storage_environment import configured_storage_root
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location, storage_path

__all__ = ["playwright_browsers_root"]


def playwright_browsers_root(
    cache_root: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    settings: Settings | None = None,
) -> Path:
    """Return the directory Playwright keeps browser binaries in.

    Uses an explicit ``cache_root`` when supplied. Otherwise the managed cache
    is the browsers member beneath the storage root. Injectable ``env`` and
    ``settings`` allow root checks without changing ambient process state.
    """
    if cache_root is not None:
        return cache_root
    if settings is not None:
        return storage_path(StorageCategory.PLAYWRIGHT_BROWSERS, settings=settings)
    if env is None:
        return storage_path(StorageCategory.PLAYWRIGHT_BROWSERS, settings=load_settings())
    return configured_storage_root(environ=env) / storage_location(StorageCategory.PLAYWRIGHT_BROWSERS).relative_path()
