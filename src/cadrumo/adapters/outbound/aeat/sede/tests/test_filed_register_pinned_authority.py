"""The filed register reuses its caller's authority operation pin."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import pytest
from playwright.async_api import Playwright

from cadrumo.adapters.outbound.aeat.sede import filed_data_capture_port as capture_port
from cadrumo.adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession
from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort
from cadrumo.application.auth.session_types import AeatSession
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_open_register_passes_the_pinned_authority_and_closes_both_scopes(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The adapter must not fork authority while opening its register session."""
    events: list[str] = []
    session = cast(AeatSession, object())
    settings = Settings.model_construct(cadrumo_live_filed_register_walk_timeout_ms=4321)
    playwright = cast(Playwright, object())
    register = cast(DeclaracionesRegisterSession, object())
    expected_secret_backend_factory = cast(CertificateSecretBackendFactory, object())
    expected_browser_session_factory = cast(BrowserSessionFactoryPort, object())
    expected_operator_scope_ports = cast(OperatorScopePorts, object())

    @asynccontextmanager
    async def expected_effect_guard() -> AsyncGenerator[None]:
        yield

    async def expected_session_write_reporter(effect: OperationEffect) -> None:
        raise AssertionError(f"opening the register unexpectedly published a session effect: {effect}")

    async def fake_active_verified_session(
        *,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operation: str,
        operator_scope_ports: OperatorScopePorts,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[AeatSession, Settings]:
        assert certificate_secret_backend_factory is expected_secret_backend_factory
        assert browser_session_factory is expected_browser_session_factory
        assert operation == "filed-register-pinned-authority-test"
        assert operator_scope_ports is expected_operator_scope_ports
        assert authority_operation is not None
        assert authority_operation is pinned_authority
        assert effect_guard is expected_effect_guard
        assert on_session_write is expected_session_write_reporter
        events.append("session-acquired")
        return session, settings

    @asynccontextmanager
    async def fake_shared_playwright(received_session: AeatSession) -> AsyncGenerator[Playwright]:
        assert received_session is session
        events.append("playwright-enter")
        try:
            yield playwright
        finally:
            events.append("playwright-exit")

    @asynccontextmanager
    async def fake_open_declarations_register(
        received_session: AeatSession,
        *,
        operation: PinnedAuthorityOperation,
        settings: Settings,
        playwright: Playwright | None = None,
    ) -> AsyncGenerator[DeclaracionesRegisterSession]:
        assert received_session is session
        assert operation is pinned_authority
        assert settings is expected_settings
        assert playwright is expected_playwright
        events.append("register-enter")
        try:
            yield register
        finally:
            events.append("register-exit")

    def forbidden_authority_open() -> object:
        raise AssertionError("Sede opened a second bundled authority operation")

    pinned_authority = authority_operation
    expected_settings = settings
    expected_playwright = playwright
    monkeypatch.setattr(capture_port, "active_verified_session", fake_active_verified_session)
    monkeypatch.setattr(capture_port, "shared_playwright", fake_shared_playwright)
    monkeypatch.setattr(capture_port, "open_declarations_register", fake_open_declarations_register)
    monkeypatch.setattr(capture_port, "bundled_indexed_authority", forbidden_authority_open)

    adapter = capture_port.SedeFiledDataCapturePort(
        certificate_secret_backend_factory=expected_secret_backend_factory,
        browser_session_factory=expected_browser_session_factory,
        operator_scope_ports=expected_operator_scope_ports,
    )

    async with adapter.open_register(
        operation="filed-register-pinned-authority-test",
        authority_operation=pinned_authority,
        effect_guard=expected_effect_guard,
        on_session_write=expected_session_write_reporter,
    ) as register_port:
        assert register_port.walk_timeout_ms == 4321

    assert events == [
        "session-acquired",
        "playwright-enter",
        "register-enter",
        "register-exit",
        "playwright-exit",
    ]
