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
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, SkipValidation, ValidationError

from ...core import STRICT_FROZEN_CONFIG, AuthProviderKind
from ...core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from ...core.errors import CadrumoError
from ...core.logging import get_logger
from ...core.time import now, validate_utc_aware
from ...domain.user_profile import UserProfileStatus
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
from ._workflow_repository import workflow_state_repository as _workflow_state_repository

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
    )
    from ...core.config import Settings
    from . import AuthProvider

_logger = get_logger(__name__)


@runtime_checkable
class _TargetedAuthProvider(Protocol):
    """Provider extension for Cl@ve flows that accept a requested live target."""

    async def authenticate_for_target(
        self,
        *,
        target_url: str | None = None,
    ) -> AeatSession: ...

    async def verify_for_target(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion: ...


@runtime_checkable
class _PersistedTargetProbeProvider(_TargetedAuthProvider, Protocol):
    """Cl@ve provider extension with a direct persisted-session probe."""

    async def probe_persisted_session(
        self,
        *,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]: ...


def _get_session_store() -> SessionStoreProtocol:
    """Return the sole encrypted outbound session-store implementation."""
    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")
    session_store = outbound_auth.session_store
    if not isinstance(session_store, SessionStoreProtocol):
        raise TypeError("outbound auth session store does not implement SessionStoreProtocol")
    return session_store


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


class CorruptAuthSessionError(CadrumoError):
    """Raised when persisted session metadata cannot be parsed."""


class AuthSessionUnavailableError(CadrumoError):
    """Raised when no verified active AEAT session can be supplied."""


class SessionDeserializationError(AuthSessionUnavailableError):
    """Raised when a persisted session field cannot be deserialized to the expected type.

    Replaces the bare :exc:`TypeError` raised by :func:`_session_metadata_datetime`
    so callers catch a typed, registry-bound error that inherits from
    :class:`AuthSessionUnavailableError`.
    """


class AuthProfileIdentityMismatchError(CadrumoError):
    """Raised when the active profile identity cannot own the requested auth session."""


class ClaveCredentialsIncompleteError(CadrumoError):
    """Raised when a Cl@ve mode lacks a credential half the AEAT flow needs.

    Distinct from :class:`AuthProfileIdentityMismatchError`: nothing
    disagrees here, a credential is simply absent. The operator's recovery
    is to record it rather than to switch profile, so the refusal names
    what is missing and points at the profile it belongs on.
    """


class ClaveCredentials(BaseModel):
    """Cl@ve credential halves for one provider kind, and where each came from.

    ``dni_nie`` and ``numero_soporte`` are the effective values: the
    active profile's when it carries one, the :class:`Settings` surface's
    otherwise, so an operator who configured Cl@ve through the
    environment keeps working. The ``profile_`` fields record what the
    profile itself held, because the provider adapters read their
    credentials from :class:`Settings` - a profile-borne value only
    reaches AEAT once it has been bound onto the settings the provider
    will read.
    """

    model_config = STRICT_FROZEN_CONFIG

    provider_kind: AuthProviderKind
    dni_nie: str = ""
    numero_soporte: str = ""
    fecha_validez: str = ""
    profile_tax_id: str = ""
    profile_dni_nie: str = ""
    profile_numero_soporte: str = ""
    profile_fecha_validez: str = ""

    @property
    def contraste(self) -> str:
        """Return whichever contraste the operator's document carries.

        Cl@ve asks a NIE holder for the numero de soporte and a DNI
        holder for the validity date, so exactly one of the two is
        expected to be present and either satisfies the non-QR route.
        """
        return self.numero_soporte or self.fecha_validez


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
    settings, expected_identity = _prepare_clave_auth(settings, provider_kind)
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
    async with _provider_lifecycle(provider):
        try:
            refreshed_session, assertion = await _probe_existing_session(provider, target_url=target_url)
        except AuthSessionUnavailableError:
            raise
        except Exception as exc:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.verify_failed",
            ) from exc

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
    settings, expected_identity = _prepare_clave_auth(settings, provider_kind)
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
        async with _provider_lifecycle(provider):
            session, assertion = await _authenticate_and_verify_provider(
                provider,
                target_url=target_url,
            )
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


