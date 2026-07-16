"""Persisted AEAT session discovery and verification.

:func:`ensure_authenticated_aeat_session` returns
:class:`AuthenticatedAeatSessionResult` after coordinating
:class:`AuthProviderKind` selection, :class:`SessionStoreProtocol` persistence,
and :class:`PersistedAuthSession` reuse.

See Also:
    :mod:`application.auth`
        Public auth facade that re-exports this session lifecycle.
    :class:`application.auth.AuthAcquisitionLockRecord`
        Profile/provider lock record used to serialize live authentication.
    :mod:`application.live._session`
        Read-only live-entry helper that calls this module only after
        :class:`core.access_gate.AeatAccessGate` allows a live read.
    :mod:`adapters.outbound.aeat.auth`
        Concrete providers and persisted-session store implementations.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, SkipValidation, ValidationError

from ...core import STRICT_FROZEN_CONFIG, AuthProviderKind
from ...core.errors import AeatError
from ...core.logging import get_logger
from ...core.time import now, validate_utc_aware
from ..auth_credentials import ActiveCertificateCredentials
from . import select_provider
from ._acquisition_lock import (
    AuthAcquisitionLockRecord,
    AuthAcquisitionLockStatus,
    acquire_auth_acquisition_lock,
    auth_lock_ttl_seconds,
    clear_auth_acquisition_lock,
)
from ._operator_scope import (
    active_profile_storage_span,
    assert_auth_recovery_not_in_progress,
    auth_mutation_span,
)
from ._protocols import SessionStoreProtocol

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
    )
    from ...core.config import Settings
    from ..workflow import WorkflowStateRepository
    from . import AuthProvider

_logger = get_logger(__name__)


class _TargetedAuthProvider(Protocol):
    """Provider extension for Cl@ve flows that accept a requested live target."""

    async def authenticate(
        self,
        *,
        target_url: str | None = None,
    ) -> AeatSession: ...

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion: ...


class _PersistedTargetProbeProvider(_TargetedAuthProvider, Protocol):
    """Cl@ve provider extension with a direct persisted-session probe."""

    async def probe_persisted_session(
        self,
        *,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]: ...


def _workflow_state_repository() -> WorkflowStateRepository:
    """Resolve the public workflow repository without loading workflow at auth import time."""
    workflow = import_module("cadrumo.application.workflow")
    factory = cast(Callable[[], object], workflow.workflow_state_repository)
    return cast("WorkflowStateRepository", factory())

def _get_session_store() -> SessionStoreProtocol:
    """Return the sole encrypted outbound session-store implementation."""
    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")
    return cast(SessionStoreProtocol, outbound_auth.session_store)


def _invalid_assertion_diagnostic(assertion: AeatLoginAssertion) -> str:
    """Return a non-secret diagnostic suffix for a failed live assertion."""
    parts = [
        f"status={getattr(assertion, 'status_code', None)}",
        f"error={getattr(assertion, 'error_message', None)!r}",
    ]
    detail = getattr(assertion, "assertion_detail", None)
    landing_url = getattr(detail, "landing_url", None)
    if isinstance(landing_url, str) and landing_url:
        try:
            parsed = urlsplit(landing_url)
        except ValueError:
            parts.append("landing_url_parse=invalid")
        else:
            parts.append(f"landing_host={parsed.netloc!r}")
            parts.append(f"landing_path={parsed.path!r}")
    session_cookie_present = getattr(detail, "session_cookie_present", None)
    if session_cookie_present is not None:
        parts.append(f"session_cookie_present={bool(session_cookie_present)}")
    return " ".join(parts)


class StorageStatePaths(BaseModel):
    """Logical storage-state identifier for one provider's persisted AEAT session."""

    model_config = STRICT_FROZEN_CONFIG

    storage_state: Path


class CorruptAuthSessionError(AeatError):
    """Raised when persisted session metadata cannot be parsed."""


