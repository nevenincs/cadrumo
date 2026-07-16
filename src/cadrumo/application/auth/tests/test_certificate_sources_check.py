"""Real-behavior tests for certificate-source expiry/rotation awareness.

Exercises :func:`application.auth.check_operator_certificate_sources`
against real self-signed PKCS#12 bundles generated at runtime via
:mod:`cryptography` — no mocks or fakes — mirroring the pattern already
established for the single-certificate health evaluator in
``adapters/outbound/aeat/auth/tests/test_health.py``. See GitHub issue
#591 (multi-cert rotation-awareness slice).
"""

from __future__ import annotations

import asyncio
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
    get_secret_store,
    override_secret_store,
)
from ....adapters.persistence.storage.master_key import current_active_bucket_session
from ....core import AuthProviderKind
from ....core.config import load_settings, override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ... import wizard as _wizard  # noqa: F401  (importing wizard seeds the ProfileKey registry)
from ...state_projection import build_operator_state_projection
from ...user_profile import (
    profile_create_storage_span,
    profile_storage_session,
    register_minimal_profile,
)
from ...workflow import workflow_state_repository
from .. import (
    AuthLoginPreconditionError,
    ProviderProbeResult,
    build_live_auth_preflight_report,
    check_operator_certificate_sources,
    configure_operator_auth,
    inspect_operator_auth,
    login_operator_auth,
    project_active_certificate_credentials,
    register_operator_certificate_source,
    resolve_active_certificate_credentials,
    select_operator_certificate_source,
    select_provider,
    set_operator_certificate_source_secret,
    update_auth,
)
from .._operator import test_operator_auth as run_operator_auth_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_BUCKET_B = "44444444-4444-4444-8444-444444444444"
_MISSING_BUCKET = "55555555-5555-4555-8555-555555555555"
_PROFILE_LABEL = "gestor-cert-rotation"
_SECRET = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret
_SECRET_B = "bucket-b-correct-horse"  # noqa: S105 - synthetic test fixture, not a secret
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)


