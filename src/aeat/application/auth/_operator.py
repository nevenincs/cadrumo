"""Operator-facing auth application services for the config CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core.config import Settings
from ...core.errors import AeatError
from ...core.i18n import tr
from . import AuthProviderKind
from ._acquisition_lock import clear_auth_acquisition_lock
from ._actions import update_auth
from ._catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from ._models import AuthState
from ._sessions import (
    delete_persisted_session,
    ensure_authenticated_aeat_session,
    load_persisted_session,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth.certificate import LoadedCertificate
    from ..state_projection import OperatorStateProjection
    from ..workflow._models import WorkflowState
    from ..workflow._persistence import WorkflowStateRepository


class AuthProviderReservedError(AeatError, ValueError):
    """Raised when a known provider slot is reserved but not implemented."""


class AuthProvidersReport(BaseModel):
    """Auth provider catalogue projected for operator output."""

    model_config = _STRICT_FROZEN

    providers: tuple[AuthProviderListing, ...]


class AuthConfigureResult(BaseModel):
    """Result of configuring an auth provider in workflow state.

    ``complete`` reports whether the provider is now operationally
    usable. The certificate provider configured without a resolvable
    ``--file`` records the provider selection but is NOT operationally
    ready: ``complete`` is ``False`` and ``incomplete_reason`` states a
    certificate path is still required. The operator must never be told
    "configured" when the provider cannot yet be used.
    """

    model_config = _STRICT_FROZEN

    provider: str
    file: str = ""
    complete: bool = True
    incomplete_reason: str = ""
    active_profile: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_alignment_detail: str = ""
    next_action: str = ""


class AuthStatusResult(BaseModel):
    """Current local auth readiness state."""

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    active_profile_next_action: str = ""
    backend_configured: bool = False
    backend_available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""


class AuthTestResult(AuthStatusResult):
    """Auth readiness plus a deeper local readiness probe.

    ``auth status`` is a pure read of the canonical state projection.
    ``auth test`` carries every field ``auth status`` does — so the two
    can never disagree on ``configured`` — and runs a real per-provider
    local probe. For the certificate provider the probe opens the
    ``.p12`` file, parses the PKCS#12 envelope, classifies the bundle
    health (``ok`` / ``expired`` / ``expiring`` / ``corrupt`` /
    ``unreadable``), and surfaces the verdict as ``probe_result``. For
    Cl@ve Móvil the probe classifies the configured DNI/NIE through the
    real identity classifier and reports ``ok`` / ``invalid_identity`` /
    ``identity_unset``. The persisted-session inspection ``auth status``
    cannot perform — does an encrypted AEAT session token exist on disk
    and is it still within its idle deadline — is also reported here
    (round-3 G5 + round-5 M4).

    Attributes:
        persisted_session_present: Whether an encrypted AEAT session
            token is on disk for the probed provider.
        persisted_session_expired: Whether that token has passed its
            idle deadline; ``None`` when no token is present.
        probe_summary: A one-line operator-facing verdict of the local
            probe.
        probe_result: A typed verdict of the per-provider probe. Values
            include ``ok``, ``expired``, ``expiring``, ``corrupt``,
            ``unreadable``, ``invalid_identity``, ``identity_unset``,
            ``no_path_set``, ``file_missing``, ``no_provider``. Empty
            only when no provider could be resolved.
    """

    model_config = _STRICT_FROZEN

    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    probe_summary: str = ""
    probe_result: str = ""


class AuthLoginResult(BaseModel):
    """Result of an operator-triggered live authentication attempt."""

    model_config = _STRICT_FROZEN

    provider: str
    authenticated: bool
    reused_persisted_session: bool
    fresh: bool
    removed_sessions: int
    acquired_lock: bool
    reset_lock_state: str = ""
    verification_status: str = ""


class AuthClearResult(BaseModel):
    """Result of clearing local auth metadata and persisted state."""

    model_config = _STRICT_FROZEN

    removed_sessions: int
    cleared_workflow_state: bool
    cleared_locks: int


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return implemented and reserved auth provider slots."""

    return AuthProvidersReport(providers=list_auth_providers())


class AuthConfigureNoActiveBucketError(AeatError):
    """Raised when ``configure_operator_auth`` runs before an active profile bucket exists.

    The bucket-event-history ADR requires every event to be scoped to a
    bucket id. Provider configuration must happen after
    ``aeat config profile create NAME`` has activated a profile bucket; running before
    that point would either leave a silent audit hole or require deferred
    replay, both of which the ADR refuses. Surfacing the refusal here
    keeps the bootstrap contract explicit at the CLI surface.
    """


