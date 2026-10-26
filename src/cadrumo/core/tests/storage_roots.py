"""Project the canonical storage resolver into pure target-platform conformance vectors."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePath

from ..storage_environment import StorageMode, StoragePlatform, _anchored_storage_root, _normalized_absolute


def resolve_storage_root(
    *,
    platform: StoragePlatform | None,
    mode: StorageMode,
    environ: Mapping[str, str],
    checkout: PurePath | str | None = None,
    channel: str | None = None,
    path_type: type[PurePath] | None = None,
) -> PurePath:
    """Resolve target-platform syntax through the production anchoring and normalization owners."""
    return _normalized_absolute(
        _anchored_storage_root(
            platform=platform, mode=mode, environ=environ, checkout=checkout, channel=channel, path_type=path_type
        )
    )
