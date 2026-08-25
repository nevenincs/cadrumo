"""Local auth provider and persisted-session probes for operator services.

The local probe path classifies :class:`AuthProviderKind` configuration with
:class:`ProviderProbeResult` values and reuses persisted-session metadata via
:func:`load_persisted_session`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...adapters.persistence.storage import has_active_bucket_session
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import AuthProviderKind
from ...core.config import Settings, load_settings
from ...core.errors import CadrumoError
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from ..auth_credentials import (
    ActiveCertificateCredentials,
    unnamed_certificate_credentials,
)
from .operator_scope import active_profile_storage_span
from .probes import ProviderProbeResult
from .sessions import (
    ClaveCredentials,
    bind_clave_credentials_to_settings,
    clave_auth_facts_from_profile_values,
    load_persisted_session,
    resolve_clave_credentials,
)

_log = get_logger(__name__)

if TYPE_CHECKING:
    from cadrumo.application.workflow.state_models import WorkflowState

    from ...adapters.outbound.aeat.auth.certificate import CertificateHealth


def classify_identity_alignment(profile_tax_id: str, provider_identity: str) -> str:
    """Classify a Cl@ve Móvil identity against the active profile tax id.

    The single home for the five-way alignment ladder shared by the live
    identity-state probe and ``_auth_configure_result``. Inputs are the
    already-normalised (stripped, upper-cased) tax id and provider identity.
    """
    if not profile_tax_id and not provider_identity:
        return "profile_tax_id_missing_and_clave_identity_missing"
    if not profile_tax_id:
        return "profile_tax_id_missing"
    if not provider_identity:
        return "clave_identity_missing"
    if profile_tax_id == provider_identity:
        return "matches"
    return "mismatch"


def _active_profile_path_values(state: WorkflowState | None = None) -> dict[str, str]:
    """Return the active profile's schema-path values, empty when unreadable.

    A readiness probe answers questions like "is auth configured" and the
    operator must be able to ask them before unlocking anything, so the
    absence of a bucket session is an ordinary state here rather than a
    fault. The session is checked before the read is attempted: the
    encrypted store raises through its SQL layer, which wraps the refusal
    in a driver exception that no domain-level except clause would catch,
    so declining the doomed read is what keeps the probe answerable.
    """
    if state is None and not has_active_bucket_session():
        return {}
    try:
        from cadrumo.application.workflow.persistence import workflow_state_repository

        from ..user_profile.projections import record_to_path_values

        resolved_state = state if state is not None else workflow_state_repository().load()
        record = resolved_state.active_profile_record()
        return dict(record_to_path_values(record)) if record is not None else {}
    except (OSError, CadrumoError, AttributeError, LookupError):
        _log.debug("active profile read failed during an auth probe; treating as empty", exc_info=True)
        return {}


def probe_clave_credentials(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
    state: WorkflowState | None = None,
) -> ClaveCredentials | None:
    """Resolve the credentials a readiness probe should report on.

    Routes through the same resolver the live session entry uses, so a
    surface cannot report a credential as unconfigured that the session
    entry would authenticate with. Unlike the session entry this never
    refuses: an absent credential is the state being reported, not a
    fault.
    """
    if provider_kind is None:
        return None
    return resolve_clave_credentials(
        provider_kind,
        settings=settings,
        facts=clave_auth_facts_from_profile_values(_active_profile_path_values(state)),
    )


def bind_profile_auth_settings(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
    state: WorkflowState | None = None,
) -> Settings:
    """Bind the profile credentials that the selected backend will actually use.

    Status and live authentication must construct a provider from the same
    effective settings. This uses the live session resolver and binder rather
    than reproducing their precedence rules in a readiness-only projection.
    """
    if provider_kind not in (AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE):
        return settings
    assert provider_kind is not None
    facts = clave_auth_facts_from_profile_values(_active_profile_path_values(state))
    credentials = resolve_clave_credentials(provider_kind, settings=settings, facts=facts)
    if credentials is None:
        return settings
    return bind_clave_credentials_to_settings(
        settings,
        credentials,
        route=facts.clave_movil_route,
    )


def live_auth_identity_state(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
    state: WorkflowState | None = None,
) -> tuple[bool, bool, str]:
    """Project whether the configured live-auth identity is usable."""
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return False, provider_kind is AuthProviderKind.CERTIFICATE, "not_applicable"
    values = _active_profile_path_values(state)
    facts = clave_auth_facts_from_profile_values(values)
    credentials = resolve_clave_credentials(provider_kind, settings=settings, facts=facts)
    provider_identity = credentials.dni_nie if credentials is not None else ""
    alignment = classify_identity_alignment(facts.tax_id, provider_identity)
    return bool(facts.tax_id), bool(provider_identity), alignment


def live_auth_identity_kind(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
    state: WorkflowState | None = None,
) -> str:
    """Return the safe identity-kind label for the configured provider."""
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return ""
    from ...adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilConfigurationError, classify_identity

    credentials = probe_clave_credentials(provider_kind, settings=settings, state=state)
    identity = credentials.dni_nie if credentials is not None else ""
    try:
        return classify_identity(identity)
    except ClaveMovilConfigurationError:
        return "invalid_or_missing"


def live_auth_mode(provider_kind: AuthProviderKind | None, *, settings: Settings) -> str:
    """Project the configured interactive mode without acquiring a session."""
    if provider_kind is AuthProviderKind.CLAVE_MOVIL:
        return "non_qr" if settings.cadrumo_clave_prefer_non_qr else "qr"
    if provider_kind is AuthProviderKind.CERTIFICATE:
        return "certificate"
    return ""


class _LocalSessionProbe(BaseModel):
    """Outcome of the on-disk persisted-session probe run by ``auth test``."""

    model_config = _STRICT_FROZEN

    present: bool = False
    expired: bool | None = None
    state: str = ""
    summary: str = ""


def probe_local_session(provider: str, *, settings: Settings | None = None) -> _LocalSessionProbe:
    """Inspect the persisted AEAT session token for ``provider`` on disk.

    A pure local read — it never opens a browser or contacts AEAT. It
    answers the question ``auth status`` cannot: is there actually a
    usable session token on disk for this provider right now.
    """
    if not provider:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            state="no_provider",
            summary=tr("application.auth.operator.probe.no_provider"),
        )
    try:
        kind = AuthProviderKind(provider)
    except ValueError:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            state="no_provider",
            summary=tr("application.auth.operator.probe.no_provider"),
        )

    resolved_settings = settings or load_settings()
    try:
        with active_profile_storage_span(resolved_settings):
            session = load_persisted_session(resolved_settings, kind)
    except (CadrumoError, OSError):
        _log.debug("local auth session probe failed; treating persisted session as absent", exc_info=True)
        session = None
    if session is None:
        return _LocalSessionProbe(
            present=False,
            expired=None,
            state="no_session",
            summary=tr("application.auth.operator.probe.no_session"),
        )
    expired = session.is_expired(now())
    if expired:
        state = "expired"
        summary = tr("application.auth.operator.probe.session_expired")
    else:
        state = "live"
        summary = tr("application.auth.operator.probe.session_live")
    return _LocalSessionProbe(
        present=True,
        expired=expired,
        state=state,
        summary=summary,
    )


class _ProviderProbeOutcome(BaseModel):
    """Verdict of the per-provider local probe run by ``auth test``."""

    model_config = _STRICT_FROZEN

    result: ProviderProbeResult
    summary: str = ""
    days_until_expiry: int | None = None


class ProviderConfigurationProbe(BaseModel):
    """Public per-provider local configuration readiness verdict.

    Wraps the pure-local :func:`probe_provider_credentials` (no network,
    no active-profile requirement) so the workstation doctor
    (``aeat config check``) can render one certificate / Cl@ve Móvil
    readiness row per :class:`core.AuthProviderKind`
    directly from :class:`core.config.Settings`. ``result`` is the
    typed :class:`ProviderProbeResult`; ``summary`` is the localised
    one-line operator-facing verdict.
    """

    model_config = _STRICT_FROZEN

    provider: str
    result: ProviderProbeResult
    summary: str = ""


def probe_provider_configuration(
    provider: str,
    *,
    settings: Settings | None = None,
) -> ProviderConfigurationProbe:
    """Run the pure-local per-provider configuration probe for ``provider``.

    Resolves the certificate path or Cl@ve Móvil identity from
    :class:`core.config.Settings` and classifies the local
    configuration health without any network call or active-profile
    session. Returns a typed :class:`ProviderConfigurationProbe`; it
    never raises for a missing or malformed configuration — an absent
    provider surfaces as :attr:`ProviderProbeResult.NO_PATH_SET` /
    :attr:`ProviderProbeResult.IDENTITY_UNSET`, a broken one as
    ``expired`` / ``corrupt`` / ``invalid_identity``.
    """
    resolved_settings = settings or load_settings()
    credentials = (
        unnamed_certificate_credentials(resolved_settings) if provider == AuthProviderKind.CERTIFICATE.value else None
    )
    return probe_provider_credentials(
        provider,
        "",
        settings=resolved_settings,
        certificate_credentials=credentials,
    )


def probe_provider_credentials(
    provider: str,
    certificate_path: str,
    *,
    settings: Settings | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> ProviderConfigurationProbe:
    """Probe one provider using the caller's already-resolved credential snapshot."""
    outcome = _probe_configured_provider(
        provider,
        certificate_path,
        settings=settings,
        certificate_credentials=certificate_credentials,
    )
    return ProviderConfigurationProbe(
        provider=provider,
        result=outcome.result,
        summary=outcome.summary,
    )


