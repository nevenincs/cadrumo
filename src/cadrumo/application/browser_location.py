"""The browsers folder Cadrumo hands Playwright for its browser automation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from ..core.config import Settings, load_settings
from ..core.storage_environment import configured_storage_root, resolve_storage_path
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location

__all__ = ["playwright_browsers_root"]


def playwright_browsers_root(
    cache_root: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    settings: Settings | None = None,
) -> Path:
    """Return the directory Playwright keeps browser binaries in.

    Uses an explicit ``cache_root`` when supplied. Otherwise the Cadrumo
    ``CADRUMO_PLAYWRIGHT_BROWSERS_DIR`` setting controls the managed cache,
    rooted under the configured storage root by default. Injectable ``env`` and
    ``settings`` allow precedence checks without changing ambient process state.
    """
    if cache_root is not None:
        return cache_root
    environment = os.environ if env is None else env
    if settings is not None and "cadrumo_playwright_browsers_dir" in settings.model_fields_set:
        return settings.cadrumo_playwright_browsers_dir
    storage_root = configured_storage_root(environ=environment)
    cadrumo_override = environment.get("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "").strip()
    if cadrumo_override:
        return resolve_storage_path(cadrumo_override, root=storage_root)
    if settings is not None:
        return settings.cadrumo_playwright_browsers_dir
    if env is None:
        return load_settings().cadrumo_playwright_browsers_dir
    default = storage_location(StorageCategory.PLAYWRIGHT_BROWSERS).relative_path()
    return resolve_storage_path(default, root=storage_root)
