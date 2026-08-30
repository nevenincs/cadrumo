"""Operator-facing auth application services for the config CLI.

Auth configuration and login actions mutate
:class:`application.workflow.WorkflowState`, validate the active bucket
through :func:`application.workflow.assess_active_profile_health`, and
emit durable :class:`domain.buckets.BucketEvent` records through
:class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Status, test, and preflight surfaces consume the canonical
:func:`application.state_projection.build_operator_state_projection`
producer, then narrow its
:class:`application.state_projection.ProjectionAuthReadiness` and
:class:`application.state_projection.ProjectionActiveProfile` fields into
operator-facing result records.

See Also:
    :class:`application.auth.models.AuthState`
        Workflow-owned persisted authentication readiness.
    :class:`application.auth.AuthStatusResult`
        CLI readiness result emitted by ``auth status``.
    :class:`application.auth.AuthTestResult`
        CLI readiness result emitted by ``auth test`` with local provider
        probes.
    :class:`application.auth.LiveAuthPreflightReport`
        Redacted readiness report used before a live read can request login.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ...core import AuthProviderKind
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.config import Settings, load_settings
from ...core.i18n import tr
from ...core.identity import tax_id_identity_token
from ...core.time import now
from ..auth_credentials import ActiveCertificateCredentials
from ..operator_actions import (
    PreconditionVerdict,
    no_action_precondition_verdict,
)
from ._mutation import AuthBucketEventSpec as _BucketEventSpec
from ._mutation import build_auth_bucket_events as _build_bucket_events
from .actions import update_auth
from .catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from .credentials import (
    ActiveAuthProjectionSnapshot,
    active_auth_projection_span,
)
from .models import (
    AuthCleanupOperationKind,
)
from .operator_cleanup import (
    apply_auth_cleanup_intent,
    assert_logout_request_matches,
    assert_reset_request_matches,
    auth_cleanup_bucket_events,
    auth_cleanup_intent_has_effects,
    build_auth_cleanup_intent,
    clear_scoped_locks,
    delete_certificate_source_secrets,
    delete_scoped_sessions,
)
from .operator_probes import (
    classify_identity_alignment as _classify_identity_alignment,
)
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
from .operator_results import (
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    AuthConfigureResult,
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    AuthLoginResult,
    AuthLogoutResult,
    AuthOperationRequiresCustodySessionError,
    AuthProviderReservedError,
    AuthProvidersReport,
    AuthResetResult,
    AuthStatusResult,
    AuthTestResult,
    LiveAuthPreflightReport,
)
from .operator_scope import active_profile_storage_span as _active_profile_storage_span
from .operator_scope import (
    assert_auth_recovery_not_in_progress as _assert_auth_recovery_not_in_progress,
)
from .operator_scope import (
    assert_certificate_secret_mutation_not_in_progress as _assert_certificate_secret_mutation_not_in_progress,
)
from .operator_scope import auth_mutation_span as _auth_mutation_span
from .operator_scope import (
    auth_operator_settings_scope as _auth_operator_settings_scope,
)
from .operator_scope import resolve_auth_operation_scope
from .sessions import (
    clave_auth_facts_from_profile_values,
    ensure_authenticated_aeat_session,
    resolve_clave_credentials,
)

if TYPE_CHECKING:
    from ...domain.buckets.event import BucketEvent, BucketEventType
    from ..state_projection import OperatorStateProjection
    from ..workflow.state_models import WorkflowState


_build_auth_cleanup_intent = build_auth_cleanup_intent


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return the :class:`AuthProvidersReport` enumerating implemented and reserved auth provider slots."""
    return AuthProvidersReport(providers=list_auth_providers())


