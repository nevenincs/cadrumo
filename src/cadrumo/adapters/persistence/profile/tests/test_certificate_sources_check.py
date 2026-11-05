"""Real-behavior tests for certificate-source expiry/rotation awareness.

Exercises :func:`application.auth.check_operator_certificate_sources`
against real self-signed PKCS#12 bundles generated at runtime via
:mod:`cryptography`, while injecting the application-owned secret capability.
See GitHub issue #591 (multi-cert rotation-awareness slice).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.operator_projection_test_support import (
    build_live_auth_preflight_report,
    configure_operator_auth,
    inspect_operator_auth,
)
from cadrumo.adapters.persistence.profile.tests.operator_projection_test_support import (
    test_operator_auth as run_operator_auth_test,
)
from cadrumo.application.auth.certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from cadrumo.application.auth.credentials import (
    resolve_active_certificate_credentials,
)
from cadrumo.application.auth.probes import ProviderProbeResult
from cadrumo.application.auth.providers import select_provider
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings, override_settings
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle

from .certificate_sources_check_support import (
    OPERATOR_PROBE_PORTS,
    OPERATOR_SCOPE_PORTS,
    register_operator_profile,
    register_select_with_secret,
)
from .certificate_sources_check_support import (
    isolated_backend as isolated_backend,
)
from .certificate_sources_check_support import (
    manages_storage_roots as manages_storage_roots,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def _register_and_select_personal_source(tmp_path: Path, operation: PinnedAuthorityOperation) -> Path:
    """Register a valid ``personal`` certificate source with no bound secret and select it."""
    register_operator_profile()
    now = datetime.now(UTC)
    cert_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="personal",
        subject_cn="gestor-personal",
    )
    register_operator_certificate_source(
        name="personal",
        certificate_path=cert_path,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        operation=operation,
    )
    select_operator_certificate_source(
        name="personal",
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        operation=operation,
    )
    return cert_path


def _describe_and_probe_omitted(certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory):
    """Describe the certificate provider, then read the omitted-provider status and test through the operator surface."""
    provider_description = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=load_settings(),
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    ).describe()
    omitted_status = inspect_operator_auth(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=OPERATOR_PROBE_PORTS,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    omitted_test = run_operator_auth_test(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=OPERATOR_PROBE_PORTS,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    return provider_description, omitted_status, omitted_test


def test_resolver_returns_selected_source_path_and_secure_storage_secret(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """The active-credential resolver returns the selected source's path and its stored secret."""
    cert_path = register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )

    assert credentials.source_name == "personal"
    assert credentials.certificate_path == cert_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT


def test_check_opens_the_bundle_with_the_secure_storage_secret_no_global_fallback(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """``check`` resolves each source's passphrase from secure storage, not a global setting.

    The global password is intentionally wrong: the probe must open the
    PKCS#12 with the per-source secure-storage secret alone, classifying
    it ``ok``.
    """
    register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=OPERATOR_PROBE_PORTS,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    cert_path = register_select_with_secret(tmp_path, certificate_secret_backend_factory)

    status = inspect_operator_auth(
        "certificate",
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=OPERATOR_PROBE_PORTS,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    test_result = run_operator_auth_test(
        "certificate",
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=OPERATOR_PROBE_PORTS,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    credentials = resolve_active_certificate_credentials(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    with bundled_indexed_authority().operation() as _certificate_authority_operation_for_test:
        cert_path = _register_and_select_personal_source(tmp_path, _certificate_authority_operation_for_test)

        with override_settings(
            cadrumo_certificate_password_secret=SecretStr("unrelated-global-secret"),
            cadrumo_certificate_friendly_name="unrelated-global-label",
        ):
            credentials = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    with bundled_indexed_authority().operation() as _certificate_authority_operation_for_test:
        cert_path = _register_and_select_personal_source(tmp_path, _certificate_authority_operation_for_test)
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path, operator_scope_ports=OPERATOR_SCOPE_PORTS
        )

        with override_settings(cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT)):
            provider_description = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=load_settings(),
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            ).describe()
            explicit_status = inspect_operator_auth(
                AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            omitted_status = inspect_operator_auth(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            explicit_test = run_operator_auth_test(
                AuthProviderKind.CERTIFICATE.value,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            omitted_test = run_operator_auth_test(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            omitted_preflight = build_live_auth_preflight_report(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    cert_path = register_select_with_secret(tmp_path, certificate_secret_backend_factory)
    configure_operator_auth(
        AuthProviderKind.CERTIFICATE.value, certificate_path=cert_path, operator_scope_ports=OPERATOR_SCOPE_PORTS
    )

    with override_settings(
        cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global"),
    ):
        provider_description, omitted_status, omitted_test = _describe_and_probe_omitted(
            certificate_secret_backend_factory
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
    with bundled_indexed_authority().operation() as _certificate_authority_operation_for_test:
        register_operator_profile()
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
        register_operator_certificate_source(
            name="selected",
            certificate_path=cert_v1,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="selected",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="selected",
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        configure_operator_auth(
            AuthProviderKind.CERTIFICATE.value, certificate_path=cert_v1, operator_scope_ports=OPERATOR_SCOPE_PORTS
        )
        register_operator_certificate_source(
            name="selected",
            certificate_path=cert_v2,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        cert_v1.unlink()

        with override_settings(cadrumo_certificate_password_secret=SecretStr("intentionally-wrong-global")):
            credentials = resolve_active_certificate_credentials(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            provider_description = select_provider(
                AuthProviderKind.CERTIFICATE,
                settings=load_settings(),
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            ).describe()
            status = inspect_operator_auth(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
            )
            test_result = run_operator_auth_test(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=OPERATOR_PROBE_PORTS,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    with bundled_indexed_authority().operation() as _certificate_authority_operation_for_test:
        register_operator_profile()
        registered_path = tmp_path / "registered-but-inactive.p12"
        registered_path.write_bytes(b"registered source bytes")
        register_operator_certificate_source(
            name="inactive",
            certificate_path=registered_path,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
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
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    register_operator_profile()
    now = datetime.now(UTC)
    global_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="legacy-global",
        subject_cn="legacy-global",
    )
    configure_operator_auth(
        AuthProviderKind.CERTIFICATE.value, certificate_path=global_path, operator_scope_ports=OPERATOR_SCOPE_PORTS
    )

    with override_settings(
        cadrumo_certificate_path=global_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
        cadrumo_certificate_friendly_name="legacy-global",
    ):
        provider_description, omitted_status, omitted_test = _describe_and_probe_omitted(
            certificate_secret_backend_factory
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
    register_operator_profile()
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
    configure_operator_auth(
        AuthProviderKind.CERTIFICATE.value, certificate_path=stale_path, operator_scope_ports=OPERATOR_SCOPE_PORTS
    )
    stale_path.unlink()

    with override_settings(
        cadrumo_certificate_path=explicit_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ):
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        ).describe()
        status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=OPERATOR_PROBE_PORTS,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        )
        test_result = run_operator_auth_test(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=OPERATOR_PROBE_PORTS,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
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
    register_operator_profile()
    now = datetime.now(UTC)
    configured_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="configured-file",
        subject_cn="configured-file",
    )
    configure_operator_auth(
        AuthProviderKind.CERTIFICATE.value, certificate_path=configured_path, operator_scope_ports=OPERATOR_SCOPE_PORTS
    )

    with override_settings(
        cadrumo_certificate_path=None,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ):
        credentials = resolve_active_certificate_credentials(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        )
        provider_description = select_provider(
            AuthProviderKind.CERTIFICATE,
            settings=load_settings(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        ).describe()

    assert credentials.certificate_path == configured_path
    assert credentials.password is not None
    assert credentials.password.get_secret_value() == CERTIFICATE_BUNDLE_INPUT
    assert provider_description.available is True
