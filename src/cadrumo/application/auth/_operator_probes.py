"""Local auth provider and persisted-session probes for operator services.

The local probe path classifies :class:`AuthProviderKind` configuration with
:class:`ProviderProbeResult` values and reuses persisted-session metadata via
:func:`load_persisted_session`.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import AuthProviderKind
from ...core.config import Settings, load_settings, unwrap_optional_secret
from ...core.errors import CadrumoError
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from ..auth_credentials import (
    ActiveCertificateCredentials,
    unnamed_certificate_credentials,
)
from ._operator_scope import active_profile_storage_span
from ._sessions import load_persisted_session

_log = get_logger(__name__)

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def _live_auth_identity_state(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
    state: WorkflowState | None = None,
) -> tuple[bool, bool, str]:
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return False, provider_kind is AuthProviderKind.CERTIFICATE, "not_applicable"
    try:
        from ..user_profile import record_to_path_values
        from ..workflow import workflow_state_repository

        resolved_state = state if state is not None else workflow_state_repository().load()
        record = resolved_state.active_profile_record()
        values = record_to_path_values(record) if record is not None else {}
        profile_tax_id = (values.get("identity.tax_id") or "").strip().upper()
    except (OSError, CadrumoError, AttributeError, LookupError):
        _log.debug("profile tax-id probe failed; treating as empty", exc_info=True)
        profile_tax_id = ""
    provider_identity = unwrap_optional_secret(settings.cadrumo_clave_movil_dni_nie).strip().upper()
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
    return bool(profile_tax_id), bool(provider_identity), alignment


def _live_auth_identity_kind(provider_kind: AuthProviderKind | None, *, settings: Settings) -> str:
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return ""
    from ...adapters.outbound.aeat.auth import ClaveMovilConfigurationError, classify_identity

    identity = unwrap_optional_secret(settings.cadrumo_clave_movil_dni_nie).strip()
    try:
        return classify_identity(identity)
    except ClaveMovilConfigurationError:
        return "invalid_or_missing"


def _live_auth_mode(provider_kind: AuthProviderKind | None, *, settings: Settings) -> str:
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


def _probe_local_session(provider: str, *, settings: Settings | None = None) -> _LocalSessionProbe:
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


class ProviderProbeResult(StrEnum):
    """Canonical result codes returned by the per-provider local probe."""

    NO_PROVIDER = "no_provider"
    NO_PATH_SET = "no_path_set"
    FILE_MISSING = "file_missing"
    UNREADABLE = "unreadable"
    CORRUPT = "corrupt"
    EXPIRED = "expired"
    EXPIRING = "expiring"
    OK = "ok"
    IDENTITY_UNSET = "identity_unset"
    INVALID_IDENTITY = "invalid_identity"


class _ProviderProbeOutcome(BaseModel):
    """Verdict of the per-provider local probe run by ``auth test``."""

    model_config = _STRICT_FROZEN

    result: ProviderProbeResult | str = ""
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
    result: ProviderProbeResult | str = ""
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
        return _probe_certificate_bundle(
            certificate_path,
            settings=settings,
            certificate_credentials=certificate_credentials,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return _probe_clave_movil_identity(settings=settings)
    return _ProviderProbeOutcome()


def _probe_certificate_bundle(
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
    from ...adapters.outbound.aeat.auth.certificate import (
        CertificateError,
        CertificateHealthSeverity,
    )
    from ...adapters.outbound.aeat.auth.certificate import (
        health as evaluate_certificate_health,
    )

    resolved_settings = settings or load_settings()
    credentials = certificate_credentials or unnamed_certificate_credentials(resolved_settings)
    configured_certificate_path = credentials.certificate_path
    raw = (certificate_path or "").strip() or (
        str(configured_certificate_path) if configured_certificate_path is not None else ""
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


def _probe_clave_movil_identity(*, settings: Settings | None = None) -> _ProviderProbeOutcome:
    """Classify the configured Cl@ve Móvil DNI/NIE through the real classifier.

    A well-formed identity surfaces as ``ok``; a malformed identity as
    ``invalid_identity``; an unset identity as ``identity_unset``. The
    probe never contacts AEAT — it validates the local configuration.
    """
    from ...adapters.outbound.aeat.auth import ClaveMovilConfigurationError, classify_identity

    resolved_settings = settings or load_settings()
    raw = unwrap_optional_secret(resolved_settings.cadrumo_clave_movil_dni_nie).strip()
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
