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
from pydantic import SecretStr

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ... import wizard as _wizard  # noqa: F401  (importing wizard seeds the ProfileKey registry)
from ...user_profile import profile_create_storage_span, register_minimal_profile
from ...workflow import workflow_state_repository
from .. import (
    ProviderProbeResult,
    check_operator_certificate_sources,
    inspect_operator_auth,
    register_operator_certificate_source,
    resolve_active_certificate_credentials,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from .._operator import test_operator_auth as run_operator_auth_test

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


# ---------------------------------------------------------------------------
# Shared-resolution parity: register, select, check, status, test, and the
# active-credential resolver must all consume the SAME certificate bytes and
# the same secure-storage secret. No global-credential fallback for a selected
# named source.
# ---------------------------------------------------------------------------


@pytest.fixture
def _isolated_secret_store(tmp_path: Path) -> Iterator[SecretStore]:
    """Inject a deterministic :class:`SecretStore` for the per-source secret tests.

    ``get_secret_store()`` is a process-wide singleton; overriding it keeps
    the certificate-secret writes/reads (set, resolve, check, status, test)
    isolated and consistent within the test.
    """
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "sec-blobs", master_key_provider=provider)
    store = SecretStore(store_dir=tmp_path / "sec-secrets", blob_store=blob_store, master_key_provider=provider)
    override_secret_store(store)
    try:
        yield store
    finally:
        override_secret_store(None)


def _register_select_with_secret(tmp_path: Path) -> Path:
    """Register a real PKCS#12 source, bind its secure-storage passphrase, and select it.

    Returns the certificate path. The bound secret is ``_SECRET`` — the same
    passphrase the bundle is encrypted with — so a probe opening the bundle
    with the resolved per-source secret succeeds.
    """
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(_SECRET))
    select_operator_certificate_source(name="personal")
    return cert_path


def test_resolver_returns_selected_source_path_and_secure_storage_secret(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """The active-credential resolver returns the selected source's path and its stored secret."""
    cert_path = _register_select_with_secret(tmp_path)

    credentials = resolve_active_certificate_credentials()

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == _SECRET


def test_check_opens_the_bundle_with_the_secure_storage_secret_no_global_fallback(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """``check`` resolves each source's passphrase from secure storage, not a global setting.

    No ``override_settings(cadrumo_certificate_password_secret=...)`` is
    applied: the probe must open the PKCS#12 with the per-source
    secure-storage secret alone, classifying it ``ok``.
    """
    _register_select_with_secret(tmp_path)

    report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.name == "personal"
    assert entry.result == ProviderProbeResult.OK


def test_status_test_and_resolver_agree_on_the_selected_certificate_bytes(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """``auth status``, ``auth test``, and the resolver report the same certificate path.

    ``auth test`` additionally opens the bundle through its probe using the
    resolved per-source secret, so its probe classifies ``ok`` — proving the
    same resolved bytes and secret flow through the status/test surfaces.
    """
    cert_path = _register_select_with_secret(tmp_path)

    status = inspect_operator_auth("certificate")
    test_result = run_operator_auth_test("certificate")
    credentials = resolve_active_certificate_credentials()

    assert credentials.certificate_path == cert_path
    assert status.certificate_path == str(cert_path)
    assert test_result.certificate_path == str(cert_path)
    assert test_result.probe_result == ProviderProbeResult.OK


def test_selected_source_without_secret_fails_closed_no_global_credential_leak(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A selected source with no bound secret resolves ``password=None`` and never leaks a global secret."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    select_operator_certificate_source(name="personal")

    with override_settings(cadrumo_certificate_password_secret=SecretStr("unrelated-global-secret")):
        credentials = resolve_active_certificate_credentials()

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is None