def _probe_configured_provider(
    provider: str,
    certificate_path: str,
    *,
    settings: Settings | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> _ProviderProbeOutcome:
    """Run a real per-provider local probe and return a typed verdict.

    For the certificate provider this opens the ``.p12`` file, parses
    the PKCS#12 envelope, and surfaces the bundle's expiry health. For
    Cl@ve Móvil the configured DNI/NIE is classified through the real
    identity classifier. No network call is made; the probe is a pure
    local readiness check (round-5 M4).
    """
    if not provider:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.NO_PROVIDER,
            summary=tr("application.auth.operator.probe.no_provider"),
        )
    try:
        kind = AuthProviderKind(provider)
    except ValueError:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.NO_PROVIDER,
            summary=tr("application.auth.operator.probe.no_provider"),
        )

    if kind is AuthProviderKind.CERTIFICATE:
        return probe_certificate_bundle(
            certificate_path,
            settings=settings,
            certificate_credentials=certificate_credentials,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return _probe_clave_movil_identity(settings=settings)
    return _ProviderProbeOutcome(
        result=ProviderProbeResult.NO_PROVIDER,
        summary=tr("application.auth.operator.probe.no_provider"),
    )


def _resolved_probe_certificate_path(
    certificate_path: str,
    *,
    configured_certificate_path: Path | None,
) -> str:
    """Resolve the effective probe path: the caller's argument, else the configured path."""
    return (certificate_path or "").strip() or (
        str(configured_certificate_path) if configured_certificate_path is not None else ""
    )


def _classify_bundle_health(bundle_health: CertificateHealth) -> _ProviderProbeOutcome:
    """Map a certificate-bundle health verdict to its probe outcome.

    ``EXPIRED`` classifies an already-lapsed bundle distinctly from a
    ``CRITICAL``/``WARN`` expiring one; every other severity is ``ok``.
    """
    from ...adapters.outbound.aeat.auth.certificate import CertificateHealthSeverity

    severity = bundle_health.severity
    if severity is CertificateHealthSeverity.EXPIRED:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.EXPIRED,
            summary=tr(
                "application.auth.operator.probe.certificate_expired",
                days=abs(bundle_health.days_until_expiry),
            ),
            days_until_expiry=bundle_health.days_until_expiry,
        )
    if severity is CertificateHealthSeverity.CRITICAL or severity is CertificateHealthSeverity.WARN:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.EXPIRING,
            summary=tr(
                "application.auth.operator.probe.certificate_expiring",
                days=bundle_health.days_until_expiry,
            ),
            days_until_expiry=bundle_health.days_until_expiry,
        )
    return _ProviderProbeOutcome(
        result=ProviderProbeResult.OK,
        summary=tr(
            "application.auth.operator.probe.certificate_ok",
            days=bundle_health.days_until_expiry,
        ),
        days_until_expiry=bundle_health.days_until_expiry,
    )


