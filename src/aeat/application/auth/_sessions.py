"""Persisted AEAT session discovery and verification."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.outbound.aeat.auth import _session_store
from ...core.errors import AeatError
from ...core.i18n import tr
from ...core.logging import get_logger
from . import AuthProviderKind, select_provider
from ._acquisition_lock import (
    AuthAcquisitionLockRecord,
    AuthAcquisitionLockStatus,
    acquire_auth_acquisition_lock,
    auth_lock_ttl_seconds,
    clear_auth_acquisition_lock,
)

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
    )
    from ...core.config import Settings
    from . import AuthProvider

    ProviderFactory = Callable[
        [AuthProviderKind, Settings, BrowserSessionFactory | None],
        AuthProvider,
    ]

_logger = get_logger(__name__)


class StorageStatePaths(BaseModel):
    """Logical storage-state identifier for one provider's persisted AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    storage_state: Path


class CorruptAuthSessionError(AeatError):
    """Raised when persisted session metadata cannot be parsed."""


class AuthSessionUnavailableError(AeatError):
    """Raised when no verified active AEAT session can be supplied."""


class AuthenticatedAeatSessionResult(BaseModel):
    """Outcome of ensuring an authenticated AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    provider_kind: AuthProviderKind
    session: AeatSession
    assertion: AeatLoginAssertion
    reused_persisted_session: bool
    acquired_lock: AuthAcquisitionLockRecord | None = None
    reset_lock: AuthAcquisitionLockStatus | None = None
    removed_sessions: tuple[Path, ...] = ()
    fresh: bool = False


class PersistedAuthSession(BaseModel):
    """Provider-neutral view of encrypted AEAT session metadata."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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

    from ..workflow._models import require_active_bucket_id

    resolved = kind or AuthProviderKind.CERTIFICATE
    stem = _STEM_BY_KIND[resolved]
    storage_state = settings.aeat_token_dir / f"{require_active_bucket_id()}-{stem}.json"
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
            tr("application.auth.sessions.errors.no_session")
        )
    if persisted.is_expired(datetime.now(UTC)):
        raise AuthSessionUnavailableError(
            tr("application.auth.sessions.errors.session_expired")
        )
    paths = storage_state_paths(settings, persisted.provider_kind)
    if not _session_store.exists(paths.storage_state):
        raise AuthSessionUnavailableError(
            tr("application.auth.sessions.errors.state_missing")
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
            tr("application.auth.sessions.errors.verify_failed")
        ) from exc
    finally:
        await _close_provider(provider)

    if not bool(getattr(assertion, "is_valid", False)):
        raise AuthSessionUnavailableError(
            tr("application.auth.sessions.errors.sede_rejected")
        )
    return refreshed_session


async def ensure_authenticated_aeat_session(
    settings: Settings,
    *,
    kind: AuthProviderKind | None = None,
    fresh: bool = False,
    reset_lock: bool = False,
    operation: str = "auth-ensure-session",
    browser_session_factory: BrowserSessionFactory | None = None,
    provider_factory: ProviderFactory | None = None,
) -> AuthenticatedAeatSessionResult:
    """Return a verified AEAT session, authenticating only when required.

    This is the central live-auth orchestration surface. Callers should
    not hand-roll provider probing, lock handling, or session deletion.
    The sequence is:

    1. optionally reset an acquisition lock requested by the operator;
    2. probe persisted session state when not forcing fresh auth;
    3. acquire the profile/provider auth lock;
    4. probe persisted state again to avoid races;
    5. optionally delete persisted session state for ``fresh``;
    6. authenticate and verify through the selected provider.
    """

    provider_kind = _resolve_provider_kind(settings, kind)
    reset_status = (
        clear_auth_acquisition_lock(settings, provider_kind, reason="operator-reset-before-ensure")
        if reset_lock
        else None
    )
    if not fresh:
        reused = await _try_probe_verified_session(
            settings,
            provider_kind,
            browser_session_factory=browser_session_factory,
            provider_factory=provider_factory,
        )
        if reused is not None:
            session, assertion = reused
            return AuthenticatedAeatSessionResult(
                provider_kind=provider_kind,
                session=session,
                assertion=assertion,
                reused_persisted_session=True,
                reset_lock=reset_status,
            )

    removed_sessions: list[Path] = []
    with acquire_auth_acquisition_lock(
        settings,
        provider_kind,
        ttl_seconds=auth_lock_ttl_seconds(settings, provider_kind),
        operation=operation,
    ) as lock_record:
        if not fresh:
            reused = await _try_probe_verified_session(
                settings,
                provider_kind,
                browser_session_factory=browser_session_factory,
                provider_factory=provider_factory,
            )
            if reused is not None:
                session, assertion = reused
                return AuthenticatedAeatSessionResult(
                    provider_kind=provider_kind,
                    session=session,
                    assertion=assertion,
                    reused_persisted_session=True,
                    acquired_lock=lock_record,
                    reset_lock=reset_status,
                )
        if fresh:
            removed_sessions = delete_persisted_session(settings, kind=provider_kind)

        provider = _build_provider(
            settings,
            provider_kind,
            browser_session_factory=browser_session_factory,
            provider_factory=provider_factory,
        )
        try:
            session = await provider.authenticate()
            assertion = await provider.verify(session)
        finally:
            await _close_provider(provider)
        if not bool(getattr(assertion, "is_valid", False)):
            from ...adapters.outbound.aeat.auth import AeatLoginAssertionError

            raise AeatLoginAssertionError(
                "AEAT authentication completed but live verification failed: "
                f"status={getattr(assertion, 'status_code', None)} "
                f"error={getattr(assertion, 'error_message', None)!r}"
            )
        return AuthenticatedAeatSessionResult(
            provider_kind=provider_kind,
            session=session,
            assertion=assertion,
            reused_persisted_session=False,
            acquired_lock=lock_record,
            reset_lock=reset_status,
            removed_sessions=tuple(removed_sessions),
            fresh=fresh,
        )


