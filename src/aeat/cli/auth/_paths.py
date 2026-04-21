"""Storage-state path helpers for the ``aeat auth`` CLI.

``AeatAuthenticator`` today persists a single
``{aeat_token_dir}/{profile}-storage.json`` +
``{aeat_token_dir}/{profile}-storage.meta.json`` pair per workstation,
regardless of provider kind. Once per-provider storage segmentation
lands (EPIC #279 follow-up), this module becomes the single place that
has to grow a kind-parameterised path scheme.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ...auth import AuthProviderKind
    from ...config import Settings


class StorageStatePaths(BaseModel):
    """On-disk locations for one provider's persisted session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    storage_state: Path
    metadata: Path


def storage_state_paths(settings: Settings, _kind: AuthProviderKind | None = None) -> StorageStatePaths:
    """Resolve the storage-state + metadata path pair for a provider.

    ``_kind`` is accepted for future-compatibility and ignored today;
    all kinds share the authenticator's single-session file layout.
    """
    storage_state = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"
    metadata = storage_state.with_suffix(".meta.json")
    return StorageStatePaths(storage_state=storage_state, metadata=metadata)
