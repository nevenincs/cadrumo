"""Operator-facing auth application services for the config CLI.

Auth configuration and login actions emit bucket events through
:class:`BucketEventHistoryRepository` so every provider switch and
session renewal is reflected in the audit trail.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import Settings, load_settings, unwrap_optional_secret
from ...core.i18n import tr
from ...core.time import now
from . import AuthProviderKind
from ._acquisition_lock import AuthAcquisitionLockState, clear_auth_acquisition_lock
from ._actions import update_auth
from ._catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from ._models import AuthState
from ._operator_probes import (
    _live_auth_identity_kind,
    _live_auth_identity_state,
    _live_auth_mode,
    _probe_configured_provider,
    _probe_local_session,
)
from ._operator_results import (
    AuthClearResult,
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    AuthConfigureResult,
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    AuthLoginResult,
    AuthProviderReservedError,
    AuthProvidersReport,
    AuthStatusResult,
    AuthTestResult,
    LiveAuthPreflightReport,
)
from ._operator_scope import (
    active_profile_storage_span as _active_profile_storage_span,
)
from ._operator_scope import (
    auth_operator_settings_scope as _auth_operator_settings_scope,
)
from ._sessions import (
    delete_persisted_session,
    ensure_authenticated_aeat_session,
)

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from ..workflow._models import WorkflowState
    from ..workflow._persistence import WorkflowStateRepository


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return the :class:`AuthProvidersReport` enumerating implemented and reserved auth provider slots."""
    return AuthProvidersReport(providers=list_auth_providers())