def configure_operator_auth(provider: str, *, certificate_path: Path | None = None) -> AuthConfigureResult:
    """Configure the active auth provider in workflow state.

    The active profile is resolved through
    :func:`application.workflow.assess_active_profile_health` before the
    :class:`application.workflow.WorkflowState` mutation is written, so a
    dangling or unreadable active bucket cannot receive an auth selection.
    Persists the workflow-state update and a typed
    ``AUTH_PROVIDER_CONFIGURED`` event into the bucket-event-history
    catalogue in a single SQL transaction (via
    :meth:`adapters.persistence.storage.SecureObjectRepository.save_many`),
    so a crash between the two writes cannot leave the state mutated without
    the catalogue event landing. The certificate path is recorded as a payload
    value when supplied because it is a filesystem reference, not credential
    material; certificate passwords, private keys, and session tokens never
    enter the payload.

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

    See Also:
        :class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`
            Durable per-bucket event history that receives the typed auth event.
        :class:`application.workflow.ActiveProfileHealth`
            Redacted health verdict used to accept or refuse the active bucket.
    """
    from ...domain.buckets.event import BucketEventType
    from ..workflow.persistence import workflow_state_repository
    from ..workflow.profile_health import assess_active_profile_health

    listing = _implemented_provider(provider)
    resolved_settings = load_settings()
    occurred_at = now()
    payload: dict[str, str] = {"provider_id": listing.id}
    if certificate_path is not None:
        payload["certificate_path"] = str(certificate_path)

    with _active_profile_storage_span(resolved_settings) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        with _auth_mutation_span(settings=resolved_settings, bucket_id=bucket_id):
            state_repo = workflow_state_repository()

            def mutate(current_state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                _assert_auth_recovery_not_in_progress(current_state)
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
                        precondition_verdict=profile_health.precondition_verdict,
                    )
                if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
                    raise AuthConfigureDanglingActiveProfileError(
                        translated_message="application.auth.operator.errors.unreadable_active_profile",
                        context={
                            "active_profile": active_bucket_id,
                            "status": profile_health.status,
                        },
                        precondition_verdict=profile_health.precondition_verdict,
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
        certificate_path=certificate_path,
    )