def _normalise_credential(value: object) -> str:
    """Strip a credential without case-folding it.

    A DNI/NIE is canonically upper-case, but a numero de soporte is
    transcribed from the document exactly as printed, so only surrounding
    whitespace is removed here.
    """
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return str(value or "").strip()


def _prepare_clave_auth(
    settings: Settings,
    provider_kind: AuthProviderKind,
) -> tuple[Settings, str | None]:
    """Bind profile-borne Cl@ve credentials and refuse an incomplete mode.

    Returns the settings the provider should read - the caller's, with any
    profile-borne credential bound onto it - and the identity a resulting
    session must carry, or ``None`` when the provider kind carries no
    Cl@ve identity to bind.

    The refusal happens here, at the entry to every live session, so an
    operator who has not finished recording their Cl@ve credentials is
    told what is absent before a browser opens rather than part-way
    through an AEAT form.

    The expected identity is returned for EVERY provider, not only the
    Cl@ve ones. Each provider binds a comparable identity at session
    bind - the certificate provider parses a normalised NIF/NIE out of
    the certificate subject and refuses the session outright without one
    - so there is no provider for which the profile comparison is
    meaningless, and a provider that returned no expectation would leave
    the session check silently no-opping.
    """
    facts = _active_profile_auth_facts()
    credentials = _resolve_clave_credentials(settings, provider_kind, facts=facts)
    if credentials is None:
        _assert_profile_identity_available_for_deferred_check(facts)
        return settings, facts.tax_id or None
    _require_clave_credentials(settings, credentials)
    expected_identity = _assert_active_profile_identity_matches_provider(credentials)
    return _bind_clave_credentials_to_settings(settings, credentials), expected_identity


def _resolve_clave_credentials(
    settings: Settings,
    provider_kind: AuthProviderKind,
    *,
    facts: ClaveAuthFacts | None = None,
) -> ClaveCredentials | None:
    """Resolve the Cl@ve halves for ``provider_kind`` from the active profile.

    Reads the profile record through the lifecycle service when the
    caller does not already hold its facts; that read needs an unlocked
    bucket session. A readiness probe that already holds the profile's
    values should call :func:`resolve_clave_credentials` directly rather
    than pay for a second read.
    """
    if provider_kind is AuthProviderKind.CERTIFICATE:
        return None
    return resolve_clave_credentials(
        provider_kind,
        settings=settings,
        facts=facts if facts is not None else _active_profile_auth_facts(),
    )


def resolve_clave_credentials(
    provider_kind: AuthProviderKind,
    *,
    settings: Settings,
    facts: ClaveAuthFacts,
) -> ClaveCredentials | None:
    """Resolve the Cl@ve halves for ``provider_kind``, profile first.

    The single home for the profile-beats-settings precedence. Both the
    live session entry and the operator readiness surfaces resolve
    through here, so a status surface cannot report a credential as
    unconfigured that the session entry would happily authenticate with.

    Returns ``None`` for the certificate provider, which authenticates
    with an installed certificate and needs neither Cl@ve field.
    """
    if provider_kind is AuthProviderKind.CERTIFICATE:
        return None
    if provider_kind is AuthProviderKind.CLAVE_PERMANENTE:
        settings_dni_nie = _normalise_tax_identity(settings.cadrumo_clave_permanente_dni_nie)
        settings_numero_soporte = ""
        settings_fecha_validez = ""
    else:
        settings_dni_nie = _normalise_tax_identity(settings.cadrumo_clave_movil_dni_nie)
        settings_numero_soporte = _normalise_credential(settings.cadrumo_clave_movil_nie_soporte)
        settings_fecha_validez = _normalise_credential(settings.cadrumo_clave_movil_dni_fecha)
    return ClaveCredentials(
        provider_kind=provider_kind,
        dni_nie=facts.dni_nie or settings_dni_nie,
        numero_soporte=facts.numero_soporte or settings_numero_soporte,
        fecha_validez=facts.fecha_validez or settings_fecha_validez,
        profile_tax_id=facts.tax_id,
        profile_dni_nie=facts.dni_nie,
        profile_numero_soporte=facts.numero_soporte,
        profile_fecha_validez=facts.fecha_validez,
    )