def configure_operator_auth(provider: str, *, certificate_path: Path | None = None) -> AuthConfigureResult:
    """Configure the active auth provider in workflow state.

    Persists the workflow-state update and a typed
    ``AUTH_PROVIDER_CONFIGURED`` event into the bucket-event-history
    catalogue in a single SQL transaction (via
    :meth:`SecureObjectRepository.save_many`), so a crash between the
    two writes cannot leave the state mutated without the catalogue
    event landing. The certificate path is recorded as a payload value
    when supplied because it is a filesystem reference, not credential
    material; certificate passwords, private keys, and session tokens
    never enter the payload.

    Args:
        provider: The auth provider identifier to configure (e.g.
            ``"certificate"``). Must be an implemented provider id.
        certificate_path: Optional filesystem path to the operator's
            certificate file. Recorded in the event payload when supplied.

    Returns:
        An :class:`AuthConfigureResult` carrying the updated workflow state.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet. The operator must run ``aeat config profile create NAME`` first.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ...core import resolve_active_bucket_id
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ..workflow._persistence import workflow_state_repository
    from ..workflow._profile_health import assess_active_profile_health

    listing = _implemented_provider(provider)

    if resolve_active_bucket_id() is None:
        raise AuthConfigureNoActiveBucketError(
            translated_message="application.auth.operator.errors.no_active_bucket",
        )
    state_repo = workflow_state_repository()
    current_state = state_repo.load()
    profile_health = assess_active_profile_health(current_state)
    active_bucket_id = profile_health.active_profile
    if active_bucket_id is None:
        raise AuthConfigureNoActiveBucketError(
            translated_message="application.auth.operator.errors.no_active_bucket",
        )
    if profile_health.status == "dangling_pointer":
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.dangling_active_profile",
            context={"active_profile": active_bucket_id},
        )
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.unreadable_active_profile",
            context={
                "active_profile": active_bucket_id,
                "status": profile_health.status,
                "next_action": profile_health.next_action,
            },
        )

    next_state = _append_bucket_event(
        update_auth(
            current_state,
            provider=listing.id,
            certificate_path=str(certificate_path) if certificate_path is not None else None,
        ),
        action="auth.provider.configured",
        object_id=listing.id,
    )
    active_bucket_id = next_state.active_profile_bucket_id()
    assert active_bucket_id is not None  # invariant: update_auth preserves the active profile

    occurred_at = now()
    payload: dict[str, str] = {"provider_id": listing.id}
    if certificate_path is not None:
        payload["certificate_path"] = str(certificate_path)
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=active_bucket_id,
        event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=listing.id,
        payload=payload,
    )
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=active_bucket_id,
            event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.PROFILE,
            object_id=listing.id,
            payload_version=1,
            payload=payload,
        ),
    )

    state_write = state_repo.to_secure_object_write(next_state)
    catalogue_write = catalogue_repo.to_secure_object_write(next_catalogue)
    secure_object_repository_for_active_bucket().save_many((state_write, catalogue_write))

    return _auth_configure_result(
        state=next_state,
        provider=listing.id,
        certificate_path=certificate_path,
    )


def inspect_operator_auth(provider: str | None = None) -> AuthStatusResult:
    """Return current local auth state as :class:`AuthStatusResult`, optionally scoped to a known provider slot.

    Consumes the canonical :func:`build_operator_state_projection`. The
    ``configured`` field is the projection's single canonical
    operational-readiness definition — ``auth status`` and ``auth test``
    read the same datum and cannot disagree. The live backend is probed
    (via the projection) for the ``available`` / ``health_*`` fields.
    """
    if provider is not None:
        get_auth_provider(provider)

    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(
        requested_provider=provider,
        probe_live_backend=True,
        include_workspace_summary=False,
        include_pending_obligations=False,
    )
    return _auth_status_from_projection(projection)


def _auth_status_from_projection(projection: OperatorStateProjection) -> AuthStatusResult:
    """Project the canonical state projection into the ``AuthStatusResult`` emit shape.

    The :class:`AuthStatusResult` is a CLI emit shape derived from the
    one :class:`OperatorStateProjection`; it is not a second
    state-assembly path. ``backend_configured`` mirrors the single
    canonical ``configured``, and ``backend_available`` mirrors the
    single canonical ``available``.
    """
    auth = projection.auth
    active = projection.active_profile
    return AuthStatusResult(
        provider=auth.provider,
        configured=auth.configured,
        authenticated=auth.authenticated,
        available=auth.available,
        active_profile=active.profile_id or "",
        active_profile_status=active.health_status,
        active_profile_registered=active.registered_bucket,
        active_profile_record_present=active.record_present,
        active_profile_next_action=active.next_action,
        backend_configured=auth.configured,
        backend_available=auth.available,
        certificate_path=auth.certificate_path,
        health_severity=auth.health_severity,
        health_summary=auth.health_summary,
    )


def _auth_configure_result(
    *,
    state: WorkflowState,
    provider: str,
    certificate_path: Path | None,
) -> AuthConfigureResult:
    """Build a redacted configuration result that exposes identity readiness."""
    from ..user_profile._projections import record_to_path_values

    active_profile = state.active_profile_bucket_id() or ""
    record = state.active_profile_record()
    values = record_to_path_values(record)
    profile_tax_id = (values.get("identity.tax_id") or "").strip().upper()
    settings = load_settings()
    provider_identity = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        provider_identity = unwrap_optional_secret(settings.aeat_clave_movil_dni_nie).strip().upper()
    alignment = "not_applicable"
    alignment_detail = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        if not profile_tax_id and not provider_identity:
            alignment = "profile_tax_id_missing_and_clave_identity_missing"
        elif not profile_tax_id:
            alignment = "profile_tax_id_missing"
        elif not provider_identity:
            alignment = "clave_identity_missing"
        elif profile_tax_id == provider_identity:
            alignment = "matches"
        else:
            alignment = "mismatch"
        alignment_detail = _identity_alignment_detail(
            alignment,
            profile_tax_id=profile_tax_id,
            provider_identity=provider_identity,
        )
    complete, incomplete_reason = _certificate_completeness(provider, certificate_path)
    if not complete:
        next_action = f"aeat config auth configure --provider {provider} --file PATH"
    elif provider == AuthProviderKind.CLAVE_MOVIL.value and alignment in {
        "mismatch",
        "clave_identity_missing",
        "profile_tax_id_missing",
        "profile_tax_id_missing_and_clave_identity_missing",
    }:
        # A Cl@ve identity that does not align with the active profile
        # cannot pass live auth; `auth test` would only re-report the
        # same mismatch. Route the operator to the actual fix instead
        # (persona-fleet finding G2).
        next_action = _identity_alignment_next_action(alignment)
    elif provider == AuthProviderKind.CLAVE_MOVIL.value:
        next_action = "aeat config auth test --provider clave_movil"
    else:
        next_action = f"aeat config auth test --provider {provider}"
    return AuthConfigureResult(
        provider=provider,
        file=str(certificate_path) if certificate_path is not None else "",
        complete=complete,
        incomplete_reason=incomplete_reason,
        active_profile=active_profile,
        profile_tax_id_present=bool(profile_tax_id),
        provider_identity_present=bool(provider_identity) if provider == AuthProviderKind.CLAVE_MOVIL.value else True,
        identity_alignment=alignment,
        identity_alignment_detail=alignment_detail,
        next_action=next_action,
    )


def _identity_alignment_next_action(alignment: str) -> str:
    """Return the concrete command that resolves a Cl@ve alignment fault.

    Fully localised (round-5 M6 — earlier versions dropped into English
    mid-sentence in non-English locales). A misaligned Cl@ve identity
    cannot authenticate; a missing Cl@ve identity routes to the
    configuration command that supplies it; a missing or mismatched
    profile tax id routes to the profile editor / switcher.
    """
    if alignment == "clave_identity_missing":
        return tr("application.auth.operator.alignment.clave_identity_missing_next_action")
    if alignment == "profile_tax_id_missing":
        return tr("application.auth.operator.alignment.profile_tax_id_missing_next_action")
    if alignment == "profile_tax_id_missing_and_clave_identity_missing":
        return tr("application.auth.operator.alignment.both_missing_next_action")
    # mismatch: the two identities differ; switch to the matching
    # profile or correct whichever value is wrong.
    return tr("application.auth.operator.alignment.mismatch_next_action")


def _identity_alignment_detail(
    alignment: str,
    *,
    profile_tax_id: str,
    provider_identity: str,
) -> str:
    """Explain a Cl@ve identity-alignment verdict in operator language.

    A bare ``identity_alignment: mismatch`` token states *that*
    something is wrong but never *what* is compared or how to fix it
    (persona-fleet finding G2). This returns a sentence naming the two
    compared values — the Cl@ve identity's DNI/NIE and the active
    profile's tax id — and the concrete step the operator must take.
    """
    if alignment == "matches" or alignment == "not_applicable":
        return ""
    if alignment == "mismatch":
        return tr(
            "application.auth.operator.alignment.mismatch_detail",
            clave_identity=provider_identity,
            profile_tax_id=profile_tax_id,
        )
    if alignment == "clave_identity_missing":
        return tr("application.auth.operator.alignment.clave_identity_missing_detail")
    if alignment == "profile_tax_id_missing":
        return tr("application.auth.operator.alignment.profile_tax_id_missing_detail")
    if alignment == "profile_tax_id_missing_and_clave_identity_missing":
        return tr("application.auth.operator.alignment.both_missing_detail")
    return ""


def _certificate_completeness(
    provider: str,
    certificate_path: Path | None,
) -> tuple[bool, str]:
    """Report whether a configured provider is operationally complete.

    The certificate provider is operationally complete only when a
    certificate path is supplied AND it resolves to an existing file.
    Selecting the provider without a usable ``--file`` records the
    selection but leaves the slot unusable; the operator must be told
    the configuration is incomplete, not that it succeeded.
    """
    if provider != AuthProviderKind.CERTIFICATE.value:
        return True, ""
    if certificate_path is None:
        return False, tr("application.auth.operator.errors.certificate_file_required")
    try:
        resolves = certificate_path.is_file()
    except OSError:
        resolves = False
    if not resolves:
        return False, tr(
            "application.auth.operator.errors.certificate_file_unresolved",
            certificate_path=str(certificate_path),
        )
    return True, ""


def test_operator_auth(provider: str | None = None, *, settings: Settings | None = None) -> AuthTestResult:
    """Return auth readiness as :class:`AuthTestResult`, plus a deeper local session-token probe.

    ``auth test`` and ``auth status`` (:func:`inspect_operator_auth`)
    both consume :func:`build_operator_state_projection`, so they report
    the SAME ``configured`` — the cross-surface disagreement is closed
    structurally. The live backend probe is kept (it is what the
    projection's ``probe_live_backend`` performs) and feeds only the
    separate ``available`` / ``health_*`` fields; it never recomputes
    ``configured``.

    On top of the shared readiness, ``auth test`` performs a local
    readiness probe that ``auth status`` does not: it inspects the
    encrypted AEAT session token persisted on disk for the probed
    provider and reports whether one is present and whether it is still
    within its idle deadline. This gives ``auth test`` an observable
    behaviour beyond ``auth status`` (persona-fleet finding G5).

    When the operator passes ``--provider`` the requested provider is
    actively probed. When no provider is requested, ``auth test`` scopes
    the readiness to whatever provider is configured in workflow state;
    if none is configured it does NOT invent a default and probe it —
    that would let ``auth test`` report a provider ``available`` while
    ``auth status`` reports no provider at all. Both surfaces report the
    same "no provider configured" state on the same state.
    """
    with _auth_operator_settings_scope(settings) as resolved_settings:
        provider_kind = _provider_kind_or_none(provider)
        requested_provider = provider_kind.value if provider_kind is not None else None

        from ..state_projection import build_operator_state_projection

        projection = build_operator_state_projection(
            requested_provider=requested_provider,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
        )
        status = _auth_status_from_projection(projection)
        session_probe = _probe_local_session(status.provider, settings=resolved_settings)
        provider_probe = _probe_configured_provider(
            status.provider,
            status.certificate_path,
            settings=resolved_settings,
        )
        return AuthTestResult(
            **status.model_dump(),
            persisted_session_present=session_probe.present,
            persisted_session_expired=session_probe.expired,
            persisted_session_state=session_probe.state,
            probe_summary=provider_probe.summary or session_probe.summary,
            probe_result=provider_probe.result,
        )


def build_live_auth_preflight_report(
    provider: str | None = None,
    *,
    settings: Settings | None = None,
) -> LiveAuthPreflightReport:
    """Return a redacted preflight report before a live read may trigger auth.

    Returns a :class:`LiveAuthPreflightReport` with provider status,
    identity alignment, and active-profile health indicators.
    """
    resolved_settings = settings or load_settings()
    provider_kind = _provider_kind_or_none(provider)
    if provider_kind is None:
        try:
            provider_kind = _configured_or_default_provider(resolved_settings)
        except ValueError:
            provider_kind = None
    probe = test_operator_auth(
        provider_kind.value if provider_kind is not None else provider,
        settings=resolved_settings,
    )
    profile_tax_id_present, provider_identity_present, identity_alignment = _live_auth_identity_state(
        provider_kind,
        settings=resolved_settings,
    )
    return LiveAuthPreflightReport(
        provider=probe.provider,
        configured=probe.configured,
        available=probe.available,
        active_profile=probe.active_profile,
        active_profile_status=probe.active_profile_status,
        active_profile_registered=probe.active_profile_registered,
        active_profile_record_present=probe.active_profile_record_present,
        profile_tax_id_present=profile_tax_id_present,
        provider_identity_present=provider_identity_present,
        identity_alignment=identity_alignment,
        identity_kind=_live_auth_identity_kind(provider_kind, settings=resolved_settings),
        auth_mode=_live_auth_mode(provider_kind, settings=resolved_settings),
        prefer_non_qr=(
            resolved_settings.aeat_clave_prefer_non_qr if provider_kind is AuthProviderKind.CLAVE_MOVIL else None
        ),
        timeout_ms=resolved_settings.aeat_clave_movil_timeout_ms
        if provider_kind is AuthProviderKind.CLAVE_MOVIL
        else None,
        dni_fecha_configured=bool((resolved_settings.aeat_clave_movil_dni_fecha or "").strip())
        if provider_kind is AuthProviderKind.CLAVE_MOVIL
        else None,
        nie_soporte_configured=bool(unwrap_optional_secret(resolved_settings.aeat_clave_movil_nie_soporte).strip())
        if provider_kind is AuthProviderKind.CLAVE_MOVIL
        else None,
        certificate_path_configured=resolved_settings.aeat_certificate_path is not None,
        certificate_file_present=bool(
            resolved_settings.aeat_certificate_path is not None and resolved_settings.aeat_certificate_path.is_file(),
        ),
        certificate_backend=resolved_settings.aeat_certificate_backend.value,
        persisted_session_present=probe.persisted_session_present,
        persisted_session_expired=probe.persisted_session_expired,
        persisted_session_state=probe.persisted_session_state,
        probe_result=probe.probe_result,
    )


async def login_operator_auth(
    provider: str | None = None,
    *,
    fresh: bool = False,
    reset_lock: bool = False,
    target_url: str | None = None,
    settings: Settings | None = None,
    pytest_current_test: str | None = None,
) -> AuthLoginResult:
    """Acquire or verify a live AEAT session as :class:`AuthLoginResult`, and persist backend auth state.

    Refuses with a localised, user-prose message — never a raw env-var
    or class name — when a pytest live-read attempt is missing its
    live-test opt-in, or when the configured provider is locally
    incomplete (certificate path unset / file missing / unreadable).
    Round-5 B2.
    """
    if settings is not None:
        with _auth_operator_settings_scope(settings):
            return await login_operator_auth(
                provider,
                fresh=fresh,
                reset_lock=reset_lock,
                target_url=target_url,
                settings=None,
                pytest_current_test=pytest_current_test,
            )
    resolved_settings = load_settings()
    provider_kind = _provider_kind_or_none(provider)
    if provider_kind is None:
        provider_kind = _configured_or_default_provider(resolved_settings)
    _implemented_provider(provider_kind.value)

    from ...core.access_gate import AeatAccessGate, AeatLiveReadNotEnabledError

    gate = AeatAccessGate(resolved_settings)
    # During pytest, the live-test opt-in remains the first refusal so
    # test execution cannot accidentally reach external services.
    # Outside pytest, auth login is an operational read surface and
    # proceeds to provider readiness/session checks.
    try:
        gate.require_live_read(pytest_current_test=pytest_current_test)
    except AeatLiveReadNotEnabledError as exc:
        raise AuthLoginNotEnabledError(
            translated_message="application.auth.operator.login.refused_live_tests_disabled",
            context={"provider": provider_kind.value},
        ) from exc

    # Provider-specific local-readiness preconditions. A certificate
    # provider with no path / a missing file / an unreadable bundle
    # cannot authenticate; refuse here with prose, rather than letting
    # the raw bundle-load exception escape.
    _assert_login_precondition(resolved_settings, provider_kind)

    with _active_profile_storage_span(resolved_settings):
        result = await ensure_authenticated_aeat_session(
            resolved_settings,
            kind=provider_kind,
            fresh=fresh,
            reset_lock=reset_lock,
            operation="operator-auth-login",
            target_url=target_url,
        )

        from ..workflow._persistence import workflow_state_repository

        repository = workflow_state_repository()
        repository.update(
            lambda current: _append_bucket_event(
                update_auth(
                    current,
                    provider=provider_kind.value,
                    authenticated=True,
                ),
                action="auth.session.verified",
                object_id=provider_kind.value,
            ),
        )

    return AuthLoginResult(
        provider=provider_kind.value,
        authenticated=True,
        reused_persisted_session=result.reused_persisted_session,
        fresh=result.fresh,
        removed_sessions=len(result.removed_sessions),
        acquired_lock=result.acquired_lock is not None,
        reset_lock_state=result.reset_lock.state.value if result.reset_lock is not None else "",
        verification_status=getattr(result.assertion, "status", "") or "",
    )


def clear_operator_auth(
    *,
    provider: str | None = None,
    all_providers: bool = False,
    sessions: bool = False,
    locks: bool = False,
    settings: Settings | None = None,
) -> AuthClearResult:
    """Clear workflow auth state, persisted sessions, and acquisition locks, returning a :class:`AuthClearResult`."""
    if settings is not None:
        with _auth_operator_settings_scope(settings):
            return clear_operator_auth(
                provider=provider,
                all_providers=all_providers,
                sessions=sessions,
                locks=locks,
                settings=None,
            )
    provider_kind = _provider_kind_or_none(provider)
    resolved_settings = load_settings()
    removed_sessions: list[Path] = []
    session_event_count = 0
    if sessions or all_providers:
        with _active_profile_storage_span(resolved_settings):
            removed_sessions = delete_persisted_session(
                resolved_settings,
                kind=None if all_providers else provider_kind,
            )
        session_event_count = len(removed_sessions)

    cleared_locks = _clear_acquisition_locks(
        resolved_settings,
        provider_kind=provider_kind,
        all_providers=all_providers,
        locks_requested=locks,
    )

    with _active_profile_storage_span(resolved_settings):
        from ..workflow._persistence import workflow_state_repository

        repository = workflow_state_repository()
        current_provider = repository.load().auth.provider
        should_clear_workflow_state = provider_kind is None or all_providers or current_provider == provider_kind.value
        _apply_auth_clear_to_repository(
            repository=repository,
            provider_kind=provider_kind,
            current_provider=current_provider,
            should_clear_workflow_state=should_clear_workflow_state,
            session_event_count=session_event_count,
            cleared_locks=cleared_locks,
        )

    return AuthClearResult(
        removed_sessions=len(removed_sessions),
        cleared_workflow_state=should_clear_workflow_state,
        cleared_locks=cleared_locks,
    )


def _clear_acquisition_locks(
    settings: Settings,
    *,
    provider_kind: AuthProviderKind | None,
    all_providers: bool,
    locks_requested: bool,
) -> int:
    """Clear acquisition locks for the targeted provider(s) and return the cleared count.

    With ``locks_requested`` or ``all_providers`` set, the target lock
    kinds are every provider (if ``all_providers`` or no specific
    ``provider_kind`` was supplied) or the single requested kind. A
    lock that was already absent does not count toward the cleared
    total.
    """
    if not (locks_requested or all_providers):
        return 0
    lock_kinds = list(AuthProviderKind) if all_providers or provider_kind is None else [provider_kind]
    cleared = 0
    for kind in lock_kinds:
        status = clear_auth_acquisition_lock(settings, kind, reason="operator-clear")
        if status.state is not AuthAcquisitionLockState.ABSENT:
            cleared += 1
    return cleared


def _apply_auth_clear_to_repository(
    *,
    repository: WorkflowStateRepository,
    provider_kind: AuthProviderKind | None,
    current_provider: str | None,
    should_clear_workflow_state: bool,
    session_event_count: int,
    cleared_locks: int,
) -> None:
    """Apply the operator-clear transition to the workflow-state repository.

    When ``should_clear_workflow_state`` is set, the auth state is
    reset and a ``auth.provider.cleared`` event is appended; the
    session-cleared and lock-cleared events are appended whenever
    their counters are non-zero. When the workflow state is left
    untouched, only the non-zero session / lock events are emitted —
    and only if at least one was actually performed.
    """
    if should_clear_workflow_state:
        event_object = current_provider or (provider_kind.value if provider_kind is not None else "all")
        events = (
            ("auth.provider.cleared", event_object),
            *_optional_clear_events(event_object, session_event_count, cleared_locks),
        )
        repository.update(
            lambda current: _append_bucket_events(current.model_copy(update={"auth": AuthState()}), events),
        )
        return
    if not (session_event_count or cleared_locks):
        return
    event_object = provider_kind.value if provider_kind is not None else "all"
    events = _optional_clear_events(event_object, session_event_count, cleared_locks)
    repository.update(lambda current: _append_bucket_events(current, events))


def _optional_clear_events(
    event_object: str,
    session_event_count: int,
    cleared_locks: int,
) -> tuple[tuple[str, str], ...]:
    """Build the variable-length tail of clear events keyed on non-zero counters."""
    events: list[tuple[str, str]] = []
    if session_event_count:
        events.append(("auth.session.cleared", event_object))
    if cleared_locks:
        events.append(("auth.lock.cleared", event_object))
    return tuple(events)


def _assert_login_precondition(settings: Settings, provider_kind: AuthProviderKind) -> None:
    """Refuse login when a provider's local readiness is unmet.

    Uses :class:`AuthLoginPreconditionError` carrying a localised
    summary so the operator never sees raw env-var or class names
    (round-5 B2). Reads the workflow-state certificate path when
    Settings has none, mirroring how :func:`inspect_operator_auth` and
    the state projection cross the env-var / workflow-state seam.
    """
    if provider_kind is AuthProviderKind.CERTIFICATE:
        cert_path = settings.aeat_certificate_path
        if cert_path is None:
            from ..workflow._persistence import workflow_state_repository

            recorded = workflow_state_repository().load().auth.certificate_path or ""
            cert_path = Path(recorded) if recorded else None
        if cert_path is None:
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.login.refused_certificate_path_unset",
            )
        if not cert_path.is_file():
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.login.refused_certificate_file_missing",
                context={"path": str(cert_path)},
            )
    if (
        provider_kind is AuthProviderKind.CLAVE_MOVIL
        and not unwrap_optional_secret(settings.aeat_clave_movil_dni_nie).strip()
    ):
        raise AuthLoginPreconditionError(
            translated_message="application.auth.operator.login.refused_clave_movil_identity_unset",
        )


def _implemented_provider(provider: str) -> AuthProviderListing:
    listing = get_auth_provider(provider)
    if not listing.implemented:
        raise AuthProviderReservedError(
            translated_message="application.auth.errors.provider_reserved",
            context={"provider": provider},
        )
    return listing


def _provider_kind_or_none(provider: str | None) -> AuthProviderKind | None:
    if provider is None:
        return None
    listing = _implemented_provider(provider)
    return AuthProviderKind(listing.id)


def _configured_or_default_provider(settings: Settings) -> AuthProviderKind:
    from ..workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    if state.auth.provider:
        return AuthProviderKind(state.auth.provider)
    if settings.aeat_auth_provider is not None:
        return AuthProviderKind(settings.aeat_auth_provider.value)
    return AuthProviderKind.CERTIFICATE


def _append_bucket_event(
    state: WorkflowState,
    *,
    action: str,
    object_id: str,
) -> WorkflowState:
    from ..workflow._models import WorkflowEvent

    # Auth flows can run before a profile is bound (e.g. `auth configure`
    # during initial setup). Falling back to the literal "default" silently
    # pools the unbound-session event into any operator's bucket that
    # happens to be named "default" — agent-audited as CRIT bucket-isolation
    # leak. Use a clearly system-scoped sentinel that cannot collide with
    # a real profile UUID so repair surfaces can spot + clear these.
    bucket_id = state.active_profile_bucket_id() or "__unbound_session__"
    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event)})


def _append_bucket_events(
    state: WorkflowState,
    events: tuple[tuple[str, str], ...],
) -> WorkflowState:
    updated = state
    for action, object_id in events:
        updated = _append_bucket_event(updated, action=action, object_id=object_id)
    return updated
