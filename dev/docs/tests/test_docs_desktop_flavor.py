"""Desktop documentation flavor: the built page and its frame bridge, for real.

The desktop application shows the documentation in a frame on its own origin,
under a policy that admits nothing from the network, and talks to it through
``docs/_static/cadrumo-desktop-bridge.js``. These gates build a fixture page
through the real ``docs/conf.py`` in both flavors and drive the real bridge and
the real ``cadrumo-docs.js`` in Chromium, with the page framed cross-origin by a
stand-in window that plays the application's part of the protocol.

* The desktop page references nothing remote, loads the bridge before
  ``cadrumo-docs.js``, and names the application's window origins; the web page
  keeps exactly the scripts it shipped before the flavor existed.
* The bridge talks only to a parent window at a listed origin, takes a shell
  chord in the capture phase before any page listener (the palette's Ctrl+K
  listener included), routes off-origin links outside the frame, reports the
  context menu, theme and location, applies commands and zoom, ignores unknown
  types, refuses another version and malformed values, and never carries a
  field it does not define.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command

from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]

_DOCS = REPO_ROOT / "docs"
_SUBPROCESS_TIMEOUT_S = 1200
_CHANNEL = "cadrumo-desktop"
_EXTERNAL_URL = "https://example.org/"

_FIXTURE_PAGE = f"""# Fixture

Body with an [external link]({_EXTERNAL_URL}) and a [local link](#second).

## Second

Closing paragraph.
"""

#: The scripts the web flavor rendered on this page before the desktop flavor
#: existed, in order. The web flavor must keep shipping exactly these.
_WEB_SCRIPTS = [
    "_static/jquery.js",
    "_static/_sphinx_javascript_frameworks_compat.js",
    "_static/documentation_options.js",
    "_static/doctools.js",
    "_static/sphinx_highlight.js",
    "_static/scripts/furo.js",
    "_static/clipboard.min.js",
    "_static/copybutton.js",
    "_static/js/hoverxref.js",
    "_static/js/tooltipster.bundle.min.js",
    "_static/js/micromodal.min.js",
    "_static/design-tabs.js",
    "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
    "_static/cadrumo-docs.js",
]

#: Every field each outbound message type may carry, envelope included.
_OUTBOUND_FIELDS = {
    "ready": {"url", "title", "lang", "theme"},
    "location": {"url", "title"},
    "theme": {"theme"},
    "shortcut": {"id"},
    "open-external": {"url"},
    "context-menu": {"x", "y", "selection", "link"},
}


def _build_fixture_site(work: Path, **env_overrides: str) -> tuple[Path, CommandResult]:
    """Build the fixture page through the real ``docs/conf.py``; return its HTML root and the run."""
    source = work / "docs"
    source.mkdir(parents=True)
    shutil.copy2(_DOCS / "conf.py", source / "conf.py")
    for name in ("_static", "_templates", "_inventories"):
        shutil.copytree(_DOCS / name, source / name)
    (source / "fixture.md").write_text(_FIXTURE_PAGE, encoding="utf-8")
    env = {
        key: value for key, value in os.environ.items() if key not in {"CADRUMO_DOCS_BASE_URL", "CADRUMO_DOCS_FLAVOR"}
    }
    env.update(
        {
            "CADRUMO_DOCS_PROJECT_ROOT": str(REPO_ROOT),
            "CADRUMO_DOCS_SCOPE": "user",
            "CADRUMO_DOCS_OFFLINE": "1",
            "CADRUMO_DOCS_ONLY": "fixture.md",
            "CADRUMO_DOCS_MASTER_DOC": "fixture",
            "CADRUMO_DOCS_SKIP_SEQUENCE_CHECK": "1",
            "CADRUMO_DOCS_SKIP_CLI_TREE": "1",
            "CADRUMO_DOCS_SKIP_CLI_REFERENCE": "1",
            "CADRUMO_LOCAL_STORAGE_ROOT": str(work / "state"),
            **env_overrides,
        }
    )
    html = work / "html"
    result = run_command(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-j",
            "1",
            "-q",
            str(source),
            str(html),
            str(source / "fixture.md"),
        ],
        cwd=REPO_ROOT,
        environment=env,
        timeout_seconds=_SUBPROCESS_TIMEOUT_S,
    )
    return html, result


def _built_page(work: Path, **env_overrides: str) -> str:
    html, result = _build_fixture_site(work, **env_overrides)
    assert result.returncode == 0, result.stdout + result.stderr
    return (html / "fixture.html").read_text(encoding="utf-8")


def _script_tags(page: str) -> list[dict[str, str]]:
    """Return every ``<script src=...>`` element's attributes, in document order."""
    from html.parser import HTMLParser

    tags: list[dict[str, str]] = []

    class _Collector(HTMLParser):
        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "script":
                values = {name: value or "" for name, value in attrs}
                if "src" in values:
                    tags.append(values)

    _Collector().feed(page)
    return tags


def _loaded_resource_urls(page: str) -> list[str]:
    """Return the URL of every element the browser fetches on load, excluding anchors."""
    from html.parser import HTMLParser

    urls: list[str] = []

    class _Collector(HTMLParser):
        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = {name: value or "" for name, value in attrs}
            if tag in {"script", "img", "iframe", "source", "audio", "video", "embed"} and values.get("src"):
                urls.append(values["src"])
            elif tag == "link" and values.get("href"):
                urls.append(values["href"])
            elif tag == "object" and values.get("data"):
                urls.append(values["data"])

    _Collector().feed(page)
    return urls


def _without_version(src: str) -> str:
    return src.split("?", 1)[0]


@pytest.fixture(scope="module")
def flavor_pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """The fixture page built once per flavor with the default configuration."""
    return {
        "web": _built_page(tmp_path_factory.mktemp("web-flavor")),
        "desktop": _built_page(tmp_path_factory.mktemp("desktop-flavor"), CADRUMO_DOCS_FLAVOR="desktop"),
    }


def test_desktop_page_loads_nothing_remote(flavor_pages: dict[str, str]) -> None:
    """No script, stylesheet, image or frame on the desktop page comes from the network."""
    urls = _loaded_resource_urls(flavor_pages["desktop"])
    assert urls, "the parser found no loaded resource at all; the check would pass vacuously"
    remote = [url for url in urls if url.lower().startswith(("http:", "https:", "//"))]
    assert remote == []
    sources = [_without_version(tag["src"]) for tag in _script_tags(flavor_pages["desktop"])]
    assert "_static/js/hoverxref.js" not in sources
    assert "_static/jquery.js" not in sources


def test_desktop_page_loads_the_bridge_before_the_page_script(flavor_pages: dict[str, str]) -> None:
    """The bridge is a plain classic script ahead of ``cadrumo-docs.js`` and names no origin itself."""
    tags = _script_tags(flavor_pages["desktop"])
    sources = [_without_version(tag["src"]) for tag in tags]
    bridge = sources.index("_static/cadrumo-desktop-bridge.js")
    assert bridge < sources.index("_static/cadrumo-docs.js")
    assert set(tags[bridge]) == {"src"}


def test_web_page_keeps_its_scripts(flavor_pages: dict[str, str]) -> None:
    """The published flavor still ships the scripts it did before, and no bridge."""
    sources = [_without_version(tag["src"]) for tag in _script_tags(flavor_pages["web"])]
    assert sources == _WEB_SCRIPTS


def test_configuration_refuses_an_unknown_flavor(tmp_path: Path) -> None:
    """``docs/conf.py`` fails the build rather than guess a flavor."""
    _, result = _build_fixture_site(tmp_path, CADRUMO_DOCS_FLAVOR="mobile")
    assert result.returncode != 0
    assert "CADRUMO_DOCS_FLAVOR must be 'web' or 'desktop'" in result.stdout + result.stderr


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


@pytest.fixture(scope="module")
def bridge_site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Origins]:
    """Serve the desktop-flavor page, the stand-in shell, and the same stand-in pages at a third origin."""
    work = tmp_path_factory.mktemp("bridge-site")
    html, result = _build_fixture_site(work / "build", CADRUMO_DOCS_FLAVOR="desktop")
    assert result.returncode == 0, result.stdout + result.stderr
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
    command = {"channel": _CHANNEL, "version": 1, "type": "command", "name": "open-search"}
    same_origin.evaluate("(m) => window.postToDocs(m)", command)
    # A frame at another origin cannot read the shell document; it reaches the
    # docs frame through the top window's frame list.
    other_origin.evaluate("(m) => window.top.frames[0].postMessage(m, '*')", command)
    window.settle()
    assert not window.palette_open()


