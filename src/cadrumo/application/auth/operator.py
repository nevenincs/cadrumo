"""Operator-facing auth application services for the config CLI.

Auth configuration and login actions mutate
:class:`application.workflow.state_models.WorkflowState`, validate the active bucket
through :func:`application.workflow.profile_health.assess_active_profile_health`, and
emit durable :class:`domain.buckets.event.BucketEvent` records through
:class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Status, test, and preflight surfaces consume the canonical
:func:`application.state_projection.build_operator_state_projection`
producer, then narrow its
:class:`application.state_projection_auth.ProjectionAuthReadiness` and
:class:`application.state_projection_models.ProjectionActiveProfile` fields into
operator-facing result records.

See Also:
    :class:`application.auth.models.AuthState`
        Workflow-owned persisted authentication readiness.
    :class:`application.auth.operator_results.AuthStatusResult`
        CLI readiness result emitted by ``auth status``.
    :class:`application.auth.operator_results.AuthTestResult`
        CLI readiness result emitted by ``auth test`` with local provider
        probes.
    :class:`application.auth.operator_results.LiveAuthPreflightReport`
        Redacted readiness report used before a live read can request login.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, nullcontext
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ...core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ...core.config import Settings, load_settings
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ..auth_credentials import ActiveCertificateCredentials
from ._mutation import AuthBucketEventSpec as _BucketEventSpec
from ._mutation import build_auth_bucket_events as _build_bucket_events
from .actions import update_auth
from .catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from .certificate_secret_backend import CertificateSecretBackendFactory
from .credentials import (
    ActiveAuthProjectionSnapshot,
    active_auth_projection_span,
)
from .operator_events import append_auth_bucket_event
from .operator_probe_ports import OperatorProbePorts
from .operator_probes import (
    live_auth_identity_kind as _live_auth_identity_kind,
)
from .operator_probes import (
    live_auth_identity_state as _live_auth_identity_state,
)
from .operator_probes import (
    live_auth_mode as _live_auth_mode,
)
from .operator_probes import (
    probe_clave_credentials,
)
from .operator_probes import (
    probe_local_session as _probe_local_session,
)
from .operator_result_projections import (
    auth_configure_result as _auth_configure_result,
)
from .operator_result_projections import (
    auth_status_from_projection as _auth_status_from_projection,
)
from .operator_results import (
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    AuthConfigureResult,
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    AuthLoginResult,
    AuthProvidersReport,
    AuthStatusResult,
    AuthTestResult,
    LiveAuthPreflightReport,
)
from .operator_scope import active_profile_storage_span as _active_profile_storage_span
from .operator_scope import (
    assert_auth_recovery_not_in_progress as _assert_auth_recovery_not_in_progress,
)
from .operator_scope import auth_mutation_span as _auth_mutation_span
from .operator_scope import (
    auth_operator_settings_scope as _auth_operator_settings_scope,
)
from .operator_scope_ports import OperatorScopePorts
from .preferences import set_profile_auth_preference
from .protocols import BrowserSessionFactoryPort, session_store
from .sessions import (
    ensure_authenticated_aeat_session,
)

if TYPE_CHECKING:
    from ...domain.buckets.event import BucketEvent, BucketEventType
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..state_projection_ports import StateProjectionReadPorts
    from ..workflow.state_models import WorkflowState


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return the report enumerating executable authentication providers."""
    return AuthProvidersReport(providers=list_auth_providers())


def _configured_active_profile(state: WorkflowState, *, operation: PinnedAuthorityOperation) -> str:
    from ..workflow.profile_health import RECORD_FAULT_STATUSES, assess_active_profile_health

    profile_health = assess_active_profile_health(state, operation=operation)
    active_bucket_id = profile_health.active_profile
    if active_bucket_id is None:
        raise AuthConfigureNoActiveBucketError(
            translated_message="application.auth.operator.errors.no_active_bucket",
        )
    if profile_health.status == "dangling_pointer":
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.dangling_active_profile",
            context={"active_profile": active_bucket_id},
            precondition_verdict=profile_health.precondition_verdict,
        )
    if profile_health.status in RECORD_FAULT_STATUSES:
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.unreadable_active_profile",
            context={"active_profile": active_bucket_id, "status": profile_health.status},
            precondition_verdict=profile_health.precondition_verdict,
        )
    return active_bucket_id


