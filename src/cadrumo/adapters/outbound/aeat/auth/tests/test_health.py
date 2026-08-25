"""Unit tests for the certificate pre-expiry health evaluator.

Every test generates a real self-signed PKCS#12 bundle at runtime via
:mod:`cryptography`. The evaluator is exercised through both the in-memory
:func:`evaluate_loaded_certificate_health` entry point and the
disk-reading :func:`health` entry point.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from ......core.errors import CadrumoError
from ..certificate import (
    CertificateBundle,
    CertificateHealth,
    CertificateHealthSeverity,
    CertificatePreExpiryError,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    health,
    load_certificate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SECRET = "correct-horse-battery-staple"
_WARN_DAYS = 60
_CRITICAL_DAYS = 14
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)


def _build_pkcs12(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str = "bundle.p12",
) -> Path:
    """Generate a real self-signed PKCS#12 bundle with the given window."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "aeat-health-subject"),
        ],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"health-cert",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(_SECRET.encode("utf-8")),
    )
    out = tmp_path / name
    out.write_bytes(pfx_bytes)
    return out


def _loaded_cert_for_window(
    tmp_path: Path,
    *,
    not_valid_after: datetime,
    not_valid_before: datetime | None = None,
) -> LoadedCertificate:
    """Return a LoadedCertificate with ``not_after`` at the given point."""
    not_valid_before = not_valid_before or (_NOW - timedelta(days=1))
    p12 = _build_pkcs12(
        tmp_path,
        not_valid_before=not_valid_before,
        not_valid_after=not_valid_after,
    )
    from pydantic import SecretStr

    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(_SECRET),
        friendly_name=None,
    )
    return load_certificate(bundle)


# ── Severity buckets ────────────────────────────────────────────────────────


def test_health_ok_bucket(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(
        tmp_path,
        not_valid_after=now + timedelta(days=200),
    )
    result = evaluate_loaded_certificate_health(
        cert,
        warn_days=_WARN_DAYS,
        critical_days=_CRITICAL_DAYS,
        now=now,
    )
    assert result.severity is CertificateHealthSeverity.OK
    assert result.days_until_expiry >= 199  # int floor of 200d
    assert result.warn_threshold_days == _WARN_DAYS
    assert result.critical_threshold_days == _CRITICAL_DAYS


def test_health_warn_exact_boundary(tmp_path: Path) -> None:
    """A cert with exactly ``warn_days`` remaining is WARN (inclusive)."""
    now = _NOW
    cert = _loaded_cert_for_window(
        tmp_path,
        not_valid_after=now + timedelta(days=_WARN_DAYS, seconds=30),
    )
    result = evaluate_loaded_certificate_health(cert, warn_days=_WARN_DAYS, critical_days=_CRITICAL_DAYS, now=now)
    assert result.severity is CertificateHealthSeverity.WARN
    assert result.days_until_expiry == _WARN_DAYS


def test_health_warn_below_boundary(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(tmp_path, not_valid_after=now + timedelta(days=30))
    result = evaluate_loaded_certificate_health(cert, warn_days=_WARN_DAYS, critical_days=_CRITICAL_DAYS, now=now)
    assert result.severity is CertificateHealthSeverity.WARN


def test_health_critical_exact_boundary(tmp_path: Path) -> None:
    """Exactly ``critical_days`` remaining → CRITICAL (inclusive)."""
    now = _NOW
    cert = _loaded_cert_for_window(
        tmp_path,
        not_valid_after=now + timedelta(days=_CRITICAL_DAYS, seconds=30),
    )
    result = evaluate_loaded_certificate_health(cert, warn_days=_WARN_DAYS, critical_days=_CRITICAL_DAYS, now=now)
    assert result.severity is CertificateHealthSeverity.CRITICAL
    assert result.days_until_expiry == _CRITICAL_DAYS


def test_health_critical_below_boundary(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(tmp_path, not_valid_after=now + timedelta(days=3))
    result = evaluate_loaded_certificate_health(cert, warn_days=_WARN_DAYS, critical_days=_CRITICAL_DAYS, now=now)
    assert result.severity is CertificateHealthSeverity.CRITICAL
    assert 0 < result.days_until_expiry < _CRITICAL_DAYS


def test_health_expired(tmp_path: Path) -> None:
    """An expired cert never raises from ``health()`` — returns EXPIRED."""
    now = _NOW
    p12 = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=10),
        not_valid_after=now - timedelta(days=1),
    )
    from pydantic import SecretStr

    result = health(
        p12,
        password=SecretStr(_SECRET),
        warn_days=_WARN_DAYS,
        critical_days=_CRITICAL_DAYS,
        now=now,
    )
    assert result.severity is CertificateHealthSeverity.EXPIRED
    assert result.days_until_expiry < 0


# ── health() disk path ──────────────────────────────────────────────────────


def test_health_disk_path_ok(tmp_path: Path) -> None:
    now = _NOW
    p12 = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=365),
    )
    from pydantic import SecretStr

    result = health(
        p12,
        password=SecretStr(_SECRET),
        warn_days=_WARN_DAYS,
        critical_days=_CRITICAL_DAYS,
        now=now,
    )
    assert result.severity is CertificateHealthSeverity.OK
    assert "aeat-health-subject" in result.subject


# ── Model & error invariants ────────────────────────────────────────────────


def test_health_model_is_frozen(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(tmp_path, not_valid_after=now + timedelta(days=200))
    result = evaluate_loaded_certificate_health(cert, warn_days=_WARN_DAYS, critical_days=_CRITICAL_DAYS, now=now)
    assert isinstance(result, CertificateHealth)
    with pytest.raises(ValueError, match=r"frozen|Instance is frozen"):
        result.severity = CertificateHealthSeverity.CRITICAL


def test_pre_expiry_error_is_cadrumo_error() -> None:
    assert issubclass(CertificatePreExpiryError, CadrumoError)


def test_evaluate_rejects_inverted_thresholds(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(tmp_path, not_valid_after=now + timedelta(days=100))
    with pytest.raises(ValueError, match=r"warn_days|critical_days|threshold"):
        evaluate_loaded_certificate_health(cert, warn_days=10, critical_days=30, now=now)


def test_evaluate_rejects_nonpositive_critical(tmp_path: Path) -> None:
    now = _NOW
    cert = _loaded_cert_for_window(tmp_path, not_valid_after=now + timedelta(days=100))
    with pytest.raises(ValueError, match=r"critical_days|must be positive|greater than"):
        evaluate_loaded_certificate_health(cert, warn_days=60, critical_days=0, now=now)