def probe_certificate_bundle(
    certificate_path: str,
    *,
    settings: Settings | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> _ProviderProbeOutcome:
    """Open the configured ``.p12`` and classify the certificate's health.

    Resolves the three certificate-state cases distinctly: no path,
    path-set-file-missing, path-set-file-present. The file-present case
    additionally opens the bundle and inspects expiry through
    :func:`adapters.outbound.aeat.auth.certificate.health`, which
    reports :attr:`~adapters.outbound.aeat.auth.certificate.CertificateHealthSeverity.EXPIRED`
    for an already-lapsed certificate rather than raising — an expired
    but otherwise well-formed bundle must classify as ``expired``, never
    ``corrupt``.
    """
    from ...adapters.outbound.aeat.auth.certificate import CertificateError
    from ...adapters.outbound.aeat.auth.certificate import (
        health as evaluate_certificate_health,
    )

    resolved_settings = settings or load_settings()
    credentials = certificate_credentials or unnamed_certificate_credentials(resolved_settings)
    raw = _resolved_probe_certificate_path(
        certificate_path,
        configured_certificate_path=credentials.certificate_path,
    )
    if not raw:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.NO_PATH_SET,
            summary=tr("application.auth.operator.probe.certificate_path_unset"),
        )
    path = Path(raw)
    if not path.is_file():
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.FILE_MISSING,
            summary=tr(
                "application.auth.operator.probe.certificate_file_missing",
                path=str(path),
            ),
        )
    try:
        path.read_bytes()
    except OSError as exc:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.UNREADABLE,
            summary=tr(
                "application.auth.operator.probe.certificate_unreadable",
                error=type(exc).__name__,
            ),
        )
    password = credentials.password
    if password is None:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.CORRUPT,
            summary=tr("application.auth.operator.probe.certificate_corrupt"),
        )
    try:
        bundle_health = evaluate_certificate_health(
            path,
            password=password,
            warn_days=resolved_settings.cadrumo_cert_warn_days,
            critical_days=resolved_settings.cadrumo_cert_critical_days,
            friendly_name=credentials.friendly_name,
        )
    except CertificateError as exc:
        _log.warning("certificate load failed; treating bundle as unparseable", exc_info=True)
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.CORRUPT,
            summary=tr(
                "application.auth.operator.probe.certificate_corrupt_detail",
                error=str(exc),
            ),
        )
    return _classify_bundle_health(bundle_health)


