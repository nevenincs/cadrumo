"""Rendered documentation surfaces: the identity page and the sequence widget.

Each gate builds a focused page in a ``tmp_path`` with ``CADRUMO_DOCS_OFFLINE``
set so intersphinx inventories are not fetched, then inspects the rendered site
and the widget assets it ships.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command
from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"


def _render_focused_index(tmp_path: Path, flavor: str) -> Path:
    """Build only the index page of one documentation flavor and return its output root."""
    docs_source = tmp_path / "docs-source"
    shutil.copytree(_DOCS, docs_source, ignore=shutil.ignore_patterns("_build", "api", "cli"))
    output = tmp_path / "html"
    env = {
        **os.environ,
        "CADRUMO_DOCS_OFFLINE": "1",
        "CADRUMO_DOCS_PROJECT_ROOT": str(_REPO_ROOT),
        "CADRUMO_DOCS_ONLY": "index.md",
        "CADRUMO_DOCS_MASTER_DOC": "index",
        "CADRUMO_DOCS_SINGLE_PAGE": "1",
        "CADRUMO_STORAGE_ROOT": str(tmp_path / "cadrumo-docs-state"),
        # This gate reads the RENDERED index page's identity marks only; the
        # cli-sequence golden check and the cli-tree projection are enforced by
        # their dedicated gates and are not part of this page's assertions.
        "CADRUMO_DOCS_SKIP_SEQUENCE_CHECK": "1",
        "CADRUMO_DOCS_SKIP_CLI_TREE": "1",
        "CADRUMO_DOCS_FLAVOR": flavor,
    }
    result = run_command(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-j",
            "1",
            str(docs_source),
            str(output),
            str(docs_source / "index.md"),
        ],
        cwd=_REPO_ROOT,
        environment=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def test_rendered_site_identity_and_static_marks_are_canonical(tmp_path: Path) -> None:
    """A real focused HTML build and shipped SVGs expose the canonical identity."""
    from bs4 import BeautifulSoup
    from defusedxml import ElementTree
    from PIL import Image

    output = _render_focused_index(tmp_path, "web")
    rendered = BeautifulSoup((output / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert rendered.title is not None
    assert rendered.title.get_text(strip=True) == "Cadrumo documentation - local Spanish tax preparation"
    site_name = rendered.find("meta", property="og:site_name")
    assert site_name is not None
    assert site_name.get("content") == "Cadrumo documentation"
    heading = rendered.find("h1")
    assert heading is not None
    assert heading.get_text(" ", strip=True).startswith("Cadrumo documentation")
    assert "Copyright © 2026, the Cadrumo authors" in rendered.get_text(" ", strip=True)
    assert "advice from a qualified professional" in rendered.get_text(" ", strip=True)
    assert rendered.find("link", rel="prefetch") is None

    namespace = "{http://www.w3.org/2000/svg}"
    for filename in ("cadrumo-mark-light.svg", "cadrumo-mark-dark.svg"):
        mark = ElementTree.parse(_DOCS / "_static" / filename).getroot()
        assert mark is not None
        assert mark.findtext(f"{namespace}title") == "Cadrumo documentation"
        assert mark.findtext(f"{namespace}desc", "").startswith("The Cadrumo mark")
        assert [element.text for element in mark.iter(f"{namespace}text")] == ["CADRUMO"]

    favicon = ElementTree.parse(_DOCS / "_static" / "cadrumo-favicon.svg").getroot()
    assert favicon is not None
    assert favicon.attrib["aria-label"] == "Cadrumo mark"

    # Every icon the web head links is shipped at the size it declares.
    icons = {
        (link.get("href"), " ".join(link.get_attribute_list("rel")), link.get("sizes"))
        for link in rendered.find_all("link", rel=["icon", "apple-touch-icon", "manifest"])
    }
    assert icons >= {
        ("_static/cadrumo-favicon.ico", "icon", "32x32"),
        ("_static/cadrumo-favicon.svg", "icon", None),
        ("_static/cadrumo-icon-square-180.png", "apple-touch-icon", None),
        ("_static/cadrumo.webmanifest", "manifest", None),
    }
    with Image.open(output / "_static" / "cadrumo-favicon.ico") as ico:
        assert ico.format == "ICO"
        assert ico.info["sizes"] == {(16, 16), (32, 32), (48, 48)}
    with Image.open(output / "_static" / "cadrumo-icon-square-180.png") as touch:
        assert touch.size == (180, 180)
    manifest = json.loads((output / "_static" / "cadrumo.webmanifest").read_text(encoding="utf-8"))
    for icon in manifest["icons"]:
        with Image.open(output / "_static" / icon["src"]) as image:
            assert f"{image.width}x{image.height}" == icon["sizes"]
    og_image = rendered.find("meta", property="og:image")
    assert og_image is not None
    og_content = og_image.get("content")
    assert isinstance(og_content, str), og_content
    assert og_content.endswith("_static/cadrumo-icon-square-512.png")


def test_desktop_flavor_links_only_icons_the_package_serves(tmp_path: Path) -> None:
    """The packaged copy's head names no favicon or manifest file the documentation scheme refuses."""
    from bs4 import BeautifulSoup

    from dev.packaging.native.docs_scan import scan_page, served_media_types
    from dev.packaging.native.layout import load_layout

    output = _render_focused_index(tmp_path, "desktop")
    page = (output / "index.html").read_text(encoding="utf-8")
    rendered = BeautifulSoup(page, "html.parser")
    icons = [link.get("href") for link in rendered.find_all("link", rel=["icon", "apple-touch-icon", "manifest"])]
    assert icons == ["_static/cadrumo-favicon.svg"]
    assert scan_page(page, served_media_types(load_layout()["user_docs"])).refused == []


