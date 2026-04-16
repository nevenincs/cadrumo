"""PKCS#12 client-certificate authentication for AEAT Sede Electrónica.

This module is the public surface for certificate-based authentication
against the Spanish tax authority's Sede Electrónica. Callers import
exclusively from :mod:`aeat.auth`; the backend implementations live in
the private :mod:`aeat.auth._certificate_backends` package.

Design constraints (see
``.vault/adr/2026-04-12-cert-auth-adr.md``):

* All boundary records are pydantic v2 ``BaseModel`` with
  ``model_config = ConfigDict(strict=True, frozen=True)``.
* Cert passphrases are :class:`pydantic.SecretStr`. The secret value is
  materialised only at the exact TLS-handshake boundary and is never
  logged, persisted, or serialised by ``model_dump``.
* Parsed private-key material and the raw PKCS#12 bytes live in
  :class:`pydantic.PrivateAttr` fields on :class:`LoadedCertificate`,
  so they can never be leaked via ``model_dump`` or ``repr``.
* All errors inherit from :class:`aeat.errors.AeatError` via
  :class:`CertificateError`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr

from aeat.errors import AeatError
from aeat.logging import get_logger

if TYPE_CHECKING:
    from aeat.auth._certificate_backends._base import _CertBackend
    from aeat.config import Settings

log = get_logger(__name__)


# ── Errors ──────────────────────────────────────────────────────────────────


class CertificateError(AeatError):
    """Base class for every certificate-auth domain error."""


class CertificateLoadError(CertificateError):
    """Raised when PKCS#12 bytes cannot be parsed at all."""


class CertificatePasswordError(CertificateError):
    """Raised when the passphrase env var is missing/empty or wrong."""


class CertificateExpiredError(CertificateError):
    """Raised when a loaded certificate's ``not_after`` is in the past."""


class CertificatePreExpiryError(CertificateError):
    """Raised when a certificate is within the pre-expiry danger window.

    Distinct from :class:`CertificateExpiredError` (which fires after
    ``not_after`` has elapsed): this error is raised proactively by the
    workflow gate and CLI surfaces when a loaded certificate's
    ``days_until_expiry`` has fallen below the configured critical
    threshold, before the bundle becomes technically unusable. Callers
    may suppress it via an explicit override flag (for example
    ``aeat submission submit --force-expiring-cert``).
    """


class CertificateHandshakeError(CertificateError):
    """Raised when handshake input is structurally invalid.

    TLS failures encountered during :func:`verify_handshake` are
    returned as ``HandshakeResult(success=False, ...)`` rather than
    raised; this exception is reserved for cases where the caller
    passed nonsense (e.g. an empty URL).
    """


# ── Enums ───────────────────────────────────────────────────────────────────


class CertificateBackend(StrEnum):
    """Closed catalogue of supported certificate backends.

    Attributes:
        PLAYWRIGHT_CONTEXT: Primary. Supply the PKCS#12 to
            ``browser.new_context(client_certificates=[...])``.
        USER_DATA_DIR: Deferred. Install into the OS cert store and
            launch Chrome with ``--user-data-dir``.
        MTLS_PROXY: Deferred. Route the browser through a local
            mTLS-injecting proxy.
        HTTPX_FALLBACK: Verify-only. Perform a direct mTLS handshake
            via ``httpx`` for CI smoke tests.
    """

    PLAYWRIGHT_CONTEXT = "PLAYWRIGHT_CONTEXT"
    USER_DATA_DIR = "USER_DATA_DIR"
    MTLS_PROXY = "MTLS_PROXY"
    HTTPX_FALLBACK = "HTTPX_FALLBACK"


class CertificateHealthSeverity(StrEnum):
    """Closed catalogue of certificate health verdicts.

    Mapping from ``days_until_expiry`` to severity is driven by the
    ``warn_threshold_days`` / ``critical_threshold_days`` fields on the
    :class:`CertificateHealth` record and the sourced values in
    :class:`aeat.config.Settings`.

    Attributes:
        OK: Certificate has more than ``warn_threshold_days`` remaining.
        WARN: Within the warning window but outside the critical one.
        CRITICAL: Inside the critical window but not yet expired.
        EXPIRED: ``not_after`` has already elapsed.
    """

    OK = "OK"
    WARN = "WARN"
    CRITICAL = "CRITICAL"
    EXPIRED = "EXPIRED"


