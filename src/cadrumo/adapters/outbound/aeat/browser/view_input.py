"""Person input, navigation and page dialogs for the Sede view's page.

:class:`ViewInputAdapter` is the only way the window's hands reach the view's
page. It opens a Playwright-owned CDP session on that page and translates the
closed ``view.input`` variants to ``Input.dispatchMouseEvent``,
``Input.dispatchKeyEvent`` and ``Input.insertText``; the toolbar verbs back,
forward, reload and home to Playwright navigations; and the page's own dialogs
to ``view.notice`` documents answered by ``view.dialog``. No script is evaluated
on the page and no URL is accepted from the window: ``home`` opens the
backend's ``aeat.domains.sede``.

Every event is validated against the contract's own models before it is sent,
so an out-of-range value, an oversized text or an unknown variant is refused
here as well as at the frame reader, and a coordinate inside the contract's
range is clamped to the page's current viewport. Use is not limited: no rate
bound, throttle or coalescing applies to the events that pass validation.

A page dialog blocks the page, and with it every CDP input or navigation that
waits for the page, including the click that opened the dialog. The owner hands
each dialog to :meth:`ViewInputAdapter.dialog_opened` from the view context's
page observer, and the adapter returns control to its caller as soon as a
dialog opens, so the caller can route the person's ``view.dialog`` answer;
while a dialog is open, input is not sent.

Key events carry no printable text. Printable text arrives as text input; a
key event only raises ``keydown`` and ``keyup`` in the page, apart from Enter,
which also raises the character a form submission needs.

Input, URLs, titles and dialog text are private taxpayer data and are never
logged. The only CDP methods this module names are the ones it sends:
``Input.dispatchMouseEvent``, ``Input.dispatchKeyEvent``, ``Input.insertText``
and ``Page.getNavigationHistory``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from cadrumo_client.contracts.view_stream import (
    VIEW_MAX_CSS_EXTENT,
    VIEW_MAX_DIALOG_MESSAGE_LENGTH,
    VIEW_MAX_PROMPT_TEXT_LENGTH,
    VIEW_MAX_SEQUENCE,
    KeyAction,
    KeyInput,
    PointerAction,
    PointerButton,
    PointerInput,
    TextInput,
    ViewDialog,
    ViewDialogKind,
    ViewDialogPrompt,
    ViewInput,
    ViewNavigate,
    ViewNavigateVerb,
    ViewNotice,
    ViewNoticeCode,
    WheelInput,
)

from .....core.config import Settings
from .....core.logging import get_logger
from .._playwright import BrowserContext, Page, PlaywrightError

if TYPE_CHECKING:
    from playwright.async_api import CDPSession, Dialog

logger = get_logger(__name__)

#: How long a navigation verb may take to commit before it is reported as failed.
_NAVIGATION_COMMIT_TIMEOUT_MS: Final[int] = 15_000

#: CDP modifier bits: Alt 1, Control 2, Meta 4, Shift 8.
_NON_SHIFT_MODIFIERS: Final[int] = 0b0111
_CONTROL_MODIFIER: Final[int] = 0b0010
_META_MODIFIER: Final[int] = 0b0100
_SELECT_ALL_CHORDS: Final[frozenset[int]] = frozenset({_CONTROL_MODIFIER, _META_MODIFIER})

_POINTER_TYPES: Final[Mapping[PointerAction, str]] = MappingProxyType(
    {
        PointerAction.DOWN: "mousePressed",
        PointerAction.UP: "mouseReleased",
        PointerAction.MOVE: "mouseMoved",
    }
)
#: CDP button name and its bit in the ``buttons`` mask, in the order a held button is reported.
_POINTER_BUTTONS: Final[Mapping[PointerButton, tuple[str, int]]] = MappingProxyType(
    {
        PointerButton.LEFT: ("left", 1),
        PointerButton.RIGHT: ("right", 2),
        PointerButton.MIDDLE: ("middle", 4),
    }
)

#: Windows virtual key codes of the named keys a key event may carry.
_NAMED_KEY_CODES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "Backspace": 8,
        "Tab": 9,
        "Enter": 13,
        "Shift": 16,
        "Control": 17,
        "Alt": 18,
        "Pause": 19,
        "CapsLock": 20,
        "Escape": 27,
        " ": 32,
        "PageUp": 33,
        "PageDown": 34,
        "End": 35,
        "Home": 36,
        "ArrowLeft": 37,
        "ArrowUp": 38,
        "ArrowRight": 39,
        "ArrowDown": 40,
        "PrintScreen": 44,
        "Insert": 45,
        "Delete": 46,
        "Meta": 91,
        "ContextMenu": 93,
        "NumLock": 144,
        "ScrollLock": 145,
        **{f"F{number}": 111 + number for number in range(1, 13)},
    }
)
#: Virtual key codes of the ASCII punctuation keys, by the character they produce unshifted.
_PUNCTUATION_KEY_CODES: Final[Mapping[str, int]] = MappingProxyType(
    {";": 186, "=": 187, ",": 188, "-": 189, ".": 190, "/": 191, "`": 192, "[": 219, "\\": 220, "]": 221, "'": 222}
)
#: The same keys by physical position, for a shifted or non-ASCII character on them.
_PUNCTUATION_CODE_KEY_CODES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "Semicolon": 186,
        "Equal": 187,
        "Comma": 188,
        "Minus": 189,
        "Period": 190,
        "Slash": 191,
        "Backquote": 192,
        "BracketLeft": 219,
        "Backslash": 220,
        "BracketRight": 221,
        "Quote": 222,
        "IntlBackslash": 226,
    }
)
_LETTER_CODE_PREFIX: Final[str] = "Key"
_DIGIT_CODE_PREFIX: Final[str] = "Digit"
_ENTER_TEXT: Final[str] = "\r"


class ViewInputOutcome(StrEnum):
    """What became of one ``view.input`` event."""

    DISPATCHED = "dispatched"
    """Sent to the page, or still in flight because the page opened a dialog meanwhile."""
    BLOCKED_BY_DIALOG = "blocked_by_dialog"
    """A page dialog is open and the page cannot take input; the event was not sent."""
    REFUSED_UNKNOWN_VARIANT = "refused_unknown_variant"
    """The event is not one of the closed input variants."""
    REFUSED_OUT_OF_RANGE = "refused_out_of_range"
    """A field is outside the contract's bounds, including an oversized text."""
    REFUSED_UNKNOWN_KEY = "refused_unknown_key"
    """The key is neither a supported named key nor a single character."""

    @property
    def refused(self) -> bool:
        """Whether the event broke the contract; the caller ends the view as a protocol violation."""
        return self.value.startswith("refused_")