def _require_clave_credentials(settings: Settings, credentials: ClaveCredentials) -> None:
    """Refuse a Cl@ve mode whose flow lacks a credential it needs.

    Every Cl@ve mode needs the DNI/NIE that identifies the person. The
    contraste - the numero de soporte for a NIE, the validity date for a
    DNI - is read only by the non-QR fallback form, so it is required
    exactly when that route is selected; the QR route asks for neither
    and must not be refused for their absence.
    """
    if not credentials.dni_nie:
        raise ClaveCredentialsIncompleteError(
            translated_message="application.auth.sessions.errors.clave_identity_missing",
            context={"provider": credentials.provider_kind.value},
        )
    if credentials.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return
    if not settings.cadrumo_clave_prefer_non_qr:
        return
    if not credentials.contraste:
        raise ClaveCredentialsIncompleteError(
            translated_message="application.auth.sessions.errors.clave_contraste_missing",
            context={"provider": credentials.provider_kind.value},
        )


def _assert_profile_identity_available_for_deferred_check(facts: ClaveAuthFacts) -> None:
    """Refuse a provider whose only identity check is deferred when there is nothing to defer to.

    A provider with no operator-configured credential - the certificate
    provider - skips the comparison above, and its identity is instead
    compared at session bind against the profile's fiscal id. That
    deferral is sound only while the profile HAS a fiscal id. Cleared, the
    expectation is empty, the session comparison returns without
    comparing, and neither guard refuses: one absent field disarms both.

    A profile promoted to ACTIVE recorded a fiscal id to get there, so a
    blank one is a deliberate later clear and is refused. A profile still
    in setup may never have recorded one yet and legitimately needs a
    session to finish setting up, so it authenticates - the read it
    performs is what must refuse, and that guard belongs to the read.

    No status at all means no profile record was read, which is a
    different condition with its own refusals upstream; answering it here
    would tell an operator with no profile to restore a field on it.
    """
    if facts.tax_id:
        return
    if facts.profile_status in (None, UserProfileStatus.SETUP_INCOMPLETE):
        return
    raise AuthProfileIdentityMismatchError(
        translated_message="application.auth.sessions.errors.profile_identity_cleared",
    )


def _assert_active_profile_identity_matches_provider(
    credentials: ClaveCredentials | None,
) -> str | None:
    """Fail closed before live auth can bind one taxpayer's session to another profile.

    Applies to every Cl@ve mode. It once returned early for anything but
    Cl@ve Movil, so two of the three providers were promised a
    fail-closed check they never received: the configured credential was
    never compared to the profile, and because no expectation was
    returned the session check downstream had nothing to compare either
    and silently passed.

    The certificate provider has no operator-configured credential to
    compare here - its identity exists only once the certificate is
    read at session bind - so it is checked there rather than exempted,
    and the caller supplies the profile identity as the expectation.
    """
    if credentials is None:
        return None
    if not credentials.profile_tax_id:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.profile_tax_id_missing",
        )
    if credentials.profile_tax_id != credentials.dni_nie:
        raise AuthProfileIdentityMismatchError(
            translated_message="application.auth.sessions.errors.clave_identity_profile_mismatch",
        )
    return credentials.dni_nie


def _bind_clave_credentials_to_settings(
    settings: Settings,
    credentials: ClaveCredentials,
) -> Settings:
    """Return settings carrying the profile's Cl@ve credentials.

    The outbound providers read their credentials from :class:`Settings`,
    so a value the profile holds is inert until it is bound here. When the
    profile carries nothing the caller's settings are returned unchanged,
    which keeps the environment-configured path byte-identical.
    """
    overrides: dict[str, object] = {}
    if credentials.profile_dni_nie:
        field = (
            "cadrumo_clave_permanente_dni_nie"
            if credentials.provider_kind is AuthProviderKind.CLAVE_PERMANENTE
            else "cadrumo_clave_movil_dni_nie"
        )
        overrides[field] = SecretStr(credentials.profile_dni_nie)
    if credentials.provider_kind is AuthProviderKind.CLAVE_MOVIL:
        if credentials.profile_numero_soporte:
            overrides["cadrumo_clave_movil_nie_soporte"] = SecretStr(credentials.profile_numero_soporte)
        if credentials.profile_fecha_validez:
            # The DNI contraste setting is a plain ``str`` the page flow types
            # verbatim into the AEAT form, so it is bound unwrapped.
            overrides["cadrumo_clave_movil_dni_fecha"] = credentials.profile_fecha_validez
    if not overrides:
        return settings

    from ...core.config import Settings as SettingsModel

    merged = settings.model_dump()
    merged.update(overrides)
    # ``model_copy(update=)`` skips validators in Pydantic v2, so the merged
    # mapping is revalidated. Only credential fields are overridden here, so
    # none of the derived route/storage defaults that ``override_settings``
    # has to unset can be disturbed.
    bound = SettingsModel.model_validate(merged)
    object.__setattr__(bound, "__pydantic_fields_set__", settings.model_fields_set | set(overrides))
    return bound