# ---------------------------------------------------------------------------
# Progressive-enhancement sequence widget verification
#
# The stepped-player widget (docs/_static/cadrumo-docs.js) enhances the
# server-rendered `cli-sequence` transcript; the terminal styling lives in
# docs/_static/cadrumo-docs.css. These gates assert, with no mocks: the widget
# ships zero external requests, it is wired and implemented, and a real
# nitpicky (-n -W) Sphinx build of a sequence page renders a content-identical
# no-JS transcript, carries the enhanceable markup, and ships the widget
# assets.
# ---------------------------------------------------------------------------

_STATIC = _DOCS / "_static"
_WIDGET_JS = _STATIC / "cadrumo-docs.js"
_WIDGET_CSS = _STATIC / "cadrumo-docs.css"

#: A quote/paren-anchored protocol-relative or absolute URL in an asset — the
#: shape a CDN or external font reference would take. A bare ``//`` line comment
#: is deliberately excluded (it is not a URL).
_EXTERNAL_URL_RE = re.compile(r"""(?:url\(|["'(])\s*(?:https?:)?//""")

_SEQUENCE_ID = "modelo-303-demo"
_SEQUENCE_PAGE = "index"
_SEQUENCE_DIRECTIVE_BODY = (
    "@setup aeat app ledger import --file fixtures/x.csv\n"
    "aeat app modelo work calculate wu_demo\n"
    "@result aeat app modelo work verify wu_demo\n"
    '@expect result.status == "verified_complete"'
)


def _sequence_golden_json() -> str:
    """Return a schema-valid golden matching the fixture directive's three frames."""
    from ..sequences.golden_store import GoldenFrame, SequenceGolden
    from ..sequences.schema import FrameKind

    golden = SequenceGolden(
        sequence_id=_SEQUENCE_ID,
        frames=(
            GoldenFrame(
                kind=FrameKind.SETUP,
                argv=("aeat", "app", "ledger", "import", "--file", "fixtures/x.csv"),
                exit_code=0,
            ),
            GoldenFrame(
                kind=FrameKind.COMMAND,
                argv=("aeat", "app", "modelo", "work", "calculate", "wu_demo"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.calculate",
                    "status": "ok",
                    "notices": [],
                    "result": {"casillas_computed": 4},
                },
                envelope_source="stdout",
            ),
            GoldenFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "app", "modelo", "work", "verify", "wu_demo"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.verify",
                    "status": "ok",
                    "notices": [],
                    "result": {"status": "verified_complete"},
                },
                envelope_source="stdout",
            ),
        ),
    )
    return json.dumps(golden.model_dump(mode="json"), indent=2) + "\n"


