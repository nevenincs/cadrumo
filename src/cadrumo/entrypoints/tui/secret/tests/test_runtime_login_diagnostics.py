"""Real login-screen events expose safe outcomes without credential or exception text."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.widgets import Button, Input

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from .....application.operations.registry import OperationFrontendProjection
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....application.runtime.profile_access import RuntimeProfileStatus
from .....application.user_profile.login_interaction import ProfileLoginChoice
from .....core.diagnostic_log import DiagnosticFormatter
from .....core.logging import LOG_FILE_FORMAT, get_logger
from ..runtime_login import RuntimeLoginScreen
from ..runtime_login_contracts import RuntimeLoginMethod

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PRIVATE_CANARY = "private-login-input-and-error-canary"


class _Client(RuntimeFrontendClient):
    """A credential-exchange fault port for presentation and logging tests."""

    def __init__(self, profile_id: UUID, error: BaseException) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id = None
        self.error = error
        self.closed = False
        self.proof: bytearray | None = None

    @override
    def login_password(
        self, secret: bytearray, *, timeout: float = 20, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        self.proof = secret
        raise self.error

    @override
    def close(self) -> None:
        self.closed = True


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))

    @override
    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        self.lines.append(line)
        self.events.append((record.getMessage(), json.loads(line.rsplit(" | ", 1)[1])))


class _FailingDiagnostic(logging.Handler):
    def __init__(self, event: str, failure: BaseException) -> None:
        super().__init__()
        self.event, self.failure = event, failure

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == self.event:
            raise self.failure


@pytest.fixture
def capture() -> Iterator[_Capture]:
    logger = get_logger("cadrumo.entrypoints.tui.secret.runtime_login_attempt")
    previous = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = _Capture()
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous[0])
        logger.propagate = previous[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unavailable", "credential", "unexpected"])
async def test_login_failure_is_correlated_and_keeps_private_text_out_of_logs(capture: _Capture, failure: str) -> None:
    profile_id = uuid4()
    error = (
        RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if failure == "unavailable"
        else RuntimeFrontendRefusedError("credential_rejected")
        if failure == "credential"
        else ValueError(_PRIVATE_CANARY)
    )
    client = _Client(profile_id, error)

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        if failure == "unavailable":
            raise error
        return client

    screen = RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label=_PRIVATE_CANARY),),
        open_client=open_client,
        accept_handoff=lambda _handoff: False,
    )
    app = App[None]()
    async with app.run_test(size=(140, 60)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()
        screen.query_one("#runtime-login-credential", Input).value = _PRIVATE_CANARY
        screen.query_one("#runtime-login-submit", Button).press()
        for _ in range(100):
            await pilot.pause(0.01)
            if any(event == "tui_login_finished" for event, _ in capture.events):
                break

    assert any(event == "tui_login_started" for event, _ in capture.events)
    refusal = next(fields for event, fields in capture.events if event in {"tui_login_refused", "tui_login_failed"})
    assert (
        refusal["reason_code"]
        == {
            "unavailable": "runtime_unavailable",
            "credential": "credential_rejected",
            "unexpected": "unexpected_login_failure",
        }[failure]
    )
    assert refusal["outcome"] == ("failed" if failure == "unexpected" else "refused")
    assert len({fields["diagnostic_id"] for _, fields in capture.events}) == 1
    assert _PRIVATE_CANARY not in "\n".join(capture.lines)
    assert client.closed is (failure != "unavailable")
    if client.proof is not None:
        assert not any(client.proof)


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_kind", ["none", "refusal", "cancellation"])
async def test_cleanup_diagnostic_interrupt_cannot_skip_close_or_replace_a_primary(
    capture: _Capture, primary_kind: str
) -> None:
    profile_id = uuid4()
    client = _Client(profile_id, ValueError("unused exchange failure"))
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if primary_kind == "refusal"
        else asyncio.CancelledError("synthetic pending cancellation")
        if primary_kind == "cancellation"
        else None
    )
    interruption = KeyboardInterrupt("synthetic diagnostic interruption")

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    screen = RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="synthetic choice"),),
        open_client=open_client,
        accept_handoff=lambda _handoff: False,
    )
    logger = get_logger("cadrumo.entrypoints.tui.secret.runtime_login_attempt")
    handler = _FailingDiagnostic("tui_login_connection_cleanup_started", interruption)
    logger.addHandler(handler)
    try:
        if primary_kind == "none":
            with pytest.raises(KeyboardInterrupt) as caught:
                await screen._close_untransferred(client, primary_error=primary)
            assert caught.value is interruption
        elif isinstance(primary, asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError) as cancelled:
                await screen._close_untransferred(client, primary_error=primary)
            assert cancelled.value is primary
        else:
            await screen._close_untransferred(client, primary_error=primary)
    finally:
        logger.removeHandler(handler)

    assert client.closed
    assert screen._cleanup_owners == {}
    assert any(event == "tui_login_connection_cleanup_finished" for event, _ in capture.events)


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["tui_login_started", "tui_login_finished"])
async def test_diagnostic_interrupt_at_attempt_boundary_still_erases_proof_and_releases_busy_state(
    capture: _Capture, event: str
) -> None:
    profile_id = uuid4()
    client = _Client(profile_id, ValueError("unused exchange failure"))
    proof = bytearray(_PRIVATE_CANARY, "utf-8")
    interruption = KeyboardInterrupt("synthetic diagnostic interruption")

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    screen = RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="synthetic choice"),),
        open_client=open_client,
        accept_handoff=lambda _handoff: False,
    )
    screen._busy = True
    screen._pending_proof = proof
    logger = get_logger("cadrumo.entrypoints.tui.secret.runtime_login_attempt")
    handler = _FailingDiagnostic(event, interruption)
    logger.addHandler(handler)
    try:
        with pytest.raises(KeyboardInterrupt) as caught:
            await screen._attempt(profile_id, "synthetic choice", RuntimeLoginMethod.PASSWORD, proof, None)
    finally:
        logger.removeHandler(handler)

    assert caught.value is interruption
    assert not any(proof) and screen._pending_proof is None
    assert not screen._busy and screen._cleanup_owners == {}
    assert client.closed is (event == "tui_login_finished")
