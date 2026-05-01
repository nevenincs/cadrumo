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

from ....application.auth import AuthProviderKind
from ....core.errors import AeatError
from ._paths import storage_state_paths

if TYPE_CHECKING:
    from ....core.config import Settings


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
        description=(
            "Provider that produced the session. Required — callers must "
            "supply it explicitly (via the path-derived `kind_hint` in "
            "`_parse_single`) so a sidecar missing the key is treated as "
            "corrupt rather than silently attributed to the certificate "
            "provider."
        ),
    )
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime

    def is_expired(self, now: datetime) -> bool:
        """Return True if the idle deadline has elapsed at ``now``."""
        return now >= self.idle_deadline


def _parse_single(metadata_path: Path, kind_hint: AuthProviderKind) -> PersistedAuthSession:
    """Parse ``metadata_path`` into a :class:`PersistedAuthSession`.

    ``kind_hint`` is the provider kind implied by the path location
    (cert sidecar vs Cl@ve sidecar) and is used as the provider_kind
    fallback when the sidecar schema does not carry an explicit field.
    """
    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # Kent does not need the forensic filesystem path — it only helps
        # a developer. The path remains on the __cause__ chain for
        # debug tooling.
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat auth login` to sign in again."
        ) from exc

    if not isinstance(raw, dict):
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat auth login` to sign in again."
        )

    payload = dict(raw)
    # Cert sidecar writes `certificate_nif`; provider-agnostic loaders
    # expect `identity_nif`. Shim both keys so the CLI works against
    # every provider sidecar we know about today.
    if "identity_nif" not in payload and "certificate_nif" in payload:
        payload["identity_nif"] = payload["certificate_nif"]
    payload.setdefault("provider_kind", kind_hint.value)

    try:
        return PersistedAuthSession.model_validate(payload)
    except ValidationError as exc:
        # Keep the original Pydantic error on the __cause__ chain for
        # debug tooling, but do not embed its multi-line field dump or
        # the internal filesystem path in the Kent-facing message.
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat auth login` to sign in again."
        ) from exc


def load(settings: Settings, kind: AuthProviderKind | None = None) -> PersistedAuthSession | None:
    """Load the persisted session metadata for ``kind`` (or any if omitted).

    When ``kind`` is given, the lookup targets that provider's sidecar
    only. When ``kind`` is ``None`` the loader walks every known
    provider kind and returns the first session it finds, preferring
    the certificate layout for backward compatibility with older
    on-disk files.
    """
    if kind is not None:
        paths = storage_state_paths(settings, kind)
        if not paths.metadata.exists():
            return None
        return _parse_single(paths.metadata, kind)

    for candidate in (
        AuthProviderKind.CERTIFICATE,
        AuthProviderKind.CLAVE_MOVIL,
        AuthProviderKind.CLAVE_PERMANENTE,
        AuthProviderKind.CLAVE_PIN,
    ):
        paths = storage_state_paths(settings, candidate)
        if paths.metadata.exists():
            return _parse_single(paths.metadata, candidate)
    return None


def delete(settings: Settings, kind: AuthProviderKind | None = None) -> list[Path]:
    """Remove storage-state + metadata files for ``kind`` (or all when omitted).

    Returns the paths that were actually deleted. Missing files are a
    silent no-op.
    """
    removed: list[Path] = []
    kinds = (
        [kind]
        if kind is not None
        else [
            AuthProviderKind.CERTIFICATE,
            AuthProviderKind.CLAVE_MOVIL,
            AuthProviderKind.CLAVE_PERMANENTE,
            AuthProviderKind.CLAVE_PIN,
        ]
    )
    for candidate_kind in kinds:
        paths = storage_state_paths(settings, candidate_kind)
        for candidate_path in (paths.storage_state, paths.metadata):
            # `unlink()` directly rather than `exists()`-then-`unlink()` to
            # sidestep the TOCTOU window where another process removes the
            # file between the two calls. OSError is swallowed so a
            # permissions glitch on a single file does not abort the whole
            # logout sweep; callers rely on the returned list, not the
            # absolute completeness of the cleanup.
            try:
                candidate_path.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                continue
            removed.append(candidate_path)
    return removed
