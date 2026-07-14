"""Real-behavior tests for certificate-source expiry/rotation awareness.

Exercises :func:`application.auth.check_operator_certificate_sources`
against real self-signed PKCS#12 bundles generated at runtime via
:mod:`cryptography` — no mocks or fakes — mirroring the pattern already
established for the single-certificate health evaluator in
``adapters/outbound/aeat/auth/tests/test_health.py``. See GitHub issue
#591 (multi-cert rotation-awareness slice).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ... import wizard as _wizard  # noqa: F401  (importing wizard seeds the ProfileKey registry)
from ...user_profile import profile_create_storage_span, register_minimal_profile
from ...workflow import workflow_state_repository
from .. import (
    ProviderProbeResult,
    check_operator_certificate_sources,
    register_operator_certificate_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_PROFILE_LABEL = "gestor-cert-rotation"
_SECRET = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)


def _register_operator_profile():
    return lambda state: register_minimal_profile(
        state,
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Open an isolated storage root plus an active bucket session for the whole test."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield


def _build_pkcs12(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str,
    subject_cn: str,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle with the given validity window."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, subject_cn),
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
        name=name.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(_SECRET.encode("utf-8")),
    )
    out = tmp_path / f"{name}.p12"
    out.write_bytes(pfx_bytes)
    return out


def test_check_reports_ok_for_a_certificate_far_from_expiry(tmp_path: Path) -> None:
    """A certificate with hundreds of days remaining is classified ``ok``."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = _build_pkcs12(
        tmp_path,
        not_valid_before=_NOW - timedelta(days=1),
        not_valid_after=_NOW + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)

    with override_settings(cadrumo_certificate_password_secret=_SECRET):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.name == "personal"
    assert entry.result == ProviderProbeResult.OK
    assert entry.days_until_expiry is not None
    assert entry.days_until_expiry >= 199
    assert report.has_warnings is False


def test_check_reports_expiring_within_the_warning_window(tmp_path: Path) -> None:
    """A certificate inside the 60-day warning window is classified ``expiring``.

    Uses ``freeze_time``-free real-clock-relative dates: the warning
    threshold is evaluated against wall-clock ``now()`` inside the
    probe, so the fixture is built relative to real "now" rather than a
    frozen reference to avoid a second clock dependency in the test.
    """
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="apoderado-acme",
        subject_cn="apoderado-acme",
    )
    register_operator_certificate_source(name="apoderado-acme", certificate_path=cert_path)

    with override_settings(cadrumo_certificate_password_secret=_SECRET):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.result == ProviderProbeResult.EXPIRING
    assert entry.days_until_expiry is not None
    assert 0 < entry.days_until_expiry <= 60
    assert report.has_warnings is True


def test_check_reports_expired_for_a_lapsed_certificate(tmp_path: Path) -> None:
    """A certificate whose validity has already elapsed is classified ``expired``."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=400),
        not_valid_after=now - timedelta(days=5),
        name="expired-cert",
        subject_cn="expired-cert",
    )
    register_operator_certificate_source(name="expired-cert", certificate_path=cert_path)

    with override_settings(cadrumo_certificate_password_secret=_SECRET):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.result == ProviderProbeResult.EXPIRED
    assert entry.days_until_expiry is not None
    assert entry.days_until_expiry < 0
    assert report.has_warnings is True


def test_check_covers_every_registered_source_independently(tmp_path: Path) -> None:
    """Each registered source is classified independently, not only the active one.

    A gestor with a valid personal certificate and an expiring apoderado
    certificate must see BOTH verdicts, and ``has_warnings`` must reflect
    the union across sources — not just whichever source is active.
    """
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    valid_cert = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=300),
        name="personal",
        subject_cn="gestor-personal",
    )
    expiring_cert = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=10),
        name="apoderado-acme",
        subject_cn="apoderado-acme",
    )
    register_operator_certificate_source(name="personal", certificate_path=valid_cert)
    register_operator_certificate_source(name="apoderado-acme", certificate_path=expiring_cert, friendly_name="ACME SL")

    with override_settings(cadrumo_certificate_password_secret=_SECRET):
        report = check_operator_certificate_sources()

    by_name = {entry.name: entry for entry in report.entries}
    assert set(by_name) == {"personal", "apoderado-acme"}
    assert by_name["personal"].result == ProviderProbeResult.OK
    assert by_name["apoderado-acme"].result == ProviderProbeResult.EXPIRING
    assert by_name["apoderado-acme"].friendly_name == "ACME SL"
    assert report.has_warnings is True, "the active-source selection must not mask the expiring apoderado certificate"


def test_check_classifies_a_missing_certificate_file_distinctly(tmp_path: Path) -> None:
    """A registered source whose file has since been deleted surfaces ``file_missing``, never ``ok``."""
    workflow_state_repository().update(_register_operator_profile())
    ghost_path = tmp_path / "deleted.p12"
    ghost_path.write_bytes(b"placeholder")
    register_operator_certificate_source(name="deleted", certificate_path=ghost_path)
    ghost_path.unlink()

    with override_settings(cadrumo_certificate_password_secret=_SECRET):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.result == ProviderProbeResult.FILE_MISSING
    assert entry.days_until_expiry is None
    assert report.has_warnings is False, "a missing file is a distinct problem from an approaching expiry"


def test_check_with_no_registered_sources_is_empty_and_has_no_warnings() -> None:
    """No registered sources yields an empty report, not an error."""
    workflow_state_repository().update(_register_operator_profile())

    report = check_operator_certificate_sources()

    assert report.entries == ()
    assert report.has_warnings is False
