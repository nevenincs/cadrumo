"""Tests for the central AEAT auth-session ensure API."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr

from ....adapters.outbound.aeat.auth import (
    AeatLoginAssertion,
    AeatSession,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
)
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import SecretStoreBackend, Settings, override_settings
from ....tests.secure_sql import dev_test_database_password
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .. import AuthProvider, AuthProviderDescription, AuthProviderKind
from .._acquisition_lock import inspect_auth_acquisition_lock
from .._sessions import AuthSessionUnavailableError, ensure_authenticated_aeat_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import BrowserSessionFactory

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_SEDE_URL = f"{Settings.external_constants().aeat.domains.sede}/"


class _ScriptedAuthProvider:
    """Auth provider driven by explicit probe/auth outcomes for orchestration checks."""

    kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL

    def __init__(
        self,
        *,
        probe: tuple[AeatSession, AeatLoginAssertion] | Exception | None = None,
        auth: tuple[AeatSession, AeatLoginAssertion] | None = None,
    ) -> None:
        self._probe = probe
        self._auth = auth
        self.probe_calls = 0
        self.authenticate_calls = 0
        self.verify_calls = 0
        self.close_calls = 0

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(kind=self.kind, label="scripted-clave-movil", configured=True, available=True)

    async def probe_persisted_session(
        self,
        *,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]:
        del target_url
        self.probe_calls += 1
        if isinstance(self._probe, Exception):
            raise self._probe
        if self._probe is None:
            raise AuthSessionUnavailableError("no persisted session")
        return self._probe

    async def authenticate(
        self,
        *,
        browser_session: object | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        del browser_session, target_url
        self.authenticate_calls += 1
        if self._auth is None:
            raise AuthSessionUnavailableError("auth not configured")
        return self._auth[0]

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        del target_url
        self.verify_calls += 1
        if self._auth is None:
            raise AuthSessionUnavailableError("auth not configured")
        assert session is self._auth[0]
        return self._auth[1]

    async def close(self) -> None:
        self.close_calls += 1


def test_scripted_provider_satisfies_auth_provider_protocol() -> None:
    """_ScriptedAuthProvider must be recognised as a valid AuthProvider by the runtime check.

    This guards against the provider drifting out of step with the protocol as new
    required methods are added; if the protocol grows a method this provider
    lacks, this test will fail with an ``AssertionError``, surfacing the gap
    before any orchestration test can produce a false-positive.
    """
    assert isinstance(_ScriptedAuthProvider(), AuthProvider), (
        "_ScriptedAuthProvider does not satisfy the AuthProvider runtime-checkable protocol; "
        "update it to match the protocol definition in aeat.application.auth"
    )


@pytest.fixture(autouse=True)
def _active_profile(tmp_path: Path) -> Iterator[None]:
    with override_settings(
        aeat_clave_movil_dni_nie=SecretStr("12345678Z"),
        aeat_local_storage_root=tmp_path,
        aeat_secret_store_backend=SecretStoreBackend.FILE,
        aeat_secret_passphrase=SecretStr(dev_test_database_password()),
    ):
        dispose_engine()
        with profile_create_storage_span("operator"):
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id="operator",
                    overrides={"identity.tax_id": "12345678Z"},
                ),
            )
            try:
                yield
            finally:
                dispose_engine()


def _settings(tmp_path: Path) -> Settings:
    """Build a validated Settings instance with the cl@ve-movil identity pinned.

    Direct constructor kwargs route the values through the pydantic
    validator chain. The autouse ``_active_profile`` fixture pins the
    same identity through ``override_settings`` for the ContextVar
    layer; this helper produces an explicit Settings instance to pass
    into functions that take ``settings`` as a kwarg.
    """
    return Settings(
        aeat_clave_movil_dni_nie=SecretStr("12345678Z"),
        aeat_token_dir=tmp_path / "tokens",
    )


def _session() -> AeatSession:
    return AeatSession(
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=_T0,
        idle_deadline=_T0 + timedelta(minutes=20),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=ClaveMovilSessionDetail(
            dni_nie="12345678Z",
            used_non_qr_fallback=True,
            verification_code="ABC",
            landing_url=_SEDE_URL,
        ),
    )


def _assertion(valid: bool = True) -> AeatLoginAssertion:
    return AeatLoginAssertion(
        target_url=_SEDE_URL,
        is_valid=valid,
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        identity_nif="12345678Z",
        status_code=200,
        elapsed_ms=1,
        attempted_at=_T0,
        error_message=None if valid else "invalid live assertion",
        assertion_detail=ClaveMovilLoginAssertionDetail(
            session_cookie_present=valid,
            landing_url=_SEDE_URL,
        ),
    )


def _factory(
    providers: list[_ScriptedAuthProvider],
) -> Callable[[AuthProviderKind, Settings, BrowserSessionFactory | None], AuthProvider]:
    def build(
        kind: AuthProviderKind,
        settings: Settings,
        browser_session_factory: BrowserSessionFactory | None,
    ) -> AuthProvider:
        del kind, settings, browser_session_factory
        return providers.pop(0)

    return build


@pytest.mark.asyncio
async def test_ensure_reuses_persisted_session_without_acquiring_lock(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    session = _session()
    assertion = _assertion()
    provider = _ScriptedAuthProvider(probe=(session, assertion))

    result = await ensure_authenticated_aeat_session(
        settings,
        kind=AuthProviderKind.CLAVE_MOVIL,
        provider_factory=_factory([provider]),
    )

    assert result.session is session
    assert result.assertion is assertion
    assert result.reused_persisted_session is True
    assert result.acquired_lock is None
    assert provider.probe_calls == 1
    assert provider.authenticate_calls == 0
    assert inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL).locked is False


@pytest.mark.asyncio
async def test_ensure_acquires_lock_then_authenticates_after_probe_failure(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    session = _session()
    assertion = _assertion()
    first_probe = _ScriptedAuthProvider(probe=AuthSessionUnavailableError("missing"))
    second_probe = _ScriptedAuthProvider(probe=AuthSessionUnavailableError("missing"))
    auth_provider = _ScriptedAuthProvider(auth=(session, assertion))

    result = await ensure_authenticated_aeat_session(
        settings,
        kind=AuthProviderKind.CLAVE_MOVIL,
        provider_factory=_factory([first_probe, second_probe, auth_provider]),
    )

    assert result.session is session
    assert result.assertion is assertion
    assert result.reused_persisted_session is False
    assert result.acquired_lock is not None
    assert first_probe.probe_calls == 1
    assert second_probe.probe_calls == 1
    assert auth_provider.authenticate_calls == 1
    assert auth_provider.verify_calls == 1
    assert inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL).locked is False


@pytest.mark.asyncio
async def test_ensure_fresh_skips_persisted_probe(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    session = _session()
    assertion = _assertion()
    auth_provider = _ScriptedAuthProvider(auth=(session, assertion))

    result = await ensure_authenticated_aeat_session(
        settings,
        kind=AuthProviderKind.CLAVE_MOVIL,
        fresh=True,
        provider_factory=_factory([auth_provider]),
    )

    assert result.session is session
    assert result.fresh is True
    assert result.reused_persisted_session is False
    assert auth_provider.probe_calls == 0
    assert auth_provider.authenticate_calls == 1


@pytest.mark.asyncio
async def test_ensure_raises_when_assertion_is_invalid(tmp_path: Path) -> None:
    """When the provider returns an assertion with is_valid=False the service
    must raise AeatLoginAssertionError rather than returning a result that
    would let an unverified session propagate to callers.

    This test exercises the is_valid gate in ensure_authenticated_aeat_session;
    without it, a provider that silently returns a failed assertion would pass
    through undetected.
    """
    from ....adapters.outbound.aeat.auth import AeatLoginAssertionError

    settings = _settings(tmp_path)
    session = _session()
    # is_valid=False triggers the gate.
    invalid_assertion = _assertion(valid=False)
    # The service builds three providers: probe-outside-lock, probe-inside-lock,
    # then authenticate. All three are needed in the factory queue.
    probe_1 = _ScriptedAuthProvider(probe=AuthSessionUnavailableError("no session"))
    probe_2 = _ScriptedAuthProvider(probe=AuthSessionUnavailableError("no session"))
    auth_provider = _ScriptedAuthProvider(auth=(session, invalid_assertion))

    with pytest.raises(AeatLoginAssertionError):
        await ensure_authenticated_aeat_session(
            settings,
            kind=AuthProviderKind.CLAVE_MOVIL,
            provider_factory=_factory([probe_1, probe_2, auth_provider]),
        )