class NavigationOutcome(StrEnum):
    """What became of one ``view.navigate`` verb."""

    NAVIGATED = "navigated"
    """The navigation committed."""
    NO_HISTORY = "no_history"
    """Back or forward has no history entry to go to."""
    AWAITING_DIALOG = "awaiting_dialog"
    """A page dialog, such as a leave-page confirmation, is open and holds the navigation."""
    FAILED = "failed"
    """The navigation was aborted, timed out or the page is gone."""
    REFUSED_UNKNOWN_VERB = "refused_unknown_verb"
    """The verb is not one of the closed navigation verbs."""


class DialogOutcome(StrEnum):
    """What became of one ``view.dialog`` answer."""

    ANSWERED = "answered"
    STALE = "stale"
    """No open dialog carries that id; nothing was answered."""


@dataclass(frozen=True, slots=True)
class NavigationAvailability:
    """Whether the page has history to go back or forward to, for the toolbar."""

    can_go_back: bool
    can_go_forward: bool


@dataclass(frozen=True, slots=True)
class NavigationEntry:
    """The page's current history entry, read without evaluating script in the page.

    ``url`` and ``title`` are private taxpayer data and stay in memory.
    """

    url: str
    title: str = field(repr=False)
    availability: NavigationAvailability


@dataclass(slots=True)
class _OpenDialog:
    prompt: ViewDialogPrompt
    dialog: Dialog