def inspect_operator_auth(provider: str | None = None) -> AuthStatusResult:
    """Return current local auth state as :class:`AuthStatusResult`, optionally scoped to a known provider slot.

    Consumes the canonical
    :func:`application.state_projection.build_operator_state_projection`.
    The ``configured`` field is the
    :class:`application.state_projection.ProjectionAuthReadiness` single
    canonical operational-readiness definition; ``auth status`` and ``auth
    test`` read the same datum and cannot disagree. The live backend is probed
    (via the projection) for the ``available`` / ``health_*`` fields, while the
    active-profile fields mirror
    :class:`application.state_projection.ProjectionActiveProfile`.
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
        active_profile=active.label or active.profile_id or "",
        active_profile_status=active.health_status,
        active_profile_registered=active.registered_bucket,
        active_profile_record_present=active.record_present,
        active_profile_precondition_verdict=active.precondition_verdict,
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
    from ..user_profile.projections import record_to_path_values

    record = state.active_profile_record()
    values = record_to_path_values(record)
    profile_tax_id = tax_id_identity_token(values.get("identity.tax_id") or "")
    settings = load_settings()
    provider_identity = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        # The profile's own values are already in hand, so the shared
        # resolver is fed directly rather than re-reading the record.
        credentials = resolve_clave_credentials(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
            facts=clave_auth_facts_from_profile_values(values),
        )
        provider_identity = credentials.dni_nie if credentials is not None else ""
    alignment = "not_applicable"
    alignment_detail = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        alignment = _classify_identity_alignment(profile_tax_id, provider_identity)
        alignment_detail = _identity_alignment_detail(
            alignment,
            profile_tax_id=profile_tax_id,
            provider_identity=provider_identity,
        )
    complete, incomplete_reason = _certificate_completeness(provider, certificate_path)
    if provider == AuthProviderKind.CLAVE_MOVIL.value and alignment != "matches":
        complete = False
        incomplete_reason = alignment_detail
    return AuthConfigureResult(
        provider=provider,
        file=str(certificate_path) if certificate_path is not None else "",
        complete=complete,
        incomplete_reason=incomplete_reason,
        profile_tax_id_present=bool(profile_tax_id),
        provider_identity_present=bool(provider_identity) if provider == AuthProviderKind.CLAVE_MOVIL.value else True,
        identity_alignment=alignment,
        identity_alignment_detail=alignment_detail,
        precondition_verdict=(
            _incomplete_auth_configuration_verdict(
                provider=provider,
                certificate_path=certificate_path,
                profile_tax_id_present=bool(profile_tax_id),
                provider_identity_present=bool(provider_identity),
                identity_alignment=alignment,
            )
            if not complete
            else None
        ),
    )


def _incomplete_auth_configuration_verdict(
    *,
    provider: str,
    certificate_path: Path | None,
    profile_tax_id_present: bool,
    provider_identity_present: bool,
    identity_alignment: str,
) -> PreconditionVerdict:
    """Record an incomplete configuration without inventing a recovery command.

    Choosing a certificate file or changing one of two competing identities is
    an operator decision.  The application records the exact failed condition,
    but cannot honestly materialise a single executable command from those
    facts.
    """
    if provider == AuthProviderKind.CERTIFICATE.value:
        condition_id = "auth.certificate.file_ready"
        evidence_id = "auth.configure.certificate.file_readiness"
        facts = {
            "certificate_file_provided": certificate_path is not None,
            "certificate_file_resolves": False,
            "provider": provider,
        }
    elif provider == AuthProviderKind.CLAVE_MOVIL.value:
        condition_id = "auth.clave_movil.identity_aligned"
        evidence_id = "auth.configure.clave_movil.identity_alignment"
        facts = {
            "identity_alignment": identity_alignment,
            "profile_tax_id_present": profile_tax_id_present,
            "provider": provider,
            "provider_identity_present": provider_identity_present,
        }
    else:
        raise RuntimeError(f"unsupported incomplete auth provider: {provider}")
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence_id,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _identity_alignment_detail(
    alignment: str,
    *,
    profile_tax_id: str,
    provider_identity: str,
) -> str:
    """Explain a Cl@ve identity-alignment verdict in operator language.

    A bare ``identity_alignment: mismatch`` token states *that*
    something is wrong but never *what* is compared or how to fix it.
    This returns a sentence naming the two
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
        with _active_profile_storage_span(settings):
            return test_operator_auth(provider, settings=None)

    with _auth_operator_settings_scope(None) as resolved_settings:
        provider_kind = _provider_kind_or_none(provider)
        requested_provider = provider_kind.value if provider_kind is not None else None

        with active_auth_projection_span(
            settings=resolved_settings,
            requested_provider=requested_provider,
        ) as snapshot:
            return _test_operator_auth_from_snapshot(
                snapshot,
                requested_provider=requested_provider,
                resolved_settings=resolved_settings,
            )


def _test_operator_auth_from_snapshot(
    snapshot: ActiveAuthProjectionSnapshot,
    *,
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
        auth_snapshot=snapshot,
        requested_provider=requested_provider,
        probe_live_backend=True,
        include_workspace_summary=False,
        include_pending_obligations=False,
    )
    status = _auth_status_from_projection(projection)
    session_probe = _probe_local_session(status.provider, settings=resolved_settings)
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
    credentials = probe_clave_credentials(provider_kind, settings=settings, state=state)
    return {
        "prefer_non_qr": settings.cadrumo_clave_prefer_non_qr,
        "timeout_ms": settings.cadrumo_clave_movil_timeout_ms,
        "dni_fecha_configured": bool(credentials is not None and credentials.fecha_validez),
        "nie_soporte_configured": bool(credentials is not None and credentials.numero_soporte),
    }