class AuthSessionUnavailableError(AeatError):
    """Raised when no verified active AEAT session can be supplied."""


class SessionDeserializationError(AuthSessionUnavailableError):
    """Raised when a persisted session field cannot be deserialized to the expected type.

    Replaces the bare :exc:`TypeError` raised by :func:`_session_metadata_datetime`
    so callers catch a typed, registry-bound error that inherits from
    :class:`AuthSessionUnavailableError`.
    """


class AuthProfileIdentityMismatchError(AeatError):
    """Raised when the active profile identity cannot own the requested auth session."""


class AuthenticatedAeatSessionResult(BaseModel):
    """Outcome of ensuring an authenticated AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    provider_kind: AuthProviderKind
    session: SkipValidation[Any]
    assertion: SkipValidation[Any]
    reused_persisted_session: bool
    acquired_lock: AuthAcquisitionLockRecord | None = None
    reset_lock: AuthAcquisitionLockStatus | None = None
    removed_sessions: tuple[Path, ...] = ()
    fresh: bool = False


class PersistedAuthSession(BaseModel):
    """Provider-neutral view of encrypted AEAT session metadata."""

    model_config = STRICT_FROZEN_CONFIG

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
    AuthProviderKind.CLAVE_PERMANENTE: "clave-permanente-storage",
}


def storage_state_paths(
    kind: AuthProviderKind | None = None,
    *,
    bucket_id: str | None = None,
) -> StorageStatePaths:
    """Return the logical storage-state identifier for ``kind``.

    Returns a :class:`StorageStatePaths` carrying the stable logical object key
    for the provider's encrypted session state.
    """
    from ...core import require_active_bucket_id
    from ...core.auth_session_keys import aeat_auth_session_storage_state_path

    resolved = kind or AuthProviderKind.CERTIFICATE
    stem = _STEM_BY_KIND[resolved]
    storage_state = aeat_auth_session_storage_state_path(bucket_id or require_active_bucket_id(), stem)
    return StorageStatePaths(storage_state=storage_state)


def load_persisted_session(settings: Settings, kind: AuthProviderKind | None = None) -> PersistedAuthSession | None:
    """Load persisted AEAT session metadata for ``kind`` or the active provider.

    Returns a :class:`PersistedAuthSession`.
    """
    if kind is None and settings.cadrumo_auth_provider is not None:
        kind = settings.cadrumo_auth_provider
    if kind is not None:
        if kind not in _STEM_BY_KIND:
            # A provider without a persisted-session stem holds no reusable
            # session, so there is nothing to load (and no stem to resolve).
            return None
        paths = storage_state_paths(kind)
        if not _get_session_store().exists(paths.storage_state):
            _logger.debug("load_persisted_session: no session metadata found for provider %s", kind.value)
            return None
        return _parse_single(paths.storage_state, kind)

    for candidate in _STEM_BY_KIND:
        paths = storage_state_paths(candidate)
        if _get_session_store().exists(paths.storage_state):
            return _parse_single(paths.storage_state, candidate)
    _logger.debug("load_persisted_session: no session metadata found for any registered provider")
    return None


def delete_persisted_session(
    settings: Settings,
    kind: AuthProviderKind | None = None,
    *,
    bucket_id: str | None = None,
) -> list[Path]:
    """Remove persisted encrypted sessions for ``kind`` or every session-bearing provider.

    A ``kind`` of ``None`` sweeps every provider that actually persists a browser
    session (the ``_STEM_BY_KIND`` set). Reserved catalogue slots are not
    :class:`AuthProviderKind` members and therefore never enter this storage
    loop; operator ``--all`` scope may name them for idempotent configuration
    cleanup without manufacturing session paths for unsupported providers.
    """
    removed: list[Path] = []
    kinds = [kind] if kind is not None else list(_STEM_BY_KIND)
    for candidate_kind in kinds:
        if candidate_kind not in _STEM_BY_KIND:
            continue
        paths = storage_state_paths(candidate_kind, bucket_id=bucket_id)
        if not _get_session_store().delete(paths.storage_state):
            continue
        _logger.debug("delete_persisted_session: removed auth session %s", paths.storage_state)
        removed.append(paths.storage_state)
    return removed


def persisted_session_exists(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    bucket_id: str | None = None,
) -> bool:
    """Return whether ``kind`` has persisted session state in ``bucket_id``."""
    del settings
    if kind not in _STEM_BY_KIND:
        return False
    return _get_session_store().exists(storage_state_paths(kind, bucket_id=bucket_id).storage_state)


async def require_verified_aeat_session(
    settings: Settings,
    *,
    kind: AuthProviderKind | None = None,
    target_url: str | None = None,
) -> AeatSession:
    """Return a verified active :class:`AeatSession` without exposing provider mechanics."""
    provider_kind = _resolve_provider_kind(settings, kind)
    expected_identity = _assert_active_profile_identity_matches_provider(settings, provider_kind)
    persisted = load_persisted_session(settings, kind)
    if persisted is None:
        raise AuthSessionUnavailableError(
            translated_message="application.auth.sessions.errors.no_session",
        )
    if persisted.is_expired(now()):
        raise AuthSessionUnavailableError(
            translated_message="application.auth.sessions.errors.session_expired",
        )
    paths = storage_state_paths(persisted.provider_kind)
    if not _get_session_store().exists(paths.storage_state):
        raise AuthSessionUnavailableError(
            translated_message="application.auth.sessions.errors.state_missing",
        )

    from ...adapters.outbound.aeat.browser import default_browser_session_factory

    provider = select_provider(
        persisted.provider_kind,
        settings=settings,
        browser_session_factory=default_browser_session_factory,
    )
    try:
        refreshed_session, assertion = await _probe_existing_session(provider, target_url=target_url)
    except AuthSessionUnavailableError:
        raise
    except Exception as exc:
        raise AuthSessionUnavailableError(
            translated_message="application.auth.sessions.errors.verify_failed",
        ) from exc
    finally:
        await _close_provider(provider)

    if not bool(getattr(assertion, "is_valid", False)):
        raise AuthSessionUnavailableError(
            translated_message="application.auth.sessions.errors.sede_rejected",
        )
    _assert_session_identity_matches_expected(refreshed_session, expected_identity)
    return refreshed_session


async def ensure_authenticated_aeat_session(
    settings: Settings,
    *,
    kind: AuthProviderKind | None = None,
    fresh: bool = False,
    reset_lock: bool = False,
    operation: str = "auth-ensure-session",
    target_url: str | None = None,
    browser_session_factory: BrowserSessionFactory | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> AuthenticatedAeatSessionResult:
    """Serialize and fail-close the central live-session writer."""
    with active_profile_storage_span(settings) as bucket_id:
        if bucket_id is None:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.no_session",
            )
        with auth_mutation_span(settings=settings, bucket_id=bucket_id):
            assert_auth_recovery_not_in_progress(_workflow_state_repository().load())
            return await _ensure_authenticated_aeat_session_locked(
                settings,
                kind=kind,
                fresh=fresh,
                reset_lock=reset_lock,
                operation=operation,
                target_url=target_url,
                browser_session_factory=browser_session_factory,
                certificate_credentials=certificate_credentials,
            )


async def _ensure_authenticated_aeat_session_locked(
    settings: Settings,
    *,
    kind: AuthProviderKind | None = None,
    fresh: bool = False,
    reset_lock: bool = False,
    operation: str = "auth-ensure-session",
    target_url: str | None = None,
    browser_session_factory: BrowserSessionFactory | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
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

    Returns an :class:`AuthenticatedAeatSessionResult` carrying the live
    session and the lock-reset status when one was requested.
    """
    provider_kind = _resolve_provider_kind(settings, kind)
    expected_identity = _assert_active_profile_identity_matches_provider(settings, provider_kind)
    reset_status = (
        clear_auth_acquisition_lock(settings, provider_kind, reason="operator-reset-before-ensure")
        if reset_lock
        else None
    )
    if not fresh:
        reused = await _try_probe_verified_session(
            settings,
            provider_kind,
            target_url=target_url,
            browser_session_factory=browser_session_factory,
            certificate_credentials=certificate_credentials,
        )
        if reused is not None:
            session, assertion = reused
            _assert_session_identity_matches_expected(session, expected_identity)
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
                target_url=target_url,
                browser_session_factory=browser_session_factory,
                certificate_credentials=certificate_credentials,
            )
            if reused is not None:
                session, assertion = reused
                _assert_session_identity_matches_expected(session, expected_identity)
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
            certificate_credentials=certificate_credentials,
        )
        try:
            session, assertion = await _authenticate_and_verify_provider(
                provider,
                target_url=target_url,
            )
        finally:
            await _close_provider(provider)
        if not bool(getattr(assertion, "is_valid", False)):
            from ...adapters.outbound.aeat.auth import AeatLoginAssertionError

            raise AeatLoginAssertionError(
                "AEAT authentication completed but live verification failed: "
                f"{_invalid_assertion_diagnostic(assertion)}",
            )
        _assert_session_identity_matches_expected(session, expected_identity)
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
        persisted = _get_session_store().load(storage_state_path)
    except (ValueError, ValidationError) as exc:
        raise CorruptAuthSessionError(
            translated_message="application.auth.sessions.errors.corrupt_session",
        ) from exc
    if persisted is None:
        return None

    try:
        raw = json.loads(json.dumps(persisted.metadata, default=str))
    except (TypeError, ValueError) as exc:
        raise CorruptAuthSessionError(
            translated_message="application.auth.sessions.errors.corrupt_session",
        ) from exc

    if not isinstance(raw, dict):
        raise CorruptAuthSessionError(
            translated_message="application.auth.sessions.errors.corrupt_session",
        )

    try:
        session = _provider_neutral_session_metadata(raw)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise CorruptAuthSessionError(
            translated_message="application.auth.sessions.errors.corrupt_session",
        ) from exc
    if session.provider_kind is not kind_hint:
        _logger.debug(
            "_parse_single: provider_kind mismatch in %s (expected %s, got %s)",
            storage_state_path,
            kind_hint.value,
            session.provider_kind.value,
        )
        raise CorruptAuthSessionError(
            translated_message="application.auth.sessions.errors.corrupt_session",
        )
    return session


