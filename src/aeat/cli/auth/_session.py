"""Persisted-session helpers for the ``aeat auth`` CLI.

``AeatAuthenticator`` writes a JSON metadata sidecar next to each
storage_state file. This module reads that sidecar for the ``status``
and ``logout`` subcommands; neither touches the authenticator's
cryptographic material. Corrupt sidecars fail closed with an
actionable error asking the operator to re-run ``aeat auth login``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...auth import AuthProviderKind
from ...errors import AeatError
from ._paths import storage_state_paths

if TYPE_CHECKING:
    from ...config import Settings


class CorruptAuthSessionError(AeatError):
    """Raised when the persisted session metadata cannot be parsed."""


class PersistedAuthSession(BaseModel):
    """Authoritative view of the on-disk session sidecar for CLI use.

    Only the provider-agnostic fields are modelled here; the CLI does
    not need handshake payloads or certificate thumbprints for the
    status surface.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    provider_kind: AuthProviderKind = Field(
        default=AuthProviderKind.CERTIFICATE,
        description="Provider that produced the session.",
    )
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime

    def is_expired(self, now: datetime) -> bool:
        """Return True if the idle deadline has elapsed at ``now``."""
        return now >= self.idle_deadline


def load(settings: Settings, kind: AuthProviderKind | None = None) -> PersistedAuthSession | None:
    """Load the persisted session metadata for ``kind`` (or the only slot today)."""
    paths = storage_state_paths(settings, kind)
    metadata_path = paths.metadata
    if not metadata_path.exists():
        return None

    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorruptAuthSessionError(
            f"auth session metadata at {metadata_path} is not valid JSON: {exc}; "
            "run `aeat auth login` to reauthenticate"
        ) from exc

    if not isinstance(raw, dict):
        raise CorruptAuthSessionError(
            f"auth session metadata at {metadata_path} must be a JSON object; run `aeat auth login` to reauthenticate"
        )

    # The authenticator writes `certificate_nif` today; map to the
    # provider-agnostic `identity_nif` expected by ``PersistedAuthSession``.
    payload = dict(raw)
    if "identity_nif" not in payload and "certificate_nif" in payload:
        payload["identity_nif"] = payload["certificate_nif"]

    # The authenticator's current sidecar has no explicit `provider_kind`
    # key; certificate is the only provider that writes metadata today,
    # so default there. Future providers will add the field.
    payload.setdefault("provider_kind", AuthProviderKind.CERTIFICATE.value)

    try:
        return PersistedAuthSession.model_validate(payload)
    except ValidationError as exc:
        raise CorruptAuthSessionError(
            f"auth session metadata at {metadata_path} failed validation: {exc}; "
            "run `aeat auth login` to reauthenticate"
        ) from exc


def delete(settings: Settings, kind: AuthProviderKind | None = None) -> list[Path]:
    """Remove the storage-state and metadata files for ``kind``.

    Returns the paths that were actually deleted. Missing files are a
    silent no-op.
    """
    paths = storage_state_paths(settings, kind)
    removed: list[Path] = []
    for candidate in (paths.storage_state, paths.metadata):
        if candidate.exists():
            candidate.unlink()
            removed.append(candidate)
    return removed
