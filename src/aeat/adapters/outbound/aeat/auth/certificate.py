"""PKCS#12 client-certificate records and checks for AEAT Sede Electrónica.

This module is the public surface for certificate-based authentication
against the Spanish tax authority's Sede Electrónica. Callers import
exclusively from :mod:`aeat.adapters.outbound.aeat.auth`; the backend implementations live in
the private :mod:`aeat.adapters.outbound.aeat.auth._certificate_backends` package.

:class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator` consumes this
surface by loading a :class:`CertificateBundle` into a :class:`LoadedCertificate`,
recording :class:`CertificateHealth`, deriving the taxpayer NIF/NIE through
:func:`extract_nif_from_subject`, and storing :class:`HandshakeResult` evidence
in certificate-backed sessions.

Design constraints:

* All boundary records are pydantic v2 ``BaseModel`` with
  ``model_config`` set to the shared strict, frozen project config.
* Cert passphrases are :class:`pydantic.SecretStr`. The secret value is
  materialised only at the exact TLS-handshake boundary and is never
  logged, persisted, or serialised by ``model_dump``.
* Parsed private-key material and the raw PKCS#12 bytes live in
  :class:`pydantic.PrivateAttr` fields on :class:`LoadedCertificate`,
  so they can never be leaked via ``model_dump`` or ``repr``.
* All errors inherit from :class:`aeat.core.errors.AeatError` via
  :class:`CertificateError`.

See Also:
    :class:`aeat.adapters.outbound.aeat.auth.CertificateContextProvisioner`
    for wiring :class:`LoadedCertificate` into browser contexts, and
    :func:`aeat.adapters.outbound.aeat.auth.describe_certificate_provider`
    for the provider summary built from :class:`CertificateHealth`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import BaseModel, Field, PrivateAttr, SecretStr

from .....core import STRICT_FROZEN_CONFIG
from .....core.config import CertificateBackend
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.time._utc import coerce_utc_aware
from ._errors import AeatLoginAssertionError, AeatSessionExpiredError, AuthError, AuthValidationError

if TYPE_CHECKING:
    from ._certificate_backends._base import _CertBackend

log = get_logger(__name__)


# ── Errors ──────────────────────────────────────────────────────────────────


class CertificateError(AuthError):
    """Base class for every certificate-auth domain error.

    Subclasses remain catchable through the shared :class:`AuthError` branch
    while preserving certificate-specific causes for loading, password,
    health, handshake, and subject-identity failures.
    """


class CertificateLoadError(CertificateError):
    """Raised when :func:`load_certificate` cannot parse PKCS#12 bytes."""


class CertificatePasswordError(CertificateError):
    """Raised when :class:`CertificateBundle.password` is empty or wrong."""


class CertificateExpiredError(CertificateError):
    """Raised when :func:`load_certificate` sees an elapsed ``not_after``."""


class CertificatePreExpiryError(CertificateError):
    """Raised when a certificate is within the pre-expiry danger window.

    Distinct from :class:`CertificateExpiredError` (which fires after
    ``not_after`` has elapsed): this error is raised proactively by the
    workflow gate and CLI surfaces when a loaded certificate's
    ``days_until_expiry`` has fallen below the configured critical
    threshold, before the bundle becomes technically unusable. Callers
    may suppress it via an explicit override flag on the narrow
    programmatic surfaces that still support certificate probes.
    """


class CertificateHandshakeError(CertificateError):
    """Raised when handshake input is structurally invalid.

    TLS failures encountered during :func:`verify_handshake` are
    returned as ``HandshakeResult(success=False, ...)`` rather than
    raised; this exception is reserved for cases where the caller
    passed nonsense (e.g. an empty URL).
    """


class CertificateNifParseError(CertificateError):
    """Raised when no NIF / NIE can be parsed from a certificate subject.

    The project's authenticator derives the taxpayer NIF from the
    FNMT certificate subject (canonical source: the ``serialNumber``
    RDN, OID 2.5.4.5). Certificates that carry no such attribute,
    that use a CIF (legal-entity) shape, or whose CN/serialNumber
    lacks a recognisable DNI (``[0-9]{7,8}[A-Z]``) or NIE
    (``[XYZ][0-9]{7}[A-Z]``) identifier produce this error. Callers
    MUST propagate it rather than guess the identifier from other
    fields.
    """


# AeatLoginAssertionError and AeatSessionExpiredError are now in ._errors


# ── Enums ───────────────────────────────────────────────────────────────────


