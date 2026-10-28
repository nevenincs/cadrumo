"""The Sede view's input, navigation and dialog adapter, proven against a real headless Chromium.

Every case drives the production :class:`ViewInputAdapter` on a real page. The
page records the events it receives in ``window.log``; the tests read that log
back, so what is asserted is what the page saw, not what the adapter sent.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

import pytest
from playwright.async_api import BrowserContext, Dialog, Download, FileChooser, Page, Route, async_playwright

from cadrumo_client.contracts.view_stream import (
    KeyAction,
    KeyInput,
    PointerAction,
    PointerButton,
    PointerInput,
    TextInput,
    ViewDialog,
    ViewDialogKind,
    ViewInput,
    ViewNavigate,
    ViewNavigateVerb,
    ViewNotice,
    ViewNoticeCode,
    WheelInput,
)

from ......core.config import Settings
from ......tests.component_record_support import record_shared_browser
from ..profile import Profile
from ..session import BrowserSession
from ..view_input import (
    DialogOutcome,
    NavigationAvailability,
    NavigationOutcome,
    ViewInputAdapter,
    ViewInputOutcome,
)
from .view_page_support import EVENT_TIMEOUT_SECONDS, SyntheticSite, until, view_browser

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE: Final[str] = Settings.external_constants().aeat.domains.sede
_SHIFT: Final[int] = 8
_CONTROL: Final[int] = 2

# Button, text field and form field at fixed positions of a 400 x 300 page.
_BUTTON: Final[tuple[int, int]] = (70, 40)
_FIELD: Final[tuple[int, int]] = (120, 112)
_FORM_FIELD: Final[tuple[int, int]] = (120, 172)
_FORM_PAGE: Final[str] = """
<body style="margin:0">
<button id="b" style="position:absolute;left:20px;top:20px;width:100px;height:40px">go</button>
<input id="i" style="position:absolute;left:20px;top:100px;width:200px;height:24px">
<form id="f"><input id="fi" name="q" style="position:absolute;left:20px;top:160px;width:200px;height:24px"></form>
<div style="position:absolute;top:0;left:0;width:1px;height:3000px"></div>
<script>
window.log = [];
for (const kind of ['mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu', 'mousemove'])
  document.addEventListener(kind, e => log.push([kind, e.clientX, e.clientY, e.button, e.buttons, e.detail]));
for (const kind of ['keydown', 'keyup', 'keypress'])
  document.addEventListener(kind, e => log.push([kind, e.key, e.code, e.ctrlKey, e.shiftKey]));
document.getElementById('f').addEventListener('submit', e => { e.preventDefault(); log.push(['submit']); });
</script>
</body>
"""
_DIALOG_BUTTON: Final[dict[str, tuple[int, int]]] = {"alert": (70, 40), "confirm": (190, 40), "prompt": (310, 40)}
_DIALOG_PAGE: Final[str] = """
<body style="margin:0">
<button id="a" style="position:absolute;left:20px;top:20px;width:100px;height:40px"
  onclick="alert(document.body.dataset.long ? 'x'.repeat(5000) : 'hola'); document.title = 'after-alert'">a</button>
<button id="c" style="position:absolute;left:140px;top:20px;width:100px;height:40px"
  onclick="document.title = 'confirm:' + confirm('seguro?')">c</button>
<button id="p" style="position:absolute;left:260px;top:20px;width:100px;height:40px"
  onclick="document.title = 'prompt:' + prompt('nombre?', 'dflt')">p</button>
