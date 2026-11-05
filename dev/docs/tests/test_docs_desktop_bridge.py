"""Desktop documentation flavor: the frame bridge, driven for real.

The application talks to the documentation through
``docs/_static/cadrumo-desktop-bridge.js``. These gates build a fixture page
through the real ``docs/conf.py`` and drive the real bridge and the real
``cadrumo-docs.js`` in Chromium, with the page framed cross-origin by a
stand-in window that plays the application's part of the protocol.

* The bridge talks only to a parent window at a listed origin, takes a shell
  chord in the capture phase before any page listener (the palette's Ctrl+K
  listener included), routes off-origin links outside the frame, reports the
  context menu, theme and location, applies commands and zoom, ignores unknown
  types, refuses another version and malformed values, and never carries a
  field it does not define.
* The bridge announces the later features it serves, answers a bounded search
  with the page search controller's own ranked rows as plain-text excerpts on
  the documentation origin, navigates only within that origin, goes home to
  the page's language root, relays the page palette's key and trigger to the
  window, and applies a forced appearance the way the theme's toggle does.
  The search fixture is a real Pagefind index over the built page with
  injected term, casilla and command records.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..pagefind_index import build_search_index
from ..pagefind_inject import Materialised, inject_records
from ..terminology.search_record import ResultDisplayClass, SearchRecordKind
from ..terminology.unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    normalise_display_class_weight,
)
from .docs_desktop_support import (
    EXTERNAL_URL,
    SEARCH_TERM,
    SIDEBAR_EXTERNAL_URL,
    SIDEBAR_TERM,
    build_fixture_site,
)
from .http_serve_support import serve_directory

if TYPE_CHECKING:
    from pagefind.index import PagefindIndex

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_CHANNEL = "cadrumo-desktop"
_PALETTE_SHORTCUT = "palette.open"
_FEATURES = ["search", "navigate", "home", "appearance", "language"]

#: Every field each outbound message type may carry, envelope included.
_OUTBOUND_FIELDS = {
    "ready": {"url", "title", "lang", "theme", "features"},
    "location": {"url", "title"},
    "theme": {"theme"},
    "language-change": {"language"},
    "shortcut": {"id"},
    "open-external": {"url"},
    "context-menu": {"x", "y", "selection", "link", "pointer"},
    "search-progress": {"id"},
    "search-results": {"id", "results"},
}

#: Every field one search result carries.
_RESULT_FIELDS = {"kind", "title", "url", "excerpt", "ranges", "crumb"}


# ── The bridge in a browser ────────────────────────────────────────────────


@dataclass(frozen=True)
class _Origins:
    docs: str
    shell_origin: str
    other: str


_SHELL_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>shell</title>
<style>html, body {{ margin: 0; padding: 0; }} iframe {{ position: absolute; left: 40px; top: 30px;
width: 900px; height: 640px; border: 0; }}</style></head>
<body>
<iframe id="docs" src="{docs_url}"></iframe>
<script>
  window.received = [];
  var frame = document.getElementById("docs");
  window.addEventListener("message", function (event) {{
    if (event.source !== frame.contentWindow || event.origin !== {docs_origin!r}) return;
    window.received.push(event.data);
  }});
  window.sendToDocs = function (message) {{
    frame.contentWindow.postMessage(message, {docs_origin!r});
  }};
</script>
</body></html>
"""

#: Served at another origin and framed by the shell, so the documentation it
#: frames in turn has a parent that is not the top window.
_RELAY_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>relay</title></head><body>
<iframe id="docs" src="{docs_url}"></iframe>
<script>
  window.received = [];
  window.addEventListener("message", function (event) {{ window.received.push(event.data); }});
</script>
</body></html>
"""

_NESTED_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>nested</title></head><body>
<iframe id="relay" src="{relay_url}"></iframe>
</body></html>
"""

_SIBLING_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>sibling</title></head><body>
<script>
  window.postToDocs = function (message) {{
    parent.document.getElementById("docs").contentWindow.postMessage(message, {docs_origin!r});
  }};