class CertificateHealthSeverity(StrEnum):
    """Closed catalogue of certificate health verdicts.

    Mapping from ``days_until_expiry`` to severity is driven by the
    ``warn_threshold_days`` / ``critical_threshold_days`` fields on the
    :class:`CertificateHealth` record and the sourced values in
    :class:`aeat.core.config.Settings`.

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

    :func:`load_certificate` turns this pointer into a
    :class:`LoadedCertificate`. The selected :class:`CertificateBackend`
    determines which private backend later consumes the loaded certificate.

    The PKCS#12 passphrase is carried directly as a
    :class:`pydantic.SecretStr` so callers no longer have to round-trip
    the secret through ``os.environ``. The secret is materialised
    only at the exact PKCS#12-decode boundary and is never logged,
    persisted, or serialised by ``model_dump``.

    Attributes:
        path: Filesystem path to the ``.p12`` / ``.pfx`` bundle.
        password: PKCS#12 passphrase as a :class:`SecretStr`.
        friendly_name: Optional human-readable label for logs.
        backend: Which backend should consume this bundle.
    """

    model_config = STRICT_FROZEN_CONFIG

    path: Path
    password: SecretStr
    friendly_name: str | None = None
    backend: CertificateBackend


class LoadedCertificate(BaseModel):
    """A parsed, validated, in-memory PKCS#12 certificate.

    :class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator` uses this
    record for NIF/NIE extraction, :class:`CertificateHealth` evaluation,
    :class:`HandshakeResult` creation, and browser-context provisioning.

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

    model_config = STRICT_FROZEN_CONFIG

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

        Returns:
            True when the certificate has expired relative to ``now``.
        """
        reference = now if now is not None else datetime.now(UTC)
        return reference > self.not_after

    @override
    def __repr__(self) -> str:  # pragma: no cover - trivial
        """Return a developer-readable string showing subject, issuer, thumbprint, and backend."""
        return (
            f"LoadedCertificate(subject={self.subject!r}, "
            f"issuer={self.issuer!r}, "
            f"sha256_thumbprint={self.sha256_thumbprint!r}, "
            f"backend={self.backend.value})"
        )