<button id="u" style="position:absolute;left:20px;top:100px;width:100px;height:40px">u</button>
<script>window.onbeforeunload = e => { e.preventDefault(); e.returnValue = ''; };</script>
</body>
"""


class _Notices:
    """Collect the notices the adapter reports, as the lane to the window would."""

    def __init__(self) -> None:
        self.received: list[ViewNotice] = []

    def __call__(self, notice: ViewNotice) -> None:
        self.received.append(notice)


@asynccontextmanager
async def _adapter(
    page_html: str | None = None, *, on_notice: Callable[[ViewNotice], None] | None = None
) -> AsyncGenerator[tuple[ViewInputAdapter, BrowserContext, Page, _Notices]]:
    async with view_browser() as (context, page):
        if page_html is not None:
            await page.set_content(page_html)
        collected = _Notices()
        adapter = await ViewInputAdapter.attach(
            context, page, settings=Settings(), notices=on_notice if on_notice is not None else collected
        )
        # What the view context's page observer does for the owner.
        page.on("dialog", adapter.dialog_opened)
        try:
            yield adapter, context, page, collected
        finally:
            await adapter.close()


def _pointer(
    action: PointerAction,
    position: tuple[int, int],
    *,
    button: PointerButton = PointerButton.LEFT,
    click_count: int = 1,
    modifiers: int = 0,
) -> ViewInput:
    return ViewInput(
        event=PointerInput(
            action=action,
            x=position[0],
            y=position[1],
            button=button,
            click_count=0 if action is PointerAction.MOVE else click_count,
            modifiers=modifiers,
        )
    )


def _key(action: KeyAction, key: str, code: str = "", modifiers: int = 0) -> ViewInput:
    return ViewInput(event=KeyInput(action=action, key=key, code=code, modifiers=modifiers))


async def _click(
    adapter: ViewInputAdapter,
    position: tuple[int, int],
    *,
    button: PointerButton = PointerButton.LEFT,
    click_count: int = 1,
) -> ViewInputOutcome:
    pressed = await adapter.input(_pointer(PointerAction.DOWN, position, button=button, click_count=click_count))
    assert pressed is ViewInputOutcome.DISPATCHED
    return await asyncio.wait_for(
        adapter.input(_pointer(PointerAction.UP, position, button=button, click_count=click_count)),
        timeout=EVENT_TIMEOUT_SECONDS,
    )


async def _press(adapter: ViewInputAdapter, key: str, code: str = "", modifiers: int = 0) -> None:
    for action in (KeyAction.DOWN, KeyAction.UP):
        assert await adapter.input(_key(action, key, code, modifiers)) is ViewInputOutcome.DISPATCHED


async def _log(page: Page) -> list[list[object]]:
    return cast("list[list[object]]", await page.evaluate("window.log.splice(0)"))


async def _until_title(page: Page, title: str) -> None:
    async def poll() -> None:
        while await page.title() != title:
            await asyncio.sleep(0.02)

    await asyncio.wait_for(poll(), timeout=EVENT_TIMEOUT_SECONDS)


def _kinds(log: list[list[object]]) -> list[object]:
    return [entry[0] for entry in log]


@pytest.mark.asyncio
async def test_input_pointer_click_reaches_the_page_at_the_clicked_position() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        assert await _click(adapter, _BUTTON) is ViewInputOutcome.DISPATCHED
        log = await _log(page)

    assert [entry for entry in log if entry[0] in {"mousedown", "mouseup", "click"}] == [
        ["mousedown", 70, 40, 0, 1, 1],
        ["mouseup", 70, 40, 0, 0, 1],
        ["click", 70, 40, 0, 0, 1],
    ]


@pytest.mark.asyncio
async def test_input_double_click_and_secondary_button_reach_the_page() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _BUTTON)
        await _click(adapter, _BUTTON, click_count=2)
        double = await _log(page)
        await _click(adapter, _BUTTON, button=PointerButton.RIGHT)
        secondary = await _log(page)

    assert "dblclick" in _kinds(double)
    assert [entry[3] for entry in secondary if entry[0] == "contextmenu"] == [2]
    assert ["mousedown", 70, 40, 2, 2, 1] in secondary


@pytest.mark.asyncio
async def test_input_pointer_move_reports_the_buttons_held_during_a_drag() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        assert await adapter.input(_pointer(PointerAction.MOVE, (30, 30))) is ViewInputOutcome.DISPATCHED
        await adapter.input(_pointer(PointerAction.DOWN, (30, 30)))
        await adapter.input(_pointer(PointerAction.MOVE, (60, 50), button=PointerButton.NONE))
        await adapter.input(_pointer(PointerAction.UP, (60, 50)))
        await adapter.input(_pointer(PointerAction.MOVE, (80, 50)))
        log = await _log(page)

    moves = [entry for entry in log if entry[0] == "mousemove"]
    assert [(entry[1], entry[2], entry[4]) for entry in moves] == [(30, 30, 0), (60, 50, 1), (80, 50, 0)]


@pytest.mark.asyncio
async def test_input_clamps_a_coordinate_inside_the_contract_to_the_viewport() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        assert await adapter.input(_pointer(PointerAction.MOVE, (4000, 4000))) is ViewInputOutcome.DISPATCHED
        log = await _log(page)

    assert [entry[:3] for entry in log if entry[0] == "mousemove"] == [["mousemove", 399, 299]]


@pytest.mark.asyncio
async def test_input_wheel_scrolls_the_page() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        wheel = ViewInput(event=WheelInput(x=100, y=100, delta_x=0, delta_y=400, modifiers=0))
        assert await adapter.input(wheel) is ViewInputOutcome.DISPATCHED

        async def scrolled() -> None:
            while await page.evaluate("window.scrollY") == 0:
                await asyncio.sleep(0.02)

        await asyncio.wait_for(scrolled(), timeout=EVENT_TIMEOUT_SECONDS)


@pytest.mark.asyncio
async def test_input_text_is_inserted_at_the_focus() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        assert await adapter.input(ViewInput(event=TextInput(text="hola ñ €"))) is ViewInputOutcome.DISPATCHED
        value = await page.input_value("#i")

    assert value == "hola ñ €"


@pytest.mark.asyncio
async def test_input_key_events_raise_key_events_and_insert_no_text() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        await _log(page)
        await _press(adapter, "a", "KeyA")
        log = await _log(page)
        value = await page.input_value("#i")

    assert log == [["keydown", "a", "KeyA", False, False], ["keyup", "a", "KeyA", False, False]]
    assert value == ""


@pytest.mark.asyncio
async def test_input_backspace_and_select_all_edit_the_focused_field() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        await adapter.input(ViewInput(event=TextInput(text="abc")))
        await _press(adapter, "Backspace", "Backspace")
        after_backspace = await page.input_value("#i")
        await _press(adapter, "a", "KeyA", _CONTROL)
        await _press(adapter, "Backspace", "Backspace")
        after_select_all = await page.input_value("#i")

    assert after_backspace == "ab"
    assert after_select_all == ""


@pytest.mark.asyncio
async def test_input_enter_submits_a_form_and_tab_moves_the_focus() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        await _press(adapter, "Tab", "Tab")
        focused_after_tab = await page.evaluate("document.activeElement.id")
        await _press(adapter, "Tab", "Tab", _SHIFT)
        focused_after_shift_tab = await page.evaluate("document.activeElement.id")
        await _click(adapter, _FORM_FIELD)
        await _log(page)
        await _press(adapter, "Enter", "Enter")
        log = await _log(page)

    assert focused_after_tab == "fi"
    assert focused_after_shift_tab == "i"
    assert _kinds(log) == ["keydown", "keypress", "submit", "keyup"]


@pytest.mark.asyncio
async def test_input_modifiers_reach_the_page_with_the_key() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        await _log(page)
        await _press(adapter, "Enter", "Enter", _CONTROL)
        log = await _log(page)

    assert [entry for entry in log if entry[0] == "keydown"] == [["keydown", "Enter", "Enter", True, False]]
    assert "keypress" not in _kinds(log)


@pytest.mark.asyncio
async def test_input_has_no_rate_bound() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        outcomes = [await adapter.input(_pointer(PointerAction.MOVE, (index % 300, 200))) for index in range(200)]
        log = await _log(page)

    assert set(outcomes) == {ViewInputOutcome.DISPATCHED}
    assert len([entry for entry in log if entry[0] == "mousemove"]) == 200


def _unchecked(event: object) -> ViewInput:
    """Build a message the way a bypassed validator could, so only the adapter's own check can refuse it."""
    return ViewInput.model_construct(kind="view.input", event=event)


