"""Real-behavior certificate-source health tests.

Exercises certificate expiry, absence, and per-source aggregation using real
self-signed PKCS#12 bundles generated at runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests._operator_probe_fakes import fake_operator_probe_ports
from cadrumo.adapters.persistence.profile.tests._operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from cadrumo.adapters.persistence.profile.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from cadrumo.application.auth.operator_probe_ports import CertificateHealthBand, CertificateHealthObservation
from cadrumo.application.auth.probes import ProviderProbeResult
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _certificate_indexed_authority_for_test,
)
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_PROFILE_LABEL = "gestor-cert-rotation"
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports()


def _register_operator_profile() -> None:
    """Seed the profile before the test opens its workflow store."""
    register_minimal_profile(profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Open an isolated storage root plus an active bucket session per test."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_BUCKET_ID),
    ):
        yield


@pytest.fixture
def certificate_secret_backend_factory() -> InMemoryCertificateSecretBackendFactory:
    """Inject the application contract without importing a persistence adapter."""
    return InMemoryCertificateSecretBackendFactory()


def test_check_reports_ok_for_a_certificate_far_from_expiry(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A certificate with hundreds of days remaining is classified ``ok``."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        cert_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=_NOW - timedelta(days=1),
            not_valid_after=_NOW + timedelta(days=200),
            name="personal",
            subject_cn="gestor-personal",
        )
        register_operator_certificate_source(
            name="personal",
            certificate_path=cert_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="personal",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )

        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert entry.name == "personal"
        assert entry.result == ProviderProbeResult.OK
        assert entry.days_until_expiry is not None
        assert entry.days_until_expiry >= 199
        assert report.has_warnings is False


def test_check_reports_expiring_within_the_warning_window(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A certificate inside the 60-day warning window is classified ``expiring``."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=30),
            name="apoderado-acme",
            subject_cn="apoderado-acme",
        )
        register_operator_certificate_source(
            name="apoderado-acme",
            certificate_path=cert_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="apoderado-acme",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )

        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=fake_operator_probe_ports(
                certificate_health=CertificateHealthObservation(
                    severity=CertificateHealthBand.WARN,
                    days_until_expiry=30,
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert entry.result == ProviderProbeResult.EXPIRING
        assert entry.days_until_expiry is not None
        assert 0 < entry.days_until_expiry <= 60
        assert report.has_warnings is True


def test_check_reports_expired_for_a_lapsed_certificate(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A certificate whose validity has already elapsed is classified ``expired``."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        now = datetime.now(UTC)
        cert_path = build_pkcs12_bundle(
            tmp_path,
            not_valid_before=now - timedelta(days=400),
            not_valid_after=now - timedelta(days=5),
            name="expired-cert",
            subject_cn="expired-cert",
        )
        register_operator_certificate_source(
            name="expired-cert",
            certificate_path=cert_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="expired-cert",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )

        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=fake_operator_probe_ports(
                certificate_health=CertificateHealthObservation(
                    severity=CertificateHealthBand.EXPIRED,
                    days_until_expiry=-5,
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert entry.result == ProviderProbeResult.EXPIRED
        assert entry.days_until_expiry is not None
        assert entry.days_until_expiry < 0
        assert report.has_warnings is True


def test_check_covers_every_registered_source_independently(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """Every registered source is classified, not only the active source."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
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
        register_operator_certificate_source(
            name="personal",
            certificate_path=valid_cert,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        register_operator_certificate_source(
            name="apoderado-acme",
            certificate_path=expiring_cert,
            friendly_name="ACME SL",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="personal",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="apoderado-acme",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )

        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=fake_operator_probe_ports(
                certificate_evaluator=lambda request: CertificateHealthObservation(
                    severity=CertificateHealthBand.WARN
                    if request.path.stem == "apoderado-acme"
                    else CertificateHealthBand.OK,
                    days_until_expiry=10 if request.path.stem == "apoderado-acme" else 300,
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        by_name = {entry.name: entry for entry in report.entries}
        assert set(by_name) == {"personal", "apoderado-acme"}
        assert by_name["personal"].result == ProviderProbeResult.OK
        assert by_name["apoderado-acme"].result == ProviderProbeResult.EXPIRING
        assert by_name["apoderado-acme"].friendly_name == "ACME SL"
        assert report.has_warnings is True


def test_check_classifies_a_missing_certificate_file_distinctly(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
    tmp_path: Path,
) -> None:
    """A deleted registered file surfaces ``file_missing``, never ``ok``."""
    with _certificate_indexed_authority_for_test().operation() as _certificate_authority_operation_for_test:
        _register_operator_profile()
        ghost_path = tmp_path / "deleted.p12"
        ghost_path.write_bytes(b"placeholder")
        register_operator_certificate_source(
            name="deleted",
            certificate_path=ghost_path,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        ghost_path.unlink()

        report = check_operator_certificate_sources(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert entry.result == ProviderProbeResult.FILE_MISSING
        assert entry.days_until_expiry is None
        assert report.has_warnings is False


def test_check_with_no_registered_sources_is_empty_and_has_no_warnings(
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
) -> None:
    """No registered sources yields an empty report, not an error."""
    _register_operator_profile()

    report = check_operator_certificate_sources(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    assert report.entries == ()
    assert report.has_warnings is False
