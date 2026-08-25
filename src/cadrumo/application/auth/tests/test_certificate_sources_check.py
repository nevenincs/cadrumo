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
from pydantic import SecretStr, ValidationError

from ....adapters.outbound.aeat.auth import _session_store
from ....adapters.persistence.storage import SECRET_INDEX_FILENAME, SecretStore, get_secret_store
from ....adapters.persistence.storage.master_key import current_active_bucket_session
from ....core import AuthProviderKind
from ....core.bucket_pointer import BucketPointer, write_pointer
from ....core.config import load_settings, override_settings
from ....tests.certificates import CERTIFICATE_BUNDLE_PASSPHRASE, build_pkcs12_bundle
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ... import wizard as _wizard  # noqa: F401  (importing wizard seeds the ProfileKey registry)
from ...state_projection import build_operator_state_projection
from ...workflow import workflow_state_repository
from ..actions import update_auth
from ..certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ..credentials import (
    active_auth_projection_span,
    project_active_certificate_credentials,
    resolve_active_certificate_credentials,
)
from ..operator import (
    _test_operator_auth_from_snapshot,
    build_live_auth_preflight_report,
    configure_operator_auth,
    inspect_operator_auth,
    login_operator_auth,
)
from ..operator import test_operator_auth as run_operator_auth_test
from ..operator_probes import probe_provider_credentials
from ..operator_results import (
    AuthLoginPreconditionError,
    AuthOperationRequiresCustodySessionError,
    CertificateSourceCheckEntry,
)
from ..probes import ProviderProbeResult
from ..providers import select_provider
from ..sessions import load_persisted_session, storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_BUCKET_B = "44444444-4444-4444-8444-444444444444"
_MISSING_BUCKET = "55555555-5555-4555-8555-555555555555"
_PROFILE_LABEL = "gestor-cert-rotation"
_PROFILE_LABEL_B = "gestor-route-snapshot-b"
CERTIFICATE_BUNDLE_PASSPHRASE_B = "bucket-b-correct-horse"  # noqa: S105 - synthetic test fixture, not a secret
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("invalid_result", ("", "ok", "OK", "not-a-verdict"))
def test_certificate_source_check_entry_refuses_noncanonical_probe_verdicts(invalid_result: str) -> None:
    """The operator projection cannot widen the closed provider-probe result enum."""
    with pytest.raises(ValidationError, match="result"):
        CertificateSourceCheckEntry(
            name="personal",
            certificate_path="C:/certificates/personal.p12",
            result=invalid_result,
            summary="certificate verdict",
        )


def test_certificate_source_check_entry_preserves_probe_verdict_json_value() -> None:
    """A canonical verdict remains typed in memory and serializes as its wire value."""
    entry = CertificateSourceCheckEntry(
        name="personal",
        certificate_path="C:/certificates/personal.p12",
        result=ProviderProbeResult.OK,
        summary="certificate valid",
    )

    assert entry.result is ProviderProbeResult.OK
    assert entry.model_dump(mode="json")["result"] == ProviderProbeResult.OK.value


def _register_operator_profile() -> None:
    """Seed and select the operator profile before anything opens its bucket store.

    Ordering is load-bearing, not stylistic. The capsule is published by an
    atomic no-replace directory rename onto ``buckets/<profile-id>``, and
    ``workflow_state_repository()`` materialises ``buckets/<profile-id>/db``
    on first access -- so a workflow read taken first makes the rename
    collide. Seeding through a detached ``WorkflowState`` keeps the capsule
    first; the helper only passes that argument back to its caller.
    """
    register_minimal_profile(
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
        open_test_profile_session(_BUCKET_ID),
    ):
        yield


@pytest.fixture
def _manages_storage_roots() -> None:
    """Let one route-isolation test own both complete storage-root contexts."""