def _provider_neutral_session_metadata(raw: dict[str, object]) -> PersistedAuthSession:
    """Return the common session metadata view from provider-specific metadata.

    Provider metadata is persisted by the concrete auth adapters and may
    include version, storage hash, landing URL, verification-code, or
    provider-specific diagnostics. Application callers only need the
    common reuse contract, so this function validates and narrows that
    metadata instead of treating adapter-owned fields as corruption.
    """
    return PersistedAuthSession.model_validate(
        {
            "provider_kind": AuthProviderKind(str(raw["provider_kind"])),
            "identity_nif": str(raw["identity_nif"]),
            "authenticated_at": _session_metadata_datetime(raw["authenticated_at"], field="authenticated_at"),
            "idle_deadline": _session_metadata_datetime(raw["idle_deadline"], field="idle_deadline"),
        },
    )


def _session_metadata_datetime(value: object, *, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        validate_utc_aware(parsed)
        return parsed
    raise SessionDeserializationError(
        translated_message="application.auth.errors.session_field_not_datetime",
        context={"field": field},
    )


def _resolve_provider_kind(settings: Settings, kind: AuthProviderKind | None) -> AuthProviderKind:
    if kind is not None:
        return kind
    if settings.cadrumo_auth_provider is not None:
        return settings.cadrumo_auth_provider
    return AuthProviderKind.CERTIFICATE


def _normalise_tax_identity(value: object) -> str:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return str(value or "").strip().upper()


def _assert_active_profile_identity_matches_provider(
    settings: Settings,
    provider_kind: AuthProviderKind,
) -> str | None:
    """Fail closed before live auth can bind one taxpayer's session to another profile."""
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return None
    provider_identity = _normalise_tax_identity(settings.cadrumo_clave_movil_dni_nie)
    if not provider_identity:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.clave_identity_missing",
        )

    profile_identity = _active_profile_tax_identity()
    if not profile_identity:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.profile_tax_id_missing",
        )
    if profile_identity != provider_identity:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.clave_identity_profile_mismatch",
        )
    return provider_identity