def test_shell_chords_are_taken_before_any_page_listener(
    open_window: Callable[..., _Window], bridge_site: _Origins
) -> None:
    """A chord in the keymap reaches the shell and nothing in the page, the palette's Ctrl+K listener included."""
    window = open_window(bridge_site.shell_origin)
    window.wait_for("ready")
    frame = window.frame
    frame.click("h1")
    # Before any keymap the page's own Ctrl+K palette listener is live.
    window.page.keyboard.press("Control+k")
    assert window.palette_open()
    window.page.keyboard.press("Escape")
    assert not window.palette_open()

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
    link = window.frame.locator(f"article a[href='{_EXTERNAL_URL}']")
    link.click()
    link.click(button="middle")
    requests = window.wait_for("open-external", 2)
    assert [message["url"] for message in requests] == [_EXTERNAL_URL, _EXTERNAL_URL]
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
        link = frame.locator(f"article a[href='{_EXTERNAL_URL}']")
        link.scroll_into_view_if_needed()
        box = link.bounding_box()
        assert box is not None
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        before = len(window.of_type("context-menu"))
        window.page.mouse.click(x, y, button="right")
        menu = window.wait_for("context-menu", before + 1)[-1]
        assert abs(menu["x"] - (x - frame_box["x"])) <= 1
        assert abs(menu["y"] - (y - frame_box["y"])) <= 1
        assert menu["link"] == {"href": _EXTERNAL_URL, "external": True}

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
    window.frame.locator(f"article a[href='{_EXTERNAL_URL}']").click(button="right")
    window.wait_for("context-menu")
    window.send("zoom", version=2, factor=1.5, token=unexpected_field_value)
    window.settle()
    assert unexpected_field_value not in json.dumps(window.received())
    assert all(unexpected_field_value not in line for line in window.console)