def _operational_auth_changed(
    state: WorkflowState,
    *,
    provider: str,
    certificate_path: Path | None,
    source_changed: bool,
) -> bool:
    return (
        source_changed
        or state.auth.provider != provider
        or (certificate_path is not None and state.auth.certificate_path != str(certificate_path))
    )


def configure_operator_auth(
    provider: str,
    *,
    certificate_path: Path | None = None,
    clave_movil_route: ClaveMovilRoute | None = None,
    expected_profile_revision: int | None = None,
    expected_profile_digest: str | None = None,
    operator_scope_ports: OperatorScopePorts,
    operation: PinnedAuthorityOperation,
) -> AuthConfigureResult:
    """Configure profile intent and operational auth state atomically.

    Health checks reject missing or unreadable profiles. The durable event
    includes certificate paths but never passwords, keys, or session tokens.
    """
    from ...domain.buckets.event import BucketEventType
    from ..workflow.persistence import workflow_state_repository

    listing = _provider_listing(provider)
    resolved_settings = load_settings()
    occurred_at = now()
    payload: dict[str, str] = {"provider_id": listing.id}
    if certificate_path is not None:
        payload["certificate_path"] = str(certificate_path)

    with _active_profile_storage_span(
        resolved_settings,
        operator_scope_ports=operator_scope_ports,
    ) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        with _auth_mutation_span(
            settings=resolved_settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            state_repo = workflow_state_repository()
            changed = False

            def mutate(current_state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                nonlocal changed
                _assert_auth_recovery_not_in_progress(current_state)
                active_bucket_id = _configured_active_profile(current_state, operation=operation)
                _, preference_changed = set_profile_auth_preference(
                    profile_id=active_bucket_id,
                    provider=AuthProviderKind(listing.id),
                    route=clave_movil_route,
                    profile_decode_context=operation.profile_decode_context(),
                    expected_revision=expected_profile_revision,
                    expected_content_digest=expected_profile_digest,
                )
                from .certificate_sources import active_certificate_source, register_certificate_source

                selected_source = active_certificate_source(current_state)
                source_update = (
                    (selected_source, certificate_path)
                    if listing.id == AuthProviderKind.CERTIFICATE.value
                    and certificate_path is not None
                    and selected_source is not None
                    and selected_source.certificate_path != str(certificate_path)
                    else None
                )
                operational_changed = _operational_auth_changed(
                    current_state,
                    provider=listing.id,
                    certificate_path=certificate_path,
                    source_changed=source_update is not None,
                )
                changed = preference_changed or operational_changed
                if not changed:
                    return current_state, ()
                next_state = append_auth_bucket_event(
                    update_auth(
                        current_state,
                        provider=listing.id,
                        certificate_path=str(certificate_path) if certificate_path is not None else None,
                    ),
                    action="auth.provider.configured",
                    object_id=listing.id,
                )
                if source_update is not None:
                    selected_source, selected_path = source_update
                    next_state = register_certificate_source(
                        next_state,
                        name=selected_source.name,
                        certificate_path=selected_path,
                        friendly_name=selected_source.friendly_name,
                    )
                events = _build_bucket_events(
                    bucket_id=bucket_id,
                    events=(
                        _BucketEventSpec(
                            BucketEventType.AUTH_PROVIDER_CONFIGURED,
                            listing.id,
                            payload,
                            occurred_at,
                        ),
                    ),
                )
                return next_state, events

            next_state = state_repo.update_with_bucket_events(mutate)

    return _auth_configure_result(
        state=next_state,
        provider=listing.id,
        certificate_path=(
            certificate_path
            or (
                Path(next_state.auth.certificate_path)
                if (next_state.auth.certificate_path is not None and next_state.auth.certificate_path)
                else None
            )
        ),
        changed=changed,
    )


def inspect_operator_auth(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
) -> AuthStatusResult:
    """Return current local auth state as :class:`AuthStatusResult`, optionally scoped to a known provider slot.

    Consumes the canonical
    :func:`application.state_projection.build_operator_state_projection`.
    The ``configured`` field is the
    :class:`application.state_projection_auth.ProjectionAuthReadiness` single
    canonical operational-readiness definition; ``auth status`` and ``auth
    test`` read the same datum and cannot disagree. The live backend is probed
    (via the projection) for the ``available`` / ``health_*`` fields, while the
    active-profile fields mirror
    :class:`application.state_projection_models.ProjectionActiveProfile`.
    """
    if provider is not None:
        get_auth_provider(provider)

    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=operator_probe_ports,
        operator_scope_ports=operator_scope_ports,
        read_ports=read_ports,
        requested_provider=provider,
        probe_live_backend=True,
        include_workspace_summary=False,
        include_pending_obligations=False,
        operation=operation,
    )
    return _auth_status_from_projection(projection)


def test_operator_auth(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
) -> AuthTestResult:
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
    behaviour beyond ``auth status``.

    When the operator passes ``--provider`` the requested provider is
    actively probed. When no provider is requested, ``auth test`` scopes
    the readiness to whatever provider is configured in workflow state;
    if none is configured it does NOT invent a default and probe it —
    that would let ``auth test`` report a provider ``available`` while
    ``auth status`` reports no provider at all. Both surfaces report the
    same "no provider configured" state on the same state.
    """
    if settings is not None:
        with _active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports):
            return test_operator_auth(
                provider,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=operator_probe_ports,
                operator_scope_ports=operator_scope_ports,
                read_ports=read_ports,
                operation=operation,
                settings=None,
            )

    with _auth_operator_settings_scope(None) as resolved_settings:
        provider_kind = _provider_kind_or_none(provider)
        requested_provider = provider_kind.value if provider_kind is not None else None

        with active_auth_projection_span(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=resolved_settings,
            requested_provider=requested_provider,
            operator_scope_ports=operator_scope_ports,
        ) as snapshot:
            return _test_operator_auth_from_snapshot(
                snapshot,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=operator_probe_ports,
                operator_scope_ports=operator_scope_ports,
                read_ports=read_ports,
                operation=operation,
                requested_provider=requested_provider,
                resolved_settings=resolved_settings,
            )


def _test_operator_auth_from_snapshot(
    snapshot: ActiveAuthProjectionSnapshot,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    requested_provider: str | None,
    resolved_settings: Settings,
) -> AuthTestResult:
    """Build one auth-test result without reopening its witnessed storage route.

    The persisted-session probe re-enters :func:`active_profile_storage_span`,
    but the caller still owns the outer projection span. Its active-profile
    override names ``snapshot.bucket_id`` and its bucket session remains current,
    so the re-entrant span selects that session without consulting a changed
    pointer or opening another bucket.
    """
    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=operator_probe_ports,
        operator_scope_ports=operator_scope_ports,
        read_ports=read_ports,
        auth_snapshot=snapshot,
        requested_provider=requested_provider,
        probe_live_backend=True,
        include_workspace_summary=False,
        include_pending_obligations=False,
        operation=operation,
    )
    status = _auth_status_from_projection(projection)
    session_probe = _probe_local_session(
        status.provider,
        settings=resolved_settings,
        operator_scope_ports=operator_scope_ports,
    )
    return AuthTestResult(
        **status.model_dump(),
        persisted_session_present=session_probe.present,
        persisted_session_expired=session_probe.expired,
        persisted_session_state=session_probe.state,
        probe_summary=projection.auth.probe_summary or session_probe.summary,
        probe_result=projection.auth.probe_result,
    )


class _ClaveMovilPreflightFields(TypedDict):
    """The Cl@ve Móvil preflight fields spliced into ``LiveAuthPreflightReport``."""

    prefer_non_qr: bool | None
    timeout_ms: int | None
    dni_fecha_configured: bool | None
    nie_soporte_configured: bool | None


def _clave_movil_preflight_fields(
    settings: Settings,
    provider_kind: AuthProviderKind | None,
    *,
    state: WorkflowState | None = None,
    operator_probe_ports: OperatorProbePorts,
) -> _ClaveMovilPreflightFields:
    """Return the Cl@ve Móvil preflight fields, all ``None`` for other providers.

    The two contraste booleans report whether the operator has recorded
    the value the non-QR form asks for, so they resolve through the
    shared profile-first resolver rather than the settings fields alone.
    Reading settings alone told an operator whose contraste lives on the
    encrypted profile that it was absent, while live authentication
    resolved it perfectly well.

    The redaction posture is unchanged: identity material never enters the
    report, only booleans and the QR/timeout preferences.
    """
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return {
            "prefer_non_qr": None,
            "timeout_ms": None,
            "dni_fecha_configured": None,
            "nie_soporte_configured": None,
        }
    credentials = probe_clave_credentials(
        provider_kind,
        settings=settings,
        state=state,
        operator_probe_ports=operator_probe_ports,
    )
    return {
        "prefer_non_qr": settings.cadrumo_clave_prefer_non_qr,
        "timeout_ms": settings.cadrumo_clave_movil_timeout_ms,
        "dni_fecha_configured": bool(credentials is not None and credentials.fecha_validez),
        "nie_soporte_configured": bool(credentials is not None and credentials.numero_soporte),
    }


def build_live_auth_preflight_report(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
) -> LiveAuthPreflightReport:
    """Return a redacted preflight report before a live read may trigger auth.

    Returns a :class:`LiveAuthPreflightReport` with provider status,
    identity alignment, persisted-session indicators, and active-profile health
    fields inherited from :class:`AuthTestResult`.

    A locked store answers "not ready" rather than refusing to answer. The two
    ways this report can fail to reach a profile are not the same question. When
    a custody session is open for some OTHER profile, answering about the named
    one would be a claim about a profile that was never inspected, so the
    refusal stands. When NO session is open at all, the operator is asking
    whether auth is ready before unlocking anything -- the locked workstation --
    and a readiness probe that declines to answer precisely then has no
    remaining purpose. Every field of :class:`LiveAuthPreflightReport` defaults
    to empty or false because the type exists to carry that degraded answer.

    See Also:
        :class:`core.access_gate.gate.AeatAccessGate`
            Live-read gate evaluated before an authenticated AEAT operation can
            proceed.
        :func:`test_operator_auth`
            Shared provider-readiness probe that supplies the preflight base.
    """
    from .operator_results import AuthOperationRequiresCustodySessionError

    try:
        return _build_live_auth_preflight_report(
            provider,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports,
            operation=operation,
            settings=settings,
        )
    except AuthOperationRequiresCustodySessionError:
        if operator_scope_ports.session.current() is not None:
            raise
        # Guard the RESOLVED kind, not the supplied string: the resolver
        # returns None for a provider it does not implement, so a non-empty
        # but unrecognised value passes a truthiness check on the input and
        # then raises on the attribute. The empty projection is the same
        # answer either way -- there is no session to report a provider for.
        kind = _provider_kind_or_none(provider)
        return LiveAuthPreflightReport(provider=kind.value if kind is not None else "")


def _build_live_auth_preflight_report(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
) -> LiveAuthPreflightReport:
    """Build the report against an open route, refusing when it cannot be reached."""
    if settings is not None:
        with _active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports):
            return _build_live_auth_preflight_report(
                provider,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=operator_probe_ports,
                operator_scope_ports=operator_scope_ports,
                read_ports=read_ports,
                operation=operation,
                settings=None,
            )

    resolved_settings = load_settings()
    requested_kind = _provider_kind_or_none(provider)
    requested_provider = requested_kind.value if requested_kind is not None else None
    fallback_provider = (resolved_settings.cadrumo_auth_provider or AuthProviderKind.CERTIFICATE).value
    with active_auth_projection_span(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        settings=resolved_settings,
        requested_provider=requested_provider,
        fallback_provider=fallback_provider,
        operator_scope_ports=operator_scope_ports,
    ) as snapshot:
        provider_kind = snapshot.provider
        probe = _test_operator_auth_from_snapshot(
            snapshot,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports,
            operation=operation,
            requested_provider=(provider_kind.value if provider_kind is not None else None),
            resolved_settings=resolved_settings,
        )
        profile_tax_id_present, provider_identity_present, identity_alignment = _live_auth_identity_state(
            provider_kind,
            settings=resolved_settings,
            state=snapshot.state,
            operator_probe_ports=operator_probe_ports,
        )
        certificate_path = Path(probe.certificate_path) if probe.certificate_path else None
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
            identity_kind=_live_auth_identity_kind(
                provider_kind,
                settings=resolved_settings,
                state=snapshot.state,
                operator_probe_ports=operator_probe_ports,
            ),
            auth_mode=_live_auth_mode(provider_kind, settings=resolved_settings),
            **_clave_movil_preflight_fields(
                resolved_settings,
                provider_kind,
                state=snapshot.state,
                operator_probe_ports=operator_probe_ports,
            ),
            certificate_path_configured=certificate_path is not None,
            certificate_file_present=certificate_path is not None and certificate_path.is_file(),
            persisted_session_present=probe.persisted_session_present,
            persisted_session_expired=probe.persisted_session_expired,
            persisted_session_state=probe.persisted_session_state,
            probe_result=probe.probe_result,
        )


async def login_operator_auth(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    fresh: bool = False,
    reset_lock: bool = False,
    settings: Settings | None = None,
    guarded_read_context: str | None = None,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]] | None = None,
    authority_operation: PinnedAuthorityOperation | None = None,
) -> AuthLoginResult:
    """Acquire or verify a live AEAT session as :class:`AuthLoginResult`, and persist backend auth state.

    Refuses with a localised, user-prose message — never a raw env-var
    or class name — when a pytest live-read attempt is missing its
    live-test opt-in, or when the configured provider is locally
    incomplete (certificate path unset / file missing / unreadable).
    Round-5 B2.

    See Also:
        :class:`core.access_gate.gate.AeatAccessGate`
            Enforces the live-read opt-in before provider authentication.
        :func:`application.auth.sessions.ensure_authenticated_aeat_session`
            Provider-session lifecycle helper that returns the verified session
            result consumed here.
    """
    if settings is not None:
        with _active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports):
            return await login_operator_auth(
                provider,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                browser_session_factory=browser_session_factory,
                operator_probe_ports=operator_probe_ports,
                operator_scope_ports=operator_scope_ports,
                fresh=fresh,
                reset_lock=reset_lock,
                settings=None,
                guarded_read_context=guarded_read_context,
                effect_guard=effect_guard,
                authority_operation=authority_operation,
            )
    resolved_settings = load_settings()
    requested_kind = _provider_kind_or_none(provider)
    requested_provider = requested_kind.value if requested_kind is not None else None
    fallback_provider = (resolved_settings.cadrumo_auth_provider or AuthProviderKind.CERTIFICATE).value
    with active_auth_projection_span(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        settings=resolved_settings,
        requested_provider=requested_provider,
        fallback_provider=fallback_provider,
        operator_scope_ports=operator_scope_ports,
    ) as snapshot:
        provider_kind = snapshot.provider
        if provider_kind is None:
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.errors.provider_not_configured",
            )
        _provider_listing(provider_kind.value)

        _require_live_auth_login(
            provider_kind,
            resolved_settings,
            guarded_read_context=guarded_read_context,
        )

        resolved_settings = resolved_settings.model_copy(
            update={"cadrumo_clave_permanente_password": snapshot.clave_permanente_password}
        )
        certificate_credentials = snapshot.certificate_credentials

        # Provider-specific local-readiness preconditions. A certificate
        # provider with no path / a missing file / an unreadable bundle
        # cannot authenticate; refuse here with prose, rather than letting
        # the raw bundle-load exception escape.
        _assert_login_precondition(
            resolved_settings,
            provider_kind,
            certificate_credentials=certificate_credentials,
            operator_probe_ports=operator_probe_ports,
        )

        from ...domain.buckets.event import BucketEventType
        from ..workflow.persistence import workflow_state_repository

        bucket_id = snapshot.bucket_id
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        with _auth_mutation_span(
            settings=resolved_settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            repository = workflow_state_repository()
            _assert_auth_recovery_not_in_progress(repository.load())
            with session_store().defer_writes() as staged:
                operation_span = (
                    nullcontext(authority_operation)
                    if authority_operation is not None
                    else bundled_indexed_authority().operation()
                )
                with operation_span as pinned_operation:
                    result = await ensure_authenticated_aeat_session(
                        resolved_settings,
                        certificate_secret_backend_factory=certificate_secret_backend_factory,
                        browser_session_factory=browser_session_factory,
                        kind=provider_kind,
                        certificate_credentials=certificate_credentials,
                        fresh=fresh,
                        reset_lock=reset_lock,
                        operation="operator-auth-login",
                        operator_scope_ports=operator_scope_ports,
                        profile_decode_context=pinned_operation.profile_decode_context(),
                        effect_guard=effect_guard,
                    )

                # Remote provider work has ended. Recheck current profile authority
                # only while publishing its encrypted session and verified event.
                async with effect_guard() if effect_guard is not None else nullcontext():
                    staged.publish()
                    occurred_at = now()
                    repository.update_with_bucket_events(
                        lambda current: _verified_session_update(
                            current,
                            bucket_id=bucket_id,
                            provider_kind=provider_kind,
                            occurred_at=occurred_at,
                            event_type=BucketEventType.AUTH_SESSION_VERIFIED,
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


def _require_live_auth_login(
    provider_kind: AuthProviderKind,
    settings: Settings,
    *,
    guarded_read_context: str | None,
) -> None:
    """Keep the pytest live-read refusal ahead of every provider readiness check."""
    from ...core.access_gate.errors import AeatLiveReadNotEnabledError
    from ...core.access_gate.gate import AeatAccessGate

    try:
        AeatAccessGate(settings).require_live_read(guarded_read_context=guarded_read_context)
    except AeatLiveReadNotEnabledError as exc:
        raise AuthLoginNotEnabledError(
            translated_message="application.auth.operator.login.refused_live_tests_disabled",
            context={"provider": provider_kind.value},
        ) from exc


def _verified_session_update(
    current: WorkflowState,
    *,
    bucket_id: str,
    provider_kind: AuthProviderKind,
    occurred_at: datetime,
    event_type: BucketEventType,
) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
    """Prepare verified-session state and its append-only bucket event."""
    _assert_auth_recovery_not_in_progress(current)
    return (
        append_auth_bucket_event(
            update_auth(
                current,
                provider=provider_kind.value,
                authenticated=True,
            ),
            action="auth.session.verified",
            object_id=provider_kind.value,
        ),
        _build_bucket_events(
            bucket_id=bucket_id,
            events=(
                _BucketEventSpec(
                    event_type,
                    provider_kind.value,
                    {"provider_id": provider_kind.value},
                    occurred_at,
                ),
            ),
        ),
    )


def _assert_login_precondition(
    settings: Settings,
    provider_kind: AuthProviderKind,
    *,
    certificate_credentials: ActiveCertificateCredentials | None = None,
    operator_probe_ports: OperatorProbePorts,
) -> None:
    """Refuse login when a provider's local readiness is unmet.

    Raises :class:`AuthLoginPreconditionError` with localised refusal keys so
    the operator never sees raw env-var or class names. The caller supplies
    the application-owned provider Settings projection, so this check never
    reloads or reconstructs certificate credentials independently.
    """
    if provider_kind is AuthProviderKind.CERTIFICATE:
        cert_path = certificate_credentials.certificate_path if certificate_credentials is not None else None
        if cert_path is None:
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.login.refused_certificate_path_unset",
            )
        if not cert_path.is_file():
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.login.refused_certificate_file_missing",
                context={"path": str(cert_path)},
            )
    if provider_kind is AuthProviderKind.CLAVE_MOVIL:
        credentials = probe_clave_credentials(
            provider_kind,
            settings=settings,
            operator_probe_ports=operator_probe_ports,
        )
        if credentials is None or not credentials.dni_nie:
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.login.refused_clave_movil_identity_unset",
            )


def _provider_listing(provider: str) -> AuthProviderListing:
    return get_auth_provider(provider)


def _provider_kind_or_none(provider: str | None) -> AuthProviderKind | None:
    if provider is None:
        return None
    listing = _provider_listing(provider)
    return AuthProviderKind(listing.id)


__all__ = [
    "build_live_auth_preflight_report",
    "configure_operator_auth",
    "inspect_operator_auth",
    "list_operator_auth_providers",
    "login_operator_auth",
    "test_operator_auth",
]