</script>
</body></html>
"""


def _search_records() -> Materialised:
    """One term, one casilla and one command card, each carrying the search token.

    Built as unified records with the display-class weights the injection seam
    ships, so the index holds the production record shape. Their targets are
    distinct anchors on the fixture page, because Pagefind keys a record by URL.
    """
    descriptions = {
        "concept": f"{SEARCH_TERM} names the term card. A second {SEARCH_TERM.upper()} keeps its case.",
        "casilla": f"{SEARCH_TERM} base imponible del ejercicio",
        "cli": f"{SEARCH_TERM} calculate the modelo",
    }
    concept = SearchRecord(
        id="concept:bridgetest",
        kind=SearchRecordKind.CONCEPT,
        tier=RankingTier.TERM,
        title="Bridge term",
        descriptions={OutputLanguage.ES: descriptions["concept"], OutputLanguage.EN: descriptions["concept"]},
        target="fixture.html#bridge-term",
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.DOC),
    )
    casilla = SearchRecord(
        id="casilla-record:bridgetest",
        kind=SearchRecordKind.CASILLA,
        tier=RankingTier.NAVIGATION,
        title="Modelo 200 · casilla 00562",
        descriptions={OutputLanguage.ES: descriptions["casilla"], OutputLanguage.EN: descriptions["casilla"]},
        target="fixture.html#bridge-casilla",
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CASILLA),
        metadata=SearchRecordMetadata(modelo="200", number="00562", segmento="DP200014"),
    )
    cli = SearchRecord(
        id="cli:bridgetest",
        kind=SearchRecordKind.CLI,
        tier=RankingTier.NAVIGATION,
        title="aeat app modelo calculate",
        descriptions={OutputLanguage.ES: descriptions["cli"], OutputLanguage.EN: descriptions["cli"]},
        target="fixture.html#bridge-cli",
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CLI),
        metadata=SearchRecordMetadata(command_path="aeat app modelo calculate"),
    )
    return Materialised(records=[concept, casilla, cli], concepts=1, casillas=1, cli_commands=1)


def _index_fixture_site(html: Path) -> None:
    """Write the real Pagefind index over the built page with the search records injected."""
    materialised = _search_records()

    async def inject(index: PagefindIndex) -> None:
        await inject_records(index, materialised, {})

    build_search_index(html, inject=inject)


@pytest.fixture(scope="module")
def bridge_site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Origins]:
    """Serve the desktop-flavor page, the stand-in shell, and the same stand-in pages at a third origin."""
    work = tmp_path_factory.mktemp("bridge-site")
    html, result = build_fixture_site(work / "build", CADRUMO_DOCS_FLAVOR="desktop")
    assert result.returncode == 0, result.stdout + result.stderr
    _index_fixture_site(html)
    shell_root = work / "shell"
    shell_root.mkdir()
    with ExitStack() as stack:
        _, docs_port = stack.enter_context(serve_directory(html))
        _, shell_port = stack.enter_context(serve_directory(shell_root))
        _, other_port = stack.enter_context(serve_directory(shell_root))
        origins = _Origins(
            docs=f"http://127.0.0.1:{docs_port}",
            shell_origin=f"http://127.0.0.1:{shell_port}",
            other=f"http://127.0.0.1:{other_port}",
        )
        docs_url = f"{origins.docs}/fixture.html"
        pages = {
            "shell.html": _SHELL_PAGE.format(docs_url=docs_url, docs_origin=origins.docs),
            "relay.html": _RELAY_PAGE.format(docs_url=docs_url),
            "nested.html": _NESTED_PAGE.format(relay_url=f"{origins.other}/relay.html"),
            "sibling.html": _SIBLING_PAGE.format(docs_origin=origins.docs),
        }
        for name, page in pages.items():
            (shell_root / name).write_text(page, encoding="utf-8")
        yield origins


@dataclass
class _Window:
    """One stand-in application window with the documentation framed inside it."""

    page: Any
    origins: _Origins
    console: list[str]

    @property
    def frame(self) -> Any:
        return next(frame for frame in self.page.frames if frame.url.startswith(self.origins.docs))

    def received(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = self.page.evaluate("window.received")
        for message in messages:
            assert message["channel"] == _CHANNEL and message["version"] == 1
            assert set(message) - {"channel", "version", "type"} == _OUTBOUND_FIELDS[message["type"]], message
            if message["type"] == "search-results":
                for result in message["results"]:
                    assert set(result) == _RESULT_FIELDS, result
        return messages

    def of_type(self, kind: str) -> list[dict[str, Any]]:
        return [message for message in self.received() if message["type"] == kind]

    def wait_for(self, kind: str, count: int = 1) -> list[dict[str, Any]]:
        self.page.wait_for_function(
            "([kind, count]) => window.received.filter((m) => m.type === kind).length >= count",
            arg=[kind, count],
        )
        return self.of_type(kind)

    def send(self, kind: str, version: int = 1, **fields: Any) -> None:
        self.page.evaluate(
            "(m) => window.sendToDocs(m)", {"channel": _CHANNEL, "version": version, "type": kind, **fields}
        )

    def settle(self) -> None:
        """Wait until every message sent so far has been handled by the bridge.

        Messages from one window to a frame are delivered in order, so a zoom
        sent last and observed applied proves the ones before it were handled.
        """
        self.send("zoom", factor=1.25)
        self.frame.wait_for_function("document.documentElement.style.zoom === '1.25'")

    def zoom(self) -> str:
        value = self.frame.evaluate("document.documentElement.style.zoom")
        assert isinstance(value, str)
        return value

    def palette_open(self) -> bool:
        value = self.frame.evaluate("document.querySelector('dialog.cadrumo-palette').open")
        assert isinstance(value, bool)
        return value

    def search_results(self, search_id: str) -> list[dict[str, Any]]:
        """Every ``search-results`` answer received for ``search_id``."""
        return [message for message in self.of_type("search-results") if message["id"] == search_id]

    def answer(self, search_id: str) -> list[dict[str, Any]]:
        """Wait for the one answer to ``search_id`` and return its results."""
        self.page.wait_for_function(
            "(id) => window.received.some((m) => m.type === 'search-results' && m.id === id)",
            arg=search_id,
        )
        (answer,) = self.search_results(search_id)
        results: list[dict[str, Any]] = answer["results"]
        return results


@pytest.fixture
def open_window(bridge_site: _Origins) -> Iterator[Callable[..., _Window]]:
    """Open a stand-in application window on one of the served shell origins."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context()
            # Nothing the page does may reach the network; an off-origin
            # navigation the bridge failed to stop is refused here and reported
            # by the test as a navigation, not fetched.
            context.route("https://**", lambda route: route.abort())

            def _open(origin: str, path: str = "shell.html") -> _Window:
                page = context.new_page()
                console: list[str] = []
                page.on("console", lambda message: console.append(message.text))
                page.goto(f"{origin}/{path}", wait_until="load")
                return _Window(page=page, origins=bridge_site, console=console)

            yield _open
        finally:
            browser.close()


