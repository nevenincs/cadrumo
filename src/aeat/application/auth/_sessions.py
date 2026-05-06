"""Persisted AEAT session discovery and verification."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.outbound.aeat.auth import _session_store
from ...core.errors import AeatError
from ...core.logging import get_logger
from . import AuthProviderKind, select_provider

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import AeatSession
    from ...core.config import Settings

_logger = get_logger(__name__)


class StorageStatePaths(BaseModel):
    """Logical storage-state identifier for one provider's persisted AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    storage_state: Path


class CorruptAuthSessionError(AeatError):
    """Raised when persisted session metadata cannot be parsed."""


class AuthSessionUnavailableError(AeatError):
    """Raised when no verified active AEAT session can be supplied."""


class PersistedAuthSession(BaseModel):
    """Provider-neutral view of encrypted AEAT session metadata."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    provider_kind: AuthProviderKind = Field(
        description="Provider that produced the session metadata.",
    )
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime

    def is_expired(self, now: datetime) -> bool:
        """Return True if the idle deadline has elapsed at ``now``."""
        return now >= self.idle_deadline


_STEM_BY_KIND: dict[AuthProviderKind, str] = {
    AuthProviderKind.CERTIFICATE: "storage",
    AuthProviderKind.CLAVE_MOVIL: "clave-movil-storage",
}


def storage_state_paths(
    settings: Settings,
    kind: AuthProviderKind | None = None,
) -> StorageStatePaths:
    """Return the logical storage-state identifier for ``kind``."""

    resolved = kind or AuthProviderKind.CERTIFICATE
    stem = _STEM_BY_KIND[resolved]
    storage_state = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-{stem}.json"
    return StorageStatePaths(storage_state=storage_state)


def load_persisted_session(settings: Settings, kind: AuthProviderKind | None = None) -> PersistedAuthSession | None:
    """Load persisted AEAT session metadata for ``kind`` or the active provider."""

    if kind is None and settings.aeat_auth_provider is not None:
        kind = AuthProviderKind(settings.aeat_auth_provider.value)
    if kind is not None:
        paths = storage_state_paths(settings, kind)
        if not _session_store.exists(paths.storage_state):
            _logger.debug("load_persisted_session: no session metadata found for provider %s", kind.value)
            return None
        return _parse_single(paths.storage_state, kind)

    for candidate in AuthProviderKind:
        paths = storage_state_paths(settings, candidate)
        if _session_store.exists(paths.storage_state):
            return _parse_single(paths.storage_state, candidate)
    _logger.debug("load_persisted_session: no session metadata found for any registered provider")
    return None


def delete_persisted_session(settings: Settings, kind: AuthProviderKind | None = None) -> list[Path]:
    """Remove persisted encrypted sessions for ``kind`` or every supported provider."""

    removed: list[Path] = []
    kinds = [kind] if kind is not None else list(AuthProviderKind)
    for candidate_kind in kinds:
        paths = storage_state_paths(settings, candidate_kind)
        if not _session_store.delete(paths.storage_state):
            continue
        _logger.debug("delete_persisted_session: removed auth session %s", paths.storage_state)
        removed.append(paths.storage_state)
    return removed


async def require_verified_aeat_session(
    settings: Settings,
    *,
    kind: AuthProviderKind | None = None,
) -> AeatSession:
    """Return a verified active AEAT session without exposing provider mechanics."""

    persisted = load_persisted_session(settings, kind)
    if persisted is None:
        raise AuthSessionUnavailableError(
            "No active AEAT session; run `aeat setup auth login` before reading AEAT data"
        )
    if persisted.is_expired(datetime.now(UTC)):
        raise AuthSessionUnavailableError(
            "AEAT session is expired; run `aeat setup auth login` before reading AEAT data"
        )
    paths = storage_state_paths(settings, persisted.provider_kind)
    if not _session_store.exists(paths.storage_state):
        raise AuthSessionUnavailableError(
            "AEAT session state is missing; run `aeat setup auth login` before reading AEAT data"
        )

    from ...adapters.outbound.aeat.browser import default_browser_session_factory

    provider = select_provider(
        persisted.provider_kind,
        settings=settings,
        browser_session_factory=default_browser_session_factory,
    )
    try:
        refreshed_session, assertion = await _probe_existing_session(provider)
    except AuthSessionUnavailableError:
        raise
    except Exception as exc:
        raise AuthSessionUnavailableError(
            "AEAT session could not be verified; run `aeat setup auth login` before reading AEAT data"
        ) from exc
    finally:
        await _close_provider(provider)

    if not bool(getattr(assertion, "is_valid", False)):
        raise AuthSessionUnavailableError(
            "AEAT session is not accepted by the AEAT Sede; run `aeat setup auth login` before reading AEAT data"
        )
    return refreshed_session


def _parse_single(storage_state_path: Path, kind_hint: AuthProviderKind) -> PersistedAuthSession | None:
    try:
        persisted = _session_store.load(storage_state_path)
    except (ValueError, ValidationError) as exc:
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat setup auth login` to sign in again."
        ) from exc
    if persisted is None:
        return None

    try:
        raw = json.loads(json.dumps(persisted.metadata, default=str))
    except (TypeError, ValueError) as exc:
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat setup auth login` to sign in again."
        ) from exc

    if not isinstance(raw, dict):
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat setup auth login` to sign in again."
        )

    try:
        session = PersistedAuthSession.model_validate(raw)
    except ValidationError as exc:
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat setup auth login` to sign in again."
        ) from exc
    if session.provider_kind is not kind_hint:
        _logger.debug(
            "_parse_single: provider_kind mismatch in %s (expected %s, got %s)",
            storage_state_path,
            kind_hint.value,
            session.provider_kind.value,
        )
        raise CorruptAuthSessionError(
            "Your saved auth session is damaged and cannot be read. Run `aeat setup auth login` to sign in again."
        )
    return session


async def _probe_existing_session(provider: Any) -> tuple[AeatSession, Any]:
    probe = getattr(provider, "probe_persisted_session", None)
    if probe is not None:
        return await probe()
    session = await provider.authenticate()
    assertion = await provider.verify(session)
    return session, assertion


async def _close_provider(provider: Any) -> None:
    close = getattr(provider, "close", None)
    if close is None:
        return
    try:
        result = close()
    except Exception:
        _logger.warning("provider close raised", exc_info=True)
        return
    if asyncio.iscoroutine(result):
        try:
            await result
        except Exception:
            _logger.warning("provider async close raised", exc_info=True)
