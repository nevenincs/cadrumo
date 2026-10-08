"""A synthetic AEAT login may publish its encrypted session only under current authority."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.aeat.auth import session_store
from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.profile.tests.operator_probe_fakes import fake_operator_probe_ports
from cadrumo.adapters.persistence.profile.tests.operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import bucket_session_storage_fixture
from cadrumo.application.auth.operator import configure_operator_auth, login_operator_auth
from cadrumo.application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from cadrumo.application.auth.sessions import storage_state_paths
from cadrumo.application.live.session import ensure_live_authenticated_session
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.operations import OperationEffect
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports()
_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)


def _authentication_result(identity: object, path: Path) -> tuple[AeatSession, AeatLoginAssertion]:
    assert isinstance(identity, str)
    timestamp = now()
    detail = CertificateSessionDetail(certificate_thumbprint="synthetic", certificate_subject="synthetic")
    return (
        AeatSession(
            authenticated_at=timestamp,
            idle_deadline=timestamp + timedelta(hours=1),
            storage_state_path=path,
            identity_nif=identity,
            provider_detail=detail,
        ),
        AeatLoginAssertion(
            target_url=detail.protected_resource_url,
            is_valid=True,
            identity_nif=identity,
            status_code=200,
            elapsed_ms=1,
            attempted_at=timestamp,
            assertion_detail=CertificateLoginAssertionDetail(response_successful=True),
        ),
    )


@pytest.mark.asyncio
async def test_remote_browser_state_is_discarded_when_commit_authority_is_revoked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The remote phase runs outside COMMIT and a late denial leaves no session or verified event."""
    profile = register_minimal_profile(profile_id=_BUCKET_ID)
    cert_path = tmp_path / "synthetic.p12"
    cert_path.write_bytes(b"synthetic certificate placeholder")
    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "certificate", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS, operation=operation
        )
    before = workflow_state_repository().load()
    session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
    assert not session_store.exists(session_path)

    class SyntheticProvider:
        kind = AuthProviderKind.CERTIFICATE

        async def close(self) -> None:
            return None

    phases: list[str] = []
    identity = next(fact.value for fact in profile.facts if fact.path == "identity.tax_id")

    async def remote_auth(*_args: object, **_kwargs: object) -> tuple[AeatSession, AeatLoginAssertion]:
        assert phases == []
        phases.append("remote")
        session_store.save(
            session_path,
            storage_state={"cookies": [{"name": "synthetic", "value": "private-session"}], "origins": []},
            metadata={"provider_kind": "certificate"},
        )
        assert session_store.exists(session_path)
        return _authentication_result(identity, session_path)

    monkeypatch.setattr("cadrumo.application.auth.sessions._build_provider", lambda *_a, **_kw: SyntheticProvider())
    monkeypatch.setattr("cadrumo.application.auth.sessions._authenticate_and_verify_provider", remote_auth)

    @asynccontextmanager
    async def deny_commit() -> AsyncGenerator[None]:
        assert phases == ["remote"]
        phases.append("commit-refused")
        raise PermissionError("synthetic session revoked before commit")
        yield

    with (
        bundled_indexed_authority().operation() as pinned,
        override_settings(cadrumo_live_tests_enabled="1"),
        pytest.raises(PermissionError, match="revoked before commit"),
    ):
        await login_operator_auth(
            "certificate",
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            fresh=True,
            effect_guard=deny_commit,
            authority_operation=pinned,
        )

    assert phases == ["remote", "commit-refused"]
    assert not session_store.exists(session_path)
    after = workflow_state_repository().load()
    assert after.auth.authenticated_at == before.auth.authenticated_at
    assert tuple(event for event in after.bucket_events if event.action == "auth.session.verified") == ()


@pytest.mark.asyncio
async def test_live_capture_auth_denial_discards_staged_browser_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A registered capture's late COMMIT denial must leave no encrypted browser state."""
    profile = register_minimal_profile(profile_id=_BUCKET_ID)
    cert_path = tmp_path / "synthetic-capture.p12"
    cert_path.write_bytes(b"synthetic certificate placeholder")
    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "certificate", certificate_path=cert_path, operator_scope_ports=_OPERATOR_SCOPE_PORTS, operation=operation
        )
    session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
    assert not session_store.exists(session_path)
    identity = next(fact.value for fact in profile.facts if fact.path == "identity.tax_id")
    phases: list[str] = []
    receipts: list[OperationEffect] = []

    class SyntheticProvider:
        kind = AuthProviderKind.CERTIFICATE

        async def close(self) -> None:
            return None

    async def remote_auth(*_args: object, **_kwargs: object) -> tuple[AeatSession, AeatLoginAssertion]:
        assert phases == []
        phases.append("remote")
        session_store.save(
            session_path,
            storage_state={"cookies": [{"name": "synthetic", "value": "private-capture"}], "origins": []},
            metadata={"provider_kind": "certificate"},
        )
        return _authentication_result(identity, session_path)

    monkeypatch.setattr("cadrumo.application.auth.sessions._build_provider", lambda *_a, **_kw: SyntheticProvider())
    monkeypatch.setattr("cadrumo.application.auth.sessions._authenticate_and_verify_provider", remote_auth)

    @asynccontextmanager
    async def deny_commit() -> AsyncGenerator[None]:
        assert phases == ["remote"]
        phases.append("commit-refused")
        raise PermissionError("synthetic capture authority revoked")
        yield

    async def record_effect(effect: OperationEffect) -> None:
        receipts.append(effect)

    with (
        bundled_indexed_authority().operation() as pinned,
        override_settings(cadrumo_live_tests_enabled="1"),
        pytest.raises(PermissionError, match="capture authority revoked"),
    ):
        await ensure_live_authenticated_session(
            load_settings(),
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation="synthetic-live-capture",
            target_url=None,
            profile_decode_context=pinned.profile_decode_context(),
            effect_guard=deny_commit,
            on_session_write=record_effect,
        )
    assert phases == ["remote", "commit-refused"]
    assert receipts == []
    assert not session_store.exists(session_path)

    phases.clear()

    @asynccontextmanager
    async def allow_commit() -> AsyncGenerator[None]:
        assert phases == ["remote"]
        phases.append("commit-enter")
        yield
        phases.append("commit-exit")

    with bundled_indexed_authority().operation() as pinned, override_settings(cadrumo_live_tests_enabled="1"):
        result = await ensure_live_authenticated_session(
            load_settings(),
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation="synthetic-live-capture",
            target_url=None,
            profile_decode_context=pinned.profile_decode_context(),
            effect_guard=allow_commit,
            on_session_write=record_effect,
        )
    assert result.provider_kind is AuthProviderKind.CERTIFICATE
    assert phases == ["remote", "commit-enter", "commit-exit"]
    assert receipts == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert session_store.exists(session_path)