def _write_sequence_site(root: Path, *, goldens_root: Path) -> None:
    """Write a minimal MyST site: one page with the directive, shipping the widget assets."""
    static = root / "_static"
    static.mkdir()
    shutil.copy2(_WIDGET_JS, static / _WIDGET_JS.name)
    shutil.copy2(_WIDGET_CSS, static / _WIDGET_CSS.name)
    conf = (
        'extensions = ["myst_parser"]\n'
        'myst_enable_extensions = ["colon_fence"]\n'
        "nitpicky = True\n"
        'html_static_path = ["_static"]\n'
        'html_css_files = ["cadrumo-docs.css"]\n'
        'html_js_files = ["cadrumo-docs.js"]\n'
        f"cadrumo_sequences_goldens_root = {str(goldens_root)!r}\n"
        "\n"
        "def setup(app):\n"
        "    from dev.docs.sequence_directive import register\n"
        "    register(app)\n"
    )
    (root / "conf.py").write_text(conf, encoding="utf-8")
    body = f"# Modelo 303\n\n```{{cli-sequence}} {_SEQUENCE_ID}\n:verify: Confirm the calculation is complete.\n```\n"
    (root / "index.md").write_text(body, encoding="utf-8")
    contract_dir = root / "_sequences" / "contracts" / _SEQUENCE_PAGE
    contract_dir.mkdir(parents=True)
    (contract_dir / f"{_SEQUENCE_ID}.seq").write_text(_SEQUENCE_DIRECTIVE_BODY + "\n", encoding="utf-8")


def _build_html(root: Path) -> tuple[str, Path, str]:
    """Build the site in an isolated subprocess under ``-n -W``."""
    out = root / "_out"
    result = run_command(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-n",
            "-W",
            "-j",
            "1",
            str(root),
            str(out),
        ],
        cwd=_REPO_ROOT,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    index = out / "index.html"
    html = index.read_text(encoding="utf-8") if index.is_file() else ""
    return html, out, combined


def test_sequence_widget_assets_make_no_external_requests() -> None:
    """The vendored widget JS and CSS carry zero external or CDN requests."""
    for asset in (_WIDGET_JS, _WIDGET_CSS):
        text = asset.read_text(encoding="utf-8")
        assert "http://" not in text, f"{asset.name} carries an http:// URL"
        assert "https://" not in text, f"{asset.name} carries an https:// URL"
        match = _EXTERNAL_URL_RE.search(text)
        assert match is None, (
            f"{asset.name} carries a non-relative URL near: {text[match.start() : match.start() + 40]!r}"
        )


def test_sequence_widget_is_wired_and_implemented() -> None:
    """conf.py ships both assets and the sources carry the playhead and hover-help surfaces."""
    conf = (_DOCS / "conf.py").read_text(encoding="utf-8")
    assert '"cadrumo-docs.css"' in conf
    assert '"cadrumo-docs.js"' in conf

    js = _WIDGET_JS.read_text(encoding="utf-8")
    for surface in ("initSequences", "setupSequence", "initHoverHelp", "cadrumo-sequence-payload", "cli-tree.json"):
        assert surface in js, f"widget JS is missing {surface!r}"
    # The playhead model: JS-applied state classes, not frame hiding.
    for surface in ('"is-active"', '"is-past"', '"is-future"'):
        assert surface in js, f"widget JS is missing the playhead state {surface}"
    # The operator redesign removed autonomous/timed advance entirely; no play
    # button, no timer, no reduced-motion autoplay branch may return.
    for banned in ("setInterval", "startPlay", "PLAY_INTERVAL_MS", "prefersReducedMotion", "frame.hidden"):
        assert banned not in js, f"widget JS must not carry the retired autoplay surface {banned!r}"
    # Per-frame output disclosure: outputs are individually toggleable, the
    # command line never is (the toggle governs only the output selector set).
    for surface in ('"cadrumo-output-toggle"', '"is-output-open"', "setOutputOpen"):
        assert surface in js, f"widget JS is missing the output-disclosure surface {surface}"
    assert ".cadrumo-frame-command" not in js.split("OUTPUT_SELECTOR =")[1].split(";")[0], (
        "the output disclosure must never govern the command line itself"
    )

    css = _WIDGET_CSS.read_text(encoding="utf-8")
    for surface in (
        ".cadrumo-sequence",
        ".cli-tok-placeholder",
        ".cadrumo-sequence-controls",
        ".cadrumo-cli-popover",
        ".cadrumo-frame.is-future",
        ".cadrumo-output-toggle",
        ":not(.is-output-open)",
        "--font-stack--monospace",
    ):
        assert surface in css, f"widget CSS is missing {surface!r}"
    # No terminal-chrome title bar (the removed top decorative rectangle).
    assert "cadrumo-sequence::before" not in css
    # No play-button styling remains.
    assert "cadrumo-sequence-btn--play" not in css
    assert "prefers-reduced-motion" in css


