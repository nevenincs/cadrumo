"""Explicit plain-text copy and guarded cut for the streamed Sede page.

Only a fixed page script reads the focused selection. Its node references stay
in a Playwright handle until the desktop confirms a native clipboard write;
the script then checks that exact selection before deleting it. No page code
or frontend text is evaluated as a script.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cadrumo_client.contracts.view_stream import (
    VIEW_MAX_CLIPBOARD_BYTES,
    ViewClipboard,
    ViewClipboardAction,
    ViewClipboardCommit,
    ViewClipboardSelection,
)

from ..playwright import Page, PlaywrightError

if TYPE_CHECKING:
    from playwright.async_api import Frame, JSHandle

_CAPTURE = """() => {
  if (!document.hasFocus()) return { kind: 'none', text: '' };
  const active = document.activeElement;
  // A parent document can retain an old range while focus is in its child frame.
  if (active instanceof HTMLIFrameElement || active instanceof HTMLFrameElement)
    return { kind: 'none', text: '' };
  if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
    if (active instanceof HTMLInputElement && active.type === 'password')
      return { kind: 'password', text: '' };
    const start = active.selectionStart, end = active.selectionEnd;
    if (start === null || end === null || start >= end) return { kind: 'none', text: '' };
    return { kind: 'input', text: active.value.slice(start, end), element: active,
      start, end, value: active.value, cuttable: !active.readOnly && !active.disabled };
  }
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.rangeCount)
    return { kind: 'none', text: '' };
  const range = selection.getRangeAt(0);
  const parent = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
    ? range.commonAncestorContainer : range.commonAncestorContainer.parentElement;
  const root = parent?.closest('[contenteditable]');
  const cuttable = !!root && root.isContentEditable &&
    root.contains(selection.anchorNode) && root.contains(selection.focusNode) &&
    (active === root || root.contains(active));
  return { kind: 'range', text: selection.toString(), active, root, cuttable,
    anchor: selection.anchorNode, focus: selection.focusNode,
    anchorOffset: selection.anchorOffset, focusOffset: selection.focusOffset };
}"""

_DELETE = """(saved) => {
  if (!document.hasFocus() || !saved.cuttable || document.activeElement !== saved.active &&
      saved.kind !== 'input') return false;
  if (saved.kind === 'input') {
    const element = saved.element;
    const sameInput = () => element.isConnected && document.activeElement === element &&
        !(element instanceof HTMLInputElement && element.type === 'password') && !element.readOnly &&
        !element.disabled && element.value === saved.value &&
        element.selectionStart === saved.start && element.selectionEnd === saved.end &&
        element.value.slice(saved.start, saved.end) === saved.text;
    if (!sameInput()) return false;
    if (!element.dispatchEvent(new InputEvent('beforeinput', {
      bubbles: true, cancelable: true, inputType: 'deleteByCut' }))) return false;
    if (!sameInput()) return false;
    element.setRangeText('', saved.start, saved.end, 'start');
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteByCut' }));
    return true;
  }
  if (saved.kind !== 'range' || !saved.root?.isConnected || !saved.root.isContentEditable)
    return false;
  const selection = window.getSelection();
  const sameRange = () => document.hasFocus() && saved.root.isConnected && saved.root.isContentEditable &&
      document.activeElement === saved.active && selection && selection.rangeCount === 1 && !selection.isCollapsed &&
      selection.anchorNode === saved.anchor && selection.focusNode === saved.focus &&
      selection.anchorOffset === saved.anchorOffset && selection.focusOffset === saved.focusOffset &&
      selection.toString() === saved.text && saved.root.contains(selection.getRangeAt(0).commonAncestorContainer);
  if (!sameRange()) return false;
  const range = selection.getRangeAt(0);
  if (!saved.root.dispatchEvent(new InputEvent('beforeinput', {
        bubbles: true, cancelable: true, inputType: 'deleteByCut' }))) return false;
  if (!sameRange()) return false;
  range.deleteContents();
  selection.collapseToStart();
  saved.root.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteByCut' }));
  return true;
}"""


def _copyable_text(description: dict[str, object], request: ViewClipboard) -> str | None:
    """Return the selected text when this request may take it: never a password, nothing empty or oversized."""
    text = description.get("text")
    if (
        description.get("kind") == "password"
        or not isinstance(text, str)
        or not text
        or len(text.encode("utf-8")) > VIEW_MAX_CLIPBOARD_BYTES
        or (request.action is ViewClipboardAction.CUT and not description.get("cuttable"))
    ):
        return None
    return text


@dataclass(slots=True)
class _Pending:
    request_id: int
    page: Page = field(repr=False)
    handle: JSHandle = field(repr=False)


class ViewClipboardAdapter:
    """Hold one cut selection until the desktop acknowledges its clipboard write."""

    def __init__(self) -> None:
        """Start without a selected DOM handle."""
        self._pending: _Pending | None = None

    async def close(self) -> None:
        """Release the held selection when this view ends."""
        pending, self._pending = self._pending, None
        if pending is not None:
            with suppress(PlaywrightError):
                await pending.handle.dispose()

    async def select(self, page: Page | None, request: ViewClipboard) -> ViewClipboardSelection:
        """Read only the focused frame's current non-password selection."""
        await self.close()
        refused = ViewClipboardSelection(request_id=request.request_id)
        if page is None or page.is_closed():
            return refused
        for frame in reversed(page.frames):
            selection = await self._select_in_frame(frame, page, request)
            if selection is not None:
                return selection
        return refused

    async def _select_in_frame(self, frame: Frame, page: Page, request: ViewClipboard) -> ViewClipboardSelection | None:
        """Read one frame's selection; ``None`` means the frame holds none and the next may be asked."""
        refused = ViewClipboardSelection(request_id=request.request_id)
        handle: JSHandle | None = None
        try:
            handle = await frame.evaluate_handle(_CAPTURE)
            description = await handle.evaluate(
                "saved => ({ kind: saved.kind, text: saved.text, cuttable: saved.cuttable === true })"
            )
            if description.get("kind") == "none":
                await handle.dispose()
                return None
            text = _copyable_text(description, request)
            if text is None:
                await handle.dispose()
                return refused
            if request.action is ViewClipboardAction.CUT:
                self._pending = _Pending(request_id=request.request_id, page=page, handle=handle)
            else:
                await handle.dispose()
            return ViewClipboardSelection(request_id=request.request_id, text=text)
        except PlaywrightError:
            if handle is not None:
                with suppress(PlaywrightError):
                    await handle.dispose()
            return refused

    async def commit(self, answer: ViewClipboardCommit, page: Page | None) -> bool:
        """Delete only the same selection after a successful clipboard write."""
        pending, self._pending = self._pending, None
        if pending is None:
            return False
        try:
            if pending.request_id != answer.request_id or not answer.apply or pending.page is not page:
                return False
            return bool(await pending.handle.evaluate(_DELETE))
        except PlaywrightError:
            return False
        finally:
            with suppress(PlaywrightError):
                await pending.handle.dispose()