def test_check_reports_ok_for_a_certificate_far_from_expiry(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A certificate with hundreds of days remaining is classified ``ok``."""
    _register_operator_profile()
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=_NOW - timedelta(days=1),
        not_valid_after=_NOW + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))

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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="apoderado-acme",
        subject_cn="apoderado-acme",
    )
    register_operator_certificate_source(name="apoderado-acme", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="apoderado-acme", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))

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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=400),
        not_valid_after=now - timedelta(days=5),
        name="expired-cert",
        subject_cn="expired-cert",
    )
    register_operator_certificate_source(name="expired-cert", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="expired-cert", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))

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
    _register_operator_profile()
    now = datetime.now(UTC)
    valid_cert = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=300),
        name="personal",
        subject_cn="gestor-personal",
    )
    expiring_cert = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=10),
        name="apoderado-acme",
        subject_cn="apoderado-acme",
    )
    register_operator_certificate_source(name="personal", certificate_path=valid_cert)
    register_operator_certificate_source(name="apoderado-acme", certificate_path=expiring_cert, friendly_name="ACME SL")
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    set_operator_certificate_source_secret(name="apoderado-acme", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))

    report = check_operator_certificate_sources()

    by_name = {entry.name: entry for entry in report.entries}
    assert set(by_name) == {"personal", "apoderado-acme"}
    assert by_name["personal"].result == ProviderProbeResult.OK
    assert by_name["apoderado-acme"].result == ProviderProbeResult.EXPIRING
    assert by_name["apoderado-acme"].friendly_name == "ACME SL"
    assert report.has_warnings is True, "the active-source selection must not mask the expiring apoderado certificate"


def test_check_classifies_a_missing_certificate_file_distinctly(tmp_path: Path) -> None:
    """A registered source whose file has since been deleted surfaces ``file_missing``, never ``ok``."""
    _register_operator_profile()
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
    _register_operator_profile()

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
def _isolated_secret_store() -> SecretStore:
    """Return the route-canonical :class:`SecretStore` for the per-source secret tests.

    The settings route and the active bucket session's master key are
    already isolated per test by the ``_isolated_backend`` autouse
    fixture, so the route-canonical store from :func:`get_secret_store`
    is already test-isolated without a process-wide override.
    """
    return get_secret_store()


def _register_select_with_secret(tmp_path: Path) -> Path:
    """Register a real PKCS#12 source, bind its secure-storage passphrase, and select it.

    Returns the certificate path. The bound secret is ``CERTIFICATE_BUNDLE_PASSPHRASE`` — the same
    passphrase the bundle is encrypted with — so a probe opening the bundle
    with the resolved per-source secret succeeds.
    """
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
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
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE


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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    select_operator_certificate_source(name="personal")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path)

    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_v1 = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="selected-v1",
        subject_cn="selected-v1",
    )
    cert_v2 = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=300),
        name="selected-v2",
        subject_cn="selected-v2",
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_v1)
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
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
    _register_operator_profile()
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
    _register_operator_profile()
    now = datetime.now(UTC)
    global_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="legacy-global",
        subject_cn="legacy-global",
    )
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=global_path)

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
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
    _register_operator_profile()
    now = datetime.now(UTC)
    stale_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=30),
        name="stale-workflow",
        subject_cn="stale-workflow",
    )
    explicit_path = build_pkcs12_bundle(
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
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
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
    _register_operator_profile()
    now = datetime.now(UTC)
    configured_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="configured-file",
        subject_cn="configured-file",
    )
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=configured_path)

    with override_settings(
        cadrumo_certificate_path=None,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
    ):
        credentials = resolve_active_certificate_credentials()
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
        ).describe()

    assert credentials.certificate_path == configured_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE
    assert provider_description.available is True


def test_explicit_settings_second_root_uses_its_own_cached_secret_store(
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """Initializing root A first cannot redirect root B certificate secrets into A."""
    root_a_fixture = tmp_path / "route-a"
    with (
        isolated_profile_storage_root(tmp_path=root_a_fixture),
        open_test_profile_session(_BUCKET_ID),
    ):
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="route-a",
            subject_cn="route-a",
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_a)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
        settings_a = load_settings()
        store_a = get_secret_store(settings=settings_a)

    root_b_fixture = tmp_path / "route-b"
    with (
        isolated_profile_storage_root(tmp_path=root_b_fixture),
        open_test_profile_session(_BUCKET_B),
    ):
        register_minimal_profile(
            profile_id=_BUCKET_B,
            display_name="gestor-route-b",
        )
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="route-b",
            subject_cn="route-b",
            password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b)
        with override_settings(cadrumo_blob_store_dir=tmp_path / "route-b-explicit-blobs") as settings_b:
            set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
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
    assert credentials_b.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE_B
    assert provider_b.available is True
    assert operator_test_b.certificate_path == str(cert_b)
    assert operator_test_b.probe_result == ProviderProbeResult.OK


def test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session(
    _manages_storage_roots: None,
    tmp_path: Path,
) -> None:
    """A matching UUID cannot reuse key material from a different storage root.

    Per-profile custody changed what "cannot" looks like. These calls once
    opened root B's bucket on demand and answered from B's own material; they
    now cannot, because opening B's custody session needs the operator's
    password. The guarantee under test is unchanged and the stricter end of it
    holds: root A's open session never answers a root B question.

    The surfaces split on HOW they decline, and the split is asserted rather
    than smoothed over. The credential resolver and the provider factory
    swallow the refusal and return an empty credential -- a truthful "no
    credential is available", which every consumer already reads as
    not-configured. ``check``, ``auth test`` and the live preflight let it
    through, because each renders an operator VERDICT about a named profile
    and a silent "nothing found" would be indistinguishable from "inspected
    and found nothing" when nothing was inspected at all.
    """
    now = datetime.now(UTC)
    root_b_fixture = tmp_path / "same-id-route-b"
    with (
        isolated_profile_storage_root(tmp_path=root_b_fixture),
        override_settings(cadrumo_blob_store_dir=tmp_path / "same-id-route-b-blobs"),
        open_test_profile_session(_BUCKET_ID),
    ):
        _register_operator_profile()
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="same-id-route-b",
            subject_cn="same-id-route-b",
            password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)
        settings_b = load_settings()

    root_a_fixture = tmp_path / "same-id-route-a"
    with (
        isolated_profile_storage_root(tmp_path=root_a_fixture),
        override_settings(cadrumo_blob_store_dir=tmp_path / "same-id-route-a-blobs"),
        open_test_profile_session(_BUCKET_ID),
    ):
        _register_operator_profile()
        cert_a = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="same-id-route-a",
            subject_cn="same-id-route-a",
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_a)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
        configure_operator_auth(AuthProviderKind.CLAVE_MOVIL.value)

        ambient_before = current_active_bucket_session()
        assert ambient_before is not None
        assert ambient_before.bucket_id == _BUCKET_ID

        degraded_credentials = resolve_active_certificate_credentials(settings=settings_b)
        degraded_provider = select_provider(AuthProviderKind.CERTIFICATE, settings=settings_b).describe()

        assert degraded_credentials.certificate_path is None
        assert degraded_credentials.password is None
        assert degraded_credentials.source_name is None
        assert degraded_provider.configured is False
        assert degraded_provider.available is False

        for verdict_operation in (
            lambda: check_operator_certificate_sources(settings=settings_b),
            lambda: run_operator_auth_test(settings=settings_b),
            lambda: build_live_auth_preflight_report(settings=settings_b),
        ):
            with pytest.raises(AuthOperationRequiresCustodySessionError) as raised:
                verdict_operation()
            context = raised.value.context
            assert context is not None
            assert context["bucket_id"] == _BUCKET_ID
            assert root_b_fixture.name in str(context["storage_root"])
            assert root_a_fixture.name not in str(context["storage_root"])

        ambient_after = current_active_bucket_session()
        assert ambient_after is ambient_before
        assert ambient_after.bucket_id == _BUCKET_ID
        assert cert_a.exists()
        assert cert_b.exists()


def test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A retained state snapshot has no authority to read a later bucket's secret."""
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_a = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="retained-state-a",
        subject_cn="retained-state-a",
        password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_a)
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
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

    with open_test_profile_session(_BUCKET_B):
        register_minimal_profile(
            profile_id=_BUCKET_B,
            display_name="gestor-retained-state-b",
        )
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="retained-state-b",
            subject_cn="retained-state-b",
            password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)

    with open_test_profile_session(_BUCKET_B):
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


