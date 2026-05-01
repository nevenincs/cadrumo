"""Storage-state path helpers for the ``aeat auth`` CLI.

Each auth provider owns its own sidecar file so two providers don't
clobber each other's storage-state. The certificate provider keeps
the original layout (``{profile}-storage.json`` + ``.meta.json``) for
backward compatibility with existing on-disk files and the live
tests that already write there. Cl@ve Móvil writes to
``{profile}-clave-movil-storage.json`` + ``.meta.json``. Future
providers plug in by adding a branch here only.

``storage_state_paths(settings)`` — with no ``kind`` — returns the
certificate path, which preserves the v1 behaviour for callers that
predate multi-provider storage.
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
    AuthProviderKind.CLAVE_PERMANENTE: "clave-permanente-storage",
    AuthProviderKind.CLAVE_PIN: "clave-pin-storage",
}


def storage_state_paths(
    settings: Settings,
    kind: AuthProviderKind | None = None,
) -> StorageStatePaths:
    """Return the storage-state + metadata path pair for ``kind``.

    When ``kind`` is omitted the certificate layout is returned — the
    legacy default that predates multi-provider storage.
    """
    resolved = kind or AuthProviderKind.CERTIFICATE
    stem = _STEM_BY_KIND.get(resolved, f"{resolved.value}-storage")
    storage_state = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-{stem}.json"
    metadata = storage_state.with_suffix(".meta.json")
    return StorageStatePaths(storage_state=storage_state, metadata=metadata)