def _register_operator_profile():
    return lambda state: register_minimal_profile(
        state,
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Open an isolated storage root plus an active bucket session for the whole test."""
    if "_manages_storage_roots" in request.fixturenames:
        yield
        return
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield


@pytest.fixture
def _manages_storage_roots() -> None:
    """Let one route-isolation test own both complete storage-root contexts."""


def _build_pkcs12(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str,
    subject_cn: str,
    password: str = _SECRET,
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
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    out = tmp_path / f"{name}.p12"
    out.write_bytes(pfx_bytes)
    return out


def test_check_reports_ok_for_a_certificate_far_from_expiry(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
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
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(_SECRET))

    report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.name == "personal"
    assert entry.result == ProviderProbeResult.OK
    assert entry.days_until_expiry is not None
    assert entry.days_until_expiry >= 199
    assert report.has_warnings is False


def test_check_reports_expiring_within_the_warning_window(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
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
    set_operator_certificate_source_secret(name="apoderado-acme", secret=SecretStr(_SECRET))

    report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.result == ProviderProbeResult.EXPIRING
    assert entry.days_until_expiry is not None
    assert 0 < entry.days_until_expiry <= 60
    assert report.has_warnings is True


def test_check_reports_expired_for_a_lapsed_certificate(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
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
    set_operator_certificate_source_secret(name="expired-cert", secret=SecretStr(_SECRET))

    report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.result == ProviderProbeResult.EXPIRED
    assert entry.days_until_expiry is not None
    assert entry.days_until_expiry < 0
    assert report.has_warnings is True


def test_check_covers_every_registered_source_independently(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
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
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(_SECRET))
    set_operator_certificate_source_secret(name="apoderado-acme", secret=SecretStr(_SECRET))

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

    ``override_secret_store`` installs an explicit process-wide test store so
    certificate-secret writes/reads (set, resolve, check, status, test) stay
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

    The global password is intentionally wrong: the probe must open the
    PKCS#12 with the per-source secure-storage secret alone, classifying
    it ``ok``.
    """
    _register_select_with_secret(tmp_path)

    with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
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

    with override_settings(
        cadrumo_certificate_password_secret=SecretStr("unrelated-global-secret"),
        cadrumo_certificate_friendly_name="unrelated-global-label",
    ):
        credentials = resolve_active_certificate_credentials()

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is None
    assert credentials.friendly_name is None


def test_central_provider_and_explicit_or_omitted_probes_fail_closed_without_named_secret(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A valid global password cannot satisfy a selected named source with no bound secret."""
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
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path)

    with override_settings(cadrumo_certificate_password_secret=SecretStr(_SECRET)):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()
        explicit_status = inspect_operator_auth(AuthProviderKind.CERTIFICATE.value)
        omitted_status = inspect_operator_auth()
        explicit_test = run_operator_auth_test(AuthProviderKind.CERTIFICATE.value)
        omitted_test = run_operator_auth_test()
        omitted_preflight = build_live_auth_preflight_report()

    assert provider_description.available is False
    assert explicit_status.provider == AuthProviderKind.CERTIFICATE.value
    assert omitted_status.provider == AuthProviderKind.CERTIFICATE.value
    assert explicit_status.available is False
    assert omitted_status.available is False
    assert explicit_test.probe_result == ProviderProbeResult.CORRUPT
    assert omitted_test.probe_result == ProviderProbeResult.CORRUPT
    assert omitted_preflight.certificate_path_configured is True
    assert omitted_preflight.certificate_file_present is True


def test_bound_named_secret_wins_over_wrong_global_through_central_and_omitted_routes(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """The selected secure-storage secret feeds the central factory and omitted probes."""
    cert_path = _register_select_with_secret(tmp_path)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path)

    with override_settings(
        cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global"),
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()
        omitted_status = inspect_operator_auth()
        omitted_test = run_operator_auth_test()

    assert provider_description.available is True
    assert omitted_status.provider == AuthProviderKind.CERTIFICATE.value
    assert omitted_status.available is True
    assert omitted_test.probe_result == ProviderProbeResult.OK


def test_reregistering_active_source_keeps_resolver_provider_status_and_test_on_new_path(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Renewing the selected source updates its path mirror and every consuming surface."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_v1 = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="selected-v1",
        subject_cn="selected-v1",
    )
    cert_v2 = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=300),
        name="selected-v2",
        subject_cn="selected-v2",
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_v1)
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET))
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_v1)
    register_operator_certificate_source(name="selected", certificate_path=cert_v2)
    cert_v1.unlink()

    with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
        credentials = resolve_active_certificate_credentials()
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()
        status = inspect_operator_auth()
        test_result = run_operator_auth_test()

    assert credentials.certificate_path == cert_v2
    assert provider_description.configured is True
    assert provider_description.available is True
    assert status.certificate_path == str(cert_v2)
    assert status.configured is True
    assert status.available is True
    assert test_result.certificate_path == str(cert_v2)
    assert test_result.configured is True
    assert test_result.probe_result == ProviderProbeResult.OK


def test_resolver_preserves_unnamed_single_certificate_credential_when_no_named_source_is_selected(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """An unselected registration preserves the unnamed Settings path and password."""
    workflow_state_repository().update(_register_operator_profile())
    registered_path = tmp_path / "registered-but-inactive.p12"
    registered_path.write_bytes(b"registered source bytes")
    register_operator_certificate_source(name="inactive", certificate_path=registered_path)
    global_path = tmp_path / "unnamed-certificate.p12"
    global_path.write_bytes(b"unnamed single-certificate bytes")
    global_password = SecretStr("unnamed-certificate-password")

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=global_password,
        cadrumo_certificate_friendly_name="unnamed-certificate",
    ):
        credentials = resolve_active_certificate_credentials()

    assert credentials.source_name is None
    assert credentials.certificate_path == global_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == global_password.get_secret_value()
    assert credentials.friendly_name == "unnamed-certificate"


def test_central_provider_preserves_unnamed_single_certificate_credential_without_selected_source(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """The unnamed Settings path and password remain valid when no source is selected."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    global_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="legacy-global",
        subject_cn="legacy-global",
    )
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=global_path)

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(_SECRET),
        cadrumo_certificate_friendly_name="legacy-global",
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()
        omitted_status = inspect_operator_auth()
        omitted_test = run_operator_auth_test()

    assert provider_description.available is True
    assert omitted_status.provider == AuthProviderKind.CERTIFICATE.value
    assert omitted_status.available is True
    assert omitted_test.probe_result == ProviderProbeResult.OK