class AuthConfigureDanglingActiveProfileError(AeatError, ValueError):
    """Raised when the active-profile pointer does not resolve to a registered bucket."""


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

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet. The operator must run ``aeat config profile create NAME`` first.
    """

    from datetime import UTC, datetime

    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ..workflow._models import resolve_active_bucket_id
    from ..workflow._persistence import workflow_state_repository
    from ..workflow._profile_health import assess_active_profile_health

    listing = _implemented_provider(provider)

    if resolve_active_bucket_id() is None:
        raise AuthConfigureNoActiveBucketError(
            tr("application.auth.operator.errors.no_active_bucket"),
        )
    state_repo = workflow_state_repository()
    current_state = state_repo.load()
    profile_health = assess_active_profile_health(current_state)
    active_bucket_id = profile_health.active_profile
    if active_bucket_id is None:
        raise AuthConfigureNoActiveBucketError(
            tr("application.auth.operator.errors.no_active_bucket"),
        )
    if profile_health.status == "dangling_pointer":
        raise AuthConfigureDanglingActiveProfileError(
            tr(
                "application.auth.operator.errors.dangling_active_profile",
                active_profile=active_bucket_id,
            )
        )
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        raise AuthConfigureDanglingActiveProfileError(
            tr(
                "application.auth.operator.errors.unreadable_active_profile",
                active_profile=active_bucket_id,
                status=profile_health.status,
                next_action=profile_health.next_action,
            )
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

    occurred_at = datetime.now(UTC)
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
    """Return current local auth state, optionally scoped to a known provider slot.

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
    settings = Settings()
    provider_identity = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        provider_identity = (settings.aeat_clave_movil_dni_nie or "").strip().upper()
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