def _probe_clave_movil_identity(*, settings: Settings | None = None) -> _ProviderProbeOutcome:
    """Classify the configured Cl@ve Móvil DNI/NIE through the real classifier.

    A well-formed identity surfaces as ``ok``; a malformed identity as
    ``invalid_identity``; an unset identity as ``identity_unset``. The
    probe never contacts AEAT — it validates the local configuration.
    """
    from ...adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilConfigurationError, classify_identity

    resolved_settings = settings or load_settings()
    credentials = probe_clave_credentials(AuthProviderKind.CLAVE_MOVIL, settings=resolved_settings)
    raw = credentials.dni_nie if credentials is not None else ""
    if not raw:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.IDENTITY_UNSET,
            summary=tr("application.auth.operator.probe.clave_movil_identity_unset"),
        )
    try:
        classify_identity(raw)
    except ClaveMovilConfigurationError as exc:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.INVALID_IDENTITY,
            summary=tr(
                "application.auth.operator.probe.clave_movil_identity_invalid",
                error=str(exc),
            ),
        )
    return _ProviderProbeOutcome(
        result=ProviderProbeResult.OK,
        summary=tr("application.auth.operator.probe.clave_movil_identity_ok"),
    )


__all__ = [
    "ProviderConfigurationProbe",
    "bind_profile_auth_settings",
    "classify_identity_alignment",
    "live_auth_identity_kind",
    "live_auth_identity_state",
    "live_auth_mode",
    "probe_certificate_bundle",
    "probe_clave_credentials",
    "probe_local_session",
    "probe_provider_configuration",
    "probe_provider_credentials",
]
