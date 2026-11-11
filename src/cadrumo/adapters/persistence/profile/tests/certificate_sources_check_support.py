"""Shared setup for the split test modules."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.certificate_source_operations import (
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.tests.operator_probe_fakes import fake_operator_probe_ports
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle

OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


BUCKET_ID = "33333333-3333-4333-8333-333333333333"


BUCKET_B = "44444444-4444-4444-8444-444444444444"


MISSING_BUCKET = "55555555-5555-4555-8555-555555555555"


PROFILE_LABEL = "gestor-cert-rotation"


PROFILE_LABEL_B = "gestor-route-snapshot-b"


CERTIFICATE_BUNDLE_INPUT_B = "bucket-b-correct-horse"


NOW = datetime(filing_year_envelope().horizon, 5, 28, 14, 10, 0, tzinfo=UTC)


OPERATOR_PROBE_PORTS = fake_operator_probe_ports()


def register_operator_profile() -> None:
    """Seed and select the operator profile before anything opens its bucket store.

    Ordering is load-bearing, not stylistic. The capsule is published by an
    atomic no-replace directory rename onto ``buckets/<profile-id>``, and
    ``workflow_state_repository()`` materialises ``buckets/<profile-id>/db``
    on first access -- so a workflow read taken first makes the rename
    collide. Seeding through a detached ``WorkflowState`` keeps the capsule
    first; the helper only passes that argument back to its caller.
    """
    register_minimal_profile(
        profile_id=BUCKET_ID,
        display_name=PROFILE_LABEL,
    )


@pytest.fixture(autouse=True)
def isolated_backend(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Open an isolated storage root plus an active bucket session for the whole test."""
    if "manages_storage_roots" in request.fixturenames:
        yield
        return
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(BUCKET_ID),
    ):
        yield


@pytest.fixture
def manages_storage_roots() -> None:
    """Let one route-isolation test own both complete storage-root contexts."""


def register_select_with_secret(
    tmp_path: Path,
    certificate_secret_backend_factory: InMemoryCertificateSecretBackendFactory,
) -> Path:
    """Register a real PKCS#12 source, bind its secure-storage passphrase, and select it.

    Returns the certificate path. The bound secret is ``CERTIFICATE_BUNDLE_INPUT`` — the same
    passphrase the bundle is encrypted with — so a probe opening the bundle
    with the resolved per-source secret succeeds.
    """
    with bundled_indexed_authority().operation() as _certificate_authority_operation_for_test:
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
            operation=_certificate_authority_operation_for_test,
        )
        set_operator_certificate_source_secret(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            name="personal",
            secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        select_operator_certificate_source(
            name="personal",
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=_certificate_authority_operation_for_test,
        )
        return cert_path