# ── Pydantic boundary records ───────────────────────────────────────────────


class CertificateBundle(BaseModel):
    """Operator-supplied pointer at a PKCS#12 bundle on disk.

    The password is referenced by *env var name*, never as a literal.
    The actual secret value is read at load time via :func:`os.environ`
    and wrapped in :class:`pydantic.SecretStr` from that point forward.

    Attributes:
        path: Filesystem path to the ``.p12`` / ``.pfx`` bundle.
        password_env_var: Name of the environment variable holding the
            passphrase. Never the passphrase itself.
        friendly_name: Optional human-readable label for logs.
        backend: Which backend should consume this bundle.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    path: Path
    password_env_var: str = Field(min_length=1)
    friendly_name: str | None = None
    backend: CertificateBackend


class LoadedCertificate(BaseModel):
    """A parsed, validated, in-memory PKCS#12 certificate.

    Public fields are safe to log and serialise. Secret material
    (raw PKCS#12 bytes, parsed private key, passphrase) lives in
    :class:`pydantic.PrivateAttr` fields and is therefore invisible to
    ``model_dump``, ``model_dump_json``, and the overridden
    :meth:`__repr__`.

    Attributes:
        subject: X.509 subject distinguished name.
        issuer: X.509 issuer distinguished name.
        not_before: Validity start (timezone-aware UTC).
        not_after: Validity end (timezone-aware UTC).
        serial_number: Hex-encoded serial number.
        sha256_thumbprint: Hex-encoded SHA-256 fingerprint of the DER
            encoding.
        source_path: Path the bundle was loaded from.
        friendly_name: Optional label propagated from the bundle.
        backend: Backend this cert should be handed to.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    serial_number: str
    sha256_thumbprint: str
    source_path: Path
    friendly_name: str | None
    backend: CertificateBackend

    _pkcs12_bytes: bytes = PrivateAttr(default=b"")
    _password: SecretStr = PrivateAttr(default=SecretStr(""))
    _private_key_handle: object | None = PrivateAttr(default=None)

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True if the certificate's validity has elapsed.

        Args:
            now: Timezone-aware reference time. Defaults to
                :func:`datetime.now` in UTC.
        """
        reference = now if now is not None else datetime.now(UTC)
        return reference > self.not_after

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"LoadedCertificate(subject={self.subject!r}, "
            f"issuer={self.issuer!r}, "
            f"sha256_thumbprint={self.sha256_thumbprint!r}, "
            f"backend={self.backend.value})"
        )

    def preload_into_browser_context(self, context: object) -> None:
        """Validate that ``context`` was created with this certificate.

        This method gives the loaded certificate object the exact
        browser-preload surface the status reader already expects,
        while keeping the concrete backend behavior in
        :mod:`aeat.auth`.
        """
        backend = _select_backend(self.backend)
        backend.preload(self, context)


class CertificateHealth(BaseModel):
    """Structured health verdict for a PKCS#12 certificate bundle.

    Computed from a loaded certificate's ``not_after`` against a
    reference ``evaluated_at`` timestamp and a pair of warning /
    critical thresholds sourced from
    :class:`aeat.config.Settings`. The record never carries any
    secret material; it is safe to log, persist, or surface to the
    CLI.

    Attributes:
        subject: RFC-4514 subject DN.
        issuer: RFC-4514 issuer DN.
        serial_number: Hex-encoded serial number.
        not_before: Timezone-aware validity start.
        not_after: Timezone-aware validity end.
        days_until_expiry: Whole days between ``evaluated_at`` and
            ``not_after``. Negative when the certificate is expired.
        severity: :class:`CertificateHealthSeverity` bucket.
        warn_threshold_days: The WARN cut-off that produced this
            verdict.
        critical_threshold_days: The CRITICAL cut-off that produced
            this verdict.
        evaluated_at: Timezone-aware reference timestamp.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    days_until_expiry: int
    severity: CertificateHealthSeverity
    warn_threshold_days: int = Field(gt=0)
    critical_threshold_days: int = Field(gt=0)
    evaluated_at: datetime


class HandshakeResult(BaseModel):
    """Structured outcome of a :func:`verify_handshake` attempt.

    Attributes:
        success: Whether the TLS handshake completed successfully.
        status_code: HTTP status returned by the verify URL (0 if the
            handshake failed before any HTTP response was observed).
        server_cert_chain: Tuple of subject DNs from the server-presented
            chain, outermost leaf first. Empty on failure.
        elapsed_ms: Wall-clock elapsed time in milliseconds.
        attempted_at: Timezone-aware UTC timestamp of the attempt.
        error_message: Human-readable failure reason when
            ``success=False``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    success: bool
    status_code: int
    server_cert_chain: tuple[str, ...]
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None


# ── Browser integration Protocol ────────────────────────────────────────────


@runtime_checkable
class _BrowserContextLike(Protocol):
    """Structural typing hint for a Playwright ``BrowserContext``.

    Declared as a :class:`typing.Protocol` so this module does not
    import ``playwright`` at module load. The actual attribute surface
    Playwright exposes is large and out of scope for static typing here;
    the ``ty`` checker treats the protocol body as informational only.
    """


# ── Loader ──────────────────────────────────────────────────────────────────


def _read_password_from_env(env_var: str) -> SecretStr:
    """Read ``env_var`` and wrap its value in :class:`SecretStr`.

    Raises :class:`CertificatePasswordError` if the variable is unset
    or empty.
    """
    raw = os.environ.get(env_var)
    if not raw:
        raise CertificatePasswordError(
            f"environment variable {env_var!r} is unset or empty; "
            "set it to the PKCS#12 passphrase before calling load_certificate()"
        )
    return SecretStr(raw)


def _ensure_utc(value: datetime) -> datetime:
    """Coerce a naive datetime to UTC-aware (PKCS#12 datetimes vary)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def load_certificate(bundle: CertificateBundle) -> LoadedCertificate:
    """Load and validate a PKCS#12 bundle from disk.

    The passphrase is read from ``os.environ[bundle.password_env_var]``;
    if the env var is unset or empty a :class:`CertificatePasswordError`
    is raised *before* any file I/O. On a successful load the returned
    :class:`LoadedCertificate` carries the raw PKCS#12 bytes and a
    parsed private-key handle in :class:`PrivateAttr` fields so the
    backends can consume them without a second on-disk round-trip.

    Args:
        bundle: Operator-supplied :class:`CertificateBundle`.

    Returns:
        A frozen :class:`LoadedCertificate`. Its public fields are safe
        to log; secret material is never serialised.

    Raises:
        CertificatePasswordError: Env var unset/empty or wrong password.
        CertificateLoadError: PKCS#12 bytes cannot be parsed.
        CertificateExpiredError: Certificate's validity has elapsed.
    """
    password = _read_password_from_env(bundle.password_env_var)

    try:
        raw_bytes = bundle.path.read_bytes()
    except OSError as exc:
        raise CertificateLoadError(f"could not read PKCS#12 bundle at {bundle.path}: {exc}") from exc

    try:
        parsed = pkcs12.load_pkcs12(raw_bytes, password.get_secret_value().encode("utf-8"))
    except ValueError as exc:
        message = str(exc).lower()
        if "invalid password" in message or "mac verify" in message:
            raise CertificatePasswordError(
                f"wrong passphrase for PKCS#12 bundle at {bundle.path} (env var {bundle.password_env_var!r})"
            ) from exc
        raise CertificateLoadError(f"could not parse PKCS#12 bundle at {bundle.path}: malformed bytes") from exc

    if parsed.cert is None or parsed.cert.certificate is None:
        raise CertificateLoadError(f"PKCS#12 bundle at {bundle.path} contains no end-entity certificate")

    x509_cert = parsed.cert.certificate
    not_before = _ensure_utc(x509_cert.not_valid_before_utc)
    not_after = _ensure_utc(x509_cert.not_valid_after_utc)

    friendly_name: str | None = bundle.friendly_name
    if friendly_name is None and parsed.cert.friendly_name is not None:
        try:
            friendly_name = parsed.cert.friendly_name.decode("utf-8")
        except UnicodeDecodeError:
            friendly_name = None

    loaded = LoadedCertificate(
        subject=x509_cert.subject.rfc4514_string(),
        issuer=x509_cert.issuer.rfc4514_string(),
        not_before=not_before,
        not_after=not_after,
        serial_number=format(x509_cert.serial_number, "x"),
        sha256_thumbprint=x509_cert.fingerprint(hashes.SHA256()).hex(),
        source_path=bundle.path,
        friendly_name=friendly_name,
        backend=bundle.backend,
    )

    object.__setattr__(loaded, "_pkcs12_bytes", raw_bytes)
    object.__setattr__(loaded, "_password", password)
    object.__setattr__(loaded, "_private_key_handle", parsed.key)

    if loaded.is_expired():
        raise CertificateExpiredError(
            f"certificate for subject {loaded.subject!r} expired at {loaded.not_after.isoformat()}"
        )

    log.info(
        "Loaded PKCS#12 certificate: subject=%s thumbprint=%s friendly_name=%s backend=%s",
        loaded.subject,
        loaded.sha256_thumbprint,
        loaded.friendly_name,
        loaded.backend.value,
    )
    return loaded


def load_certificate_from_settings(settings: Settings) -> LoadedCertificate:
    """Load the configured PKCS#12 bundle from :class:`aeat.config.Settings`.

    The settings model holds the passphrase as ``SecretStr`` but the
    lower-level loader reads it from the process environment. This
    helper performs the sanctioned bridge once and reuses the existing
    loader and validation path.
    """
    if settings.aeat_certificate_path is None:
        raise CertificateLoadError("AEAT_CERTIFICATE_PATH is not set")
    if settings.aeat_certificate_password_secret is None:
        raise CertificatePasswordError("AEAT_CERTIFICATE_PASSWORD_SECRET is not set")
    env_var = "AEAT_CERTIFICATE_PASSWORD_SECRET"
    original_secret = os.environ.get(env_var)
    os.environ[env_var] = settings.aeat_certificate_password_secret.get_secret_value()
    try:
        bundle = CertificateBundle(
            path=settings.aeat_certificate_path,
            password_env_var=env_var,
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )
        return load_certificate(bundle)
    finally:
        if original_secret is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = original_secret


# ── Pre-expiry health evaluator ─────────────────────────────────────────────


def _bucket_severity(
    *,
    days_until_expiry: int,
    warn_days: int,
    critical_days: int,
) -> CertificateHealthSeverity:
    """Map ``days_until_expiry`` to a :class:`CertificateHealthSeverity`.

    Boundary semantics: a cert with exactly ``critical_days`` remaining
    is classified CRITICAL (inclusive), and exactly ``warn_days``
    remaining is classified WARN (inclusive). Negative / zero days
    (i.e. expired) always produce EXPIRED.

    Args:
        days_until_expiry: Whole days between ``evaluated_at`` and
            ``not_after``.
        warn_days: Warning window in days (must be ``> critical_days``).
        critical_days: Critical window in days.

    Returns:
        The appropriate severity bucket.
    """
    if days_until_expiry <= 0:
        return CertificateHealthSeverity.EXPIRED
    if days_until_expiry <= critical_days:
        return CertificateHealthSeverity.CRITICAL
    if days_until_expiry <= warn_days:
        return CertificateHealthSeverity.WARN
    return CertificateHealthSeverity.OK


def evaluate_loaded_certificate_health(
    cert: LoadedCertificate,
    *,
    warn_days: int,
    critical_days: int,
    now: datetime | None = None,
) -> CertificateHealth:
    """Compute a :class:`CertificateHealth` from an already-loaded cert.

    The helper exists so callers that have already paid the PKCS#12
    decode cost (e.g. :class:`aeat.workflow.WorkflowEngine`) can reuse
    the parsed record rather than re-reading the bundle from disk.

    Args:
        cert: A previously-loaded :class:`LoadedCertificate`.
        warn_days: Warning threshold in days. Must be > ``critical_days``.
        critical_days: Critical threshold in days. Must be positive.
        now: Optional timezone-aware reference timestamp. Defaults to
            :func:`datetime.now` in UTC.

    Returns:
        A frozen :class:`CertificateHealth` record.

    Raises:
        ValueError: If ``critical_days <= 0`` or ``warn_days <= critical_days``.
    """
    if critical_days <= 0:
        raise ValueError(f"critical_days must be positive, got {critical_days}")
    if warn_days <= critical_days:
        raise ValueError(f"warn_days ({warn_days}) must be strictly greater than critical_days ({critical_days})")
    evaluated_at = now if now is not None else datetime.now(UTC)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=UTC)
    delta_seconds = (cert.not_after - evaluated_at).total_seconds()
    # Floor division keeps "one second before expiry" at 0 days → EXPIRED.
    days_until_expiry = int(delta_seconds // 86400)
    severity = _bucket_severity(
        days_until_expiry=days_until_expiry,
        warn_days=warn_days,
        critical_days=critical_days,
    )
    return CertificateHealth(
        subject=cert.subject,
        issuer=cert.issuer,
        serial_number=cert.serial_number,
        not_before=cert.not_before,
        not_after=cert.not_after,
        days_until_expiry=days_until_expiry,
        severity=severity,
        warn_threshold_days=warn_days,
        critical_threshold_days=critical_days,
        evaluated_at=evaluated_at,
    )


def health(
    path: Path,
    *,
    password_env_var: str,
    warn_days: int,
    critical_days: int,
    backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
    friendly_name: str | None = None,
    now: datetime | None = None,
) -> CertificateHealth:
    """Load ``path`` and return its :class:`CertificateHealth`.

    Unlike :func:`load_certificate`, this function **never** raises on
    an expired certificate — it returns a
    :class:`CertificateHealth` record with severity
    :attr:`CertificateHealthSeverity.EXPIRED` instead. Genuine load
    failures (missing passphrase, corrupt bytes, I/O) still raise the
    matching :class:`CertificateError` subclass, because those are not
    pre-expiry conditions.

    Args:
        path: Filesystem path to the PKCS#12 bundle.
        password_env_var: Name of the env var holding the passphrase.
        warn_days: Warning threshold in days (see
            :func:`evaluate_loaded_certificate_health`).
        critical_days: Critical threshold in days.
        backend: Backend the bundle belongs to (default
            ``PLAYWRIGHT_CONTEXT``).
        friendly_name: Optional label propagated to the bundle.
        now: Optional reference time, for deterministic tests.

    Returns:
        A frozen :class:`CertificateHealth` record.

    Raises:
        CertificatePasswordError: Env var unset/empty or wrong password.
        CertificateLoadError: PKCS#12 bytes cannot be parsed.
    """
    bundle = CertificateBundle(
        path=path,
        password_env_var=password_env_var,
        friendly_name=friendly_name,
        backend=backend,
    )
    try:
        loaded = load_certificate(bundle)
    except CertificateExpiredError:
        # Re-load the raw bytes just to extract the metadata for the
        # health record. load_certificate refuses to return the
        # LoadedCertificate once expiry is detected, so we repeat the
        # minimal x509 decode here. A second decode failure is
        # surfaced as CertificateLoadError rather than swallowed, to
        # honour the "never-crash on pre-expiry path" contract.
        password = _read_password_from_env(password_env_var)
        try:
            raw_bytes = path.read_bytes()
            parsed = pkcs12.load_pkcs12(raw_bytes, password.get_secret_value().encode("utf-8"))
        except (OSError, ValueError) as exc:
            raise CertificateLoadError(
                f"could not re-decode PKCS#12 bundle at {path} for expired-cert health report: {exc}"
            ) from exc
        if parsed.cert is None or parsed.cert.certificate is None:  # pragma: no cover - defended above
            raise
        x509_cert = parsed.cert.certificate
        not_before = _ensure_utc(x509_cert.not_valid_before_utc)
        not_after = _ensure_utc(x509_cert.not_valid_after_utc)
        evaluated_at = now if now is not None else datetime.now(UTC)
        if evaluated_at.tzinfo is None:
            evaluated_at = evaluated_at.replace(tzinfo=UTC)
        delta_seconds = (not_after - evaluated_at).total_seconds()
        days_until_expiry = int(delta_seconds // 86400)
        return CertificateHealth(
            subject=x509_cert.subject.rfc4514_string(),
            issuer=x509_cert.issuer.rfc4514_string(),
            serial_number=format(x509_cert.serial_number, "x"),
            not_before=not_before,
            not_after=not_after,
            days_until_expiry=days_until_expiry,
            severity=CertificateHealthSeverity.EXPIRED,
            warn_threshold_days=warn_days,
            critical_threshold_days=critical_days,
            evaluated_at=evaluated_at,
        )
    return evaluate_loaded_certificate_health(
        loaded,
        warn_days=warn_days,
        critical_days=critical_days,
        now=now,
    )


# ── Backend dispatch ────────────────────────────────────────────────────────


def _select_backend(backend: CertificateBackend) -> _CertBackend:
    """Return the backend implementation for ``backend``.

    Imports are performed lazily so the cryptography + playwright
    dependency cost is paid only when the relevant backend is actually
    requested.
    """
    from aeat.auth._certificate_backends._httpx_fallback import HttpxFallbackBackend
    from aeat.auth._certificate_backends._mtls_proxy import MtlsProxyBackend
    from aeat.auth._certificate_backends._playwright_context import (
        PlaywrightContextBackend,
    )
    from aeat.auth._certificate_backends._user_data_dir import UserDataDirBackend

    match backend:
        case CertificateBackend.PLAYWRIGHT_CONTEXT:
            return PlaywrightContextBackend()
        case CertificateBackend.HTTPX_FALLBACK:
            return HttpxFallbackBackend()
        case CertificateBackend.USER_DATA_DIR:
            return UserDataDirBackend()
        case CertificateBackend.MTLS_PROXY:
            return MtlsProxyBackend()


# ── Public backend-facing API ───────────────────────────────────────────────


def preload_into_browser_context(
    cert: LoadedCertificate,
    context: object,
) -> None:
    """Validate that ``context`` was constructed with ``cert``.

    Per Playwright's API, per-context client certificates must be
    supplied at :meth:`playwright.async_api.Browser.new_context` time;
    there is no post-hoc injection hook. This function therefore
    **validates** the contract rather than mutating ``context``. It is
    the integration hook the browser layer will call once it learns to
    pass a :class:`CertificateBundle` through to ``new_context``.

    Args:
        cert: The :class:`LoadedCertificate` to verify against ``context``.
        context: A Playwright ``BrowserContext`` duck-typed via
            :class:`_BrowserContextLike`.

    Raises:
        CertificateError: When the selected backend rejects the context
            (for example, when the Playwright backend is asked to
            retrofit a cert after construction, which is not supported).
    """
    cert.preload_into_browser_context(context)


def verify_handshake(cert: LoadedCertificate, url: str) -> HandshakeResult:
    """Perform an opt-in TLS handshake smoke test.

    Dispatches to the backend selected by ``cert.backend``. TLS failures
    are returned as :class:`HandshakeResult` with ``success=False`` so
    callers can record them in health-check reports without catching
    exceptions. Only structurally invalid input raises
    :class:`CertificateHandshakeError`.

    Args:
        cert: The loaded certificate to present.
        url: Fully-qualified target URL (must include scheme + host).

    Returns:
        A frozen :class:`HandshakeResult`.

    Raises:
        CertificateHandshakeError: When ``url`` is empty or malformed.
    """
    if not url or "://" not in url:
        raise CertificateHandshakeError(f"verify_handshake: invalid url {url!r}")
    backend = _select_backend(cert.backend)
    return backend.verify(cert, url)


__all__ = [
    "CertificateBackend",
    "CertificateBundle",
    "CertificateError",
    "CertificateExpiredError",
    "CertificateHandshakeError",
    "CertificateHealth",
    "CertificateHealthSeverity",
    "CertificateLoadError",
    "CertificatePasswordError",
    "CertificatePreExpiryError",
    "HandshakeResult",
    "LoadedCertificate",
    "evaluate_loaded_certificate_health",
    "health",
    "load_certificate",
    "load_certificate_from_settings",
    "preload_into_browser_context",
    "verify_handshake",
]