def build_live_auth_preflight_report(
    provider: str | None = None,
    *,
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
        :class:`core.access_gate.AeatAccessGate`
            Live-read gate evaluated before an authenticated AEAT operation can
            proceed.
        :func:`test_operator_auth`
            Shared provider-readiness probe that supplies the preflight base.
    """
    from ..user_profile.login_session_port import profile_current_bucket_session
    from .operator_results import AuthOperationRequiresCustodySessionError

    try:
        return _build_live_auth_preflight_report(provider, settings=settings)
    except AuthOperationRequiresCustodySessionError:
        if profile_current_bucket_session() is not None:
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
    settings: Settings | None = None,
) -> LiveAuthPreflightReport:
    """Build the report against an open route, refusing when it cannot be reached."""
    if settings is not None:
        with _active_profile_storage_span(settings):
            return _build_live_auth_preflight_report(provider, settings=None)

    resolved_settings = load_settings()
    requested_kind = _provider_kind_or_none(provider)
    requested_provider = requested_kind.value if requested_kind is not None else None
    fallback_provider = (resolved_settings.cadrumo_auth_provider or AuthProviderKind.CERTIFICATE).value
    with active_auth_projection_span(
        settings=resolved_settings,
        requested_provider=requested_provider,
        fallback_provider=fallback_provider,
    ) as snapshot:
        provider_kind = snapshot.provider
        probe = _test_operator_auth_from_snapshot(
            snapshot,
            requested_provider=(provider_kind.value if provider_kind is not None else None),
            resolved_settings=resolved_settings,
        )
        profile_tax_id_present, provider_identity_present, identity_alignment = _live_auth_identity_state(
            provider_kind,
            settings=resolved_settings,
            state=snapshot.state,
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
            identity_kind=_live_auth_identity_kind(provider_kind, settings=resolved_settings),
            auth_mode=_live_auth_mode(provider_kind, settings=resolved_settings),
            **_clave_movil_preflight_fields(resolved_settings, provider_kind),
            certificate_path_configured=certificate_path is not None,
            certificate_file_present=bool(
                certificate_path is not None and certificate_path.is_file(),
            ),
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
    settings: Settings | None = None,
    pytest_current_test: str | None = None,
) -> AuthLoginResult:
    """Acquire or verify a live AEAT session as :class:`AuthLoginResult`, and persist backend auth state.

    Refuses with a localised, user-prose message — never a raw env-var
    or class name — when a pytest live-read attempt is missing its
    live-test opt-in, or when the configured provider is locally
    incomplete (certificate path unset / file missing / unreadable).
    Round-5 B2.

    See Also:
        :class:`core.access_gate.AeatAccessGate`
            Enforces the live-read opt-in before provider authentication.
        :func:`application.auth.ensure_authenticated_aeat_session`
            Provider-session lifecycle helper that returns the verified session
            result consumed here.
    """
    if settings is not None:
        with _active_profile_storage_span(settings):
            return await login_operator_auth(
                provider,
                fresh=fresh,
                reset_lock=reset_lock,
                settings=None,
                pytest_current_test=pytest_current_test,
            )
    resolved_settings = load_settings()
    requested_kind = _provider_kind_or_none(provider)
    requested_provider = requested_kind.value if requested_kind is not None else None
    fallback_provider = (resolved_settings.cadrumo_auth_provider or AuthProviderKind.CERTIFICATE).value
    with active_auth_projection_span(
        settings=resolved_settings,
        requested_provider=requested_provider,
        fallback_provider=fallback_provider,
    ) as snapshot:
        provider_kind = snapshot.provider
        if provider_kind is None:
            raise AuthLoginPreconditionError(
                translated_message="application.auth.operator.errors.provider_not_configured",
            )
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

        certificate_credentials = snapshot.certificate_credentials

        # Provider-specific local-readiness preconditions. A certificate
        # provider with no path / a missing file / an unreadable bundle
        # cannot authenticate; refuse here with prose, rather than letting
        # the raw bundle-load exception escape.
        _assert_login_precondition(
            resolved_settings,
            provider_kind,
            certificate_credentials=certificate_credentials,
        )

        from ...domain.buckets.event import BucketEventType
        from ..workflow.persistence import workflow_state_repository

        bucket_id = snapshot.bucket_id
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        with _auth_mutation_span(settings=resolved_settings, bucket_id=bucket_id):
            repository = workflow_state_repository()
            _assert_auth_recovery_not_in_progress(repository.load())
            result = await ensure_authenticated_aeat_session(
                resolved_settings,
                kind=provider_kind,
                certificate_credentials=certificate_credentials,
                fresh=fresh,
                reset_lock=reset_lock,
                operation="operator-auth-login",
            )

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
        _append_bucket_event(
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


@contextmanager
def _revocation_storage_span(
    settings: Settings,
    *,
    target_bucket_id: str | None = None,
):
    """Enter the auth storage span, naming the unrevoked session when it refuses.

    Logout and reset revoke an AEAT session that lives as an encrypted row inside
    the profile's own store, so revoking it genuinely requires the profile to be
    unlocked -- there is no key-free half to perform first. The generic custody
    refusal tells the operator the profile is locked, which reads as a
    permissions problem and leaves the important fact unsaid: the session is
    still there and still usable. This narrows the message to say so.

    Only the span's own entry refusal is rewritten. A refusal raised by the
    operation running inside the span is a different failure and keeps its own
    message.
    """
    entered = False
    try:
        with _active_profile_storage_span(settings, target_bucket_id=target_bucket_id) as bucket_id:
            entered = True
            yield bucket_id
    except AuthOperationRequiresCustodySessionError as exc:
        if entered:
            raise
        raise AuthOperationRequiresCustodySessionError(
            translated_message="application.auth.operator.errors.revoke_requires_custody_session",
            context=exc.context,
        ) from exc


def logout_operator_auth(
    *,
    provider: str | None = None,
    all_providers: bool = False,
    target_bucket_id: str | None = None,
    settings: Settings | None = None,
) -> AuthLogoutResult:
    """Terminate persisted sessions while preserving provider configuration."""
    if settings is not None:
        with _revocation_storage_span(settings, target_bucket_id=target_bucket_id):
            return logout_operator_auth(
                provider=provider,
                all_providers=all_providers,
                target_bucket_id=target_bucket_id,
                settings=None,
            )
    resolved_settings = load_settings()
    with _revocation_storage_span(resolved_settings, target_bucket_id=target_bucket_id) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        from ..workflow.persistence import workflow_state_repository

        with _auth_mutation_span(settings=resolved_settings, bucket_id=bucket_id):
            repository = workflow_state_repository()
            started_at = now()

            def prepare(state: WorkflowState) -> WorkflowState:
                _assert_certificate_secret_mutation_not_in_progress(state)
                existing = state.auth.cleanup_intent
                if existing is not None:
                    assert_logout_request_matches(
                        existing,
                        provider=provider,
                        all_providers=all_providers,
                    )
                    return state
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=state.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                intent = build_auth_cleanup_intent(
                    settings=resolved_settings,
                    bucket_id=bucket_id,
                    auth=state.auth,
                    provider_ids=scope.provider_ids,
                    all_providers=all_providers,
                    operation_kind=AuthCleanupOperationKind.LOGOUT,
                    started_at=started_at,
                )
                if not auth_cleanup_intent_has_effects(intent):
                    return state
                return state.model_copy(
                    update={"auth": state.auth.model_copy(update={"cleanup_intent": intent})},
                )

            prepared = repository.update(prepare)
            intent = prepared.auth.cleanup_intent
            if intent is None:
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=prepared.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                return AuthLogoutResult(
                    bucket_id=bucket_id,
                    providers=scope.provider_ids,
                    removed_sessions=0,
                    cleared_session_state=False,
                )
            delete_scoped_sessions(
                resolved_settings,
                intent.session_provider_ids,
                bucket_id=bucket_id,
            )
            operation_id = intent.operation_id
            operation_started_at = intent.started_at

            def finalize(state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                current_intent = state.auth.cleanup_intent
                if current_intent is None:
                    return state, ()
                if current_intent.operation_id != operation_id:
                    raise RuntimeError("auth cleanup intent changed during a serialized logout")
                clears_current = (
                    state.auth.provider in intent.provider_ids
                    and state.auth.provider == intent.provider_at_start
                    and state.auth.configured_at == intent.configured_at_at_start
                    and state.auth.authenticated_at == intent.authenticated_at_at_start
                )
                cleared_auth = state.auth.model_copy(
                    update={
                        **({"authenticated_at": None, "subject": None} if clears_current else {}),
                        "cleanup_intent": None,
                    },
                )
                clears_session_state = clears_current and intent.had_session_state
                event_provider_ids = tuple(
                    dict.fromkeys(
                        (
                            *((state.auth.provider,) if clears_session_state and state.auth.provider else ()),
                            *intent.session_provider_ids,
                        ),
                    ),
                )
                updated = _append_bucket_events(
                    state.model_copy(update={"auth": cleared_auth}),
                    tuple(("auth.session.cleared", provider_id) for provider_id in event_provider_ids),
                )
                from ...domain.buckets.event import BucketEventType

                durable_events = tuple(
                    _BucketEventSpec(
                        BucketEventType.AUTH_SESSION_CLEARED,
                        provider_id,
                        {
                            "provider_id": provider_id,
                            "operation": "logout",
                            "operation_id": operation_id,
                        },
                        operation_started_at,
                    )
                    for provider_id in event_provider_ids
                )
                if not durable_events:
                    return updated, ()
                return updated, _build_bucket_events(
                    bucket_id=bucket_id,
                    events=durable_events,
                )

            finalized = repository.update_with_bucket_events(finalize)
            cleared_session_state = (
                intent.had_session_state
                and finalized.auth.provider == intent.provider_at_start
                and finalized.auth.authenticated_at is None
                and finalized.auth.subject is None
            )
    return AuthLogoutResult(
        bucket_id=intent.bucket_id,
        providers=intent.provider_ids,
        removed_sessions=len(intent.session_provider_ids),
        cleared_session_state=cleared_session_state,
    )


def reset_operator_auth(
    *,
    provider: str | None = None,
    all_providers: bool = False,
    target_bucket_id: str | None = None,
    settings: Settings | None = None,
) -> AuthResetResult:
    """Remove auth custody through one durable, resumable reset operation."""
    if settings is not None:
        with _revocation_storage_span(settings, target_bucket_id=target_bucket_id):
            return reset_operator_auth(
                provider=provider,
                all_providers=all_providers,
                target_bucket_id=target_bucket_id,
                settings=None,
            )
    resolved_settings = load_settings()
    with _revocation_storage_span(resolved_settings, target_bucket_id=target_bucket_id) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        from ..workflow.persistence import workflow_state_repository

        with _auth_mutation_span(settings=resolved_settings, bucket_id=bucket_id):
            repository = workflow_state_repository()
            started_at = now()

            def prepare(state: WorkflowState) -> WorkflowState:
                _assert_certificate_secret_mutation_not_in_progress(state)
                existing = state.auth.cleanup_intent
                if existing is not None:
                    assert_reset_request_matches(
                        existing,
                        provider=provider,
                        all_providers=all_providers,
                    )
                    return state
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=state.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                intent = build_auth_cleanup_intent(
                    settings=resolved_settings,
                    bucket_id=bucket_id,
                    auth=state.auth,
                    provider_ids=scope.provider_ids,
                    all_providers=all_providers,
                    operation_kind=AuthCleanupOperationKind.RESET,
                    started_at=started_at,
                )
                if not auth_cleanup_intent_has_effects(intent):
                    return state
                return state.model_copy(
                    update={"auth": state.auth.model_copy(update={"cleanup_intent": intent})},
                )

            prepared = repository.update(prepare)
            intent = prepared.auth.cleanup_intent
            if intent is None:
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=prepared.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                return AuthResetResult(
                    bucket_id=bucket_id,
                    providers=scope.provider_ids,
                    removed_sessions=0,
                    cleared_provider_configuration=False,
                    cleared_locks=0,
                    removed_certificate_sources=0,
                    removed_certificate_secrets=0,
                )

            delete_scoped_sessions(
                resolved_settings,
                intent.session_provider_ids,
                bucket_id=bucket_id,
            )
            # `auth reset` keeps its existing clearance for now. The ruling that
            # produced the held-lock refusal flagged this caller too -- the
            # profile survives here, so nothing compensates for an aborted
            # acquisition -- but the operator decision taken covered the
            # `login --reset-lock` path only, and widening it unasked would
            # change a second verb's behaviour on the strength of an inference.
            clear_scoped_locks(
                resolved_settings,
                intent.lock_provider_ids,
                bucket_id=bucket_id,
                allow_held=True,
            )
            delete_certificate_source_secrets(
                bucket_id,
                intent.secret_source_names,
            )

            final_effects: dict[str, tuple[str, ...]] = {}

            def finalize(state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                current_intent = state.auth.cleanup_intent
                if current_intent is None:
                    return state, ()
                if current_intent.operation_id != intent.operation_id:
                    raise RuntimeError("auth reset intent changed during a serialized reset")
                reset_auth, provider_ids, certificate_names = apply_auth_cleanup_intent(
                    state.auth,
                    intent,
                )
                final_effects["provider_ids"] = provider_ids
                final_effects["certificate_names"] = certificate_names
                workflow_events: list[tuple[str, str]] = []
                workflow_events.extend(("auth.provider.cleared", provider_id) for provider_id in provider_ids)
                workflow_events.extend(
                    ("auth.session.cleared", provider_id) for provider_id in intent.session_provider_ids
                )
                workflow_events.extend(("auth.lock.cleared", provider_id) for provider_id in intent.lock_provider_ids)
                workflow_events.extend(("auth.certificate_source.removed", name) for name in certificate_names)
                updated = _append_bucket_events(
                    state.model_copy(update={"auth": reset_auth}),
                    tuple(workflow_events),
                )
                durable_events = auth_cleanup_bucket_events(
                    intent=intent,
                    provider_ids=provider_ids,
                    certificate_names=certificate_names,
                )
                if not durable_events:
                    return updated, ()
                return updated, _build_bucket_events(
                    bucket_id=bucket_id,
                    events=durable_events,
                )

            repository.update_with_bucket_events(finalize)
            cleared_provider_ids = final_effects.get("provider_ids", ())
            removed_source_names = final_effects.get("certificate_names", ())
    return AuthResetResult(
        bucket_id=intent.bucket_id,
        providers=intent.provider_ids,
        removed_sessions=len(intent.session_provider_ids),
        cleared_provider_configuration=bool(cleared_provider_ids or removed_source_names),
        cleared_locks=len(intent.lock_provider_ids),
        removed_certificate_sources=len(removed_source_names),
        removed_certificate_secrets=len(intent.secret_source_names),
    )


def _assert_login_precondition(
    settings: Settings,
    provider_kind: AuthProviderKind,
    *,
    certificate_credentials: ActiveCertificateCredentials | None = None,
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
        credentials = probe_clave_credentials(provider_kind, settings=settings)
        if credentials is None or not credentials.dni_nie:
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


def _append_bucket_event(
    state: WorkflowState,
    *,
    action: str,
    object_id: str,
) -> WorkflowState:
    from ..workflow.review_models import WorkflowEvent

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


__all__ = [
    "build_live_auth_preflight_report",
    "configure_operator_auth",
    "inspect_operator_auth",
    "list_operator_auth_providers",
    "login_operator_auth",
    "logout_operator_auth",
    "reset_operator_auth",
    "test_operator_auth",
]
