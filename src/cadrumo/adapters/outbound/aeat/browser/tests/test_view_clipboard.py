"""The explicit clipboard command reads a real page selection and guards cut."""

from __future__ import annotations

import pytest
from playwright.async_api import Browser

from cadrumo_client.contracts.view_stream import ViewClipboard, ViewClipboardAction, ViewClipboardCommit

from ..view_clipboard import ViewClipboardAdapter
from .view_page_support import view_browser

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter, pytest.mark.asyncio(loop_scope="module")]


async def test_document_selection_copy_and_stale_cut(chromium: Browser) -> None:
    async with view_browser(chromium) as (_context, page):
        await page.set_content('<p id="text">Hello world</p>')
        await page.evaluate("""() => { const r = document.createRange(); const t = document.querySelector('#text').firstChild;
          r.setStart(t, 0); r.setEnd(t, 5); getSelection().removeAllRanges(); getSelection().addRange(r); }""")
        adapter = ViewClipboardAdapter()
        try:
            copied = await adapter.select(page, ViewClipboard(request_id=1, action=ViewClipboardAction.COPY))
            assert copied.text == "Hello"
            assert await adapter.commit(ViewClipboardCommit(request_id=1, apply=True), page) is False
            cut = await adapter.select(page, ViewClipboard(request_id=2, action=ViewClipboardAction.CUT))
            assert cut.text is None  # Ordinary document text is not editable.
        finally:
            await adapter.close()


async def test_input_cut_requires_successful_write_and_same_selection(chromium: Browser) -> None:
    async with view_browser(chromium) as (_context, page):
        await page.set_content(
            '<input id="field" value="alpha beta"><input id="password" type="password" value="secret">'
        )
        field = page.locator("#field")
        await field.focus()
        await field.evaluate("e => e.setSelectionRange(0, 5)")
        adapter = ViewClipboardAdapter()

        def request(request_id: int) -> ViewClipboard:
            return ViewClipboard(request_id=request_id, action=ViewClipboardAction.CUT)

        try:
            assert (await adapter.select(page, request(1))).text == "alpha"
            assert await adapter.commit(ViewClipboardCommit(request_id=1, apply=False), page) is False
            assert await field.input_value() == "alpha beta"
            assert (await adapter.select(page, request(2))).text == "alpha"
            await field.evaluate("e => e.setSelectionRange(6, 10)")
            assert await adapter.commit(ViewClipboardCommit(request_id=2, apply=True), page) is False
            assert await field.input_value() == "alpha beta"
            await field.evaluate("e => e.setSelectionRange(0, 5)")
            assert (await adapter.select(page, request(3))).text == "alpha"
            assert await adapter.commit(ViewClipboardCommit(request_id=3, apply=True), None) is False
            assert await field.input_value() == "alpha beta"
            assert (await adapter.select(page, request(4))).text == "alpha"
            assert await adapter.commit(ViewClipboardCommit(request_id=4, apply=True), page) is True
            assert await field.input_value() == " beta"
            password = page.locator("#password")
            await password.focus()
            await password.evaluate("e => e.setSelectionRange(0, 6)")
            assert (
                await adapter.select(page, ViewClipboard(request_id=5, action=ViewClipboardAction.COPY))
            ).text is None
        finally:
            await adapter.close()


async def test_contenteditable_and_focused_subframe(chromium: Browser) -> None:
    async with view_browser(chromium) as (_context, page):
        await page.set_content('<div id="edit" contenteditable="true">first second</div><iframe id="child"></iframe>')
        adapter = ViewClipboardAdapter()
        try:
            await page.locator("#edit").focus()
            await page.evaluate("""() => { const t = document.querySelector('#edit').firstChild; const r = document.createRange();
              r.setStart(t, 0); r.setEnd(t, 5); getSelection().removeAllRanges(); getSelection().addRange(r); }""")
            assert (
                await adapter.select(page, ViewClipboard(request_id=1, action=ViewClipboardAction.CUT))
            ).text == "first"
            assert await adapter.commit(ViewClipboardCommit(request_id=1, apply=True), page) is True
            assert await page.locator("#edit").text_content() == " second"
            await page.locator("#child").evaluate(
                "e => e.contentDocument.body.innerHTML = '<textarea id=\"inside\">frame text</textarea>'"
            )
            frame = page.frame_locator("#child")
            inside = frame.locator("#inside")
            await inside.focus()
            await inside.evaluate("e => e.setSelectionRange(0, 5)")
            assert (
                await adapter.select(page, ViewClipboard(request_id=2, action=ViewClipboardAction.COPY))
            ).text == "frame"
            await page.evaluate("""() => { const t = document.querySelector('#edit').firstChild; const r = document.createRange();
              r.setStart(t, 1); r.setEnd(t, 7); getSelection().removeAllRanges(); getSelection().addRange(r); }""")
            await inside.focus()
            await inside.evaluate("e => e.setSelectionRange(0, 0)")
            assert (
                await adapter.select(page, ViewClipboard(request_id=3, action=ViewClipboardAction.COPY))
            ).text is None
        finally:
            await adapter.close()


async def test_cut_refuses_listener_cancellation_or_mutation(chromium: Browser) -> None:
    async with view_browser(chromium) as (_context, page):
        await page.set_content('<input id="field" value="alpha beta">')
        field = page.locator("#field")
        await field.focus()
        await field.evaluate("e => e.setSelectionRange(0, 5)")
        adapter = ViewClipboardAdapter()
        try:
            await field.evaluate(
                "e => e.addEventListener('beforeinput', event => event.preventDefault(), { once: true })"
            )
            assert (
                await adapter.select(page, ViewClipboard(request_id=1, action=ViewClipboardAction.CUT))
            ).text == "alpha"
            assert await adapter.commit(ViewClipboardCommit(request_id=1, apply=True), page) is False
            assert await field.input_value() == "alpha beta"
            await field.evaluate(
                "e => e.addEventListener('beforeinput', () => e.setSelectionRange(6, 10), { once: true })"
            )
            assert (
                await adapter.select(page, ViewClipboard(request_id=2, action=ViewClipboardAction.CUT))
            ).text == "alpha"
            assert await adapter.commit(ViewClipboardCommit(request_id=2, apply=True), page) is False
            assert await field.input_value() == "alpha beta"
        finally:
            await adapter.close()
