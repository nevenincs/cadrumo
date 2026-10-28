"""Signing in inside the Sede view publishes to the custody every CLI and TUI sync reuses.

Each case opens the production :class:`SedeViewPage` in real headless
Chromium behind the local HTTP boundary, seeds it through the application's
view session, and lets :class:`SedeViewSessionSignIn` watch it as the view
operation does. The profile, the encrypted session custody and the providers
are the real ones; only the operation host and the window are stood in.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.application.auth.acquisition_lock import AuthAcquisitionLockState
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort, BrowserSessionPort
from cadrumo.application.auth.sessions import ViewSessionPublicationOutcome, view_context_provisioner
from cadrumo.application.live.sede_view_operation import SedeViewSessionSignIn
from cadrumo.application.live.sede_view_ports import SedeViewEnd, SedeViewOpening
from cadrumo.application.live.session import ensure_live_authenticated_session, open_live_view_session
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.view_stream import (
    KeyAction,
    KeyInput,
    PointerAction,
    PointerButton,
    PointerInput,
    TextInput,
    ViewClose,
    ViewInput,
    ViewNavigate,
    ViewNavigateVerb,
    ViewPhase,
    ViewResize,
    ViewSinkInput,
    ViewState,
    WheelInput,
)

from ...browser.sede_view import SedeViewPage, interrupts_assisted_login
from ...browser.tests.real_http_boundary import (
    LocalHttpBoundary,
    open_real_browser_session,
    opened_http_boundary,
    real_browser_factory,
)
from ...browser.tests.view_page_support import RecordingViewSink, until
from .. import session_store
from .._clave_provider_common import default_sede_target_url
from ..clave_movil import ClaveMovilAuthProvider
from .view_session_support import (
    CERTIFICATE_NIF,
    CERTIFICATE_SECRET_BACKEND_FACTORY,
    OPERATOR_SCOPE_PORTS,
    SESSION_COOKIE,
    OperationHost,
    certificate_profile,
    clave_permanente_profile,
    lock_state,
    stored_cookie_names,
    stored_digest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SIGN_IN_SECONDS = 60.0
_OTHER_NIF = "00000000T"


class _LaunchCount:
    """The real browser factory, counting the browsers the sign-in's verifications launch."""

    def __init__(self, factory: BrowserSessionFactoryPort) -> None:
        self._factory = factory
        self.launches = 0

    async def __call__(self, settings: Settings) -> BrowserSessionPort:
        self.launches += 1
        return await self._factory(settings)


@dataclass
class _Panel:
    """An open view, its stood-in window and the sign-in watching it."""

    view: SedeViewPage
    sink: RecordingViewSink
    sign_in: SedeViewSessionSignIn
    factory: BrowserSessionFactoryPort
    verification_browsers: _LaunchCount
    stop: list[bool]
    browsing: asyncio.Task[SedeViewEnd] | None = None

    def start(self) -> None:
        """Start browsing, as the view operation does once the view is open."""
        self.browsing = asyncio.ensure_future(
            self.view.browse(stop_requested=lambda: self.stop[0] or self.sign_in.unknown, sign_in=self.sign_in)
        )

    def phases(self) -> list[ViewPhase]:
        return [state.phase for state in self.sink.of(ViewState)]


async def _browsing_resumed() -> None:
    return


