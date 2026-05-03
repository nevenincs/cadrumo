"""Storage-state path helpers for the ``aeat auth`` CLI.

Each available auth provider owns its own sidecar file so two providers
do not clobber each other's storage-state.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ....application.auth import AuthProviderKind

if TYPE_CHECKING:
    from ....core.config import Settings


class StorageStatePaths(BaseModel):
    """On-disk locations for one provider's persisted session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    storage_state: Path
    metadata: Path


_STEM_BY_KIND: dict[AuthProviderKind, str] = {
    AuthProviderKind.CERTIFICATE: "storage",
    AuthProviderKind.CLAVE_MOVIL: "clave-movil-storage",
}


def storage_state_paths(
    settings: Settings,
    kind: AuthProviderKind | None = None,
) -> StorageStatePaths:
    """Return the storage-state + metadata path pair for ``kind``.

    When ``kind`` is omitted the certificate layout is returned.
    """
    resolved = kind or AuthProviderKind.CERTIFICATE
    stem = _STEM_BY_KIND[resolved]
    storage_state = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-{stem}.json"
    metadata = storage_state.with_suffix(".meta.json")
    return StorageStatePaths(storage_state=storage_state, metadata=metadata)