def test_sequence_widget_carries_shell_switcher_and_copy() -> None:
    """The widget ships the shell switcher and copy control (enhancement only), no autoplay.

    The switcher toggles the server-rendered per-shell command variants by setting
    ``data-cadrumo-shell`` on the sequence root; the copy control writes the frame's
    authored single-line command (``data-command-line``) with a clipboard-plus-
    ``execCommand`` fallback. Both are JS-created, so no-JS readers keep the full
    transcript. The retired autoplay surface must stay absent.
    """
    js = _WIDGET_JS.read_text(encoding="utf-8")
    for surface in (
        "setupShellSwitcher",
        "setupCopyButtons",
        "cadrumo-shell-switcher",
        "cadrumo-shell-btn",
        "data-cadrumo-shell",
        "cadrumo-cmd-variant",
        "cadrumo-copy-btn",
        "data-command-line",
        "writeClipboard",
        "execCommand",
        "is-copied",
        # The switcher now lives in a slim block header bar at the top.
        "cadrumo-sequence-bar",
    ):
        assert surface in js, f"widget JS is missing the shell/copy surface {surface!r}"
    # aria wiring for both controls (a segmented toggle and a labelled copy button).
    assert "aria-pressed" in js
    assert '"Copy command"' in js
    # The copy control's brief "Copied" state uses a one-shot timeout, never a
    # repeating timer — the no-autoplay invariant stays intact.
    assert "setInterval" not in js
    assert "setTimeout" in js
    # Setup frames never enter the reader payload, so the widget needs no setup filter.
    assert '!== "setup"' not in js

    css = _WIDGET_CSS.read_text(encoding="utf-8")
    for surface in (
        ".cadrumo-cmd-variant",
        "[data-cadrumo-shell=",
        ".cli-continuation",
        ".cadrumo-shell-switcher",
        ".cadrumo-shell-btn",
        ".cadrumo-copy-btn",
        ".cadrumo-copy-btn.is-copied",
        '[data-shell="pwsh"] pre code::before',
        # The top switcher bar and the per-step header row.
        ".cadrumo-sequence-bar",
        ".cadrumo-frame-header",
        ".cadrumo-frame-step",
        ".cadrumo-frame-desc",
    ):
        assert surface in css, f"widget CSS is missing the shell/copy surface {surface!r}"
    # Setup scaffolding has no reader-facing disclosure surface.
    assert "details.cadrumo-setup" not in css
    # The switcher and copy transitions join the reduced-motion opt-out.
    reduced = css.rsplit("prefers-reduced-motion", 1)[1]
    assert ".cadrumo-shell-btn" in reduced
    assert ".cadrumo-copy-btn" in reduced


from ._sequence_storage_fixtures import _isolated_sequence_storage

__all__ = ["_isolated_sequence_storage"]


def test_sequence_page_ships_widget_and_degrades_without_js(
    tmp_path: Path,
    _isolated_sequence_storage: None,
) -> None:
    """A real -n -W build renders the no-JS transcript, the enhanceable markup, and ships the assets."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    (goldens_root / _SEQUENCE_PAGE).mkdir(parents=True)
    (goldens_root / _SEQUENCE_PAGE / f"{_SEQUENCE_ID}.json").write_text(_sequence_golden_json(), encoding="utf-8")
    _write_sequence_site(site, goldens_root=goldens_root)

    html, out, warnings = _build_html(site)

    # The nitpicky, warnings-as-errors build reached here without raising, so it
    # is clean; assert no residual warning text leaked either.
    assert "WARNING" not in warnings, warnings

    # No-JS degradation: the complete linear transcript is present in the static
    # HTML with no script required, while build-only setup and assertions stay absent.
    assert 'class="cadrumo-sequence"' in html
    assert 'data-cadrumo-sequence="1"' in html
    assert "Imported 3 transactions." not in html
    assert "Confirm the calculation is complete." in html  # the verify caption
    assert "Confirm result.status reads verified_complete." not in html
    assert html.count('class="cadrumo-frame"') == 2

    # Enhanceable markup: the hover-help keys (data-command-path) and the inline
    # payload the stepped player parses are both present, matching the frames.
    assert 'data-command-path="aeat app modelo work verify"' in html
    match = re.search(
        r'<script type="application/json" class="cadrumo-sequence-payload">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    payload = json.loads(match.group(1).replace("<\\/", "</"))
    assert payload["sequence_id"] == _SEQUENCE_ID
    assert [frame["kind"] for frame in payload["frames"]] == ["command", "result"]
    assert all("expects" not in frame for frame in payload["frames"])

    # The widget assets ship into the built site and the page references them.
    assert (out / "_static" / "cadrumo-docs.js").is_file()
    assert (out / "_static" / "cadrumo-docs.css").is_file()
    assert "cadrumo-docs.js" in html
    assert "cadrumo-docs.css" in html