@asynccontextmanager
async def _panel(
    boundary: LocalHttpBoundary, host: OperationHost, operation: PinnedAuthorityOperation, *, name: str
) -> AsyncGenerator[_Panel]:
    """Open the view from custody exactly as the view operation does, without browsing yet."""
    factory = real_browser_factory(boundary=boundary, profile_name=f"{name}-auth")
    seed, settings = await open_live_view_session(
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        authority_operation=operation,
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )
    provisioner = view_context_provisioner(
        settings,
        baseline=seed.baseline,
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    sink = RecordingViewSink()
    playwright, session = await open_real_browser_session(boundary=boundary, settings=settings, profile_name=name)
    try:
        view = await SedeViewPage.open(
            session,
            None,
            SedeViewOpening(
                settings=settings,
                sink=sink,
                viewport=ViewResize(css_width=640, css_height=480, scale=1.0),
                storage_state=seed.storage_state,
                provisioner=provisioner,
            ),
        )
        stop = [False]
        verification_browsers = _LaunchCount(factory)
        panel = _Panel(
            view=view,
            sink=sink,
            factory=factory,
            verification_browsers=verification_browsers,
            stop=stop,
            sign_in=SedeViewSessionSignIn(
                settings=settings,
                seed=seed,
                browser=view,
                certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
                browser_session_factory=verification_browsers,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
                authority_operation=operation,
                effect_guard_for=lambda _phase: host.effect_guard,
                on_session_write=host.report,
                resume_browsing=_browsing_resumed,
                stop_requested=lambda: stop[0],
            ),
        )
        try:
            yield panel
        finally:
            if panel.browsing is not None:
                panel.stop[0] = True
                await asyncio.wait_for(panel.browsing, timeout=30)
            await view.close()
    finally:
        await session.close()
        await playwright.stop()


async def _reuses_the_published_session(
    factory: BrowserSessionFactoryPort, operation: PinnedAuthorityOperation
) -> bool:
    """A fresh CLI or TUI acquisition after the view: whether it resumed the stored session."""
    result = await ensure_live_authenticated_session(
        load_settings(),
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operation="sync-after-view",
        target_url=None,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        profile_decode_context=operation.profile_decode_context(),
        effect_guard=OperationHost().effect_guard,
        on_session_write=OperationHost().report,
    )
    return result.reused_persisted_session


@pytest.mark.asyncio
async def test_a_manual_cl_ve_permanente_login_with_empty_custody_publishes_and_is_reused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The person signs in by hand; the next AEAT page load publishes it through the provider's verification."""
    kind = AuthProviderKind.CLAVE_PERMANENTE
    with clave_permanente_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            assert stored_digest(kind) is None
            host = OperationHost(kind=kind)
            boundary.configure("failure")
            async with _panel(boundary, host, operation, name="view-manual-permanente") as panel:
                assert not panel.sign_in.signed_in
                assert panel.sign_in.baseline.storage_state_sha256 is None
                await panel.view.context.pages[0].wait_for_load_state("load")

                # The stood-in Sede now sets its session cookie: the person has signed in.
                boundary.configure("clave-permanente-success")
                panel.start()
                panel.sink.put(ViewNavigate(verb=ViewNavigateVerb.HOME))
                await until(lambda: panel.sign_in.signed_in, timeout=_SIGN_IN_SECONDS)

                assert host.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
                assert host.guard_entries == 1
                assert host.lock_state_at_unknown is AuthAcquisitionLockState.HELD
                assert lock_state(kind) is AuthAcquisitionLockState.ABSENT
                assert panel.sign_in.baseline.storage_state_sha256 == stored_digest(kind)
                assert SESSION_COOKIE in stored_cookie_names(kind)
                assert ViewPhase.ACQUIRING not in panel.phases()
                assert panel.browsing is not None and not panel.browsing.done()

            assert await _reuses_the_published_session(panel.factory, operation)


@pytest.mark.asyncio
async def test_signed_out_loads_that_change_no_cookie_are_verified_once(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Loads that slide a cookie's expiry or touch local storage cannot change a verification's answer."""
    kind = AuthProviderKind.CLAVE_PERMANENTE
    sede = Settings.external_constants().aeat.domains.sede
    with clave_permanente_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            host = OperationHost(kind=kind)
            boundary.configure("signed-out-churn")
            async with _panel(boundary, host, operation, name="view-signed-out-churn") as panel:
                page = panel.view.context.pages[0]
                await page.wait_for_load_state("load")
                captures: set[str] = set()
                for _load in range(3):
                    # The person browses the signed-out Sede; each load changes the capture.
                    await page.goto(sede)
                    captures.add(session_store.storage_state_sha256(await panel.view.context.storage_state()))
                    await panel.sign_in.page_loaded()
                landing = default_sede_target_url(load_settings())
                probes = [url for url in boundary.requested_urls if url == landing]

                assert len(captures) == 3
                assert len(probes) == 1
                assert panel.verification_browsers.launches == 1
                assert not panel.sign_in.signed_in

                # Signing in changes the cookies, so it is verified at once.
                boundary.configure("clave-permanente-success")
                await page.goto(sede)
                await panel.sign_in.page_loaded()

                assert panel.sign_in.signed_in
                assert panel.verification_browsers.launches == 2
                assert host.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
                assert SESSION_COOKIE in stored_cookie_names(kind)


@pytest.mark.asyncio
async def test_a_page_the_provider_cannot_verify_publishes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    kind = AuthProviderKind.CLAVE_PERMANENTE
    with clave_permanente_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            host = OperationHost(kind=kind)
            boundary.configure("failure")
            async with _panel(boundary, host, operation, name="view-unverified") as panel:
                panel.start()
                panel.sink.put(ViewNavigate(verb=ViewNavigateVerb.HOME))
                panel.sink.put(ViewClose())
                assert panel.browsing is not None
                assert await asyncio.wait_for(panel.browsing, timeout=_SIGN_IN_SECONDS) is SedeViewEnd.CLOSED
                outcome = await panel.sign_in.close()

            assert outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert not panel.sign_in.signed_in
            assert host.effects == []
            assert stored_digest(kind) is None


@pytest.mark.asyncio
async def test_a_manual_login_as_another_taxpayer_publishes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The person signs in by hand as someone else: AEAT's consulta names that taxpayer, so nothing is stored."""
    kind = AuthProviderKind.CLAVE_PERMANENTE
    with clave_permanente_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            host = OperationHost(kind=kind)
            boundary.configure("failure")
            async with _panel(boundary, host, operation, name="view-other-taxpayer") as panel:
                await panel.view.context.pages[0].wait_for_load_state("load")
                boundary.configure("clave-permanente-success")
                boundary.signed_in_nif = _OTHER_NIF
                panel.start()
                panel.sink.put(ViewNavigate(verb=ViewNavigateVerb.HOME))
                panel.sink.put(ViewClose())
                assert panel.browsing is not None
                assert await asyncio.wait_for(panel.browsing, timeout=_SIGN_IN_SECONDS) is SedeViewEnd.CLOSED
                outcome = await panel.sign_in.close()

            assert outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert not panel.sign_in.signed_in
            assert host.effects == []
            assert stored_digest(kind) is None


@pytest.mark.asyncio
async def test_an_assisted_certificate_login_runs_in_the_view_and_publishes_at_once(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            host = OperationHost()
            async with _panel(boundary, host, operation, name="view-assisted") as panel:
                assert not panel.sign_in.signed_in
                panel.start()
                await until(lambda: panel.sign_in.signed_in, timeout=_SIGN_IN_SECONDS)
                await until(lambda: panel.phases()[-1] is ViewPhase.BROWSING)

                phases = panel.phases()
                assert ViewPhase.ACQUIRING in phases
                assert phases.index(ViewPhase.ACQUIRING) < len(phases) - 1
                assert host.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
                assert host.guard_entries == 1
                assert lock_state() is AuthAcquisitionLockState.ABSENT
                assert panel.sign_in.baseline.storage_state_sha256 == stored_digest()
                assert panel.browsing is not None and not panel.browsing.done()

            assert await _reuses_the_published_session(panel.factory, operation)


@pytest.mark.asyncio
async def test_the_persons_input_interrupts_an_assisted_login_and_the_view_stays_theirs(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            host = OperationHost()
            async with _panel(boundary, host, operation, name="view-interrupted") as panel:
                await panel.view.context.pages[0].wait_for_load_state("load")
                boundary.configure("blocking")
                panel.start()
                await boundary.wait_until_blocked()
                assert panel.sign_in.interruptible
                assert panel.phases()[-1] is ViewPhase.ACQUIRING

                panel.sink.put(ViewInput(event=KeyInput(action=KeyAction.DOWN, key="a", code="KeyA", modifiers=0)))
                await until(lambda: not panel.sign_in.interruptible)
                # The page the login opened stays the person's; once it answers, the panel draws it browsing.
                boundary.configure("success")
                await until(lambda: panel.phases()[-1] is ViewPhase.BROWSING)

                assert not panel.sign_in.signed_in
                assert host.effects == []
                assert stored_digest() is None
                assert lock_state() is AuthAcquisitionLockState.ABSENT
                assert panel.browsing is not None and not panel.browsing.done()


@pytest.mark.parametrize(
    ("item", "interrupts"),
    [
        (
            ViewInput(
                event=PointerInput(
                    action=PointerAction.MOVE, button=PointerButton.NONE, x=10, y=10, click_count=0, modifiers=0
                )
            ),
            False,
        ),
        (ViewInput(event=WheelInput(x=10, y=10, delta_x=0, delta_y=40, modifiers=0)), False),
        (ViewResize(css_width=800, css_height=600, scale=1.0), False),
        (
            ViewInput(
                event=PointerInput(
                    action=PointerAction.DOWN, button=PointerButton.LEFT, x=10, y=10, click_count=1, modifiers=0
                )
            ),
            True,
        ),
        (ViewInput(event=KeyInput(action=KeyAction.DOWN, key="Enter", code="Enter", modifiers=0)), True),
        (ViewInput(event=TextInput(text="12345678Z")), True),
        (ViewNavigate(verb=ViewNavigateVerb.BACK), True),
        (ViewClose(), True),
    ],
)
def test_only_a_deliberate_action_interrupts_an_assisted_login(item: ViewSinkInput, interrupts: bool) -> None:
    assert interrupts_assisted_login(item) is interrupts


@pytest.mark.asyncio
async def test_the_cli_shows_a_qr_login_in_a_window_and_the_view_keeps_it_headless(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A QR login needs a visible page: the CLI opens a headed browser, the view shows it in the panel."""
    qr_settings = Settings(
        cadrumo_token_dir=tmp_path,
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_clave_movil_dni_nie=SecretStr(CERTIFICATE_NIF),
        cadrumo_browser_headless=True,
        cadrumo_clave_prefer_non_qr=False,
    )
    with certificate_profile(tmp_path, operation):
        async with (
            opened_http_boundary() as boundary,
            _panel(boundary, OperationHost(), operation, name="view-qr") as panel,
        ):
            cli = ClaveMovilAuthProvider(qr_settings, browser_session_factory=panel.factory)
            in_view = ClaveMovilAuthProvider(qr_settings, browser_session_factory=panel.view.login_session_factory)

            assert cli._fresh_login_settings().cadrumo_browser_headless is False
            assert in_view._fresh_login_settings().cadrumo_browser_headless is True