@pytest.mark.asyncio
async def test_input_refuses_values_outside_the_contract_and_sends_nothing() -> None:
    pointer = PointerInput(action=PointerAction.DOWN, x=10, y=10, button=PointerButton.LEFT, click_count=1, modifiers=0)
    key = KeyInput(action=KeyAction.DOWN, key="a", code="KeyA", modifiers=0)
    wheel = WheelInput(x=1, y=1, delta_x=0, delta_y=0, modifiers=0)
    refused = [
        _unchecked(pointer.model_copy(update={"x": -1})),
        _unchecked(pointer.model_copy(update={"x": 4096})),
        _unchecked(pointer.model_copy(update={"y": 1.5})),
        _unchecked(pointer.model_copy(update={"y": True})),
        _unchecked(pointer.model_copy(update={"modifiers": 16})),
        _unchecked(pointer.model_copy(update={"click_count": 4})),
        _unchecked(pointer.model_copy(update={"button": PointerButton.NONE})),
        _unchecked(pointer.model_copy(update={"action": PointerAction.MOVE})),
        _unchecked(wheel.model_copy(update={"delta_x": 10_001})),
        _unchecked(wheel.model_copy(update={"delta_y": -10_001})),
        _unchecked(TextInput.model_construct(type="text", text="x" * 257)),
        _unchecked(TextInput.model_construct(type="text", text="")),
        _unchecked(TextInput.model_construct(type="text", text="line\nbreak")),
        _unchecked(key.model_copy(update={"key": ""})),
        _unchecked(key.model_copy(update={"key": "a" * 33})),
        _unchecked(key.model_copy(update={"key": "a\x00"})),
        _unchecked(key.model_copy(update={"modifiers": 99})),
    ]
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        outcomes = [await adapter.input(message) for message in refused]
        log = await _log(page)

    assert outcomes == [ViewInputOutcome.REFUSED_OUT_OF_RANGE] * len(refused)
    assert all(outcome.refused for outcome in outcomes)
    assert log == []