def test_explicit_global_settings_path_overrides_stale_workflow_mirror_for_status_and_test(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Legacy explicit Settings path is the same path emitted and probed by every surface."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    stale_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="stale-workflow",
        subject_cn="stale-workflow",
    )
    explicit_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=300),
        name="explicit-settings",
        subject_cn="explicit-settings",
    )
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=stale_path)
    stale_path.unlink()

    with override_settings(
        cadrumo_certificate_path=explicit_path,
        cadrumo_certificate_password_secret=SecretStr(_SECRET),
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()
        status = inspect_operator_auth()
        test_result = run_operator_auth_test()

    assert provider_description.available is True
    assert status.certificate_path == str(explicit_path)
    assert status.configured is True
    assert status.available is True
    assert test_result.certificate_path == str(explicit_path)
    assert test_result.configured is True
    assert test_result.probe_result == ProviderProbeResult.OK


def test_central_provider_uses_configured_workflow_path_when_global_path_is_absent(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """``auth configure --file`` remains the path authority for central callers."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    configured_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="configured-file",
        subject_cn="configured-file",
    )
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=configured_path)

    with override_settings(
        cadrumo_certificate_path=None,
        cadrumo_certificate_password_secret=SecretStr(_SECRET),
    ):
        credentials = resolve_active_certificate_credentials()
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()

    assert credentials.certificate_path == configured_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == _SECRET
    assert provider_description.available is True


def test_explicit_settings_second_root_uses_its_own_cached_secret_store(
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """Initializing root A first cannot redirect root B certificate secrets into A."""
    override_secret_store(None)
    try:
        root_a_fixture = tmp_path / "route-a"
        with (
            isolated_profile_storage_root(tmp_path=root_a_fixture),
            profile_create_storage_span(_BUCKET_ID),
        ):
            workflow_state_repository().update(_register_operator_profile())
            now = datetime.now(UTC)
            cert_a = _build_pkcs12(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="route-a",
                subject_cn="route-a",
            )
            register_operator_certificate_source(name="selected", certificate_path=cert_a)
            set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET))
            select_operator_certificate_source(name="selected")
            configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
            settings_a = load_settings()
            store_a = get_secret_store(settings=settings_a)

        root_b_fixture = tmp_path / "route-b"
        with (
            isolated_profile_storage_root(tmp_path=root_b_fixture),
            profile_create_storage_span(_BUCKET_B),
        ):
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id=_BUCKET_B,
                    display_name="gestor-route-b",
                ),
            )
            cert_b = _build_pkcs12(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="route-b",
                subject_cn="route-b",
                password=_SECRET_B,
            )
            register_operator_certificate_source(name="selected", certificate_path=cert_b)
            with override_settings(cadrumo_blob_store_dir=tmp_path / "route-b-explicit-blobs") as settings_b:
                set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET_B))
                select_operator_certificate_source(name="selected")
                configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)
                store_b = get_secret_store(settings=settings_b)
                credentials_b = resolve_active_certificate_credentials(settings=settings_b)
                provider_b = select_provider(
                    AuthProviderKind.CERTIFICATE,
                    settings=settings_b,
                ).describe()
                operator_test_b = run_operator_auth_test(settings=settings_b)

        assert store_a is not store_b
        assert store_a.store_dir == settings_a.cadrumo_secret_store_dir
        assert store_b.store_dir == settings_b.cadrumo_secret_store_dir
        assert credentials_b.certificate_path == cert_b
        assert credentials_b.password is not None
        assert credentials_b.password.get_secret_value() == _SECRET_B
        assert provider_b.available is True
        assert operator_test_b.certificate_path == str(cert_b)
        assert operator_test_b.probe_result == ProviderProbeResult.OK
    finally:
        override_secret_store(None)


def test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session(
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """A matching UUID cannot reuse key material from a different storage root."""
    override_secret_store(None)
    try:
        now = datetime.now(UTC)
        root_b_fixture = tmp_path / "same-id-route-b"
        with (
            isolated_profile_storage_root(tmp_path=root_b_fixture),
            override_settings(cadrumo_blob_store_dir=tmp_path / "same-id-route-b-blobs"),
            profile_create_storage_span(_BUCKET_ID),
        ):
            workflow_state_repository().update(_register_operator_profile())
            cert_b = _build_pkcs12(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="same-id-route-b",
                subject_cn="same-id-route-b",
                password=_SECRET_B,
            )
            register_operator_certificate_source(name="selected", certificate_path=cert_b)
            set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET_B))
            select_operator_certificate_source(name="selected")
            configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)
            settings_b = load_settings()

        root_a_fixture = tmp_path / "same-id-route-a"
        with (
            isolated_profile_storage_root(tmp_path=root_a_fixture),
            override_settings(cadrumo_blob_store_dir=tmp_path / "same-id-route-a-blobs"),
            profile_create_storage_span(_BUCKET_ID),
        ):
            workflow_state_repository().update(_register_operator_profile())
            cert_a = _build_pkcs12(
                tmp_path,
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=200),
                name="same-id-route-a",
                subject_cn="same-id-route-a",
            )
            register_operator_certificate_source(name="selected", certificate_path=cert_a)
            set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET))
            select_operator_certificate_source(name="selected")
            configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
            configure_operator_auth(AuthProviderKind.CLAVE_MOVIL.value)

            ambient_before = current_active_bucket_session()
            assert ambient_before is not None
            assert ambient_before.bucket_id == _BUCKET_ID

            credentials_b = resolve_active_certificate_credentials(settings=settings_b)
            provider_b = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=settings_b,
            ).describe()
            check_b = check_operator_certificate_sources(settings=settings_b)
            operator_test_b = run_operator_auth_test(settings=settings_b)
            preflight_b = build_live_auth_preflight_report(settings=settings_b)

            ambient_after = current_active_bucket_session()
            assert credentials_b.certificate_path == cert_b
            assert credentials_b.password is not None
            assert credentials_b.password.get_secret_value() == _SECRET_B
            assert provider_b.available is True
            assert len(check_b.entries) == 1
            assert check_b.entries[0].certificate_path == str(cert_b)
            assert check_b.entries[0].result == ProviderProbeResult.OK
            assert operator_test_b.certificate_path == str(cert_b)
            assert operator_test_b.probe_result == ProviderProbeResult.OK
            assert preflight_b.provider == AuthProviderKind.CERTIFICATE.value
            assert preflight_b.certificate_path_configured is True
            assert preflight_b.certificate_file_present is True
            assert ambient_after is ambient_before
    finally:
        override_secret_store(None)


def test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A retained state snapshot has no authority to read a later bucket's secret."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_a = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="retained-state-a",
        subject_cn="retained-state-a",
        password=_SECRET_B,
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_a)
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET))
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
    workflow_state_repository().update(
        lambda state: update_auth(
            state,
            provider=AuthProviderKind.CERTIFICATE.value,
            authenticated=True,
        ),
    )
    retained_state_a = workflow_state_repository().load()
    assert retained_state_a.auth.authenticated_at is not None

    with profile_create_storage_span(_BUCKET_B):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_BUCKET_B,
                display_name="gestor-retained-state-b",
            ),
        )
        cert_b = _build_pkcs12(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="retained-state-b",
            subject_cn="retained-state-b",
            password=_SECRET_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)

    with profile_storage_session(_BUCKET_B):
        projected_credentials = project_active_certificate_credentials(
            retained_state_a,
            settings=load_settings(),
        )
        projection = build_operator_state_projection(
            state=retained_state_a,
            requested_provider=AuthProviderKind.CERTIFICATE.value,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
        )

    assert projected_credentials.certificate_path == cert_a
    assert projected_credentials.source_name == "selected"
    assert projected_credentials.password is None
    assert projection.auth.certificate_path == str(cert_a)
    assert projection.auth.available is False
    assert projection.auth.health_summary == ""


def test_explicit_settings_provider_resolution_uses_target_bucket_and_restores_ambient_session(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Direct provider construction resolves the bucket named by Settings, not ambient state."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    cert_a = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="bucket-a",
        subject_cn="bucket-a",
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_a, friendly_name="bucket-a")
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET))
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)

    with profile_create_storage_span(_BUCKET_B):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_BUCKET_B,
                display_name="gestor-cert-b",
            ),
        )
        cert_b = _build_pkcs12(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="bucket-b",
            subject_cn="bucket-b",
            password=_SECRET_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b, friendly_name="bucket-b")
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(_SECRET_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)

    ambient_before = current_active_bucket_session()
    assert ambient_before is not None
    assert ambient_before.bucket_id == _BUCKET_ID
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    credentials = resolve_active_certificate_credentials(settings=settings_b)
    provider_description = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=settings_b,
    ).describe()
    check_report = check_operator_certificate_sources(settings=settings_b)

    ambient_after = current_active_bucket_session()
    assert credentials.source_name == "selected"
    assert credentials.certificate_path == cert_b
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == _SECRET_B
    assert credentials.friendly_name == "bucket-b"
    assert provider_description.available is True
    assert len(check_report.entries) == 1
    assert check_report.entries[0].certificate_path == str(cert_b)
    assert check_report.entries[0].result == ProviderProbeResult.OK
    assert ambient_after is ambient_before


def test_unreadable_explicit_settings_target_fails_closed_without_global_fallback(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """An unreadable explicit bucket cannot inherit otherwise valid global credentials."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    global_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="global-must-not-leak",
        subject_cn="global-must-not-leak",
    )
    with override_settings(
        cadrumo_active_profile=_MISSING_BUCKET,
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(_SECRET),
    ) as missing_settings:
        pass

    credentials = resolve_active_certificate_credentials(settings=missing_settings)
    provider_description = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=missing_settings,
    ).describe()

    assert credentials.certificate_path is None
    assert credentials.password is None
    assert credentials.friendly_name is None
    assert credentials.source_name is None
    assert provider_description.configured is False
    assert provider_description.available is False


