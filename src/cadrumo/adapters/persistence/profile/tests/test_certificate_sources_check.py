"""Real-behavior tests for certificate-source expiry/rotation awareness.

Exercises :func:`application.auth.check_operator_certificate_sources`
against real self-signed PKCS#12 bundles generated at runtime via
:mod:`cryptography`, while injecting the application-owned secret capability.
See GitHub issue #591 (multi-cert rotation-awareness slice).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.outbound.aeat.auth import session_store
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.actions import update_auth
from cadrumo.application.auth.certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from cadrumo.application.auth.credentials import (
    active_auth_projection_span,
    project_active_certificate_credentials,
    resolve_active_certificate_credentials,
)
from cadrumo.application.auth.operator import (
    build_live_auth_preflight_report,
    configure_operator_auth,
    inspect_operator_auth,
    login_operator_auth,
)
from cadrumo.application.auth.operator import test_operator_auth as run_operator_auth_test
from cadrumo.application.auth.operator_probes import probe_provider_credentials
from cadrumo.application.auth.operator_results import (
    AuthLoginPreconditionError,
    AuthOperationRequiresCustodySessionError,
)
from cadrumo.application.auth.probes import ProviderProbeResult
from cadrumo.application.auth.providers import select_provider
from cadrumo.application.auth.sessions import load_persisted_session, storage_state_paths
from cadrumo.application.state_projection import build_operator_state_projection
from cadrumo.adapters.persistence.profile.tests._operator_probe_fakes import fake_operator_probe_ports
from cadrumo.adapters.persistence.profile.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.adapters.persistence.profile.tests._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.bucket_pointer import BucketPointer, write_pointer
from cadrumo.core.config import load_settings, override_settings
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_PASSPHRASE, build_pkcs12_bundle

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_BUCKET_B = "44444444-4444-4444-8444-444444444444"
_MISSING_BUCKET = "55555555-5555-4555-8555-555555555555"
_PROFILE_LABEL = "gestor-cert-rotation"
_PROFILE_LABEL_B = "gestor-route-snapshot-b"
CERTIFICATE_BUNDLE_PASSPHRASE_B = "bucket-b-correct-horse"  # noqa: S105 - synthetic test fixture, not a secret
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports()


@pytest.mark.parametrize("invalid_result", ("", "ok", "OK", "not-a-verdict"))
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


# ---------------------------------------------------------------------------
# Shared-resolution parity: register, select, check, status, test, and the
# active-credential resolver must all consume the SAME certificate bytes and
# the same secure-storage secret. No global-credential fallback for a selected
# named source.
# ---------------------------------------------------------------------------


@pytest.fixture
def certificate_secret_backend_factory() -> InMemoryCertificateSecretBackendFactory:
    """Inject the application capability without importing a persistence adapter."""
    return InMemoryCertificateSecretBackendFactory()


def _register_select_with_secret(
    tmp_path: Path,
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
) -> Path:
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
    register_operator_certificate_source(name="personal", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="personal",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="personal", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    return cert_path


def test_resolver_returns_selected_source_path_and_secure_storage_secret(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """The active-credential resolver returns the selected source's path and its stored secret."""
    cert_path = _register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE


def test_check_opens_the_bundle_with_the_secure_storage_secret_no_global_fallback(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """``check`` resolves each source's passphrase from secure storage, not a global setting.

    The global password is intentionally wrong: the probe must open the
    PKCS#12 with the per-source secure-storage secret alone, classifying
    it ``ok``.
    """
    _register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.name == "personal"
    assert entry.result == ProviderProbeResult.OK


def test_status_test_and_resolver_agree_on_the_selected_certificate_bytes(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """``auth status``, ``auth test``, and the resolver report the same certificate path.

    ``auth test`` additionally opens the bundle through its probe using the
    resolved per-source secret, so its probe classifies ``ok`` — proving the
    same resolved bytes and secret flow through the status/test surfaces.
    """
    cert_path = _register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    status = inspect_operator_auth(
        "certificate",
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    test_result = run_operator_auth_test(
        "certificate",
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    assert credentials.certificate_path == cert_path
    assert status.certificate_path == str(cert_path)
    assert test_result.certificate_path == str(cert_path)
    assert test_result.probe_result == ProviderProbeResult.OK


def test_selected_source_without_secret_fails_closed_no_global_credential_leak(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="personal", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    select_operator_certificate_source(name="personal", operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(
        cadrumo_certificate_password_secret=SecretStr("unrelated-global-secret"),
        cadrumo_certificate_friendly_name="unrelated-global-label",
    ):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is None
    assert credentials.friendly_name is None


def test_central_provider_and_explicit_or_omitted_probes_fail_closed_without_named_secret(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="personal", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    select_operator_certificate_source(name="personal", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        explicit_status = inspect_operator_auth(
            AuthProviderKind.CERTIFICATE.value,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        omitted_status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        explicit_test = run_operator_auth_test(
            AuthProviderKind.CERTIFICATE.value,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        omitted_test = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        omitted_preflight = build_live_auth_preflight_report(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

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
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """The selected secure-storage secret feeds the central factory and omitted probes."""
    cert_path = _register_select_with_secret(tmp_path, certificate_secret_backend_factory)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(
        cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global"),
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        omitted_status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        omitted_test = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert provider_description.available is True
    assert omitted_status.provider == AuthProviderKind.CERTIFICATE.value
    assert omitted_status.available is True
    assert omitted_test.probe_result == ProviderProbeResult.OK


def test_reregistering_active_source_keeps_resolver_provider_status_and_test_on_new_path(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="selected", certificate_path=cert_v1, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="selected",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_v1, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    register_operator_certificate_source(name="selected", certificate_path=cert_v2, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    cert_v1.unlink()

    with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        test_result = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

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
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """An unselected registration preserves the unnamed Settings path and password."""
    _register_operator_profile()
    registered_path = tmp_path / "registered-but-inactive.p12"
    registered_path.write_bytes(b"registered source bytes")
    register_operator_certificate_source(name="inactive", certificate_path=registered_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    global_path = tmp_path / "unnamed-certificate.p12"
    global_path.write_bytes(b"unnamed single-certificate bytes")
    global_password = SecretStr("unnamed-certificate-password")

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=global_password,
        cadrumo_certificate_friendly_name="unnamed-certificate",
    ):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert credentials.source_name is None
    assert credentials.certificate_path == global_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == global_password.get_secret_value()
    assert credentials.friendly_name == "unnamed-certificate"


def test_central_provider_preserves_unnamed_single_certificate_credential_without_selected_source(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=global_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        cadrumo_certificate_friendly_name="legacy-global",
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        omitted_status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        omitted_test = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert provider_description.available is True
    assert omitted_status.provider == AuthProviderKind.CERTIFICATE.value
    assert omitted_status.available is True
    assert omitted_test.probe_result == ProviderProbeResult.OK


def test_explicit_global_settings_path_overrides_stale_workflow_mirror_for_status_and_test(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=stale_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    stale_path.unlink()

    with override_settings(
        cadrumo_certificate_path=explicit_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        test_result = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert provider_description.available is True
    assert status.certificate_path == str(explicit_path)
    assert status.configured is True
    assert status.available is True
    assert test_result.certificate_path == str(explicit_path)
    assert test_result.configured is True
    assert test_result.probe_result == ProviderProbeResult.OK


def test_central_provider_uses_configured_workflow_path_when_global_path_is_absent(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=configured_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(
        cadrumo_certificate_path=None,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
    ):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()

    assert credentials.certificate_path == configured_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE
    assert provider_description.available is True


def test_explicit_settings_second_root_uses_its_own_cached_secret_store(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
        register_operator_certificate_source(name="selected", certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        settings_a = load_settings()

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
        register_operator_certificate_source(name="selected", certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        with override_settings(cadrumo_blob_store_dir=tmp_path / "route-b-explicit-blobs") as settings_b:
            set_operator_certificate_source_secret(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                name="selected",
                secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
            configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
            credentials_b = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            provider_b = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=settings_b,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ).describe()
            operator_test_b = run_operator_auth_test(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

    assert settings_a.cadrumo_secret_store_dir != settings_b.cadrumo_secret_store_dir
    assert credentials_b.certificate_path == cert_b
    assert credentials_b.password is not None
    assert credentials_b.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE_B
    assert provider_b.available is True
    assert operator_test_b.certificate_path == str(cert_b)
    assert operator_test_b.probe_result == ProviderProbeResult.OK


def test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
        register_operator_certificate_source(name="selected", certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
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
        register_operator_certificate_source(name="selected", certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CLAVE_MOVIL.value, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

        ambient_before = _OPERATOR_SCOPE_PORTS.session.current()
        assert ambient_before is not None
        assert ambient_before.bucket_id == _BUCKET_ID

        degraded_credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=settings_b,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        degraded_provider = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=settings_b,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()

        assert degraded_credentials.certificate_path is None
        assert degraded_credentials.password is None
        assert degraded_credentials.source_name is None
        assert degraded_provider.configured is False
        assert degraded_provider.available is False

        for verdict_operation in (
            lambda: check_operator_certificate_sources(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ),
            lambda: run_operator_auth_test(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ),
            lambda: build_live_auth_preflight_report(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=settings_b,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ),
        ):
            with pytest.raises(AuthOperationRequiresCustodySessionError) as raised:
                verdict_operation()
            context = raised.value.context
            assert context is not None
            assert context["bucket_id"] == _BUCKET_ID
            assert root_b_fixture.name in str(context["storage_root"])
            assert root_a_fixture.name not in str(context["storage_root"])

        ambient_after = _OPERATOR_SCOPE_PORTS.session.current()
        assert ambient_after is ambient_before
        assert ambient_after.bucket_id == _BUCKET_ID
        assert cert_a.exists()
        assert cert_b.exists()


def test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="selected", certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="selected",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
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
        register_operator_certificate_source(name="selected", certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with open_test_profile_session(_BUCKET_B):
        projected_credentials = project_active_certificate_credentials(
            retained_state_a,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=load_settings(),
        )
        projection = build_operator_state_projection(
            state=retained_state_a,
            requested_provider=AuthProviderKind.CERTIFICATE.value,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert projected_credentials.certificate_path == cert_a
    assert projected_credentials.source_name == "selected"
    assert projected_credentials.password is None
    assert projection.auth.certificate_path == str(cert_a)
    assert projection.auth.available is False
    assert projection.auth.health_summary == ""


def test_resolved_credential_snapshot_survives_an_intervening_source_selection(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="source-a", certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="source-a",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="source-a", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    snapshot_a = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    register_operator_certificate_source(name="source-b", certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="source-b",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="source-b", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    snapshot_b = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    probe_a = probe_provider_credentials(
        AuthProviderKind.CERTIFICATE.value,
        str(snapshot_a.certificate_path or ""),
        settings=load_settings(),
        certificate_credentials=snapshot_a,
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
    )
    probe_b = probe_provider_credentials(
        AuthProviderKind.CERTIFICATE.value,
        str(snapshot_b.certificate_path or ""),
        settings=load_settings(),
        certificate_credentials=snapshot_b,
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
    )

    assert snapshot_a.source_name == "source-a"
    assert snapshot_a.certificate_path == cert_a
    assert snapshot_b.source_name == "source-b"
    assert snapshot_b.certificate_path == cert_b
    assert probe_a.result == ProviderProbeResult.OK
    assert probe_b.result == ProviderProbeResult.OK


def test_auth_projection_span_pins_state_and_credentials_when_pointer_changes(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="selected", certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="selected",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    session_captured_at = _NOW
    session_a_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
    session_store.save(
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
        register_operator_certificate_source(name="selected", certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        session_b_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
        session_store.save(
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
        with active_auth_projection_span(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            requested_provider=AuthProviderKind.CERTIFICATE.value,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ) as snapshot:
            assert snapshot.bucket_id == _BUCKET_ID
            assert snapshot.state is not None
            assert snapshot.certificate_credentials is not None
            write_pointer(
                settings.cadrumo_local_storage_root,
                BucketPointer.selected(bucket_id=_BUCKET_B, transition_revision=2),
            )
            state_after_pointer_change = workflow_state_repository().load()
            credentials_after_pointer_change = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            projection_after_pointer_change = build_operator_state_projection(
                auth_snapshot=snapshot,
                requested_provider=AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                probe_live_backend=True,
                include_workspace_summary=False,
                include_pending_obligations=False,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            session_after_pointer_change = load_persisted_session(
                load_settings(),
                AuthProviderKind.CERTIFICATE,
            )
            operator_test_after_pointer_change = run_operator_auth_test(
                AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            preflight_after_pointer_change = build_live_auth_preflight_report(
                AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )

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
            credentials_after_span = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            )
            session_after_span = load_persisted_session(load_settings(), AuthProviderKind.CERTIFICATE)
        assert credentials_after_span.certificate_path == cert_b
        assert credentials_after_span.password is not None
        assert credentials_after_span.password.get_secret_value() == CERTIFICATE_BUNDLE_PASSPHRASE_B
        assert session_after_span is not None
        assert session_after_span.identity_nif == "ROUTE-B"


def test_explicit_settings_provider_resolution_uses_target_bucket_and_restores_ambient_session(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="selected", certificate_path=cert_a, friendly_name="bucket-a", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="selected",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_a, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

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
        register_operator_certificate_source(name="selected", certificate_path=cert_b, friendly_name="bucket-b", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE_B),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
        configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=cert_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    ambient_before = _OPERATOR_SCOPE_PORTS.session.current()
    assert ambient_before is not None
    assert ambient_before.bucket_id == _BUCKET_ID
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    unauthenticated = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        settings=settings_b,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    assert unauthenticated.certificate_path is None
    assert unauthenticated.password is None
    assert unauthenticated.source_name is None

    with open_test_profile_session(_BUCKET_B):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=settings_b,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=settings_b,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ).describe()
        check_report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=settings_b,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    ambient_after = _OPERATOR_SCOPE_PORTS.session.current()
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
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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

    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        settings=missing_settings,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    provider_description = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=missing_settings,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    ).describe()

    assert credentials.certificate_path is None
    assert credentials.password is None
    assert credentials.friendly_name is None
    assert credentials.source_name is None
    assert provider_description.configured is False
    assert provider_description.available is False
    assert global_path.exists(), "the valid global bundle stays on disk and still never leaks into the empty result"

    with pytest.raises(AuthOperationRequiresCustodySessionError) as raised_verdict:
        check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            settings=missing_settings,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
    context = raised_verdict.value.context
    assert context is not None
    assert context["bucket_id"] == _MISSING_BUCKET


def test_login_refuses_selected_missing_file_before_unrelated_valid_global_certificate(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="selected", certificate_path=selected_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    select_operator_certificate_source(name="selected", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    configure_operator_auth(AuthProviderKind.CERTIFICATE.value, certificate_path=selected_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    selected_path.unlink()

    with (
        override_settings(
            cadrumo_certificate_path=global_path,
            cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
            cadrumo_live_tests_enabled="1",
        ),
        pytest.raises(AuthLoginPreconditionError) as raised,
    ):
        asyncio.run(
            login_operator_auth(
                AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            ),
        )

    assert raised.value.translated_message == "application.auth.operator.login.refused_certificate_file_missing"
    context = raised.value.context
    assert context is not None
    assert context["path"] == str(selected_path)


def test_check_named_source_without_secret_never_inherits_a_valid_global_password(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="personal", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    select_operator_certificate_source(name="personal", operator_scope_ports=_OPERATOR_SCOPE_PORTS)

    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT


def test_check_named_source_fails_closed_when_secure_storage_cannot_be_read(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
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
    register_operator_certificate_source(name="personal", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    set_operator_certificate_source_secret(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        name="personal",
        secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    select_operator_certificate_source(name="personal", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
    with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE)):
        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

    assert len(report.entries) == 1
    assert report.entries[0].name == "personal"
    assert report.entries[0].result == ProviderProbeResult.CORRUPT