@pytest.mark.asyncio
async def test_input_refuses_an_unknown_variant_and_sends_nothing() -> None:
    class _Unknown:
        pass

    unknown_event = ViewInput.model_construct(kind="view.input", event=_Unknown())
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        outcomes = [
            await adapter.input(unknown_event),
            await adapter.input(ViewInput.model_construct(kind="view.input", event=None)),
            await adapter.input(cast("ViewInput", _Unknown())),
        ]
        log = await _log(page)

    assert outcomes == [ViewInputOutcome.REFUSED_UNKNOWN_VARIANT] * 3
    assert log == []


@pytest.mark.asyncio
async def test_input_refuses_a_key_it_cannot_translate() -> None:
    keys = ["MediaPlayPause", "Dead", "Unidentified", "AudioVolumeUp", "Process", "ab"]
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        outcomes = [await adapter.input(_key(KeyAction.DOWN, key, "Unknown")) for key in keys]
        log = await _log(page)

    assert outcomes == [ViewInputOutcome.REFUSED_UNKNOWN_KEY] * len(keys)
    assert all(outcome.refused for outcome in outcomes)
    assert log == []


@pytest.mark.asyncio
async def test_input_translates_named_function_and_shifted_keys() -> None:
    async with _adapter(_FORM_PAGE) as (adapter, _context, page, _notices):
        await _click(adapter, _FIELD)
        await _log(page)
        for key, code, modifiers in (
            ("F5", "F5", 0),
            ("ArrowLeft", "ArrowLeft", 0),
            ("!", "Digit1", _SHIFT),
            ("ñ", "Semicolon", 0),
        ):
            await _press(adapter, key, code, modifiers)
        log = await _log(page)

    assert [entry[1] for entry in log if entry[0] == "keydown"] == ["F5", "ArrowLeft", "!", "ñ"]


@pytest.mark.asyncio
async def test_navigation_verbs_move_through_history_reload_and_home() -> None:
    site = SyntheticSite()
    first = site.page(f"{_SEDE}/first.html", "<title>first</title>")
    second = site.page(f"{_SEDE}/second.html", "<title>second</title>")
    home = site.page(f"{_SEDE}/", "<title>home</title>")
    async with _adapter() as (adapter, context, page, _notices):
        await site.apply(context)
        assert await adapter.navigation_availability() == NavigationAvailability(
            can_go_back=False, can_go_forward=False
        )
        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.BACK)) is NavigationOutcome.NO_HISTORY
        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.FORWARD)) is NavigationOutcome.NO_HISTORY

        await page.goto(first)
        await page.goto(second)
        assert await adapter.navigation_availability() == NavigationAvailability(can_go_back=True, can_go_forward=False)

        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.BACK)) is NavigationOutcome.NAVIGATED
        await until(lambda: page.url == first)
        assert await adapter.navigation_availability() == NavigationAvailability(can_go_back=True, can_go_forward=True)

        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.FORWARD)) is NavigationOutcome.NAVIGATED
        await until(lambda: page.url == second)

        reloads = site.requests_for(second)
        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.RELOAD)) is NavigationOutcome.NAVIGATED
        await until(lambda: site.requests_for(second) > reloads)

        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.HOME)) is NavigationOutcome.NAVIGATED
        await until(lambda: page.url == home)
    assert home == f"{_SEDE}/"


@pytest.mark.asyncio
async def test_navigation_reports_a_failed_navigation_and_an_unknown_verb() -> None:
    async with _adapter() as (adapter, context, page, _notices):

        async def refuse(route: Route) -> None:
            await route.abort()

        await context.route(f"{_SEDE}/**", refuse)
        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.HOME)) is NavigationOutcome.FAILED
        unknown = ViewNavigate.model_construct(kind="view.navigate", verb="https://example.com/")
        assert await adapter.navigate(unknown) is NavigationOutcome.REFUSED_UNKNOWN_VERB
        assert page.url == "about:blank"


