from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....core.auth_provider import AuthProviderKind
from ....core.config import override_settings
from ....tests.certificates import CERTIFICATE_BUNDLE_PASSPHRASE, build_pkcs12_bundle
from ..credentials import active_auth_projection_span
from ..operator import login_operator_auth
from ..operator_results import AuthConfigureNoActiveBucketError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_login_cold_root_preserves_unnamed_certificate_before_no_bucket_refusal(tmp_path: Path) -> None:
    """The route snapshot retains explicit certificate settings even without a profile."""
    now = datetime.now(UTC)
    certificate_path = build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name="cold-root-certificate",
        subject_cn="cold-root-certificate",
    )
    cold_root = tmp_path / "cold-root"

    with override_settings(
        cadrumo_local_storage_root=cold_root,
        cadrumo_active_profile=None,
        cadrumo_certificate_path=certificate_path,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE),
        cadrumo_live_tests_enabled="1",
    ) as settings:
        with active_auth_projection_span(
            settings=settings,
            requested_provider=AuthProviderKind.CERTIFICATE.value,
        ) as snapshot:
            assert snapshot.bucket_id is None
            assert snapshot.provider is AuthProviderKind.CERTIFICATE
            assert snapshot.certificate_credentials is not None
            assert snapshot.certificate_credentials.certificate_path == certificate_path

        with pytest.raises(AuthConfigureNoActiveBucketError):
            asyncio.run(
                login_operator_auth(
                    AuthProviderKind.CERTIFICATE.value,
                    settings=settings,
                    pytest_current_test="",
                ),
            )
