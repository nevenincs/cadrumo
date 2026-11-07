"""The listener, on real bundled Chromium, against a synthetic loopback server.

The server records what it really received, so each planted value is shown to have
travelled through the browser before it is shown to be absent from the output.
"""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final, override

import pytest
from playwright.async_api import BrowserContext, async_playwright
from playwright.async_api import Error as PlaywrightError
from pydantic import SecretStr

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.browser.profile import Profile
from cadrumo.adapters.outbound.aeat.browser.session import BrowserSession
from cadrumo.adapters.outbound.aeat.sede.notifications import READ_GUARD_POLICY as NOTIFICATIONS_READ_POLICY
from cadrumo.core.config import Settings, load_settings, override_settings
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.acceptance.aeat_request_capture.flows import LOGIN, ReadFlow
from dev.acceptance.aeat_request_capture.listener import (
    NotificationDetailRefusedError,
    RequestListener,
    observing_playwright,
)
from dev.acceptance.aeat_request_capture.live_flows import LiveCaptureState, run_live_capture
from dev.acceptance.aeat_request_capture.recorder import CaptureRecorder, write_report
from dev.acceptance.aeat_request_capture.runner import run_flows

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_PLANTED_NIF: Final = "12345678Z"
_QUERY_NIF: Final = "X0001502F"
_PLANTED_QUERY: Final = "plantedquerysecret"
_PLANTED_BODY: Final = "plantedbodysecret"
_PLANTED_API_BODY: Final = "plantedapibodysecret"
_PLANTED_COOKIE: Final = "plantedcookiesecret"
_PLANTED_HEADER: Final = "plantedheadersecret"
_SESSION_ID: Final = "PLANTEDSESSION42"
_PLANTED_PATH_ID: Final = "a1b2c3d4e5f6a7b8c9d0"
_DETAIL_PATH: Final = "/wlpl/GNNO-JDIT/DetalleSede"
_ALL_PLANTED: Final = (
    _PLANTED_NIF,
    _QUERY_NIF,
    _PLANTED_QUERY,
    _PLANTED_BODY,
    _PLANTED_API_BODY,
    _PLANTED_COOKIE,
    _PLANTED_HEADER,
    _SESSION_ID,
    _PLANTED_PATH_ID,
)


@dataclass
class _Received:
    raw: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(self.raw)


def _handler_for(received: _Received) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _answer(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace")
            received.raw.append(f"{self.command} {self.path}\n{self.headers}\n{body}")
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>synthetic</body></html>")

        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer()

        @override
        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return Handler


@pytest.fixture
def loopback() -> Iterator[tuple[str, _Received]]:
    received = _Received()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(received))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@asynccontextmanager
async def _product_context() -> AsyncGenerator[BrowserContext]:
    """Open a context the way the product does, through its real browser session."""
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, load_settings(), Profile(name="capture-test"))
        try:
            context = await session.create_context()
            try:
                yield context
            finally:
                await context.close()
        finally:
            await session.close()


def _recorder() -> CaptureRecorder:
    recorder = CaptureRecorder((NOTIFICATIONS_READ_POLICY,), notification_detail_paths=(_DETAIL_PATH,))
    recorder.register_flow("synthetic", (NOTIFICATIONS_READ_POLICY.id,))
    recorder.begin_flow("synthetic")
    return recorder


@pytest.mark.asyncio
async def test_planted_values_travel_through_the_browser_but_never_reach_the_output(
    loopback: tuple[str, _Received],
    tmp_path: Path,
) -> None:
    origin, received = loopback
    recorder = _recorder()
    listener = RequestListener(recorder, notification_detail_paths=(_DETAIL_PATH,))
    with observing_playwright(listener):
        async with _product_context() as context:
            await context.add_cookies([{"name": "JSESSIONID", "value": _PLANTED_COOKIE, "url": origin}])
            page = await context.new_page()
            await page.goto(
                f"{origin}/wlpl/SCEJ-MANT/{_PLANTED_NIF}/{_PLANTED_PATH_ID}/consulta;jsessionid={_SESSION_ID}"
                f"?nif={_QUERY_NIF}&secreto={_PLANTED_QUERY}",
            )
            await page.evaluate(
                """async ([url, body, header]) => {
                    await fetch(url, {method: 'POST', body, headers: {'x-planted': header}});
                }""",
                [f"{origin}/wlpl/SCEJ-MANT/zkau", f"secreto={_PLANTED_BODY}", _PLANTED_HEADER],
            )
            await context.request.post(f"{origin}/wlpl/API/lectura", form={"secreto": _PLANTED_API_BODY})
    recorder.end_flow("synthetic", "completed")

    output = tmp_path / "request-capture.json"
    write_report(recorder.report(), output)
    written = output.read_bytes()
    held_in_memory = repr(vars(recorder))

    for planted in _ALL_PLANTED:
        assert planted in received.text(), f"{planted} never reached the server, so this proves nothing"
        assert planted.encode() not in written, planted
        assert planted.lower().encode() not in written.lower(), planted
        assert planted not in held_in_memory, planted

    flows = json.loads(written)["flows"]
    requests = {(item["source"], item["method"], item["path"]): item for item in flows[0]["requests"]}
    navigation = requests[("browser", "GET", "/wlpl/SCEJ-MANT/{tax-id}/{token}/consulta;{session}")]
    assert navigation["placeholders"] == {"session": 1, "tax-id": 1, "token": 1}
    assert navigation["host"] == "127.0.0.1"
    assert requests[("browser", "POST", "/wlpl/SCEJ-MANT/zkau")]["count"] == 1
    assert requests[("api", "POST", "/wlpl/API/lectura")]["count"] == 1
    assert flows[0]["placeholders"] == {"session": 1, "tax-id": 1, "token": 1}
    assert navigation["verdicts"] == {NOTIFICATIONS_READ_POLICY.id: {"refuse:authority": 1}}