def test_resolved_credential_snapshot_survives_an_intervening_source_selection(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_a = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="snapshot-a",
        subject_cn="snapshot-a",
        password=CERTIFICATE_BUNDLE_PASSPHRASE,
    )
    cert_b = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="snapshot-b",
        subject_cn="snapshot-b",
        password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
    )
    register_operator_certificate_source(name="source-a", certificate_path=cert_a)
    set_operator_certificate_source_secret(name="source-a", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="source-a")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
    snapshot_a = resolve_active_certificate_credentials()

    register_operator_certificate_source(name="source-b", certificate_path=cert_b)
    set_operator_certificate_source_secret(name="source-b", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
    select_operator_certificate_source(name="source-b")
    snapshot_b = resolve_active_certificate_credentials()

    probe_a = probe_provider_credentials(
        AuthProviderKind.CERTIFICATE.value,
        str(snapshot_a.certificate_path or ""),
        settings=load_settings(),
        certificate_credentials=snapshot_a,
    )
    probe_b = probe_provider_credentials(
        AuthProviderKind.CERTIFICATE.value,
        str(snapshot_b.certificate_path or ""),
        settings=load_settings(),
        certificate_credentials=snapshot_b,
    )

    assert snapshot_a.source_name == "source-a"
    assert snapshot_a.certificate_path == cert_a
    assert snapshot_b.source_name == "source-b"
    assert snapshot_b.certificate_path == cert_b
    assert probe_a.result == ProviderProbeResult.OK
    assert probe_b.result == ProviderProbeResult.OK


def test_auth_projection_span_pins_state_and_credentials_when_pointer_changes(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_a = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="route-snapshot-a",
        subject_cn="route-snapshot-a",
        password=CERTIFICATE_BUNDLE_PASSPHRASE,
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_a)
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)
    session_captured_at = _NOW
    session_a_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
    _session_store.save(
        session_a_path,
        storage_state={"cookies": [], "origins": []},
        metadata={
            "provider_kind": AuthProviderKind.CERTIFICATE.value,
            "identity_nif": "ROUTE-A",
            "authenticated_at": session_captured_at.isoformat(),
            "idle_deadline": (session_captured_at + timedelta(minutes=30)).isoformat(),
        },
    )

    with open_test_profile_session(_BUCKET_B):
        register_minimal_profile(
            profile_id=_BUCKET_B,
            display_name=_PROFILE_LABEL_B,
        )
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="route-snapshot-b",
            subject_cn="route-snapshot-b",
            password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b)
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)
        session_b_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
        _session_store.save(
            session_b_path,
            storage_state={"cookies": [], "origins": []},
            metadata={
                "provider_kind": AuthProviderKind.CERTIFICATE.value,
                "identity_nif": "ROUTE-B",
                "authenticated_at": session_captured_at.isoformat(),
                "idle_deadline": (session_captured_at + timedelta(minutes=30)).isoformat(),
            },
        )

    settings = load_settings()
    write_pointer(
        settings.cadrumo_local_storage_root,
        BucketPointer.selected(bucket_id=_BUCKET_ID, transition_revision=1),
    )
    with override_settings(cadrumo_active_profile=None):
        with active_auth_projection_span(requested_provider=AuthProviderKind.CERTIFICATE.value) as snapshot:
            assert snapshot.bucket_id == _BUCKET_ID
            assert snapshot.state is not None
            assert snapshot.certificate_credentials is not None
            write_pointer(
                settings.cadrumo_local_storage_root,
                BucketPointer.selected(bucket_id=_BUCKET_B, transition_revision=2),
            )
            state_after_pointer_change = workflow_state_repository().load()
            credentials_after_pointer_change = resolve_active_certificate_credentials()
            projection_after_pointer_change = build_operator_state_projection(
                auth_snapshot=snapshot,
                requested_provider=AuthProviderKind.CERTIFICATE.value,
                probe_live_backend=True,
                include_workspace_summary=False,
                include_pending_obligations=False,
            )
            session_after_pointer_change = load_persisted_session(
                load_settings(),
                AuthProviderKind.CERTIFICATE,
            )
            operator_test_after_pointer_change = _test_operator_auth_from_snapshot(
                snapshot,
                requested_provider=AuthProviderKind.CERTIFICATE.value,
                resolved_settings=load_settings(),
            )
            preflight_after_pointer_change = build_live_auth_preflight_report(AuthProviderKind.CERTIFICATE.value)

            assert state_after_pointer_change.auth.certificate_path == str(cert_a)
            assert credentials_after_pointer_change.certificate_path == cert_a
            assert credentials_after_pointer_change.password is not None
            assert credentials_after_pointer_change.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE
            assert projection_after_pointer_change.active_profile.profile_id == _BUCKET_ID
            assert projection_after_pointer_change.auth.certificate_path == str(cert_a)
            assert projection_after_pointer_change.auth.available is True
            assert session_after_pointer_change is not None
            assert session_after_pointer_change.identity_nif == "ROUTE-A"
            # ``AuthTestResult.active_profile`` is an operator-facing display
            # field: it prefers the profile's label and falls back to the bucket
            # UUID. The immutable id is asserted above on the projection, which
            # is where it lives; here the label is the identity, and naming
            # bucket B's label explicitly keeps the pinning claim unambiguous.
            assert operator_test_after_pointer_change.active_profile == _PROFILE_LABEL
            assert operator_test_after_pointer_change.active_profile != _PROFILE_LABEL_B
            assert operator_test_after_pointer_change.certificate_path == str(cert_a)
            assert operator_test_after_pointer_change.persisted_session_present is True
            assert preflight_after_pointer_change.active_profile == _PROFILE_LABEL
            assert preflight_after_pointer_change.certificate_path_configured is True
            assert preflight_after_pointer_change.persisted_session_present is True

        # The pointer now names bucket B, so resolution follows it -- but only
        # once B's custody session is open. The nested active-profile reset
        # keeps the route pointer-driven rather than letting the session
        # helper's own override answer the question under test.
        with (
            open_test_profile_session(_BUCKET_B),
            override_settings(cadrumo_active_profile=None),
        ):
            credentials_after_span = resolve_active_certificate_credentials()
            session_after_span = load_persisted_session(load_settings(), AuthProviderKind.CERTIFICATE)
        assert credentials_after_span.certificate_path == cert_b
        assert credentials_after_span.password is not None
        assert credentials_after_span.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE_B
        assert session_after_span is not None
        assert session_after_span.identity_nif == "ROUTE-B"