def _active_profile_tax_identity() -> str:
    from ...adapters.persistence.storage import (
        activate_master_key_provider,
        get_master_key_provider,
        has_active_bucket_session,
    )
    from ...core import resolve_active_bucket_id
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import (
        build_lifecycle_service,
        record_to_path_values,
        record_to_values,
    )

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return ""
    try:
        if has_active_bucket_session():
            record = build_lifecycle_service(bucket_id=bucket_id).read(bucket_id)
        else:
            from ...core.config import override_settings

            with override_settings(cadrumo_active_profile=bucket_id):
                service = build_lifecycle_service(bucket_id=bucket_id)
                with activate_master_key_provider(get_master_key_provider(), fallback_bucket_id=bucket_id):
                    record = service.read(bucket_id)
    except ProfileNotFoundError:
        return ""

    path_values = record_to_path_values(record)
    profile_identity = _normalise_tax_identity(path_values.get("identity.tax_id"))
    if profile_identity:
        return profile_identity
    selector_values = record_to_values(record)
    return _normalise_tax_identity(selector_values.get("tax.id"))


def _assert_session_identity_matches_expected(session: object, expected_identity: str | None) -> None:
    if not expected_identity:
        return
    session_identity = _normalise_tax_identity(getattr(session, "identity_nif", ""))
    if session_identity and session_identity != expected_identity:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.session_identity_profile_mismatch",
        )