@pytest.mark.asyncio
async def test_a_notification_detail_request_is_stopped_on_both_channels_and_reported(
    loopback: tuple[str, _Received],
) -> None:
    origin, received = loopback
    recorder = _recorder()
    listener = RequestListener(recorder, notification_detail_paths=(_DETAIL_PATH,))
    with observing_playwright(listener):
        async with _product_context() as context:
            page = await context.new_page()
            with pytest.raises(PlaywrightError):
                await page.goto(f"{origin}{_DETAIL_PATH}?ncc=1")
            with pytest.raises(NotificationDetailRefusedError):
                await context.request.post(f"{origin}{_DETAIL_PATH}", form={"ncc": "1"})
    recorder.end_flow("synthetic", "completed")

    assert _DETAIL_PATH not in received.text(), "the detail request reached the server"
    assert recorder.notification_detail_requests == 2


@pytest.mark.asyncio
async def test_the_listener_restores_playwright_when_it_ends() -> None:
    from playwright.async_api import APIRequestContext, Browser

    new_context, post = Browser.new_context, APIRequestContext.post
    with observing_playwright(RequestListener(_recorder())):
        assert Browser.new_context is not new_context
        assert APIRequestContext.post is not post

    assert Browser.new_context is new_context
    assert APIRequestContext.post is post


def _flow(flow_id: str, *, needs_session: bool) -> ReadFlow:
    return ReadFlow(
        flow_id=flow_id,
        cli_command=flow_id,
        reader="synthetic",
        policy_ids=(NOTIFICATIONS_READ_POLICY.id,),
        needs_session=needs_session,
        lane_tests=(),
        read_only_because="synthetic",
    )


@pytest.mark.asyncio
async def test_a_failed_login_stops_session_flows_and_its_message_stays_out_of_the_report() -> None:
    ran: list[str] = []

    async def failing_login(_state: None) -> None:
        raise RuntimeError(f"goto https://www6.agenciatributaria.gob.es/x?nif={_PLANTED_NIF} failed")

    async def tracked(_state: None) -> None:
        ran.append("independent")

    recorder = CaptureRecorder((NOTIFICATIONS_READ_POLICY,))
    await run_flows(
        (_flow(LOGIN, needs_session=False), _flow("needs", needs_session=True), _flow("alone", needs_session=False)),
        {LOGIN: failing_login, "needs": tracked, "alone": tracked},
        None,
        recorder=recorder,
        listener=RequestListener(recorder),
    )

    report = recorder.report()
    flows = report["flows"]
    assert isinstance(flows, list)
    assert {flow["flow"]: flow["outcome"] for flow in flows} == {
        LOGIN: "failed:RuntimeError",
        "needs": "not-run:no-session",
        "alone": "completed",
    }
    assert ran == ["independent"]
    assert _PLANTED_NIF not in json.dumps(report)


def test_the_whole_live_path_rehearsed_offline_uses_the_dedicated_profile_and_writes_the_report(
    loopback: tuple[str, _Received],
    tmp_path: Path,
) -> None:
    origin, received = loopback
    seen_settings: list[Settings] = []

    async def stand_in_reader(state: LiveCaptureState) -> None:
        # The product's own session factory, under the settings the scope established.
        seen_settings.append(state.settings)
        session = await default_browser_session_factory(state.settings)
        context = await session.create_context()
        try:
            page = await context.new_page()
            await page.goto(f"{origin}/wlpl/SCEJ-MANT/{_PLANTED_NIF}/consulta?nif={_QUERY_NIF}")
        finally:
            await context.close()
            await session.close()

    output = tmp_path / "report" / "request-capture.json"
    profile_base = tmp_path / "live"
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_PLANTED_NIF),
        cadrumo_clave_movil_nie_soporte=SecretStr("E00010256"),
    ):
        recorder = run_live_capture(
            (_flow(LOGIN, needs_session=False),),
            {LOGIN: stand_in_reader},
            settings=load_settings(),
            modelo="100",
            ejercicio=filing_year_envelope().horizon,
            profile_base=profile_base,
            output=output,
            show=lambda _line: None,
        )

    assert _PLANTED_NIF in received.text()
    written = output.read_bytes()
    assert _PLANTED_NIF.encode() not in written
    assert _QUERY_NIF.encode() not in written
    assert recorder.notification_detail_requests == 0
    flow = json.loads(written)["flows"][0]
    assert flow["outcome"] == "completed"
    assert [item["path"] for item in flow["requests"] if item["host"] == "127.0.0.1"] == [
        "/wlpl/SCEJ-MANT/{tax-id}/consulta"
    ]
    assert seen_settings[0].cadrumo_storage_root == profile_base / "cadrumo-storage"
    assert not (profile_base / "cadrumo-storage" / "components" / "playwright").exists()
