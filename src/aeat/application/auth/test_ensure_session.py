"""Tests for the central AEAT auth-session ensure API."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import BrowserSessionFactory

import pytest

from ...core.config import Settings
from . import AuthProviderDescription, AuthProviderKind
from ._acquisition_lock import inspect_auth_acquisition_lock
from ._sessions import AuthSessionUnavailableError, ensure_authenticated_aeat_session

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class _Provider:
    kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL

    def __init__(
        self,
        *,
        probe: tuple[object, object] | Exception | None = None,
        auth: tuple[object, object] | None = None,
    ) -> None:
        self._probe = probe
        self._auth = auth
        self.probe_calls = 0
        self.authenticate_calls = 0
        self.verify_calls = 0
        self.close_calls = 0

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(kind=self.kind, label="_Provider", configured=True, available=True)

    async def probe_persisted_session(self, *, target_url: str | None = None) -> tuple[object, object]:
        del target_url
        self.probe_calls += 1
        if isinstance(self._probe, Exception):
            raise self._probe
        if self._probe is None:
            raise AuthSessionUnavailableError("no persisted session")
        return self._probe

    async def authenticate(self, *, target_url: str | None = None) -> object:
        del target_url
        self.authenticate_calls += 1
        if self._auth is None:
            raise AuthSessionUnavailableError("auth not configured")
        return self._auth[0]

    async def verify(self, session: object, *, target_url: str | None = None) -> object:
        del target_url
        self.verify_calls += 1
        if self._auth is None:
            raise AuthSessionUnavailableError("auth not configured")
        assert session is self._auth[0]
        return self._auth[1]

    async def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def _active_profile() -> Iterator[None]:
    from aeat.core.config import override_settings

    with override_settings(aeat_active_profile="operator"):
        yield


def _settings(tmp_path: Path) -> Settings:
    return Settings().model_copy(
        update={"aeat_token_dir": tmp_path / "tokens"}
    )


def _assertion(valid: bool = True) -> object:
    return SimpleNamespace(is_valid=valid, status_code=200, error_message=None)


@contextmanager
def _active_bucket_session() -> Iterator[None]:
    from ...adapters.persistence.storage.master_key._active_session import activate_session
    from ...adapters.persistence.storage.master_key._bucket_session import BucketSession

    key = b"t" * 32
    session = BucketSession.open(
        bucket_id="operator",
        kek=key,
        dek=key,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )
    try:
        with activate_session(session):
            yield
    finally:
        session.close()


def _factory(providers: list[_Provider]):
    def build(
        kind: AuthProviderKind, settings: Settings, browser_session_factory: BrowserSessionFactory | None
    ) -> _Provider:
        del kind, settings, browser_session_factory
        return providers.pop(0)

    return build


@pytest.mark.asyncio
async def test_ensure_reuses_persisted_session_without_acquiring_lock(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    session = SimpleNamespace(identity_nif="12345678Z")
    assertion = _assertion()
    provider = _Provider(probe=(session, assertion))

    result = await ensure_authenticated_aeat_session(
        settings,
        kind=AuthProviderKind.CLAVE_MOVIL,
        provider_factory=_factory([provider]),  # pyright: ignore[reportArgumentType]  # pyrefly: ignore[bad-argument-type]  # reason: _Provider is a duck-typed test fake; AeatSession/AeatLoginAssertion cannot be constructed without live adapters — tracked for auth-provider protocol narrowing
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
    session = SimpleNamespace(identity_nif="12345678Z")
    assertion = _assertion()
    first_probe = _Provider(probe=AuthSessionUnavailableError("missing"))
    second_probe = _Provider(probe=AuthSessionUnavailableError("missing"))
    auth_provider = _Provider(auth=(session, assertion))

    result = await ensure_authenticated_aeat_session(
        settings,
        kind=AuthProviderKind.CLAVE_MOVIL,
        provider_factory=_factory([first_probe, second_probe, auth_provider]),  # pyright: ignore[reportArgumentType]  # pyrefly: ignore[bad-argument-type]  # reason: _Provider is a duck-typed test fake; AeatSession/AeatLoginAssertion cannot be constructed without live adapters — tracked for auth-provider protocol narrowing
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
    session = SimpleNamespace(identity_nif="12345678Z")
    assertion = _assertion()
    auth_provider = _Provider(auth=(session, assertion))

    with _active_bucket_session():
        result = await ensure_authenticated_aeat_session(
            settings,
            kind=AuthProviderKind.CLAVE_MOVIL,
            fresh=True,
            provider_factory=_factory([auth_provider]),  # pyright: ignore[reportArgumentType]  # pyrefly: ignore[bad-argument-type]  # reason: _Provider is a duck-typed test fake; AeatSession/AeatLoginAssertion cannot be constructed without live adapters — tracked for auth-provider protocol narrowing
        )

    assert result.session is session
    assert result.fresh is True
    assert result.reused_persisted_session is False
    assert auth_provider.probe_calls == 0
    assert auth_provider.authenticate_calls == 1