class ClaveAuthFacts(BaseModel):
    """Authentication facts read from the active profile record."""

    model_config = STRICT_FROZEN_CONFIG

    tax_id: str = ""
    dni_nie: str = ""
    numero_soporte: str = ""
    fecha_validez: str = ""
    profile_status: UserProfileStatus | None = None


def clave_auth_facts_from_profile_values(
    values: Mapping[str, str],
    *,
    profile_status: UserProfileStatus | None = None,
) -> ClaveAuthFacts:
    """Read the auth facts out of a profile's schema-path value mapping.

    The projection a readiness surface already holds is enough to resolve
    a credential, so this lets those surfaces reuse the resolver without
    opening the profile record a second time. ``identity.tax_id`` is read
    here only in its canonical path form; the lifecycle reader applies
    the selector fallback before calling this.

    ``profile_status`` distinguishes a profile that has NOT YET recorded
    its fiscal identity from one whose identity was recorded and later
    cleared. Only the record carries that, so a caller holding just a
    value mapping leaves it unset and is treated as the stricter case.
    """
    return ClaveAuthFacts(
        tax_id=_normalise_tax_identity(values.get("identity.tax_id")),
        dni_nie=_normalise_tax_identity(values.get("auth.dni_nie")),
        numero_soporte=_normalise_credential(values.get("auth.numero_soporte")),
        fecha_validez=_normalise_credential(values.get("auth.fecha_validez")),
        profile_status=profile_status,
    )


def _active_profile_auth_facts() -> ClaveAuthFacts:
    """Read the active profile's identity and Cl@ve credentials in one pass.

    Returns empty facts when no profile is active or the record cannot be
    found, leaving the settings surface as the sole source. Reading the
    record requires an unlocked bucket session, so the locked case
    activates the master key provider for the read.
    """
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
        return ClaveAuthFacts()
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
        return ClaveAuthFacts()

    path_values = dict(record_to_path_values(record))
    if not _normalise_tax_identity(path_values.get("identity.tax_id")):
        # A record whose tax id reached the projection only through its
        # model selector still owns that identity; fold it onto the
        # canonical path so the shared reader sees one shape.
        selector_values = record_to_values(record)
        path_values["identity.tax_id"] = str(selector_values.get("tax.id") or "")
    return clave_auth_facts_from_profile_values(path_values, profile_status=record.status)


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
    async with _provider_lifecycle(provider):
        try:
            session, assertion = await _probe_existing_session(provider, target_url=target_url)
        except Exception as exc:
            _logger.debug("ensure_authenticated_aeat_session: persisted probe failed: %s", exc, exc_info=True)
            return None
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
        if not isinstance(provider, _PersistedTargetProbeProvider):
            raise TypeError("clave movil provider lacks persisted-session probing")
        return await provider.probe_persisted_session(
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
    if not isinstance(provider, _TargetedAuthProvider):
        raise TypeError("non-certificate auth provider lacks target-aware authentication")
    targeted_provider = provider
    session = await targeted_provider.authenticate_for_target(target_url=target_url)
    assertion = await targeted_provider.verify_for_target(session, target_url=target_url)
    return session, assertion


@asynccontextmanager
async def _provider_lifecycle(provider: AuthProvider) -> AsyncGenerator[None]:
    """Close ``provider`` without hiding a primary auth failure."""
    try:
        yield
    finally:
        try:
            await close_async_resources(
                provider,
                task_name="cadrumo-auth-provider-close",
                close_attempts=2,
            )
        except AsyncResourceCleanupError as cleanup_error:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.provider_close_failed",
            ) from cleanup_error
