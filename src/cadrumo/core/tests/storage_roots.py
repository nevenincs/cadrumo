"""Project the canonical storage resolver into pure target-platform conformance vectors."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePath

from ..storage_environment import StoragePlatform, anchored_storage_root, normalized_absolute


def resolve_storage_root(
    *,
    platform: StoragePlatform | None,
    environ: Mapping[str, str],
    channel: str | None = None,
    path_type: type[PurePath] | None = None,
) -> PurePath:
    """Resolve target-platform syntax through the production anchoring and normalization owners."""
    return normalized_absolute(
        anchored_storage_root(platform=platform, environ=environ, channel=channel, path_type=path_type)
    )