@dataclass(frozen=True, slots=True)
class _Completed[ValueT]:
    value: ValueT


class ViewInputAdapter:
    """Input, navigation and dialogs of one view page; build it with :meth:`attach`."""

    def __init__(
        self,
        *,
        page: Page,
        session: CDPSession,
        home_url: str,
        notices: Callable[[ViewNotice], None],
    ) -> None:
        """Hold the page and its CDP session; build it with :meth:`attach`."""
        self._page = page
        self._session = session
        self._home_url = home_url
        self._notices = notices
        self._held_buttons = 0
        self._open_dialog: _OpenDialog | None = None
        self._last_dialog_id = 0
        self._dialog_open = asyncio.Event()
        self._closed = False
        self._background: set[asyncio.Task[None]] = set()

    @classmethod
    async def attach(
        cls,
        context: BrowserContext,
        page: Page,
        *,
        settings: Settings,
        notices: Callable[[ViewNotice], None],
    ) -> Self:
        """Open the CDP session on ``page``.

        ``notices`` receives a ``dialog_opened`` notice for every dialog handed
        to :meth:`dialog_opened`; the caller forwards it to the window and
        routes the person's answer to :meth:`answer_dialog`. A ``notices`` that
        raises leaves the person no way to answer, so that dialog is dismissed
        instead.
        """
        home_url = settings.external_constants().aeat.domains.sede
        session = await context.new_cdp_session(page)
        return cls(page=page, session=session, home_url=home_url, notices=notices)

    async def input(self, message: ViewInput) -> ViewInputOutcome:
        """Send one input event to the page, clamped to its viewport.

        A refusal sends nothing. While a page dialog is open nothing is sent
        either, because the page cannot take input. Returns as soon as the page
        has taken the event, or has opened a dialog because of it. A page or
        browser that is gone raises :class:`PlaywrightError`.
        """
        event = _validated_event(message)
        if isinstance(event, ViewInputOutcome):
            return event
        if self._open_dialog is not None:
            return ViewInputOutcome.BLOCKED_BY_DIALOG
        width, height = self._viewport_extent()
        match event:
            case PointerInput():
                await self._dispatch_pointer(event, width, height)
            case WheelInput():
                await self._dispatch(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseWheel",
                        "x": min(event.x, width - 1),
                        "y": min(event.y, height - 1),
                        "deltaX": event.delta_x,
                        "deltaY": event.delta_y,
                        "modifiers": event.modifiers,
                    },
                )
            case KeyInput():
                parameters = _key_parameters(event)
                if parameters is None:
                    return ViewInputOutcome.REFUSED_UNKNOWN_KEY
                await self._dispatch("Input.dispatchKeyEvent", parameters)
            case TextInput():
                await self._dispatch("Input.insertText", {"text": event.text})
        return ViewInputOutcome.DISPATCHED

    async def navigate(self, message: ViewNavigate) -> NavigationOutcome:
        """Run one toolbar verb and return once it commits, fails or a dialog holds it.

        Back and forward report :attr:`NavigationOutcome.NO_HISTORY` when the
        page has no entry in that direction.
        """
        try:
            verb = ViewNavigateVerb(message.verb)
        except ValueError:
            return NavigationOutcome.REFUSED_UNKNOWN_VERB
        if self._open_dialog is not None:
            return NavigationOutcome.AWAITING_DIALOG
        try:
            if verb in {ViewNavigateVerb.BACK, ViewNavigateVerb.FORWARD}:
                availability = await self.navigation_availability()
                reachable = availability.can_go_back if verb is ViewNavigateVerb.BACK else availability.can_go_forward
                if not reachable:
                    return NavigationOutcome.NO_HISTORY
            completed = await self._finish_unless_dialog(self._navigation(verb))
        except PlaywrightError as exc:
            logger.info("aeat view navigation failed exc_type=%s", type(exc).__name__)
            return NavigationOutcome.FAILED
        return NavigationOutcome.NAVIGATED if completed is not None else NavigationOutcome.AWAITING_DIALOG

    async def navigation_availability(self) -> NavigationAvailability:
        """Read whether the page has history to go back or forward to."""
        history = await self._session.send("Page.getNavigationHistory")
        index = history.get("currentIndex")
        entries = history.get("entries")
        if not isinstance(index, int) or not isinstance(entries, list):
            return NavigationAvailability(can_go_back=False, can_go_forward=False)
        return NavigationAvailability(can_go_back=index > 0, can_go_forward=index < len(entries) - 1)

    async def current_entry(self) -> NavigationEntry | None:
        """Read the current history entry's URL and title and the history around it, or ``None``."""
        history = await self._session.send("Page.getNavigationHistory")
        index = history.get("currentIndex")
        entries = history.get("entries")
        if not isinstance(index, int) or not isinstance(entries, list) or not 0 <= index < len(entries):
            return None
        entry: object = entries[index]
        if not isinstance(entry, dict):
            return None
        url: object = entry.get("url")
        title: object = entry.get("title")
        if not isinstance(url, str):
            return None
        return NavigationEntry(
            url=url,
            title=title if isinstance(title, str) else "",
            availability=NavigationAvailability(can_go_back=index > 0, can_go_forward=index < len(entries) - 1),
        )

    async def answer_dialog(self, message: ViewDialog) -> DialogOutcome:
        """Accept or dismiss the open dialog the message names, with the person's answer text."""
        opened = self._open_dialog
        if opened is None or opened.prompt.dialog_id != message.dialog_id:
            return DialogOutcome.STALE
        self._open_dialog = None
        self._dialog_open.clear()
        try:
            if message.accept:
                # A prompt accepted without an answer returns its default text, as a browser's own field does.
                answer = None
                if opened.prompt.dialog_kind is ViewDialogKind.PROMPT:
                    answer = message.prompt_text if message.prompt_text is not None else opened.dialog.default_value
                await opened.dialog.accept(prompt_text=answer)
            else:
                await opened.dialog.dismiss()
        except PlaywrightError as exc:
            logger.info("aeat view dialog answer failed exc_type=%s", type(exc).__name__)
            return DialogOutcome.STALE
        return DialogOutcome.ANSWERED

    async def close(self) -> None:
        """Dismiss an open dialog, so the page is not left blocked, and release the CDP session."""
        if self._closed:
            return
        self._closed = True
        opened, self._open_dialog = self._open_dialog, None
        self._dialog_open.clear()
        if opened is not None:
            try:
                await opened.dialog.dismiss()
            except PlaywrightError as exc:
                logger.debug("aeat view dialog dismiss skipped exc_type=%s", type(exc).__name__)
        for task in tuple(self._background):
            task.cancel()
        await asyncio.gather(*self._background, return_exceptions=True)
        try:
            await self._session.detach()
        except PlaywrightError as exc:
            logger.debug("aeat view input detach skipped exc_type=%s", type(exc).__name__)

    def _viewport_extent(self) -> tuple[int, int]:
        size = self._page.viewport_size
        if size is None:
            return VIEW_MAX_CSS_EXTENT, VIEW_MAX_CSS_EXTENT
        return (
            min(max(size["width"], 1), VIEW_MAX_CSS_EXTENT),
            min(max(size["height"], 1), VIEW_MAX_CSS_EXTENT),
        )

    async def _dispatch_pointer(self, event: PointerInput, width: int, height: int) -> None:
        button = _POINTER_BUTTONS.get(event.button)
        if event.action is PointerAction.DOWN and button is not None:
            self._held_buttons |= button[1]
        elif event.action is PointerAction.UP and button is not None:
            self._held_buttons &= ~button[1]
        held = next((name for name, bit in _POINTER_BUTTONS.values() if self._held_buttons & bit), "none")
        named = button[0] if button is not None and event.action is not PointerAction.MOVE else held
        await self._dispatch(
            "Input.dispatchMouseEvent",
            {
                "type": _POINTER_TYPES[event.action],
                "x": min(event.x, width - 1),
                "y": min(event.y, height - 1),
                "button": named,
                "buttons": self._held_buttons,
                "clickCount": event.click_count,
                "modifiers": event.modifiers,
            },
        )

    async def _dispatch(self, method: str, parameters: Mapping[str, object]) -> None:
        await self._finish_unless_dialog(self._session.send(method, dict(parameters)))

    def _navigation(self, verb: ViewNavigateVerb) -> Awaitable[object]:
        match verb:
            case ViewNavigateVerb.BACK:
                return self._page.go_back(wait_until="commit", timeout=_NAVIGATION_COMMIT_TIMEOUT_MS)
            case ViewNavigateVerb.FORWARD:
                return self._page.go_forward(wait_until="commit", timeout=_NAVIGATION_COMMIT_TIMEOUT_MS)
            case ViewNavigateVerb.RELOAD:
                return self._page.reload(wait_until="commit", timeout=_NAVIGATION_COMMIT_TIMEOUT_MS)
            case ViewNavigateVerb.HOME:
                return self._page.goto(self._home_url, wait_until="commit", timeout=_NAVIGATION_COMMIT_TIMEOUT_MS)

    async def _finish_unless_dialog[ValueT](self, work: Awaitable[ValueT]) -> _Completed[ValueT] | None:
        """Await ``work``, or return ``None`` as soon as a page dialog opens.

        A dialog holds whatever waits for the page, so the work is left to
        finish in the background once the person answers.
        """
        task = asyncio.ensure_future(work)
        opened = asyncio.ensure_future(self._dialog_open.wait())
        try:
            await asyncio.wait({task, opened}, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            task.cancel()
            raise
        finally:
            opened.cancel()
        if task.done():
            return _Completed(task.result())
        self._keep(task)
        return None

    def dialog_opened(self, dialog: Dialog) -> None:
        """Take a dialog the view page opened and tell the window about it.

        The owner calls this from the view context's page observer, which
        listens for dialogs on every page of the context; the adapter does not
        listen itself, so a dialog is never handled twice. The dialog stays
        open, and the page waits, until :meth:`answer_dialog`. Only one dialog
        is open at a time; another is dismissed.
        """
        if self._closed or self._open_dialog is not None or self._last_dialog_id >= VIEW_MAX_SEQUENCE:
            self._dismiss_in_background(dialog)
            return
        try:
            kind = ViewDialogKind(dialog.type)
            prompt = ViewDialogPrompt(
                dialog_id=self._last_dialog_id + 1,
                dialog_kind=kind,
                message=dialog.message[:VIEW_MAX_DIALOG_MESSAGE_LENGTH],
                default_prompt=(
                    dialog.default_value[:VIEW_MAX_PROMPT_TEXT_LENGTH] if kind is ViewDialogKind.PROMPT else None
                ),
            )
        except ValueError as exc:
            logger.warning("aeat view dialog unsupported exc_type=%s", type(exc).__name__)
            self._dismiss_in_background(dialog)
            return
        self._last_dialog_id = prompt.dialog_id
        self._open_dialog = _OpenDialog(prompt=prompt, dialog=dialog)
        self._dialog_open.set()
        try:
            self._notices(ViewNotice(code=ViewNoticeCode.DIALOG_OPENED, dialog=prompt))
        except Exception as exc:
            logger.error("aeat view dialog notice failed exc_type=%s", type(exc).__name__)
            self._open_dialog = None
            self._dialog_open.clear()
            self._dismiss_in_background(dialog)

    def _dismiss_in_background(self, dialog: Dialog) -> None:
        self._keep(asyncio.get_running_loop().create_task(self._dismiss(dialog)))

    async def _dismiss(self, dialog: Dialog) -> None:
        try:
            await dialog.dismiss()
        except PlaywrightError as exc:
            logger.debug("aeat view dialog dismiss skipped exc_type=%s", type(exc).__name__)

    def _keep(self, task: Awaitable[object]) -> None:
        """Hold ``task`` until it ends, and report a failure by its type alone."""
        background = asyncio.ensure_future(_settle(task))
        self._background.add(background)
        background.add_done_callback(self._background.discard)


async def _settle(work: Awaitable[object]) -> None:
    try:
        await work
    except PlaywrightError as exc:
        logger.debug("aeat view page work ended exc_type=%s", type(exc).__name__)
    except Exception as exc:
        logger.error("aeat view page work failed exc_type=%s", type(exc).__name__)


def _validated_event(
    message: ViewInput,
) -> PointerInput | WheelInput | KeyInput | TextInput | ViewInputOutcome:
    """Return the event re-validated against the contract, or the outcome that refuses it."""
    if not isinstance(message, ViewInput):
        return ViewInputOutcome.REFUSED_UNKNOWN_VARIANT
    event: object = message.event
    if not isinstance(event, PointerInput | WheelInput | KeyInput | TextInput):
        return ViewInputOutcome.REFUSED_UNKNOWN_VARIANT
    try:
        checked = ViewInput.model_validate(message.model_dump(warnings=False))
    except (ValidationError, PydanticSerializationError):
        return ViewInputOutcome.REFUSED_OUT_OF_RANGE
    return checked.event


def _key_parameters(event: KeyInput) -> dict[str, object] | None:
    """Translate a key event to CDP parameters, or ``None`` for a key this adapter does not know."""
    virtual_key = _virtual_key_code(event.key, event.code)
    if virtual_key is None:
        return None
    text = _ENTER_TEXT if event.key == "Enter" and not event.modifiers & _NON_SHIFT_MODIFIERS else ""
    kind = "keyDown" if text else "rawKeyDown"
    if event.action is KeyAction.UP:
        kind = "keyUp"
    parameters: dict[str, object] = {
        "type": kind,
        "modifiers": event.modifiers,
        "key": event.key,
        "code": event.code,
        "windowsVirtualKeyCode": virtual_key,
        "nativeVirtualKeyCode": virtual_key,
    }
    if text and event.action is KeyAction.DOWN:
        parameters["text"] = text
        parameters["unmodifiedText"] = text
    if _is_select_all(event):
        # Synthetic key events bypass the platform keymap, so a platform whose
        # select-all chord is not Control+A needs the editing command named.
        parameters["commands"] = ["selectAll"]
    return parameters


def _is_select_all(event: KeyInput) -> bool:
    return event.action is KeyAction.DOWN and event.key.lower() == "a" and event.modifiers in _SELECT_ALL_CHORDS


def _virtual_key_code(key: str, code: str) -> int | None:
    """Return the Windows virtual key code of a key, ``0`` when unknown, ``None`` when unsupported."""
    named = _NAMED_KEY_CODES.get(key)
    if named is not None:
        return named
    if len(key) != 1:
        return None
    if key.isascii():
        if key.isalpha() or key.isdigit():
            return ord(key.upper())
        punctuation = _PUNCTUATION_KEY_CODES.get(key)
        if punctuation is not None:
            return punctuation
    return _physical_key_code(code)


def _physical_key_code(code: str) -> int:
    letter = code.removeprefix(_LETTER_CODE_PREFIX)
    if letter != code and len(letter) == 1 and letter.isascii() and letter.isalpha():
        return ord(letter.upper())
    digit = code.removeprefix(_DIGIT_CODE_PREFIX)
    if digit != code and len(digit) == 1 and digit.isascii() and digit.isdigit():
        return ord(digit)
    return _PUNCTUATION_CODE_KEY_CODES.get(code, 0)