@pytest.mark.asyncio
async def test_dialog_alert_reaches_the_window_and_the_answer_releases_the_page() -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        assert await _click(adapter, _DIALOG_BUTTON["alert"]) is ViewInputOutcome.DISPATCHED
        await until(lambda: len(notices.received) == 1)
        notice = notices.received[0]
        assert notice.code is ViewNoticeCode.DIALOG_OPENED
        assert notice.dialog is not None
        assert (notice.dialog.dialog_id, notice.dialog.dialog_kind) == (1, ViewDialogKind.ALERT)
        assert notice.dialog.message == "hola"
        assert notice.dialog.default_prompt is None

        answer = ViewDialog(dialog_id=1, accept=True)
        assert await adapter.answer_dialog(answer) is DialogOutcome.ANSWERED
        await _until_title(page, "after-alert")
        assert await adapter.answer_dialog(answer) is DialogOutcome.STALE


@pytest.mark.asyncio
@pytest.mark.parametrize(("accept", "expected"), [(True, "confirm:true"), (False, "confirm:false")])
async def test_dialog_confirm_returns_the_persons_choice_to_the_page(*, accept: bool, expected: str) -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        await _click(adapter, _DIALOG_BUTTON["confirm"])
        await until(lambda: len(notices.received) == 1)
        assert notices.received[0].dialog is not None
        assert notices.received[0].dialog.dialog_kind is ViewDialogKind.CONFIRM

        assert await adapter.answer_dialog(ViewDialog(dialog_id=1, accept=accept)) is DialogOutcome.ANSWERED
        await _until_title(page, expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (ViewDialog(dialog_id=1, accept=True, prompt_text="Ana"), "prompt:Ana"),
        (ViewDialog(dialog_id=1, accept=True), "prompt:dflt"),
        (ViewDialog(dialog_id=1, accept=False), "prompt:null"),
    ],
)
async def test_dialog_prompt_returns_the_typed_text_the_default_or_null(answer: ViewDialog, expected: str) -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        await _click(adapter, _DIALOG_BUTTON["prompt"])
        await until(lambda: len(notices.received) == 1)
        prompt = notices.received[0].dialog
        assert prompt is not None
        assert (prompt.dialog_kind, prompt.message, prompt.default_prompt) == (ViewDialogKind.PROMPT, "nombre?", "dflt")

        assert await adapter.answer_dialog(answer) is DialogOutcome.ANSWERED
        await _until_title(page, expected)


@pytest.mark.asyncio
async def test_dialog_blocks_input_and_navigation_until_answered_and_ids_increase() -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        await _click(adapter, _DIALOG_BUTTON["confirm"])
        await until(lambda: len(notices.received) == 1)

        assert await adapter.input(_pointer(PointerAction.MOVE, (5, 5))) is ViewInputOutcome.BLOCKED_BY_DIALOG
        assert not ViewInputOutcome.BLOCKED_BY_DIALOG.refused
        availability = await asyncio.wait_for(adapter.navigation_availability(), timeout=EVENT_TIMEOUT_SECONDS)
        assert availability == NavigationAvailability(can_go_back=False, can_go_forward=False)
        assert await adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.HOME)) is NavigationOutcome.AWAITING_DIALOG
        stale = ViewDialog(dialog_id=2, accept=True)
        assert await adapter.answer_dialog(stale) is DialogOutcome.STALE

        assert await adapter.answer_dialog(ViewDialog(dialog_id=1, accept=True)) is DialogOutcome.ANSWERED
        await _until_title(page, "confirm:true")
        assert await adapter.input(_pointer(PointerAction.MOVE, (5, 5))) is ViewInputOutcome.DISPATCHED

        await _click(adapter, _DIALOG_BUTTON["confirm"])
        await until(lambda: len(notices.received) == 2)
        second = notices.received[1].dialog
        assert second is not None
        assert second.dialog_id == 2
        await adapter.answer_dialog(ViewDialog(dialog_id=2, accept=False))


@pytest.mark.asyncio
async def test_dialog_message_is_cut_to_the_contract_bound() -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        await page.evaluate("document.body.dataset.long = '1'")
        await _click(adapter, _DIALOG_BUTTON["alert"])
        await until(lambda: len(notices.received) == 1)
        assert notices.received[0].dialog is not None
        assert notices.received[0].dialog.message == "x" * 2048
        await adapter.answer_dialog(ViewDialog(dialog_id=1, accept=True))