class CertificateHealth(BaseModel):
    """Structured health verdict for a PKCS#12 certificate bundle.

    Computed from a loaded certificate's ``not_after`` against a
    reference ``evaluated_at`` timestamp and a pair of warning /
    critical thresholds sourced from
    :class:`aeat.core.config.Settings`. The record never carries any
    secret material; it is safe to log, persist, or surface to the
    CLI. :func:`evaluate_loaded_certificate_health` computes this from an
    existing :class:`LoadedCertificate`; :func:`health` computes it from a
    bundle path while preserving the expired-certificate reporting path.

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

    model_config = STRICT_FROZEN_CONFIG

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

    Successful certificate sessions persist this result inside
    :class:`aeat.adapters.outbound.aeat.auth._authenticator_persistence.PersistedSessionMetadata`
    so resumed sessions can preserve the original mTLS probe evidence.

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

    model_config = STRICT_FROZEN_CONFIG

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


def load_certificate(bundle: CertificateBundle) -> LoadedCertificate:
    """Load and validate a PKCS#12 bundle from disk.

    This is the canonical decode path for certificate auth. It feeds
    :class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator`, operator
    probes, and backend provisioning surfaces with the same
    :class:`LoadedCertificate` contract.

    The passphrase is unwrapped from ``bundle.password`` at the
    PKCS#12-decode boundary only. An empty :class:`SecretStr` raises
    :class:`CertificatePasswordError` *before* any file I/O. On a
    successful load the returned :class:`LoadedCertificate` carries the
    raw PKCS#12 bytes and a parsed private-key handle in
    :class:`PrivateAttr` fields so the backends can consume them
    without a second on-disk round-trip.

    Args:
        bundle: Operator-supplied :class:`CertificateBundle`.

    Returns:
        A frozen :class:`LoadedCertificate`. Its public fields are safe
        to log; secret material is never serialised.

    Raises:
        CertificatePasswordError: Empty passphrase or wrong passphrase.
        CertificateLoadError: PKCS#12 bytes cannot be parsed.
        CertificateExpiredError: Certificate's validity has elapsed.
    """
    raw_password = bundle.password.get_secret_value()
    if not raw_password:
        raise CertificatePasswordError(
            f"passphrase for PKCS#12 bundle at {bundle.path} is empty; "
            "construct CertificateBundle with a non-empty SecretStr password.",
        )

    try:
        raw_bytes = bundle.path.read_bytes()
    except OSError as exc:
        raise CertificateLoadError(f"could not read PKCS#12 bundle at {bundle.path}: {exc}") from exc

    try:
        parsed = pkcs12.load_pkcs12(raw_bytes, raw_password.encode(UTF_8_ENCODING))
    except ValueError as exc:
        message = str(exc).lower()
        if "invalid password" in message or "mac verify" in message:
            raise CertificatePasswordError(
                f"wrong passphrase for PKCS#12 bundle at {bundle.path}",
            ) from exc
        raise CertificateLoadError(f"could not parse PKCS#12 bundle at {bundle.path}: malformed bytes") from exc

    if parsed.cert is None or parsed.cert.certificate is None:
        raise CertificateLoadError(f"PKCS#12 bundle at {bundle.path} contains no end-entity certificate")

    x509_cert = parsed.cert.certificate
    not_before = coerce_utc_aware(x509_cert.not_valid_before_utc)
    not_after = coerce_utc_aware(x509_cert.not_valid_after_utc)

    friendly_name: str | None = bundle.friendly_name
    if friendly_name is None and parsed.cert.friendly_name is not None:
        try:
            friendly_name = parsed.cert.friendly_name.decode(UTF_8_ENCODING)
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
    object.__setattr__(loaded, "_password", bundle.password)
    object.__setattr__(loaded, "_private_key_handle", parsed.key)

    if loaded.is_expired():
        raise CertificateExpiredError(
            f"certificate for subject {loaded.subject!r} expired at {loaded.not_after.isoformat()}",
        )

    log.info(
        "loaded PKCS#12 certificate: thumbprint=%s backend=%s",
        loaded.sha256_thumbprint,
        loaded.backend.value,
    )
    return loaded


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
    decode cost, such as :class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator`
    or operator probes, can reuse the parsed record rather than re-reading the
    bundle from disk.

    Args:
        cert: A previously-loaded :class:`LoadedCertificate`.
        warn_days: Warning threshold in days. Must be > ``critical_days``.
        critical_days: Critical threshold in days. Must be positive.
        now: Optional timezone-aware reference timestamp. Defaults to
            :func:`datetime.now` in UTC.

    Returns:
        A frozen :class:`CertificateHealth` record.

    Raises:
        AuthValidationError: If ``critical_days <= 0`` or ``warn_days <= critical_days``.
    """
    if critical_days <= 0:
        raise AuthValidationError(f"critical_days must be positive, got {critical_days}")
    if warn_days <= critical_days:
        raise AuthValidationError(
            f"warn_days ({warn_days}) must be strictly greater than critical_days ({critical_days})",
        )
    evaluated_at = coerce_utc_aware(now) if now is not None else datetime.now(UTC)
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
    password: SecretStr,
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
    failures (empty passphrase, corrupt bytes, I/O) still raise the
    matching :class:`CertificateError` subclass, because those are not
    pre-expiry conditions.

    Args:
        path: Filesystem path to the PKCS#12 bundle.
        password: PKCS#12 passphrase as a :class:`SecretStr`.
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
        CertificateExpiredError: When the certificate has expired and the raw bytes
            cannot be re-decoded for the health report.
        CertificateLoadError: When the PKCS#12 bytes cannot be re-decoded for an
            expired-cert health report.
    """
    bundle = CertificateBundle(
        path=path,
        password=password,
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
        try:
            raw_bytes = path.read_bytes()
            parsed = pkcs12.load_pkcs12(raw_bytes, password.get_secret_value().encode(UTF_8_ENCODING))
        except (OSError, ValueError) as exc:
            raise CertificateLoadError(
                f"could not re-decode PKCS#12 bundle at {path} for expired-cert health report: {exc}",
            ) from exc
        if parsed.cert is None or parsed.cert.certificate is None:  # pragma: no cover - defended above
            raise
        x509_cert = parsed.cert.certificate
        not_before = coerce_utc_aware(x509_cert.not_valid_before_utc)
        not_after = coerce_utc_aware(x509_cert.not_valid_after_utc)
        evaluated_at = coerce_utc_aware(now) if now is not None else datetime.now(UTC)
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


# ── NIF / NIE extraction from FNMT subject ──────────────────────────────────


_SERIAL_PREFIX_RE = re.compile(r"^IDCES-", re.IGNORECASE)
_DNI_RE = re.compile(r"^[0-9]{7,8}[A-Z]$")
_NIE_RE = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")
_CIF_RE = re.compile(r"^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$")
_TRAILING_NIF_RE = re.compile(r"([0-9]{7,8}[A-Z]|[XYZ][0-9]{7}[A-Z])\s*$", re.IGNORECASE)


def _normalise_candidate(candidate: str) -> str:
    """Strip surrounding whitespace and the optional ``IDCES-`` prefix."""
    stripped = candidate.strip()
    return _SERIAL_PREFIX_RE.sub("", stripped).upper()


def _iter_rdn_values(subject: str, oid: x509.ObjectIdentifier) -> list[str]:
    r"""Return every attribute value in ``subject`` matching ``oid``.

    Parses the subject via
    :meth:`cryptography.x509.Name.from_rfc4514_string`, which handles
    RFC 4514 escape sequences (``\\,``, ``\\+``, ``\\"``, ``\\#``) and
    multi-valued RDNs correctly — regex cannot. Returns the raw
    attribute values with no normalisation; callers strip prefixes
    and validate shape.
    """
    try:
        name = x509.Name.from_rfc4514_string(subject)
    except ValueError:
        return []
    return [attribute.value for attribute in name.get_attributes_for_oid(oid) if isinstance(attribute.value, str)]


def extract_nif_from_subject(cert: LoadedCertificate) -> str:
    r"""Return the FNMT taxpayer identifier encoded in ``cert``'s subject.

    FNMT *persona física* certificates carry the subject's NIF or
    NIE in the ``serialNumber`` RDN (OID ``2.5.4.5``), optionally
    prefixed with ``IDCES-``. Some older bundles repeat it in the
    common name with the format ``NAME SURNAME - NNNNNNNNL``.

    Uses :meth:`cryptography.x509.Name.from_rfc4514_string` to
    parse the subject so that RFC 4514 escape sequences (``\\,``,
    ``\\+``, etc.) and multi-valued RDNs are handled correctly.

    Args:
        cert: The loaded PKCS#12 certificate.

    Returns:
        The uppercase normalised NIF/NIE (e.g. ``"12345678Z"`` or
        ``"X1234567L"``).

    Raises:
        CertificateNifParseError: When the subject contains no
            recognisable DNI / NIE identifier, or when the value
            present is a CIF (legal-entity). Certificate auth here
            accepts individual taxpayer certificates and rejects
            organization certificates rather than guessing an identity.
    """
    subject = cert.subject

    for raw in _iter_rdn_values(subject, NameOID.SERIAL_NUMBER):
        candidate = _normalise_candidate(raw)
        if _CIF_RE.match(candidate):
            raise CertificateNifParseError(
                f"subject serialNumber {candidate!r} looks like a CIF "
                "(legal-entity). This project supports individual taxpayer "
                "(persona física) certificates only.",
            )
        if _DNI_RE.match(candidate) or _NIE_RE.match(candidate):
            return candidate

    for cn in _iter_rdn_values(subject, NameOID.COMMON_NAME):
        trailing = _TRAILING_NIF_RE.search(cn)
        if trailing is not None:
            candidate = trailing.group(1).upper()
            if _DNI_RE.match(candidate) or _NIE_RE.match(candidate):
                return candidate

    raise CertificateNifParseError(
        f"cannot parse a DNI or NIE from certificate subject "
        f"{subject!r}; expected serialNumber or CN to carry "
        "a valid persona-física identifier",
    )


# ── Backend dispatch ────────────────────────────────────────────────────────


def _select_backend(backend: CertificateBackend) -> _CertBackend:
    """Return the backend implementation for ``backend``.

    Imports are performed lazily so the cryptography + playwright
    dependency cost is paid only when the relevant backend is actually
    requested.
    """
    from ._certificate_backends._httpx_fallback import HttpxFallbackBackend
    from ._certificate_backends._playwright_context import (
        PlaywrightContextBackend,
    )

    match backend:
        case CertificateBackend.PLAYWRIGHT_CONTEXT:
            return PlaywrightContextBackend()
        case CertificateBackend.HTTPX_FALLBACK:
            return HttpxFallbackBackend()


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
    the integration hook used by
    :class:`aeat.adapters.outbound.aeat.auth.CertificateContextProvisioner`
    after it passes a :class:`CertificateBundle`-derived certificate through
    to ``new_context``.

    Args:
        cert: The :class:`LoadedCertificate` to verify against ``context``.
        context: A Playwright ``BrowserContext`` duck-typed via
            :class:`_BrowserContextLike`.
    """
    backend = _select_backend(cert.backend)
    backend.preload(cert, context)


def verify_handshake(cert: LoadedCertificate, url: str) -> HandshakeResult:
    """Perform an opt-in TLS handshake smoke test.

    :class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator` calls this
    before constructing a certificate-backed :class:`AeatSession`. Backend
    implementations own the actual transport behavior.

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
    "AeatLoginAssertionError",
    "AeatSessionExpiredError",
    "CertificateBackend",
    "CertificateBundle",
    "CertificateError",
    "CertificateExpiredError",
    "CertificateHandshakeError",
    "CertificateHealth",
    "CertificateHealthSeverity",
    "CertificateLoadError",
    "CertificateNifParseError",
    "CertificatePasswordError",
    "CertificatePreExpiryError",
    "HandshakeResult",
    "LoadedCertificate",
    "evaluate_loaded_certificate_health",
    "extract_nif_from_subject",
    "health",
    "load_certificate",
    "preload_into_browser_context",
    "verify_handshake",
]
