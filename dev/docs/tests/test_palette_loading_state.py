"""Durable gate: the Ctrl-K palette reports an in-flight search honestly.

Pagefind resolves asynchronously -- a lazy index ``import()`` on first open,
then two sequential ``pf.search`` passes -- and ``render()`` deliberately keeps
the PREVIOUS results painted until the new query resolves (a fix for an eager
repaint that blanked the palette to the bare fallback and stuck there). Without
a busy signal, that combination is indistinguishable from a dead palette: the
reader types, nothing changes, and a working search reads as a broken one.

This drives the real shipped ``docs/_static/cadrumo-docs.js`` in a real browser
and locks the busy state machine:

* the signal RAISES while a search is in flight, and the stale rows stay
  painted underneath it (the keep-old-results behaviour is not regressed);
* it CLEARS once the query settles;
* it never raises at all on the degraded no-index path, which resolves
  synchronously to nav-only -- no spinner that outlives its search.

Determinism: the palette only shows the signal after ~120ms still-pending, so a
fast search must not flash one. Rather than race that threshold, the fixture
serves the real ``pagefind.js`` through a deliberately slow handler, making the
first search provably exceed it. The delay is a real network condition on the
real file -- no palette code is stubbed, and no assertion waits on a CSS
transition. The observable asserted is the ARIA contract (``aria-busy`` on the
listbox), read through a MutationObserver transcript so the state machine is
checked as a sequence rather than sampled and hoped for.

Scope/cost: reuses the ranking gate's glossary subset + concept injection and
drives one browser -- seconds, ``integration`` marked.
"""

from __future__ import annotations

import http.server
import socketserver
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records
from .test_palette_ranking import (
    _TRIGGER_PAGE,
    _approved_concept_records,
    _build_glossary_site,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

# Comfortably above the palette's 120ms show-delay, so the signal is guaranteed
# to raise on the first search rather than depending on machine speed.
_PAGEFIND_DELAY_S = 1.2

# Records every aria-busy value the listbox takes, from before the first
# keystroke. Asserting the resulting sequence checks the state machine instead
# of sampling it at one lucky instant.
_OBSERVE_BUSY = """
() => {
  const list = document.querySelector('.cadrumo-palette-list');
  window.__busyLog = [list.getAttribute('aria-busy')];
  new MutationObserver(() => {
    const v = list.getAttribute('aria-busy');
    if (v !== window.__busyLog[window.__busyLog.length - 1]) window.__busyLog.push(v);
  }).observe(list, { attributes: true, attributeFilter: ['aria-busy'] });
}
"""


class _SlowPagefindHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the real tree, but make the Pagefind module import slow."""

    def do_GET(self) -> None:  # http.server's casing
        if self.path.split("?")[0].endswith("/pagefind/pagefind.js"):
            time.sleep(_PAGEFIND_DELAY_S)
        super().do_GET()

    def log_message(self, *args: object) -> None:
        """Keep the test output clean."""


@contextmanager
def _serve(directory: Path, handler_cls: type) -> Iterator[tuple[socketserver.TCPServer, int]]:
    # Threading: the slow handler must delay only its own response, not stall
    # the page's other assets behind it.
    handler = partial(handler_cls, directory=str(directory))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _palette_site(out: Path, *, with_index: bool) -> Path:
    """Build the glossary subset + trigger page, optionally with a real index."""
    build = _build_glossary_site(out)
    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "palette.html").write_text(_TRIGGER_PAGE, encoding="utf-8")

    if with_index:
        (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
        materialised = _approved_concept_records()

        async def inject(index: object) -> None:
            await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

        build_search_index(build, inject=inject)
    return build


def test_palette_signals_in_flight_search_then_clears(tmp_path: Path) -> None:
    """Busy raises while Pagefind is in flight, stale rows stay, then it clears."""
    out = tmp_path / "site"
    out.mkdir()
    build = _palette_site(out, with_index=True)

    with _serve(build, _SlowPagefindHandler) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/palette.html", wait_until="networkidle")
            page.keyboard.press("Control+k")
            page.evaluate(_OBSERVE_BUSY)

            # Baseline: an idle palette is not busy.
            assert page.get_attribute(".cadrumo-palette-list", "aria-busy") == "false"

            page.locator(".cadrumo-palette-input").fill("iva")

            # The signal raises while the (slow) index import is in flight.
            page.wait_for_function(
                "document.querySelector('.cadrumo-palette-list').getAttribute('aria-busy') === 'true'",
                timeout=15000,
            )
            # ...and the previous results are STILL painted underneath it. The
            # palette must never blank to nothing while it works.
            rows_while_busy = page.locator(".cadrumo-palette-item").count()
            spinner_visible = page.evaluate("getComputedStyle(document.querySelector('.cadrumo-palette-spin')).opacity")

            # It clears once the query settles with real cards painted.
            page.wait_for_function(
                "document.querySelectorAll('.cadrumo-palette-item--concept').length > 0",
                timeout=20000,
            )
            page.wait_for_function(
                "document.querySelector('.cadrumo-palette-list').getAttribute('aria-busy') === 'false'",
                timeout=15000,
            )
            busy_log = page.evaluate("window.__busyLog")
            settled_status = page.inner_text(".cadrumo-palette-status")
            browser.close()

    assert rows_while_busy > 0, "palette blanked its rows while searching"
    assert spinner_visible == "1", f"spinner not shown while busy (opacity {spinner_visible})"
    # The state machine went idle -> busy -> idle exactly, with no residual
    # spinner and no flicker back into busy after settling.
    assert busy_log == ["false", "true", "false"], busy_log
    # The live region reports the settled outcome, not a stuck "Searching…".
    assert "result" in settled_status, f"unexpected status text {settled_status!r}"


def test_palette_never_busy_without_a_pagefind_index(tmp_path: Path) -> None:
    """The degraded nav-only path resolves without ever raising the signal."""
    out = tmp_path / "site"
    out.mkdir()
    # No index pass: the palette's `import()` 404s and it degrades to nav-only.
    build = _palette_site(out, with_index=False)

    with _serve(build, http.server.SimpleHTTPRequestHandler) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/palette.html", wait_until="networkidle")
            page.keyboard.press("Control+k")
            page.evaluate(_OBSERVE_BUSY)
            page.locator(".cadrumo-palette-input").fill("iva")

            # The full-text fallback row is the settled nav-only answer.
            page.wait_for_function(
                "document.querySelectorAll('.cadrumo-palette-item').length > 0",
                timeout=15000,
            )
            # Give any stray busy transition the chance to appear and be caught
            # by the observer; the assertion below is on the recorded log, so
            # this bounds the observation window rather than hoping for a pass.
            page.wait_for_timeout(600)
            busy_log = page.evaluate("window.__busyLog")
            final_busy = page.get_attribute(".cadrumo-palette-list", "aria-busy")
            browser.close()

    # A failed import resolves fast, so the 120ms delay means the reader never
    # sees a spinner at all -- and crucially it is not left spinning forever.
    assert final_busy == "false", "palette left busy on the degraded no-index path"
    assert busy_log == ["false"], f"degraded path flashed a busy state: {busy_log}"
