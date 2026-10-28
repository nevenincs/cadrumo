"""One Sede view across every leg: the person's window, the runtime host relay, the worker and its Chromium.

The registered ``live.sede.view`` executor runs under the real operation
supervisor with its real journal, for a registered profile whose encrypted
session custody and certificate provider are the real ones. Its browser is
real headless Chromium; synthetic pages stand in for the Sede and for an
off-host site through the browser's context route, and the provider's own
verification browser runs behind the local HTTP boundary, so no request
leaves the host. The stream the executor opens is the worker's own view
endpoint, the host leg is the runtime's relay and the window is a native
connection the relay admitted by attach token.

The worker side runs in this process: the Sede pages are fulfilled by a
route in this process's Playwright, which a separately launched worker could
not be given. The relay's other admission refusals have their own tests.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import os
import time
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest
from playwright.async_api import BrowserContext, Route, WebSocketRoute, async_playwright

from cadrumo.adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, DefaultBrowserSession
from cadrumo.adapters.outbound.aeat.browser.profile import Profile
from cadrumo.adapters.outbound.aeat.browser.sede_view import SedeViewPage
from cadrumo.adapters.outbound.aeat.browser.session import BrowserSession
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.application.auth.sessions import ViewSessionPublicationOutcome
from cadrumo.application.live.sede_view_operation import (
    SedeViewPublicResultV1,
    SedeViewRequest,
    build_sede_view_definition,
    build_sede_view_registration,
)
from cadrumo.application.live.sede_view_ports import (
    SedeViewBrowser,
    SedeViewBrowserFactory,
    SedeViewEnd,
    SedeViewOpening,
)
from cadrumo.application.live.session import ensure_live_authenticated_session
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.logging import default_log_file_path
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.tests.component_record_support import record_shared_browser
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.view_stream import (
    SEDE_VIEW_DEFINITION_ID,
    PointerAction,
    PointerButton,
    PointerInput,
    TextInput,
    ViewClose,
    ViewClosed,
    ViewClosedReason,
    ViewCredit,
    ViewInput,
    ViewState,
    ViewUpstreamDocument,
    ViewWorkerBind,
)
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewDownloadAnswer,
    ViewDownloadOutcome,
    ViewFileChooser,
    ViewFileChooserAnswer,
    ViewFileChooserOutcome,
    ViewTransferComplete,
    ViewTransferCredit,
    ViewTransferDirection,
    ViewTransferUpstreamDocument,
    ViewUpload,
)
from cadrumo_client.transport.view_stream import (
    AssembledViewImage,
    ViewDownstreamReader,
    ViewTransferChunk,
    ViewTransferReceiver,
    ViewTransferSender,
    write_view_document,
    write_view_transfer_chunk,
    write_view_transfer_document,
)

from ...adapters.worker_transport import worker_endpoint
from ..view_stream_relay import ViewStreamRelay
from ..worker_view_stream import WorkerViewStream, WorkerViewStreams
from .test_view_stream_relay import _RUNTIME_NAMESPACE, _Clock, _Lane, _Window
from .view_session_world import ViewHttpBoundary, ViewSessionWorld
from .view_stream_host_support import bind_worker_leg, synthetic_worker_identity

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERSION: Final = "test"
_SEDE: Final[str] = Settings.external_constants().aeat.domains.sede.rstrip("/")
_OFF_HOST: Final = "https://www.example.com"
#: A loopback port nothing listens on: a request no route answers fails on this host.
_CLOSED_PROXY: Final = "http://127.0.0.1:9"
_SECONDS: Final = 60.0

# Private page content the scan looks for. Each is unique to this module.
_TITLE: Final = "Expediente sintetico 7c41e2"
_QUERY_VALUE: Final = "q-5e19d0b7"
_TYPED: Final = "tecleado-93b2f6"
_VIEW_COOKIE: Final = "VISTA_SINTETICA"
_DOWNLOAD: Final[bytes] = b"%PDF-1.4 descarga-sintetica-a8f3 " + os.urandom(3 * 65_520 + 911)
_UPLOAD: Final[bytes] = b"aportacion-sintetica-d21c " + os.urandom(2 * 65_520 + 333)

_HOME = f"{_SEDE}/"
_DOWNLOAD_URL = f"{_SEDE}/wlpl/descarga/justificante.pdf"
_UPLOAD_URL = f"{_SEDE}/wlpl/aportar"
_POST_URL = f"{_SEDE}/wlpl/presentar?expediente={_QUERY_VALUE}"
_POPUP_URL = f"{_OFF_HOST}/ventana?expediente={_QUERY_VALUE}"
_OFF_HOST_URL = f"{_OFF_HOST}/fuera?expediente={_QUERY_VALUE}"
_IMAGE_URL = f"{_OFF_HOST}/pixel.png"
_WORKER_URL = f"{_SEDE}/sw.js"
_SOCKET_URL = f"wss://{_SEDE.removeprefix('https://')}/socket"

#: Every control is a full-width band at a known height, so the person's click lands on it by coordinate.
_BAND = "position:absolute;left:0;width:640px;height:40px;margin:0;border:0;padding:0;box-sizing:border-box"
_HOME_PAGE: Final = f"""<!doctype html><html><head><title>{_TITLE}</title><style>
body{{margin:0}} .band{{{_BAND}}}
@keyframes pulse{{from{{background:#c00}}to{{background:#00c}}}}
#pulse{{position:absolute;left:0;top:400px;width:640px;height:80px;animation:pulse .2s linear infinite alternate}}
</style></head><body>
<a class="band" style="top:0" href="{_DOWNLOAD_URL}">descargar</a>
<input class="band" style="top:50px" type="file" onchange="fetch('{_UPLOAD_URL}', {{method: 'POST', body: this.files[0]}})">
<a class="band" style="top:100px" target="_blank" href="{_POPUP_URL}">ventana</a>
<form method="post" action="{_POST_URL}">
<input class="band" style="top:150px" type="text" name="campo">
<button class="band" style="top:200px" type="submit">presentar</button>
</form>
<img src="{_IMAGE_URL}" width="1" height="1">
<div id="pulse"></div>
<script>
navigator.serviceWorker.register('/sw.js');
const socket = new WebSocket('{_SOCKET_URL}');
socket.onmessage = (event) => socket.send('eco:' + event.data);
</script></body></html>"""
_POPUP_PAGE: Final = f"""<!doctype html><title>{_TITLE} ventana</title>
<button style="{_BAND};top:0" onclick="window.close()">cerrar</button>"""
_POSTED_PAGE: Final = f"""<!doctype html><title>{_TITLE} presentado</title>
<a style="{_BAND};top:0" href="{_OFF_HOST_URL}">fuera</a>"""
_OFF_HOST_PAGE: Final = f"<!doctype html><title>{_TITLE} fuera</title><p>fuera de la Sede</p>"


def _band(index: int) -> tuple[int, int]:
    """The centre of the band at ``index``: the bands are 50 CSS pixels apart."""
    return 320, 50 * index + 20


@dataclass
class _SedeStandIn:
    """The Sede and an off-host site, as the view's Chromium reaches them, with every request recorded.

    It is the browser's evasion seam: the context route fulfils each page and
    the WebSocket stand-in answers the page's socket. The view itself installs
    no route, policy or block.
    """

    received: list[tuple[str, str, bytes | None]] = field(default_factory=list)
    socket_messages: list[str] = field(default_factory=list)

    async def apply(self, context: BrowserContext) -> None:
        await context.route("**/*", self._fulfil)
        await context.route_web_socket(_SOCKET_URL, self._socket)

    def _socket(self, socket: WebSocketRoute) -> None:
        socket.on_message(lambda message: self.socket_messages.append(str(message)))
        socket.send("hola")

    async def _fulfil(self, route: Route) -> None:
        request = route.request
        self.received.append((request.method, request.url, request.post_data_buffer))
        url = request.url
        if url in {_SEDE, _HOME}:
            await route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=_HOME_PAGE,
                headers={"set-cookie": f"{_VIEW_COOKIE}=v-2f7d; Path=/; Secure; SameSite=Lax"},
            )
        elif url == _DOWNLOAD_URL:
            await route.fulfill(
                status=200,
                content_type="application/pdf",
                body=_DOWNLOAD,
                headers={"content-disposition": 'attachment; filename="justificante.pdf"'},
            )
        elif url == _WORKER_URL:
            await route.fulfill(status=200, content_type="text/javascript", body="self.onfetch = () => {};")
        elif url == _IMAGE_URL:
            await route.fulfill(status=200, content_type="image/gif", body=base64.b64decode(_GIF))
        elif url in {_UPLOAD_URL, _POST_URL} and request.method == "POST":
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=_POSTED_PAGE)
        elif url == _POPUP_URL:
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=_POPUP_PAGE)
        elif url == _OFF_HOST_URL:
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=_OFF_HOST_PAGE)
        else:
            await route.fulfill(status=404, body="")

    def reached(self, method: str, url: str) -> bool:
        return any(entry[0] == method and entry[1] == url for entry in self.received)

    def posted(self, url: str) -> bytes | None:
        return next((body for method, target, body in self.received if method == "POST" and target == url), None)


_GIF: Final = "R0lGODlhAQABAAAAACw="


@dataclass
class _View:
    """One running view: its supervised operation, the worker's stream, the host relay and the person's window."""

    supervisor: OperationSupervisor
    operation_id: str
    settling: asyncio.Task[OperationPersistedSnapshot]
    lane: _Lane
    site: _SedeStandIn
    root: Path


class _Panel:
    """The person's window: one reader of the view connection, which carries images, documents and transfers."""

    def __init__(self, window: _Window) -> None:
        self.window = window
        self.downloads = ViewTransferReceiver(ViewTransferDirection.DOWNLOAD)
        self.reader = ViewDownstreamReader(window.client, transfers=self.downloads)
        self.images: list[AssembledViewImage] = []
        self.states: list[ViewState] = []

    def send(self, document: ViewUpstreamDocument) -> None:
        write_view_document(self.window.client, document, deadline=time.monotonic() + 5)

    def answer(self, document: ViewTransferUpstreamDocument) -> None:
        write_view_transfer_document(self.window.client, document, deadline=time.monotonic() + 5)

    def click(self, x: int, y: int) -> None:
        for action in (PointerAction.MOVE, PointerAction.DOWN, PointerAction.UP):
            pressed = action is not PointerAction.MOVE
            self.send(
                ViewInput(
                    event=PointerInput(
                        action=action,
                        x=x,
                        y=y,
                        button=PointerButton.LEFT if pressed else PointerButton.NONE,
                        click_count=1 if pressed else 0,
                        modifiers=0,
                    )
                )
            )

    def next(self) -> object:
        """Read the next item, keeping images and states as the window would draw them."""
        item = self.reader.read(deadline=time.monotonic() + _SECONDS)
        if isinstance(item, AssembledViewImage):
            self.images.append(item)
        elif isinstance(item, ViewState):
            self.states.append(item)
        return item

    def until[ItemT](self, kind: type[ItemT]) -> ItemT:
        while not isinstance(item := self.next(), kind):
            pass
        return item

    def closed(self) -> ViewClosed:
        return self.until(ViewClosed)

    def drain(self, seconds: float) -> list[object]:
        """Read whatever arrives within ``seconds`` without waiting past it."""
        items: list[object] = []
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.window.client.read_ready():
                items.append(self.next())
            else:
                time.sleep(0.02)
        return items


def _view_browser_factory(site: _SedeStandIn) -> SedeViewBrowserFactory:
    async def open_view(opening: SedeViewOpening) -> SedeViewBrowser:
        """Open the view as production does, on a browser whose pages the stand-in site serves."""
        settings = opening.settings.model_copy(
            update={"cadrumo_browser_headless": True, "cadrumo_proxy_url": _CLOSED_PROXY}
        )
        record_shared_browser(settings)
        playwright = await async_playwright().start()
        session = BrowserSession(playwright, settings, Profile(name="sede-view-integration"), evasion_strategy=site)
        owner = DefaultBrowserSession(playwright=playwright, session=session)
        return await SedeViewPage.open(session, owner, opening)

    return open_view


def _request(world: ViewSessionWorld) -> OperationRequest[SedeViewRequest]:
    profile_id = world.profile_id
    return OperationRequest[SedeViewRequest](
        definition_id=SEDE_VIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=SedeViewRequest(profile_id=profile_id, css_width=640, css_height=480, scale=1.0),
    )


async def _sync(
    world: ViewSessionWorld, boundary: ViewHttpBoundary, operation: PinnedAuthorityOperation, name: str
) -> bool:
    """A CLI or TUI sync: whether it reused the stored session rather than signing in afresh."""
    host = world.operation_host()
    result = await ensure_live_authenticated_session(
        load_settings(),
        certificate_secret_backend_factory=world.certificate_secret_backend_factory,
        browser_session_factory=boundary.browser_session_factory(profile_name=name),
        operation=name,
        target_url=None,
        operator_scope_ports=world.operator_scope_ports,
        profile_decode_context=operation.profile_decode_context(),
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )
    return result.reused_persisted_session


@asynccontextmanager
async def _running_view(
    world: ViewSessionWorld, tmp_path: Path, boundary: ViewHttpBoundary, operation: PinnedAuthorityOperation
) -> AsyncGenerator[_View]:
    """Submit the view to the supervisor, bind its worker leg to the relay and attach no window yet."""
    site = _SedeStandIn()
    identity = synthetic_worker_identity()
    session_id, person_id = uuid4(), uuid4()
    held = {(person_id, session_id)}
    relay = ViewStreamRelay(
        runtime_boot_id=identity.runtime_boot_id,
        holds_session=lambda connection, session: (connection, session) in held,
    )
    streams = WorkerViewStreams(
        storage_root=tmp_path, identity=identity, parent_pid=os.getpid(), product_version=_VERSION
    )
    opened: list[WorkerViewStream] = []

    def open_stream(operation_identity: OperationIdentity) -> WorkerViewStream:
        # The worker host binds the stream to the session that admitted this exact view.
        sink = streams.open_view(operation_id=operation_identity.operation_id, session_id=session_id)
        opened.append(sink)
        return sink

    root = tmp_path / "operations"
    definition = build_sede_view_definition(
        certificate_secret_backend_factory=world.certificate_secret_backend_factory,
        browser_session_factory=boundary.browser_session_factory(profile_name="sede-view-provider"),
        operator_scope_ports=world.operator_scope_ports,
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=lambda _profile_id, _operation: None,
        view_browser_factory=_view_browser_factory(site),
        stream_opener=open_stream,
    )
    journal = OperationJournalRepository(storage_root=root)
    supervisor = OperationSupervisor(
        authority_operation=operation,
        registry=OperationRegistry(
            definitions=(definition,), public_registrations=(build_sede_view_registration(definition),)
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(objects=secure_object_repository_for_active_bucket()),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=now,
        lease_duration=timedelta(minutes=10),
        cleanup_timeout=timedelta(minutes=1),
    )
    operation_id = await supervisor.submit(_request(world), operation_id=os.urandom(32).hex())
    settling = asyncio.ensure_future(world.run_to_settlement(supervisor, operation_id))
    runtime = worker_endpoint(storage_root=tmp_path, worker_namespace=_RUNTIME_NAMESPACE)
    runtime.listen()
    lanes: list[_Lane] = []
    try:
        await world.until(lambda: bool(opened) or settling.done(), timeout=_SECONDS)
        assert opened, "the view settled before it opened its stream"
        bind = await asyncio.to_thread(
            bind_worker_leg, relay, storage_root=tmp_path, identity=identity, product_version=_VERSION
        )
        assert bind == ViewWorkerBind(operation_id=operation_id, session_id=session_id)
        lane = _Lane(
            tmp_path, relay, _Clock(), identity, operation_id, session_id, person_id, runtime, held, sink=opened[0]
        )
        lanes.append(lane)
        yield _View(supervisor, operation_id, settling, lane, site, root)
    finally:
        if not settling.done():
            await supervisor.request_cancel(operation_id)
            await asyncio.wait_for(asyncio.shield(settling), timeout=_SECONDS)
        relay.close()
        for sink in opened:
            await asyncio.to_thread(sink.close, ViewClosedReason.CANCELLED)
        for window in (window for lane in lanes for window in lane.windows):
            window.client.close()
            window.server.close()
        runtime.close()


async def _result(view: _View) -> SedeViewPublicResultV1:
    terminal = await asyncio.wait_for(asyncio.shield(view.settling), timeout=_SECONDS)
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    contract = view.supervisor.registry.lookup_public_contract(SEDE_VIEW_DEFINITION_ID)
    assert contract.result_schema is not None
    released = await OperationResultProjectionService(
        reader=OperationJournalRepository(storage_root=view.root),
        registry=view.supervisor.registry,
        operands=operation_secure_reference_repository(objects=secure_object_repository_for_active_bucket()),
    ).resolve(
        OperationResultProjectionRequestV1(
            operation_id=view.operation_id,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        SedeViewPublicResultV1,
    )
    assert isinstance(released, OperationResultProjectionSuccessV1)
    assert isinstance(released.projection, SedeViewPublicResultV1)
    return released.projection


def _attach(view: _View) -> _Panel:
    """Attach the person's window as the runtime does: a token for the submitting session, presented once."""
    lane = view.lane
    stranger = lane.connect_window()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        lane.relay.issue(lane.grant(peer=stranger.server.peer, session_id=uuid4()))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    window = lane.attach()
    return _Panel(window)


def _download(panel: _Panel) -> bytes:
    offer = panel.until(ViewDownload)
    assert offer.filename == "justificante.pdf"
    panel.downloads.expect(offer.transfer_id, size=offer.size)
    panel.answer(ViewDownloadAnswer(transfer_id=offer.transfer_id, outcome=ViewDownloadOutcome.ACCEPTED))
    panel.answer(panel.downloads.grant(offer.transfer_id, 2))
    received = bytearray()
    while True:
        item = panel.next()
        if isinstance(item, ViewTransferChunk):
            received += item.data
            if not item.last:
                panel.answer(panel.downloads.grant(offer.transfer_id, 1))
        elif isinstance(item, ViewTransferComplete):
            assert item.sha256 == hashlib.sha256(received).hexdigest()
            return bytes(received)


def _upload(panel: _Panel) -> None:
    chooser = panel.until(ViewFileChooser)
    assert not chooser.multiple
    panel.answer(
        ViewFileChooserAnswer(chooser_id=chooser.chooser_id, outcome=ViewFileChooserOutcome.SUPPLIED, file_count=1)
    )
    panel.answer(ViewUpload(chooser_id=chooser.chooser_id, transfer_id=1, name="aportacion.bin", size=len(_UPLOAD)))
    credit = panel.until(ViewTransferCredit)
    sender = ViewTransferSender(credit.transfer_id, io.BytesIO(_UPLOAD))
    sender.grant(credit.chunks)
    while True:
        while (chunk := sender.next_payload()) is not None:
            write_view_transfer_chunk(panel.window.client, chunk, deadline=time.monotonic() + 5)
        if sender.done:
            break
        sender.grant(panel.until(ViewTransferCredit).chunks)
    panel.answer(sender.completion())


def _credit_is_latest_wins(panel: _Panel) -> None:
    """With no credit no image arrives; each credit then draws the newest frame, skipping those replaced."""
    assert not any(isinstance(item, AssembledViewImage) for item in panel.drain(1.0))
    panel.send(ViewCredit(images=1))
    first = panel.until(AssembledViewImage).announcement.sequence
    # The page keeps animating; with the credit spent nothing more is sent.
    assert not any(isinstance(item, AssembledViewImage) for item in panel.drain(1.0))
    panel.send(ViewCredit(images=1))
    second = panel.until(AssembledViewImage).announcement.sequence
    assert second > first + 1, "frames produced while the window had no credit were replaced, not queued"


def _person_script(view: _View, panel: _Panel) -> bytes:
    """What the person does in the panel; returns the downloaded bytes."""
    panel.until(ViewState)
    _credit_is_latest_wins(panel)
    panel.click(*_band(0))
    downloaded = _download(panel)
    panel.click(*_band(1))
    _upload(panel)
    panel.click(*_band(2))
    # The popup opens in the view; its own button closes it and the panel returns to the Sede page.
    while not (isinstance(item := panel.next(), ViewState) and item.origin == _OFF_HOST and item.path == "/ventana"):
        pass
    panel.click(*_band(0))
    while not (isinstance(item := panel.next(), ViewState) and item.path == "/" and not item.loading):
        pass
    panel.click(*_band(3))
    panel.send(ViewInput(event=TextInput(text=_TYPED)))
    panel.click(*_band(4))
    while not (isinstance(item := panel.next(), ViewState) and item.path == "/wlpl/presentar" and not item.loading):
        pass
    panel.click(*_band(0))
    while not (isinstance(item := panel.next(), ViewState) and item.origin == _OFF_HOST and item.path == "/fuera"):
        pass
    del view
    return downloaded


def _scan_targets(panel: _Panel, downloaded: bytes) -> dict[str, tuple[bytes, ...]]:
    """The private values a scripted session moved, as byte strings to look for."""
    frame = max((image.data for image in panel.images), key=len)
    middle = (len(frame) // 2) // 3 * 3
    window = frame[middle : middle + 48]
    return {
        "frame": (window, base64.b64encode(window), window.hex().encode()),
        "query": (_QUERY_VALUE.encode(),),
        "title": (_TITLE.encode(),),
        "typed": (_TYPED.encode(),),
        "download": (downloaded[40:104], base64.b64encode(downloaded[42:90])),
        "upload": (_UPLOAD[40:104], base64.b64encode(_UPLOAD[42:90])),
    }


def _files_under(*roots: Path) -> Iterator[Path]:
    for root in roots:
        if root.is_dir():
            yield from (path for path in root.rglob("*") if path.is_file())


def _leaks(text: bytes, targets: dict[str, tuple[bytes, ...]]) -> list[str]:
    return [name for name, needles in targets.items() if any(needle in text for needle in needles)]


@pytest.mark.asyncio
async def test_a_scripted_session_streams_the_page_blocks_nothing_and_publishes_on_close(
    view_session_world: ViewSessionWorld,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = view_session_world
    caplog.set_level(logging.DEBUG)
    with world.registered_profile(tmp_path, operation):
        async with world.opened_http_boundary() as boundary:
            # A sync signed in first: the view opens on that session.
            await _sync(world, boundary, operation, "sync-before-view")
            seeded = world.stored_digest()
            assert seeded is not None and _VIEW_COOKIE not in world.stored_cookie_names()
            async with _running_view(world, tmp_path, boundary, operation) as view:
                panel = await asyncio.to_thread(_attach, view)
                downloaded = await asyncio.to_thread(_person_script, view, panel)

                # Every request class the pages issued completed, and none was stood in by a block.
                site = view.site
                assert downloaded == _DOWNLOAD
                assert hashlib.sha256(site.posted(_UPLOAD_URL) or b"").digest() == hashlib.sha256(_UPLOAD).digest()
                assert site.posted(_POST_URL) == f"campo={_TYPED}".encode()
                for method, url in (
                    ("GET", _HOME),
                    ("GET", _IMAGE_URL),
                    ("GET", _WORKER_URL),
                    ("GET", _POPUP_URL),
                    ("GET", _DOWNLOAD_URL),
                    ("GET", _OFF_HOST_URL),
                ):
                    assert site.reached(method, url), (method, url)
                assert site.socket_messages == ["eco:hola"]

                # Closing the panel is not a cancellation: the view publishes its session and settles.
                await asyncio.to_thread(panel.send, ViewClose())
                closed = await asyncio.to_thread(panel.closed)
                assert closed.reason is ViewClosedReason.OPERATION_ENDED
                result = await _result(view)
                assert result.end is SedeViewEnd.CLOSED
                assert result.publication is ViewSessionPublicationOutcome.PUBLISHED
                snapshot = await view.supervisor.inspect(view.operation_id)
                projected = result.model_dump_json().encode() + snapshot.model_dump_json().encode()
                journals = view.root

            # Custody now holds the view's session, and the next sync reuses that very record.
            published = world.stored_digest()
            assert published not in {None, seeded}
            assert _VIEW_COOKIE in world.stored_cookie_names()
            assert await _sync(world, boundary, operation, "sync-after-view")
            assert world.stored_digest() == published

        targets = _scan_targets(panel, downloaded)
        records = delivered_records(caplog)
        logged = b"\n".join(
            "\n".join((record.getMessage(), repr(record.args), record.exc_text or "", repr(vars(record)))).encode()
            for record in records
        )
        # The project's file sink, the operation journal and the view's settlement record are all there to scan.
        product_log = default_log_file_path()
        assert product_log.is_file()
        assert any(path.name.endswith(".json") for path in _files_under(journals))
        assert any(record.getMessage().startswith("operation settled") for record in records)
        assert _leaks(logged, targets) == []
        assert _leaks(projected, targets) == []
        # Storage, custody, journals, leases and diagnostics live under the test's root; logs in the sink's.
        leaked = {
            str(path): found
            for path in _files_under(tmp_path, product_log.parent)
            if (found := _leaks(path.read_bytes(), targets))
        }
        assert leaked == {}


@pytest.mark.asyncio
async def test_signing_out_unbinds_the_view_at_once_and_it_settles_without_publishing(
    view_session_world: ViewSessionWorld, tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    world = view_session_world
    with world.registered_profile(tmp_path, operation):
        async with world.opened_http_boundary() as boundary:
            await _sync(world, boundary, operation, "sync-before-view")
            seeded = world.stored_digest()
            assert seeded is not None
            async with _running_view(world, tmp_path, boundary, operation) as view:
                panel = await asyncio.to_thread(_attach, view)
                # The Sede page loaded and set its cookie: a close now would publish a changed session.
                await world.until(lambda: view.site.reached("GET", _HOME), timeout=_SECONDS)
                await asyncio.to_thread(panel.until, ViewState)

                # Sign-out retires the session: the host unbinds both legs before the worker settles.
                view.lane.relay.unbind_sessions((view.lane.session_id,))
                assert view.lane.relay.worker_bind(view.operation_id) is None
                closed = await asyncio.to_thread(panel.closed)
                assert closed.reason is ViewClosedReason.SESSION_RETIRED
                with pytest.raises(ProfileAccessRefusedError):
                    view.lane.relay.issue(view.lane.grant(peer=panel.window.server.peer))

                result = await _result(view)
                assert result.end is SedeViewEnd.STREAM_ENDED
                assert result.publication is None
            assert world.stored_digest() == seeded
            assert _VIEW_COOKIE not in world.stored_cookie_names()