async def _try_probe_verified_session(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    target_url: str | None,
    browser_session_factory: BrowserSessionFactory | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> tuple[AeatSession, AeatLoginAssertion] | None:
    provider = _build_provider(
        settings,
        kind,
        browser_session_factory=browser_session_factory,
        certificate_credentials=certificate_credentials,
    )
    try:
        session, assertion = await _probe_existing_session(provider, target_url=target_url)
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
    certificate_credentials: ActiveCertificateCredentials | None,
) -> AuthProvider:
    if browser_session_factory is None:
        from ...adapters.outbound.aeat.browser import default_browser_session_factory

        browser_session_factory = default_browser_session_factory
    return select_provider(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
        certificate_credentials=certificate_credentials,
    )


async def _probe_existing_session(
    provider: AuthProvider,
    *,
    target_url: str | None = None,
) -> tuple[AeatSession, AeatLoginAssertion]:
    if provider.kind is AuthProviderKind.CLAVE_MOVIL:
        return await cast(_PersistedTargetProbeProvider, provider).probe_persisted_session(
            target_url=target_url,
        )
    return await _authenticate_and_verify_provider(provider, target_url=target_url)


async def _authenticate_and_verify_provider(
    provider: AuthProvider,
    *,
    target_url: str | None,
) -> tuple[AeatSession, AeatLoginAssertion]:
    """Authenticate and verify without weakening certificate target authority."""
    if provider.kind is AuthProviderKind.CERTIFICATE:
        session = await provider.authenticate()
        assertion = await provider.verify(session)
        return session, assertion
    targeted_provider = cast(_TargetedAuthProvider, provider)
    session = await targeted_provider.authenticate(target_url=target_url)
    assertion = await targeted_provider.verify(session, target_url=target_url)
    return session, assertion


async def _close_provider(provider: AuthProvider) -> None:
    try:
        await provider.close()
    except Exception:  # BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN
        _logger.warning("provider close raised", exc_info=True)