def _parse_single(storage_state_path: Path, kind_hint: AuthProviderKind) -> PersistedAuthSession | None:
    try:
        persisted = _session_store.load(storage_state_path)
    except (ValueError, ValidationError) as exc:
        raise CorruptAuthSessionError(
            tr("application.auth.sessions.errors.corrupt_session")
        ) from exc
    if persisted is None:
        return None

    try:
        raw = json.loads(json.dumps(persisted.metadata, default=str))
    except (TypeError, ValueError) as exc:
        raise CorruptAuthSessionError(
            tr("application.auth.sessions.errors.corrupt_session")
        ) from exc

    if not isinstance(raw, dict):
        raise CorruptAuthSessionError(
            tr("application.auth.sessions.errors.corrupt_session")
        )

    try:
        session = PersistedAuthSession.model_validate(raw)
    except ValidationError as exc:
        raise CorruptAuthSessionError(
            tr("application.auth.sessions.errors.corrupt_session")
        ) from exc
    if session.provider_kind is not kind_hint:
        _logger.debug(
            "_parse_single: provider_kind mismatch in %s (expected %s, got %s)",
            storage_state_path,
            kind_hint.value,
            session.provider_kind.value,
        )
        raise CorruptAuthSessionError(
            tr("application.auth.sessions.errors.corrupt_session")
        )
    return session


def _resolve_provider_kind(settings: Settings, kind: AuthProviderKind | None) -> AuthProviderKind:
    if kind is not None:
        return kind
    if settings.aeat_auth_provider is not None:
        return AuthProviderKind(settings.aeat_auth_provider.value)
    return AuthProviderKind.CERTIFICATE


async def _try_probe_verified_session(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    browser_session_factory: BrowserSessionFactory | None,
    provider_factory: ProviderFactory | None,
) -> tuple[AeatSession, AeatLoginAssertion] | None:
    provider = _build_provider(
        settings,
        kind,
        browser_session_factory=browser_session_factory,
        provider_factory=provider_factory,
    )
    try:
        session, assertion = await _probe_existing_session(provider)
    except Exception as exc:
        _logger.debug("ensure_authenticated_aeat_session: persisted probe failed: %s", exc, exc_info=True)
        return None
    finally:
        await _close_provider(provider)
    if bool(getattr(assertion, "is_valid", False)):
        return session, assertion
    return None


def _build_provider(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    browser_session_factory: BrowserSessionFactory | None,
    provider_factory: ProviderFactory | None,
) -> AuthProvider:
    if provider_factory is not None:
        return provider_factory(kind, settings, browser_session_factory)
    if browser_session_factory is None:
        from ...adapters.outbound.aeat.browser import default_browser_session_factory

        browser_session_factory = default_browser_session_factory
    return select_provider(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
    )


async def _probe_existing_session(provider: AuthProvider) -> tuple[AeatSession, AeatLoginAssertion]:
    probe = getattr(provider, "probe_persisted_session", None)
    if probe is not None:
        return await probe()
    session = await provider.authenticate()
    assertion = await provider.verify(session)
    return session, assertion


async def _close_provider(provider: AuthProvider) -> None:
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