def _bridge_logs(window: _Window) -> list[str]:
    return [line for line in window.console if line.startswith("cadrumo-desktop-bridge: ")]


def test_bridge_announces_the_page_to_its_parent(open_window: Callable[..., _Window], bridge_site: _Origins) -> None:
    """The first message names the page, its language and its theme."""
    window = open_window(bridge_site.shell_origin)
    (ready,) = window.wait_for("ready")
    assert ready["url"] == f"{bridge_site.docs}/fixture.html"
    assert ready["title"] == window.frame.title()
    assert ready["lang"] == "en"
    assert ready["theme"] == "auto"
    assert ready["features"] == _FEATURES


def test_bridge_stays_silent_unless_framed_by_the_top_window(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """Framed one level deeper, the page tells its parent nothing and takes no message from it."""
    window = open_window(bridge_site.shell_origin, "nested.html")
    relay = next(frame for frame in window.page.frames if frame.url.endswith("/relay.html"))
    window.frame.wait_for_load_state("load")
    relay.evaluate(
        "(m) => document.getElementById('docs').contentWindow.postMessage(m, '*')",
        {"channel": _CHANNEL, "version": 1, "type": "zoom", "factor": 1.5},
    )
    window.page.wait_for_timeout(500)
    assert relay.evaluate("window.received") == []
    assert window.zoom() == ""
    assert _bridge_logs(window) == [
        "cadrumo-desktop-bridge: inactive: the page is not framed directly by the top window",
    ]


def test_bridge_does_nothing_on_a_page_opened_directly(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A page that is not framed sends nothing and logs nothing, and its own palette still opens."""
    window = open_window(bridge_site.docs, "fixture.html")
    window.page.click("h1")
    window.page.keyboard.press("Control+k")
    assert window.page.evaluate("document.querySelector('dialog.cadrumo-palette').open")
    assert _bridge_logs(window) == []


def test_bridge_ignores_a_frame_that_is_not_its_parent(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A frame beside the docs, at the shell's origin or another, is not the parent; its message is dropped."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    for origin in (bridge_site.shell_origin, bridge_site.other):
        window.page.evaluate(
            """(url) => new Promise((resolve) => {
                const sibling = document.createElement("iframe");
                sibling.src = url;
                sibling.onload = resolve;
                document.body.appendChild(sibling);
            })""",
            f"{origin}/sibling.html",
        )
    same_origin, other_origin = (
        next(frame for frame in window.page.frames if frame.url == f"{origin}/sibling.html")
        for origin in (bridge_site.shell_origin, bridge_site.other)
    )
    envelope = {"channel": _CHANNEL, "version": 1}
    messages = [
        {**envelope, "type": "command", "name": "open-search"},
        {**envelope, "type": "command", "name": "navigate", "url": f"{bridge_site.docs}/search.html"},
        {**envelope, "type": "command", "name": "home"},
        {**envelope, "type": "appearance", "theme": "dark"},
        {**envelope, "type": "search", "id": "sibling", "query": SEARCH_TERM, "limit": 5},
    ]
    for message in messages:
        same_origin.evaluate("(m) => window.postToDocs(m)", message)
        # A frame at another origin cannot read the shell document; it reaches
        # the docs frame through the top window's frame list.
        other_origin.evaluate("(m) => window.top.frames[0].postMessage(m, '*')", message)
    window.settle()
    window.page.wait_for_timeout(500)
    assert not window.palette_open()
    assert window.frame.url == f"{bridge_site.docs}/fixture.html"
    assert window.frame.evaluate("document.body.dataset.theme") == "auto"
    assert [message["type"] for message in window.received()] == ["ready"]
    assert _bridge_logs(window) == []


def test_shell_chords_are_taken_before_any_page_listener(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A chord in the keymap reaches the shell and nothing in the page, the palette's Ctrl+K listener included."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    frame = window.frame
    frame.click("h1")

    frame.evaluate(
        """() => {
            window.reachedPage = [];
            const record = (e) => { if (e.code.startsWith("Key")) window.reachedPage.push(e.code); };
            document.addEventListener("keydown", record, true);
            document.addEventListener("keydown", record);
        }"""
    )
    window.send(
        "keymap",
        chords=[
            {"id": "open-search", "code": "KeyF", "ctrlKey": True, "shiftKey": True},
            {"id": "palette-chord", "code": "KeyK", "ctrlKey": True},
        ],
    )
    window.settle()
    frame.click("h1")
    window.page.keyboard.press("Control+Shift+F")
    window.page.keyboard.press("Control+k")
    window.page.keyboard.press("Shift+F")
    shortcuts = window.wait_for("shortcut", 2)
    assert [message["id"] for message in shortcuts] == ["open-search", "palette-chord"]
    assert not window.palette_open()
    # Only the key whose modifiers match no chord reaches the page, once per listener.
    assert frame.evaluate("window.reachedPage") == ["KeyF", "KeyF"]


def test_commands_open_the_palette_and_walk_history(open_window: Callable[..., _Window], bridge_site: _Origins) -> None:
    """``open-search`` opens the page's palette; ``back`` and ``forward`` move through the frame's history."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.send("command", name="open-search")
    window.frame.wait_for_function("document.querySelector('dialog.cadrumo-palette').open")
    assert window.frame.evaluate("document.activeElement.classList.contains('cadrumo-palette-input')")
    window.frame.evaluate("document.querySelector('dialog.cadrumo-palette').close()")

    window.frame.click("article p a[href='#second']")
    (location,) = window.wait_for("location")
    assert location["url"] == f"{bridge_site.docs}/fixture.html#second"
    window.send("command", name="back")
    locations = window.wait_for("location", 2)
    assert locations[-1]["url"] == f"{bridge_site.docs}/fixture.html"
    window.send("command", name="forward")
    locations = window.wait_for("location", 3)
    assert locations[-1]["url"] == f"{bridge_site.docs}/fixture.html#second"

    window.send("command", name="reload")
    window.settle()
    assert "cadrumo-desktop-bridge: refused message: unknown command" in _bridge_logs(window)


def test_zoom_applies_within_bounds_and_each_page_starts_unzoomed(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """Zoom sets CSS zoom on the root element; out-of-range factors are refused; a new page starts at 1."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.send("zoom", factor=1.5)
    window.frame.wait_for_function("document.documentElement.style.zoom === '1.5'")
    for factor in (2.5, 0.25, "1.5", None):
        window.send("zoom", factor=factor)
    window.send("zoom", factor=2.0)
    window.frame.wait_for_function("document.documentElement.style.zoom === '2'")
    assert _bridge_logs(window).count("cadrumo-desktop-bridge: refused message: zoom factor outside 0.5 to 2.0") == 4
    window.send("zoom", factor=0.5)
    window.frame.wait_for_function("document.documentElement.style.zoom === '0.5'")

    window.frame.evaluate("setTimeout(() => window.location.reload(), 0)")
    window.wait_for("ready", 2)
    assert window.zoom() == ""
    window.send("zoom", factor=1.5)
    window.frame.wait_for_function("document.documentElement.style.zoom === '1.5'")


def test_other_versions_are_refused_and_unknown_types_ignored(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A message of another version does nothing and is logged; an unknown type does nothing silently."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.send("command", version=2, name="open-search")
    window.send("future-feature", detail="x")
    window.send("keymap", chords="not-a-list")
    window.send("keymap", chords=[{"id": "x", "code": "KeyX", "ctrlKey": "yes"}])
    window.settle()
    assert not window.palette_open()
    assert _bridge_logs(window) == [
        "cadrumo-desktop-bridge: refused message: unsupported version",
        "cadrumo-desktop-bridge: refused message: keymap chords are not a bounded list",
        "cadrumo-desktop-bridge: refused message: keymap holds a malformed chord",
    ]
    assert [message["type"] for message in window.received()] == ["ready"]


def test_links_off_the_origin_open_outside_the_frame(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A left or middle click on an off-origin link is handed to the shell and the frame stays put."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    link = window.frame.locator(f"article a[href='{EXTERNAL_URL}']")
    link.click()
    link.click(button="middle")
    requests = window.wait_for("open-external", 2)
    assert [message["url"] for message in requests] == [EXTERNAL_URL, EXTERNAL_URL]
    window.settle()
    assert window.frame.url == f"{bridge_site.docs}/fixture.html"
    assert len(window.page.frames) == 2
    assert window.page.context.pages == [window.page]


def test_context_menu_reports_position_selection_and_link(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """The page's own menu is suppressed; the shell gets frame-viewport coordinates, the selection and the link."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    frame = window.frame
    frame.evaluate(
        """() => {
            window.menuPrevented = [];
            document.addEventListener("contextmenu", (e) => window.menuPrevented.push(e.defaultPrevented));
        }"""
    )
    frame_box = window.page.locator("#docs").bounding_box()
    assert frame_box is not None

    for factor in (1, 2):
        window.send("zoom", factor=factor)
        frame.wait_for_function(f"document.documentElement.style.zoom === '{'' if factor == 1 else factor}'")
        link = frame.locator(f"article a[href='{EXTERNAL_URL}']")
        link.scroll_into_view_if_needed()
        box = link.bounding_box()
        assert box is not None
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        before = len(window.of_type("context-menu"))
        window.page.mouse.click(x, y, button="right")
        menu = window.wait_for("context-menu", before + 1)[-1]
        assert abs(menu["x"] - (x - frame_box["x"])) <= 1
        assert abs(menu["y"] - (y - frame_box["y"])) <= 1
        assert menu["link"] == {"href": EXTERNAL_URL, "external": True}

    frame.evaluate(
        """() => {
            const long = document.createElement("p");
            long.id = "long";
            long.textContent = "a".repeat(70000);
            document.querySelector("article").appendChild(long);
            const range = document.createRange();
            range.selectNodeContents(long);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
        }"""
    )
    before = len(window.of_type("context-menu"))
    frame.locator("#long").click(button="right", position={"x": 5, "y": 5})
    menu = window.wait_for("context-menu", before + 1)[-1]
    assert menu["selection"] == "a" * 65536
    assert menu["link"] is None
    local = frame.locator("article p a[href='#second']")
    before = len(window.of_type("context-menu"))
    local.click(button="right")
    menu = window.wait_for("context-menu", before + 1)[-1]
    assert menu["link"] == {"href": f"{bridge_site.docs}/fixture.html#second", "external": False}
    assert frame.evaluate("window.menuPrevented") == [True, True, True, True]


def test_context_menu_says_whether_a_pointer_or_the_keyboard_opened_it(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A right-click reports ``pointer: true``; Shift+F10 and the menu key report ``pointer: false``."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    local = window.frame.locator("article p a[href='#second']")
    local.click(button="right")
    local.focus()
    window.page.keyboard.press("Shift+F10")
    window.page.keyboard.press("ContextMenu")
    local.click(button="right")
    menus = window.wait_for("context-menu", 4)
    assert [menu["pointer"] for menu in menus] == [True, False, False, True]
    assert all(menu["link"] == {"href": f"{bridge_site.docs}/fixture.html#second", "external": False} for menu in menus)


def test_theme_changes_are_reported(open_window: Callable[..., _Window], bridge_site: _Origins) -> None:
    """Furo's own theme toggle produces one ``theme`` message per change."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    toggle = window.frame.locator("button.theme-toggle >> visible=true").first
    toggle.click()
    first = window.wait_for("theme")[0]["theme"]
    toggle.click()
    second = window.wait_for("theme", 2)[1]["theme"]
    assert {first, second} <= {"light", "dark", "auto"}
    assert first != second
    assert second == window.frame.evaluate("document.body.dataset.theme")


def test_fields_outside_the_protocol_are_never_carried(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A stray field on an incoming message is not read back out, logged or forwarded."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    unexpected_field_value = "unexpected-protocol-field-0123456789abcdef"
    window.send("zoom", factor=1.5, token=unexpected_field_value)
    window.send(
        "keymap",
        chords=[{"id": "probe", "code": "KeyJ", "ctrlKey": True, "token": unexpected_field_value}],
        token=unexpected_field_value,
    )
    window.send("command", name="open-search", token=unexpected_field_value)
    window.frame.wait_for_function("document.querySelector('dialog.cadrumo-palette').open")
    window.frame.evaluate("document.querySelector('dialog.cadrumo-palette').close()")
    window.frame.click("h1")
    window.page.keyboard.press("Control+j")
    window.wait_for("shortcut")
    window.frame.locator(f"article a[href='{EXTERNAL_URL}']").click(button="right")
    window.wait_for("context-menu")
    window.send("search", id="probe", query=SEARCH_TERM, limit=3, token=unexpected_field_value)
    window.answer("probe")
    window.send("appearance", theme="dark", token=unexpected_field_value)
    window.wait_for("theme")
    window.send("command", name="navigate", url=unexpected_field_value, token=unexpected_field_value)
    window.send("zoom", version=2, factor=1.5, token=unexpected_field_value)
    window.settle()
    assert unexpected_field_value not in json.dumps(window.received())
    assert all(unexpected_field_value not in line for line in window.console)
    assert unexpected_field_value not in json.dumps(
        window.frame.evaluate("Object.fromEntries(Object.entries(window.localStorage))")
    )


# ── Search, navigation, palette relay and appearance ───────────────────────


def _palette_rows(window: _Window, query: str) -> list[dict[str, str]]:
    """The rows the page's own Ctrl+K palette paints for ``query``, without its full-text handoff row.

    The palette paints a query's whole answer at once, closing it with a
    handoff row that names the query, so that row means every row is in place.
    """
    window.page.click("h1")
    window.page.keyboard.press("Control+k")
    window.page.locator(".cadrumo-palette-input").fill(query)
    window.page.wait_for_selector(f".cadrumo-palette-list a[href$='search.html?q={query}']")
    rows = window.page.eval_on_selector_all(
        ".cadrumo-palette-item",
        """(items) => items.map((item) => ({
            kind: (Array.from(item.classList).find((c) => c.startsWith('cadrumo-palette-item--')) || '')
                .slice('cadrumo-palette-item--'.length),
            title: item.querySelector('.cadrumo-palette-item-title').textContent,
            url: item.querySelector('a').href,
            crumb: (item.querySelector('.cadrumo-palette-item-crumb') || {textContent: ''}).textContent,
        }))""",
    )
    assert isinstance(rows, list)
    return [row for row in rows if "search.html?q=" not in row["url"]]


def _ranges_name_the_term(result: dict[str, Any]) -> bool:
    excerpt = result["excerpt"]
    assert isinstance(excerpt, str)
    return all(excerpt[start:end].lower() == SEARCH_TERM for start, end in result["ranges"])


def test_search_answers_with_the_page_controller_ranking(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """Results are the palette's own ranked rows on this origin, cards above pages, as plain text with ranges."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.send("search", id="all", query=f"  {SEARCH_TERM}  ", limit=50)
    results = window.answer("all")

    page = f"{bridge_site.docs}/fixture.html"
    assert [(result["kind"], result["url"]) for result in results] == [
        ("concept", f"{page}#bridge-term"),
        ("casilla", f"{page}#bridge-casilla"),
        ("cli", f"{page}#bridge-cli"),
        ("page", page),
    ]
    concept, casilla, cli, full_text = results
    assert casilla["crumb"] == "Casilla · Modelo 200 · 00562 · DP200014"
    assert cli["crumb"] == "Command · aeat app modelo calculate"

    # A card shows its summary; its ranges are the term's occurrences, any case.
    summary = f"{SEARCH_TERM} names the term card. A second {SEARCH_TERM.upper()} keeps its case."
    second = summary.index(SEARCH_TERM.upper())
    assert concept["excerpt"] == summary
    assert concept["ranges"] == [[0, len(SEARCH_TERM)], [second, second + len(SEARCH_TERM)]]
    assert cli["ranges"] == [[0, len(SEARCH_TERM)]]
    # A page shows Pagefind's excerpt decoded to text, its <mark> runs as ranges.
    assert "a < b & c" in full_text["excerpt"]
    assert "<mark" not in full_text["excerpt"] and "&lt;" not in full_text["excerpt"]
    assert full_text["ranges"]
    assert all(_ranges_name_the_term(result) for result in results)

    # The same rows, in the same order, as the page's own palette paints them.
    palette = _palette_rows(open_window(bridge_site.docs, "fixture.html"), SEARCH_TERM)
    assert palette == [{key: result[key] for key in ("kind", "title", "url", "crumb")} for result in results]

    window.send("search", id="two", query=SEARCH_TERM, limit=2)
    assert window.answer("two") == results[:2]


def test_search_sends_only_results_on_the_documentation_origin(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A row the palette would show for a link off the documentation origin is never sent."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.send("search", id="sidebar", query=SIDEBAR_TERM, limit=50)
    results = window.answer("sidebar")
    palette = _palette_rows(open_window(bridge_site.docs, "fixture.html"), SIDEBAR_TERM)
    assert SIDEBAR_EXTERNAL_URL in [row["url"] for row in palette]
    on_origin = [row for row in palette if row["url"].startswith(f"{bridge_site.docs}/")]
    assert len(on_origin) < len(palette)
    assert [{key: result[key] for key in ("kind", "title", "url", "crumb")} for result in results] == on_origin
    assert all(result["url"].startswith(f"{bridge_site.docs}/") for result in results)


def test_search_refuses_unbounded_requests(open_window: Callable[..., _Window], bridge_site: _Origins) -> None:
    """An oversized or malformed query, limit or id is refused and never answered; the bounds themselves pass."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    refused: list[tuple[Any, Any, Any]] = [
        ("long-query", "q" * 257, 5),
        ("not-a-query", None, 5),
        ("zero", SEARCH_TERM, 0),
        ("over", SEARCH_TERM, 51),
        ("fraction", SEARCH_TERM, 2.5),
        ("text-limit", SEARCH_TERM, "5"),
        ("", SEARCH_TERM, 5),
        ("i" * 65, SEARCH_TERM, 5),
        (7, SEARCH_TERM, 5),
    ]
    for search_id, query, limit in refused:
        window.send("search", id=search_id, query=query, limit=limit)
    window.send("search", id="i" * 64, query="q" * 256, limit=50)
    window.send("search", id="blank", query="   ", limit=1)
    window.answer("i" * 64)
    assert window.answer("blank") == []
    window.settle()
    answered = {message["id"] for message in window.of_type("search-results")}
    assert answered == {"i" * 64, "blank"}
    query_refused = "cadrumo-desktop-bridge: refused message: search query is not a bounded string"
    limit_refused = "cadrumo-desktop-bridge: refused message: search limit outside 1 to 50"
    id_refused = "cadrumo-desktop-bridge: refused message: search id is not a bounded string"
    assert _bridge_logs(window) == [query_refused] * 2 + [limit_refused] * 4 + [id_refused] * 3


def test_search_keeps_one_request_per_id_and_eight_in_flight(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A second request under an id in flight, or a ninth in flight, is refused; each accepted id is answered once."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    ids = ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i"]
    # One script turn posts every request, so all of them reach the page while
    # the first is still loading the index.
    window.page.evaluate(
        """([ids, query]) => ids.forEach((id) => window.sendToDocs(
            {channel: "cadrumo-desktop", version: 1, type: "search", id, query, limit: 3}))""",
        [ids, SEARCH_TERM],
    )
    for search_id in "abcdefgh":
        assert window.answer(search_id)
    window.settle()
    window.page.wait_for_timeout(500)
    assert window.search_results("i") == []
    assert _bridge_logs(window) == [
        "cadrumo-desktop-bridge: refused message: a search with this id is in flight",
        "cadrumo-desktop-bridge: refused message: too many searches in flight",
    ]
    # Once answered, an id and the capacity are free again.
    window.send("search", id="a", query=SEARCH_TERM, limit=3)
    window.send("search", id="i", query=SEARCH_TERM, limit=3)
    window.answer("i")
    window.page.wait_for_function(
        "() => window.received.filter((m) => m.type === 'search-results' && m.id === 'a').length === 2"
    )


def test_navigate_stays_on_the_documentation_origin_and_home_finds_the_language_root(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """``navigate`` takes only an absolute documentation URL; ``home`` lands on the page's language root."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    page = f"{bridge_site.docs}/fixture.html"
    window.send("command", name="navigate", url=f"{page}#second")
    (location,) = window.wait_for("location")
    assert location["url"] == f"{page}#second"

    refused_urls: list[Any] = [
        f"{bridge_site.other}/sibling.html",
        f"{bridge_site.shell_origin}/shell.html",
        "javascript:alert(1)",
        "data:text/html,refused",
        "fixture.html",
        f"{page}?q={'x' * 4096}",
        None,
    ]
    for url in refused_urls:
        window.send("command", name="navigate", url=url)
    window.settle()
    assert window.frame.url == f"{page}#second"
    refusal = "cadrumo-desktop-bridge: refused message: navigate URL is not on the documentation origin"
    assert _bridge_logs(window) == [refusal] * len(refused_urls)

    # Home from a fragment of the root page loads the root itself.
    window.send("command", name="home")
    assert window.wait_for("ready", 2)[-1]["url"] == page

    window.send("command", name="navigate", url=f"{bridge_site.docs}/search.html")
    ready = window.wait_for("ready", 3)[-1]
    assert ready["url"] == f"{bridge_site.docs}/search.html"
    assert ready["features"] == _FEATURES
    window.send("command", name="home")
    assert window.wait_for("ready", 4)[-1]["url"] == page


def test_page_palette_key_and_search_trigger_open_the_window_palette(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """Ctrl or Cmd+K and the page's search triggers reach the window as ``palette.open``; its palette stays shut."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    frame = window.frame
    frame.evaluate(
        """() => {
            window.reachedPage = [];
            const record = (e) => window.reachedPage.push(e.type + ":" + (e.code || e.target.className));
            const recordK = (e) => { if (e.code === "KeyK") record(e); };
            document.addEventListener("keydown", recordK, true);
            document.addEventListener("keydown", recordK);
            document.querySelectorAll("[data-cadrumo-search]").forEach((t) => t.addEventListener("click", record));
        }"""
    )
    frame.click("h1")
    for chord in ("Control+k", "Meta+k", "Control+Shift+K"):
        window.page.keyboard.press(chord)
    frame.locator("button.cadrumo-header-search").click()
    # Furo folds the sidebar into a drawer at this frame width; the trigger
    # inside it receives the same click event a pointer would send.
    frame.locator("button.cadrumo-search-trigger").evaluate("(trigger) => trigger.click()")
    shortcuts = window.wait_for("shortcut", 5)
    assert [message["id"] for message in shortcuts] == [_PALETTE_SHORTCUT] * 5
    window.settle()
    assert not window.palette_open()
    assert frame.evaluate("window.reachedPage") == []
    assert window.frame.url == f"{bridge_site.docs}/fixture.html"


def test_appearance_applies_like_the_theme_toggle_and_is_echoed(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A forced theme lands where Furo's toggle puts it, is reported once, persists, and ``auto`` returns the toggle."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    frame = window.frame

    def applied() -> list[str]:
        theme, stored = frame.evaluate("[document.body.dataset.theme, window.localStorage.getItem('theme')]")
        assert isinstance(theme, str) and isinstance(stored, str)
        return [theme, stored]

    for count, theme in enumerate(("light", "dark", "dark", "auto"), start=1):
        window.send("appearance", theme=theme)
        reports = window.wait_for("theme", count)
        assert reports[-1]["theme"] == theme
        assert applied() == [theme, theme]
    malformed: list[Any] = ["sepia", "", None, 1]
    for theme in malformed:
        window.send("appearance", theme=theme)
    window.settle()
    assert len(window.of_type("theme")) == 4
    assert applied() == ["auto", "auto"]
    refusal = "cadrumo-desktop-bridge: refused message: appearance theme is not auto, light or dark"
    assert _bridge_logs(window) == [refusal] * len(malformed)

    # After "auto" the page's own toggle chooses again.
    frame.locator("button.theme-toggle >> visible=true").first.click()
    toggled = window.wait_for("theme", 5)[-1]["theme"]
    assert toggled != "auto"
    assert applied() == [toggled, toggled]

    # A forced theme holds across page loads, as the toggle's own choice does.
    window.send("appearance", theme="light" if toggled == "dark" else "dark")
    forced = window.wait_for("theme", 6)[-1]["theme"]
    frame.evaluate("setTimeout(() => window.location.reload(), 0)")
    assert window.wait_for("ready", 2)[-1]["theme"] == forced


def test_language_switch_waits_for_host_and_preserves_fragment(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A docs choice proposes a language; only the host response navigates."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    window.frame.evaluate("""() => {
      location.hash = 'bridge-term';
      document.querySelectorAll('a.cadrumo-header-lang-item[lang="es"]').forEach((link) => link.remove());
      const link = document.createElement('a');
      link.className = 'cadrumo-header-lang-item';
      link.lang = 'es';
      link.href = 'fixture.html?language=es';
      link.textContent = 'Spanish';
      document.body.append(link);
    }""")
    before = window.frame.url
    window.frame.locator('a.cadrumo-header-lang-item[href="fixture.html?language=es"]').click()
    (choice,) = window.wait_for("language-change")
    assert choice["language"] == "es"
    assert window.frame.url == before
    window.send("language", language="es", entry=f"{bridge_site.docs}/fixture.html")
    window.frame.wait_for_url(f"{bridge_site.docs}/fixture.html?language=es#bridge-term")


def test_language_rejects_external_fallback(open_window: Callable[..., _Window], bridge_site: _Origins) -> None:
    """A language instruction cannot send documentation off its origin."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    # Remove generated switcher links so the command exercises its fallback.
    window.frame.evaluate("document.querySelectorAll('a.cadrumo-header-lang-item').forEach((link) => link.remove())")
    before = window.frame.url
    window.send("language", language="es", entry="https://example.org/")
    window.settle()
    assert window.frame.url == before
    assert "cadrumo-desktop-bridge: refused message: language has no documentation target" in _bridge_logs(window)
