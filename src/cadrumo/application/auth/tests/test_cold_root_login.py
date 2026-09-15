from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.application.auth.tests._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

from ....core.auth_provider import AuthProviderKind
from ....core.config import override_settings
from ....tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle
from ..credentials import active_auth_projection_span
from ..operator import login_operator_auth
from ..operator_results import AuthConfigureNoActiveBucketError
from ._operator_probe_fakes import fake_operator_probe_ports

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports(active_profile_session_bound=False)


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
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
        cadrumo_live_tests_enabled="1",
    ) as settings:
        with active_auth_projection_span(
            settings=settings,
            certificate_secret_backend_factory=build_certificate_secret_backend,
            requested_provider=AuthProviderKind.CERTIFICATE.value,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        ) as snapshot:
            assert snapshot.bucket_id is None
            assert snapshot.provider is AuthProviderKind.CERTIFICATE
            assert snapshot.certificate_credentials is not None
            assert snapshot.certificate_credentials.certificate_path == certificate_path

        with pytest.raises(AuthConfigureNoActiveBucketError):
            asyncio.run(
                login_operator_auth(
                    AuthProviderKind.CERTIFICATE.value,
                    certificate_secret_backend_factory=build_certificate_secret_backend,
                    browser_session_factory=default_browser_session_factory,
                    settings=settings,
                    guarded_read_context="",
                    operator_probe_ports=_OPERATOR_PROBE_PORTS,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ),
            )