@pytest.mark.asyncio
async def test_dialog_is_dismissed_when_the_window_cannot_be_told() -> None:
    def failing(notice: ViewNotice) -> None:
        raise ConnectionResetError("lane closed")

    async with _adapter(_DIALOG_PAGE, on_notice=failing) as (adapter, _context, page, _notices):
        await _click(adapter, _DIALOG_BUTTON["confirm"])
        await _until_title(page, "confirm:false")
        assert await adapter.input(_pointer(PointerAction.MOVE, (5, 5))) is ViewInputOutcome.DISPATCHED


@pytest.mark.asyncio
async def test_dialog_left_open_is_dismissed_when_the_adapter_closes() -> None:
    async with _adapter(_DIALOG_PAGE) as (adapter, _context, page, notices):
        await _click(adapter, _DIALOG_BUTTON["confirm"])
        await until(lambda: len(notices.received) == 1)
        await adapter.close()
        await _until_title(page, "confirm:false")
        await adapter.close()


@pytest.mark.asyncio
async def test_dialog_leave_page_confirmation_holds_a_navigation_until_answered() -> None:
    site = SyntheticSite()
    home = site.page(f"{_SEDE}/", "<title>home</title>")
    async with _adapter(_DIALOG_PAGE) as (adapter, context, page, notices):
        await site.apply(context)
        # A leave-page confirmation only opens for a page the person has interacted with.
        await _click(adapter, (70, 120))
        outcome = await asyncio.wait_for(
            adapter.navigate(ViewNavigate(verb=ViewNavigateVerb.HOME)), timeout=EVENT_TIMEOUT_SECONDS
        )
        assert outcome is NavigationOutcome.AWAITING_DIALOG
        await until(lambda: len(notices.received) == 1)
        prompt = notices.received[0].dialog
        assert prompt is not None
        assert prompt.dialog_kind is ViewDialogKind.BEFOREUNLOAD

        assert await adapter.answer_dialog(ViewDialog(dialog_id=1, accept=True)) is DialogOutcome.ANSWERED
        await until(lambda: page.url == home)


@dataclass
class _ForwardingObserver:
    """The owner's page observer: it forwards a dialog to the adapter and keeps the pages it hears of."""

    pages: list[Page] = field(default_factory=list)
    adapter: ViewInputAdapter | None = None

    def page_opened(self, page: Page) -> None:
        self.pages.append(page)

    def popup_opened(self, popup: Page, opener: Page) -> None:
        del popup, opener

    def download_started(self, page: Page, download: Download) -> None:
        del page, download

    def file_chooser_opened(self, page: Page, file_chooser: FileChooser) -> None:
        del page, file_chooser

    def dialog_opened(self, page: Page, dialog: Dialog) -> None:
        del page
        assert self.adapter is not None
        self.adapter.dialog_opened(dialog)


@pytest.mark.asyncio
async def test_dialog_reaches_the_window_once_through_the_view_contexts_page_observer(tmp_path: Path) -> None:
    site = SyntheticSite()
    url = site.page(f"{_SEDE}/dialogs.html", _DIALOG_PAGE)
    settings = Settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_browser_headless=True,
        # A loopback port nothing listens on, so a request no route answers cannot leave the host.
        cadrumo_proxy_url="http://127.0.0.1:9",
    )
    record_shared_browser(settings)
    observer = _ForwardingObserver()
    notices = _Notices()
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, settings, Profile(name="sede-view-input"), evasion_strategy=site)
        try:
            context = await session.create_view_context(observer=observer)
            try:
                page = await context.new_page()
                await until(lambda: page in observer.pages)
                adapter = await ViewInputAdapter.attach(context, page, settings=settings, notices=notices)
                observer.adapter = adapter
                try:
                    await page.goto(url)
                    await _click(adapter, _DIALOG_BUTTON["confirm"])
                    await until(lambda: len(notices.received) == 1)
                    await asyncio.sleep(0.2)
                    assert len(notices.received) == 1
                    assert notices.received[0].dialog is not None
                    assert notices.received[0].dialog.dialog_kind is ViewDialogKind.CONFIRM

                    assert await adapter.answer_dialog(ViewDialog(dialog_id=1, accept=True)) is DialogOutcome.ANSWERED
                    await _until_title(page, "confirm:true")
                finally:
                    await adapter.close()
            finally:
                await context.close()
        finally:
            await session.close()
