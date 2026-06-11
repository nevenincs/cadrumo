"""Local auth provider and persisted-session probes for operator services."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.config import Settings, load_settings, unwrap_optional_secret
from ...core.errors import AeatError
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from . import AuthProviderKind
from ._operator_scope import active_profile_storage_span
from ._sessions import load_persisted_session

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth.certificate import LoadedCertificate

_log = get_logger(__name__)


def _live_auth_identity_state(
    provider_kind: AuthProviderKind | None,
    *,
    settings: Settings,
) -> tuple[bool, bool, str]:
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return False, provider_kind is AuthProviderKind.CERTIFICATE, "not_applicable"
    try:
        from ..user_profile._projections import record_to_path_values
        from ..workflow._persistence import workflow_state_repository

        record = workflow_state_repository().load().active_profile_record()
        values = record_to_path_values(record) if record is not None else {}
        profile_tax_id = (values.get("identity.tax_id") or "").strip().upper()
    except (OSError, AeatError, AttributeError, LookupError):
        _log.debug("profile tax-id probe failed; treating as empty", exc_info=True)
        profile_tax_id = ""
    provider_identity = unwrap_optional_secret(settings.aeat_clave_movil_dni_nie).strip().upper()
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
    from ...adapters.outbound.aeat.auth._clave_movil import (
        ClaveMovilConfigurationError,
        _classify_identity,
    )

    identity = unwrap_optional_secret(settings.aeat_clave_movil_dni_nie).strip()
    try:
        return _classify_identity(identity)
    except ClaveMovilConfigurationError:
        return "invalid_or_missing"


def _live_auth_mode(provider_kind: AuthProviderKind | None, *, settings: Settings) -> str:
    if provider_kind is AuthProviderKind.CLAVE_MOVIL:
        return "non_qr" if settings.aeat_clave_prefer_non_qr else "qr"
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
    except (AeatError, OSError):
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


def _probe_configured_provider(
    provider: str,
    certificate_path: str,
    *,
    settings: Settings | None = None,
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
        return _probe_certificate_bundle(certificate_path, settings=settings)
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return _probe_clave_movil_identity(settings=settings)
    return _ProviderProbeOutcome()


def _probe_certificate_bundle(
    certificate_path: str,
    *,
    settings: Settings | None = None,
) -> _ProviderProbeOutcome:
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

    resolved_settings = settings or load_settings()
    raw = (certificate_path or "").strip() or (
        str(resolved_settings.aeat_certificate_path) if resolved_settings.aeat_certificate_path is not None else ""
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
    # Inspect the bundle without requiring the password: parse the
    # PKCS#12 envelope, derive expiry, and classify health. A wrong /
    # missing password surfaces as ``unreadable``; a malformed file
    # surfaces as ``corrupt``.
    try:
        bundle_bytes = path.read_bytes()
    except OSError as exc:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.UNREADABLE,
            summary=tr(
                "application.auth.operator.probe.certificate_unreadable",
                error=type(exc).__name__,
            ),
        )
    loaded = _try_load_certificate_metadata(path, bundle_bytes, resolved_settings)
    if loaded is None:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.CORRUPT,
            summary=tr("application.auth.operator.probe.certificate_corrupt"),
        )
    try:
        health = evaluate_loaded_certificate_health(
            loaded,
            warn_days=resolved_settings.aeat_cert_warn_days,
            critical_days=resolved_settings.aeat_cert_critical_days,
        )
    except CertificateError as exc:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.CORRUPT,
            summary=tr(
                "application.auth.operator.probe.certificate_corrupt_detail",
                error=str(exc),
            ),
        )
    severity = health.severity
    if severity is CertificateHealthSeverity.EXPIRED:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.EXPIRED,
            summary=tr(
                "application.auth.operator.probe.certificate_expired",
                days=abs(health.days_until_expiry),
            ),
        )
    if severity is CertificateHealthSeverity.CRITICAL or severity is CertificateHealthSeverity.WARN:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.EXPIRING,
            summary=tr(
                "application.auth.operator.probe.certificate_expiring",
                days=health.days_until_expiry,
            ),
        )
    return _ProviderProbeOutcome(
        result=ProviderProbeResult.OK,
        summary=tr(
            "application.auth.operator.probe.certificate_ok",
            days=health.days_until_expiry,
        ),
    )


def _try_load_certificate_metadata(
    path: Path,
    bundle_bytes: bytes,
    settings: Settings,
) -> LoadedCertificate | None:
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
    except (OSError, ValueError, AeatError):
        _log.warning("certificate load failed; treating bundle as unparseable", exc_info=True)
        return None


def _probe_clave_movil_identity(*, settings: Settings | None = None) -> _ProviderProbeOutcome:
    """Classify the configured Cl@ve Móvil DNI/NIE through the real classifier.

    A well-formed identity surfaces as ``ok``; a malformed identity as
    ``invalid_identity``; an unset identity as ``identity_unset``. The
    probe never contacts AEAT — it validates the local configuration.
    """
    from ...adapters.outbound.aeat.auth._clave_movil import (
        ClaveMovilConfigurationError,
        _classify_identity,
    )

    resolved_settings = settings or load_settings()
    raw = unwrap_optional_secret(resolved_settings.aeat_clave_movil_dni_nie).strip()
    if not raw:
        return _ProviderProbeOutcome(
            result=ProviderProbeResult.IDENTITY_UNSET,
            summary=tr("application.auth.operator.probe.clave_movil_identity_unset"),
        )
    try:
        _classify_identity(raw)
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