def test_login_refuses_selected_missing_file_before_unrelated_valid_global_certificate(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Public login applies the selected source path before its local precondition."""
    workflow_state_repository().update(_register_operator_profile())
    now = datetime.now(UTC)
    selected_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="selected-missing",
        subject_cn="selected-missing",
    )
    global_path = _build_pkcs12(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="unrelated-global",
        subject_cn="unrelated-global",
    )
    register_operator_certificate_source(name="selected", certificate_path=selected_path)
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=selected_path)
    selected_path.unlink()

    with (
        override_settings(
            cadrumo_certificate_path=global_path,
            cadrumo_certificate_password_secret=SecretStr(_SECRET),
            cadrumo_live_tests_enabled="1",
        ),
        pytest.raises(AuthLoginPreconditionError) as raised,
    ):
        asyncio.run(login_operator_auth(AuthProviderKind.CERTIFICATE.value))

    assert raised.value.translated_message == "application.auth.operator.login.refused_certificate_file_missing"
    context = raised.value.context
    assert context is not None
    assert context["path"] == str(selected_path)


def test_check_named_source_without_secret_never_inherits_a_valid_global_password(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A named source without a bound secret fails closed even when the global password would open it."""
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

    with override_settings(cadrumo_certificate_password_secret=SecretStr(_SECRET)):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT


def test_check_named_source_fails_closed_when_secure_storage_cannot_be_read(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A real corrupt secure-storage index cannot redirect a named source to the valid global password."""
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
    (_isolated_secret_store.store_dir / "index.json").write_text("{not-json", encoding="utf-8")

    with override_settings(cadrumo_certificate_password_secret=SecretStr(_SECRET)):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT
