"""Real-behavior certificate-source health tests.

Exercises certificate expiry, absence, and per-source aggregation using real
self-signed PKCS#12 bundles generated at runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from ....adapters.persistence.storage import SecretStore, get_secret_store
from ....tests.certificates import CERTIFICATE_BUNDLE_PASSPHRASE, build_pkcs12_bundle
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ..certificate_source_operations import (
    check_operator_certificate_sources,
    register_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ..operator_results import CertificateSourceCheckEntry
from ..probes import ProviderProbeResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_PROFILE_LABEL = "gestor-cert-rotation"
_NOW = datetime(2099, 5, 28, 14, 10, 0, tzinfo=UTC)


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
def _isolated_secret_store() -> SecretStore:
    """Return the test-isolated canonical store for source passphrases."""
    return get_secret_store()


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
    """A certificate inside the 60-day warning window is classified ``expiring``."""
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
    """Every registered source is classified, not only the active source."""
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
    assert report.has_warnings is True


def test_check_classifies_a_missing_certificate_file_distinctly(tmp_path: Path) -> None:
    """A deleted registered file surfaces ``file_missing``, never ``ok``."""
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
    assert report.has_warnings is False


def test_check_with_no_registered_sources_is_empty_and_has_no_warnings() -> None:
    """No registered sources yields an empty report, not an error."""
    _register_operator_profile()

    report = check_operator_certificate_sources()

    assert report.entries == ()
    assert report.has_warnings is False