def test_operator_auth(provider: str | None = None) -> AuthTestResult:
    """Return auth readiness plus a deeper local session-token probe.

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
    session_probe = _probe_local_session(status.provider)
    provider_probe = _probe_configured_provider(status.provider, status.certificate_path)
    return AuthTestResult(
        **status.model_dump(),
        persisted_session_present=session_probe.present,
        persisted_session_expired=session_probe.expired,
        probe_summary=provider_probe.summary or session_probe.summary,
        probe_result=provider_probe.result,
    )


class _LocalSessionProbe(BaseModel):
    """Outcome of the on-disk persisted-session probe run by ``auth test``."""

    model_config = _STRICT_FROZEN

    present: bool = False
    expired: bool | None = None
    summary: str = ""


def _probe_local_session(provider: str) -> _LocalSessionProbe:
    """Inspect the persisted AEAT session token for ``provider`` on disk.

    A pure local read — it never opens a browser or contacts AEAT. It
    answers the question ``auth status`` cannot: is there actually a
    usable session token on disk for this provider right now.
    """

    if not provider:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            summary=tr("application.auth.operator.probe.no_provider"),
        )
    try:
        kind = AuthProviderKind(provider)
    except ValueError:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            summary=tr("application.auth.operator.probe.no_provider"),
        )
    from datetime import UTC, datetime

    session = load_persisted_session(Settings(), kind)
    if session is None:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            summary=tr("application.auth.operator.probe.no_session"),
        )
    expired = session.is_expired(datetime.now(UTC))
    if expired:
        summary = tr("application.auth.operator.probe.session_expired")
    else:
        summary = tr("application.auth.operator.probe.session_live")
    return _LocalSessionProbe(
        present=True,
        expired=expired,
        summary=summary,
    )


class _ProviderProbeOutcome(BaseModel):
    """Verdict of the per-provider local probe run by ``auth test``."""

    model_config = _STRICT_FROZEN

    result: str = ""
    summary: str = ""


def _probe_configured_provider(provider: str, certificate_path: str) -> _ProviderProbeOutcome:
    """Run a real per-provider local probe and return a typed verdict.

    For the certificate provider this opens the ``.p12`` file, parses
    the PKCS#12 envelope, and surfaces the bundle's expiry health. For
    Cl@ve Móvil the configured DNI/NIE is classified through the real
    identity classifier. No network call is made; the probe is a pure
    local readiness check (round-5 M4).
    """

    if not provider:
        return _ProviderProbeOutcome(
            result="no_provider",
            summary=tr("application.auth.operator.probe.no_provider"),
        )
    try:
        kind = AuthProviderKind(provider)
    except ValueError:
        return _ProviderProbeOutcome(
            result="no_provider",
            summary=tr("application.auth.operator.probe.no_provider"),
        )

    if kind is AuthProviderKind.CERTIFICATE:
        return _probe_certificate_bundle(certificate_path)
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return _probe_clave_movil_identity()
    return _ProviderProbeOutcome()


def _probe_certificate_bundle(certificate_path: str) -> _ProviderProbeOutcome:
    """Open the configured ``.p12`` and classify the certificate's health.

    Resolves the three certificate-state cases distinctly: no path,
    path-set-file-missing, path-set-file-present. The file-present case
    additionally opens the bundle and inspects expiry through the
    health classifier so the probe distinguishes a corrupt envelope
    from an expired-but-readable certificate.
    """

    from ...adapters.outbound.aeat.auth.certificate import (
        CertificateError,
        CertificateHealthSeverity,
        evaluate_loaded_certificate_health,
    )
    from ...core.config import Settings

    settings = Settings()
    raw = (certificate_path or "").strip() or (
        str(settings.aeat_certificate_path) if settings.aeat_certificate_path is not None else ""
    )
    if not raw:
        return _ProviderProbeOutcome(
            result="no_path_set",
            summary=tr("application.auth.operator.probe.certificate_path_unset"),
        )
    path = Path(raw)
    if not path.is_file():
        return _ProviderProbeOutcome(
            result="file_missing",
            summary=tr(
                "application.auth.operator.probe.certificate_file_missing",
                path=str(path),
            ),
        )
    # Inspect the bundle without requiring the password: parse the
    # PKCS#12 envelope, derive expiry, and classify health. A wrong /
    # missing password surfaces as ``unreadable``; a malformed file
    # surfaces as ``corrupt``.
    try:
        bundle_bytes = path.read_bytes()
    except OSError as exc:
        return _ProviderProbeOutcome(
            result="unreadable",
            summary=tr(
                "application.auth.operator.probe.certificate_unreadable",
                error=type(exc).__name__,
            ),
        )
    loaded = _try_load_certificate_metadata(path, bundle_bytes, settings)
    if loaded is None:
        return _ProviderProbeOutcome(
            result="corrupt",
            summary=tr("application.auth.operator.probe.certificate_corrupt"),
        )
    try:
        health = evaluate_loaded_certificate_health(
            loaded,
            warn_days=settings.aeat_cert_warn_days,
            critical_days=settings.aeat_cert_critical_days,
        )
    except CertificateError as exc:
        return _ProviderProbeOutcome(
            result="corrupt",
            summary=tr(
                "application.auth.operator.probe.certificate_corrupt_detail",
                error=str(exc),
            ),
        )
    severity = health.severity
    if severity is CertificateHealthSeverity.EXPIRED:
        return _ProviderProbeOutcome(
            result="expired",
            summary=tr(
                "application.auth.operator.probe.certificate_expired",
                days=abs(health.days_until_expiry),
            ),
        )
    if severity is CertificateHealthSeverity.CRITICAL or severity is CertificateHealthSeverity.WARN:
        return _ProviderProbeOutcome(
            result="expiring",
            summary=tr(
                "application.auth.operator.probe.certificate_expiring",
                days=health.days_until_expiry,
            ),
        )
    return _ProviderProbeOutcome(
        result="ok",
        summary=tr(
            "application.auth.operator.probe.certificate_ok",
            days=health.days_until_expiry,
        ),
    )


def _try_load_certificate_metadata(
    path: Path,
    bundle_bytes: bytes,
    settings: Settings,
) -> "LoadedCertificate | None":
    """Parse the PKCS#12 envelope and return a :class:`LoadedCertificate` or ``None``.

    Returns ``None`` when the bundle cannot be parsed for any reason
    (wrong password, malformed envelope, unsupported encoding) so the
    caller can classify the failure as ``corrupt`` without surfacing
    a stack trace to the operator.
    """

    from ...adapters.outbound.aeat.auth.certificate import CertificateBundle, load_certificate

    del bundle_bytes  # the loader reads the file via the bundle path
    password = settings.aeat_certificate_password_secret
    if password is None:
        return None
    try:
        bundle = CertificateBundle(
            path=path,
            password=password,
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )
        return load_certificate(bundle)
    except Exception:
        return None


def _probe_clave_movil_identity() -> _ProviderProbeOutcome:
    """Classify the configured Cl@ve Móvil DNI/NIE through the real classifier.

    A well-formed identity surfaces as ``ok``; a malformed identity as
    ``invalid_identity``; an unset identity as ``identity_unset``. The
    probe never contacts AEAT — it validates the local configuration.
    """

    from ...adapters.outbound.aeat.auth._clave_movil import (
        ClaveMovilConfigurationError,
        _classify_identity,
    )

    raw = (Settings().aeat_clave_movil_dni_nie or "").strip()
    if not raw:
        return _ProviderProbeOutcome(
            result="identity_unset",
            summary=tr("application.auth.operator.probe.clave_movil_identity_unset"),
        )
    try:
        _classify_identity(raw)
    except ClaveMovilConfigurationError as exc:
        return _ProviderProbeOutcome(
            result="invalid_identity",
            summary=tr(
                "application.auth.operator.probe.clave_movil_identity_invalid",
                error=str(exc),
            ),
        )
    return _ProviderProbeOutcome(
        result="ok",
        summary=tr("application.auth.operator.probe.clave_movil_identity_ok"),
    )


class AuthLoginNotEnabledError(AeatError):
    """Raised when ``auth login`` is invoked without the live-tests safety gate enabled.

    ``aeat`` is a build / verify / export tool; live AEAT submission is
    permanently forbidden and live reads are gated behind
    ``AEAT_LIVE_TESTS_ENABLED=1``. Surfacing this refusal here, in user
    prose, replaces the raw engineering English that previously bubbled
    from the certificate-bundle precondition (round-5 B2).
    """


class AuthLoginPreconditionError(AeatError):
    """Raised when ``auth login`` cannot proceed because the configured provider is unusable.

    The error carries a localised, operator-facing message — never an
    env-var or class name (round-5 B2). Concrete cases include a
    certificate path that is unset, points at a missing file, or
    cannot be read at all.
    """


async def login_operator_auth(
    provider: str | None = None,
    *,
    fresh: bool = False,
    reset_lock: bool = False,
    target_url: str | None = None,
    settings: Settings | None = None,
) -> AuthLoginResult:
    """Acquire or verify a live AEAT session and persist backend auth state.

    Refuses with a localised, user-prose message — never a raw env-var
    or class name — when (a) the ``AEAT_LIVE_TESTS_ENABLED`` safety gate
    is off, or (b) the configured provider is locally incomplete
    (certificate path unset / file missing / unreadable). Round-5 B2.
    """

    resolved_settings = settings or Settings()
    provider_kind = _provider_kind_or_none(provider)
    if provider_kind is None:
        provider_kind = _configured_or_default_provider(resolved_settings)
    _implemented_provider(provider_kind.value)

    # The live-tests safety gate is the FIRST reason a non-live tool
    # refuses login, and must surface before any per-provider check.
    # The refusal text is user prose, never the env-var name.
    if resolved_settings.aeat_live_tests_enabled != "1":
        raise AuthLoginNotEnabledError(
            tr(
                "application.auth.operator.login.refused_live_tests_disabled",
                provider=provider_kind.value,
            )
        )

    # Provider-specific local-readiness preconditions. A certificate
    # provider with no path / a missing file / an unreadable bundle
    # cannot authenticate; refuse here with prose, rather than letting
    # the raw bundle-load exception escape.
    _assert_login_precondition(resolved_settings, provider_kind)

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
        )
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
    """Clear workflow auth state, persisted sessions, and acquisition locks."""

    provider_kind = _provider_kind_or_none(provider)
    resolved_settings = settings or Settings()
    removed_sessions: list[Path] = []
    session_event_count = 0
    if sessions or all_providers:
        removed_sessions = delete_persisted_session(resolved_settings, kind=None if all_providers else provider_kind)
        session_event_count = len(removed_sessions)

    cleared_locks = _clear_acquisition_locks(
        resolved_settings,
        provider_kind=provider_kind,
        all_providers=all_providers,
        locks_requested=locks,
    )

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
        if status.state.value != "absent":
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
            lambda current: _append_bucket_events(current.model_copy(update={"auth": AuthState()}), events)
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
                tr("application.auth.operator.login.refused_certificate_path_unset")
            )
        if not cert_path.is_file():
            raise AuthLoginPreconditionError(
                tr(
                    "application.auth.operator.login.refused_certificate_file_missing",
                    path=str(cert_path),
                )
            )
    if provider_kind is AuthProviderKind.CLAVE_MOVIL and not (
        settings.aeat_clave_movil_dni_nie or ""
    ).strip():
        raise AuthLoginPreconditionError(
            tr("application.auth.operator.login.refused_clave_movil_identity_unset")
        )


def _implemented_provider(provider: str) -> AuthProviderListing:
    listing = get_auth_provider(provider)
    if not listing.implemented:
        raise AuthProviderReservedError(provider)
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

    bucket_id = state.active_profile_bucket_id() or "default"
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