def test_explicit_settings_provider_resolution_uses_target_bucket_and_restores_ambient_session(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Direct provider construction resolves the bucket named by Settings, not ambient state.

    Both roots are the same here, so bucket B's custody session can be opened
    and the original resolution assertions stand unchanged. The unauthenticated
    call is asserted first: naming bucket B in Settings resolves B's material
    or nothing -- never bucket A's, whichever session happens to be ambient.
    """
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_a = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="bucket-a",
        subject_cn="bucket-a",
    )
    register_operator_certificate_source(name="selected", certificate_path=cert_a, friendly_name="bucket-a")
    set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="selected")
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a)

    with open_test_profile_session(_BUCKET_B):
        register_minimal_profile(
            profile_id=_BUCKET_B,
            display_name="gestor-cert-b",
        )
        cert_b = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=200),
            name="bucket-b",
            subject_cn="bucket-b",
            password=CERTIFICATE_BUNDLE_PASSPHRASE_B,
        )
        register_operator_certificate_source(name="selected", certificate_path=cert_b, friendly_name="bucket-b")
        set_operator_certificate_source_secret(name="selected", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B))
        select_operator_certificate_source(name="selected")
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b)

    ambient_before = current_active_bucket_session()
    assert ambient_before is not None
    assert ambient_before.bucket_id == _BUCKET_ID
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    unauthenticated = resolve_active_certificate_credentials(settings=settings_b)
    assert unauthenticated.certificate_path is None
    assert unauthenticated.password is None
    assert unauthenticated.source_name is None

    with open_test_profile_session(_BUCKET_B):
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
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE_B
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
    """An unreadable explicit bucket cannot inherit otherwise valid global credentials.

    The empty result now has two independent causes upstream and the same
    contract downstream: the custody guard declines to answer for a bucket with
    no open session, and the resolver's own refusal handling turns that into an
    empty credential. Neither path may reach for the perfectly valid global
    password sitting in Settings.
    """
    _register_operator_profile()
    now = datetime.now(UTC)
    global_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="global-must-not-leak",
        subject_cn="global-must-not-leak",
    )
    with override_settings(
        cadrumo_active_profile=_MISSING_BUCKET,
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
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
    assert global_path.exists(), "the valid global bundle stays on disk and still never leaks into the empty result"

    with pytest.raises(AuthOperationRequiresCustodySessionError) as raised_verdict:
        check_operator_certificate_sources(settings=missing_settings)
    context = raised_verdict.value.context
    assert context is not None
    assert context["bucket_id"] == _MISSING_BUCKET


def test_login_refuses_selected_missing_file_before_unrelated_valid_global_certificate(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Public login applies the selected source path before its local precondition."""
    _register_operator_profile()
    now = datetime.now(UTC)
    selected_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="selected-missing",
        subject_cn="selected-missing",
    )
    global_path = build_pkcs12_bundle(
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
            cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
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
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    select_operator_certificate_source(name="personal")

    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT


def test_check_named_source_fails_closed_when_secure_storage_cannot_be_read(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A real corrupt secure-storage index cannot redirect a named source to the valid global password."""
    _register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="personal")
    (_isolated_secret_store.store_dir / SECRET_INDEX_FILENAME).write_text("{not-json", encoding="utf-8")

    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
        report = check_operator_certificate_sources()

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT
