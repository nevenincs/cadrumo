"""Documentation build conformance gate.

Asserts the docs build machinery's hygiene contracts and the focused rendered
surfaces (identity page, sequence widget), each in a ``tmp_path`` with
``CADRUMO_DOCS_OFFLINE`` set so intersphinx inventories are not fetched. The
heavy whole-tree ``-n -W`` builds live one-per-module beside this file
(``test_docs_build_full_scope``, ``test_docs_build_user_scope``,
``test_docs_build_localized``) so pytest-xdist's per-file distribution runs
them concurrently; their shared machinery is
:mod:`dev.docs.tests._sphinx_build_harness`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

#: A real nitpicky whole-tree Sphinx build is minutes of work, not seconds, so
#: the project-wide 300 s per-test ceiling (``pyproject.toml``) cannot hold it.
#: That ceiling exists to fail a DEADLOCKED test in minutes instead of wedging
#: the run for hours; a legitimately long build is not a deadlock, and letting
#: it trip the ceiling produced a faulthandler stack dump carrying no docs
#: diagnostic at all -- the gate could not report a verdict either way. 1800 s
#: matches the sibling ``test_built_site_resolvability_sweep`` module, which
#: runs the same class of work.
pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]

#: Wall ceiling for every spawned subprocess here, set BELOW the per-test
#: ceiling above so the subprocess timeout wins the race and names itself
#: (``TimeoutExpired`` reports the command and the limit) instead of pytest
#: dumping a stack with no indication of which build hung.
_SUBPROCESS_TIMEOUT_S = 1200

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"
_DOCS_BUILD = _DOCS / "_build"
_CANONICAL_BUILD_ROOT = "html"
_DOCS_BUILD_LITERAL_RE = re.compile(r"docs[/\\]_build[/\\]([A-Za-z0-9_.-]+)")
_PATH_BUILD_ROOT_RE = re.compile(r"[\"']_build[\"']\s*/\s*[\"']([^\"']+)[\"']")
_BUILD_ROOT_SCAN_PREFIXES = ("src/", "dev/", ".github/")
_BUILD_ROOT_SCAN_FILES = {"justfile", "pyproject.toml", "docs/conf.py"}


def _docs_build_entries() -> set[str]:
    """Return entry names currently present directly under ``docs/_build``."""
    if not _DOCS_BUILD.exists():
        return set()
    return {path.name for path in scan_directory(_DOCS_BUILD)}


def _docs_source_paths() -> set[tuple[str, str]]:
    """Return the live docs source path set, excluding build output."""
    paths: set[tuple[str, str]] = set()
    for path in scan_directory(_DOCS, recursive=True):
        relative = path.relative_to(_DOCS)
        if relative.parts and relative.parts[0] == "_build":
            continue
        kind = "dir" if path.is_dir() else "file"
        paths.add((relative.as_posix(), kind))
    return paths


def _generated_docs_snapshot() -> set[tuple[str, str, int, int]]:
    """Return metadata for generated docs sources that validation must not touch."""
    snapshot: set[tuple[str, str, int, int]] = set()
    for root_name in ("api", "cli"):
        root = _DOCS / root_name
        if not root.exists():
            continue
        for path in scan_directory(root, recursive=True):
            relative = path.relative_to(_DOCS)
            stat = path.stat()
            kind = "dir" if path.is_dir() else "file"
            size = stat.st_size if path.is_file() else 0
            snapshot.add((relative.as_posix(), kind, size, stat.st_mtime_ns))
    return snapshot


def test_docs_build_directory_contains_only_canonical_html() -> None:
    """The repository docs build directory must not contain preview/test output."""
    entries = _docs_build_entries()
    extra = sorted(entries - {_CANONICAL_BUILD_ROOT})
    assert not extra, (
        "docs/_build must contain only the actual canonical HTML build root. "
        "Tests and changed-page validation must write to tmp_path or an OS temp "
        f"directory, not docs/_build. Extra entries: {extra}"
    )


def test_docs_build_cleanup_removes_noncanonical_entries(tmp_path: Path) -> None:
    """Canonical docs builds clear stale preview files from their build root."""
    from ..build import remove_noncanonical_build_entries

    docs_root = tmp_path / "docs"
    build_root = docs_root / "_build"
    html_root = build_root / _CANONICAL_BUILD_ROOT
    preview_dir = build_root / "index-preview"
    preview_file = build_root / "md-preview.html"
    html_root.mkdir(parents=True)
    preview_dir.mkdir()
    preview_file.write_text("<title>preview</title>\n", encoding="utf-8")

    remove_noncanonical_build_entries(docs_root)

    assert sorted(path.name for path in scan_directory(build_root)) == [_CANONICAL_BUILD_ROOT]
    assert html_root.is_dir()


def test_docs_build_jobs_accepts_only_serial_or_auto_settings() -> None:
    """The deployment override pins serial or parallel Sphinx workers."""
    from ..build import docs_build_jobs

    assert docs_build_jobs({}) == "auto"
    assert docs_build_jobs({"CADRUMO_DOCS_JOBS": "1"}) == "1"
    with pytest.raises(SystemExit, match="positive integer"):
        docs_build_jobs({"CADRUMO_DOCS_JOBS": "0"})


def test_pagefind_index_mode_defaults_to_full_and_accepts_pages() -> None:
    """Local docs keep records; deployment may index rendered pages alone."""
    from ..build import pagefind_index_mode

    assert pagefind_index_mode({}) == "full"
    assert pagefind_index_mode({"CADRUMO_DOCS_PAGEFIND_MODE": "full"}) == "full"
    assert pagefind_index_mode({"CADRUMO_DOCS_PAGEFIND_MODE": "pages"}) == "pages"


def test_pagefind_index_mode_rejects_unknown_values() -> None:
    """The deployment cannot silently select an unsupported search contract."""
    from ..build import pagefind_index_mode

    with pytest.raises(SystemExit, match="CADRUMO_DOCS_PAGEFIND_MODE"):
        pagefind_index_mode({"CADRUMO_DOCS_PAGEFIND_MODE": "records-only"})


def test_deployment_sitemap_uses_canonical_human_doc_urls(tmp_path: Path) -> None:
    """The deployed sitemap uses canonical URLs and omits generated surfaces."""
    from defusedxml import ElementTree

    from ..build import write_deployment_sitemap

    for relative in (
        "index.html",
        "guide/index.html",
        "guide/start.html",
        "cli/index.html",
        "api/client.html",
        "_modules/aeat/client.html",
        "search.html",
    ):
        page = tmp_path / relative
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html></html>", encoding="utf-8")

    write_deployment_sitemap(tmp_path, "https://cadrumo.neve.md/docs")

    sitemap = ElementTree.parse(tmp_path / "sitemap.xml")
    locations = [(element.text or "") for element in sitemap.iter() if element.tag.endswith("loc")]
    assert locations == [
        "https://cadrumo.neve.md/docs/",
        "https://cadrumo.neve.md/docs/cli/",
        "https://cadrumo.neve.md/docs/guide/",
        "https://cadrumo.neve.md/docs/guide/start.html",
    ]


@pytest.mark.parametrize(
    "changed_path",
    [
        "dev/docs/apidocs/manager.py",
        "dev/docs/cli_reference.py",
    ],
)
def test_changed_docs_validation_does_not_pollute_repository_docs(changed_path: str) -> None:
    """Changed-page validation writes generated sources and output outside live docs."""
    before = _docs_build_entries()
    paths_before = _docs_source_paths()
    generated_before = _generated_docs_snapshot()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.docs.build",
            changed_path,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    after = _docs_build_entries()
    paths_after = _docs_source_paths()
    generated_after = _generated_docs_snapshot()
    assert result.returncode == 0, (
        "changed-doc validation failed:\n" + (result.stdout or "")[-3000:] + (result.stderr or "")[-3000:]
    )
    assert after == before, (
        "changed-doc validation must not add or remove docs/_build entries. "
        f"Before: {sorted(before)}; after: {sorted(after)}"
    )
    assert paths_after == paths_before, (
        "changed-doc validation must not add or remove live docs source paths. "
        "Validation scratch files belong in the temporary docs source tree."
    )
    assert generated_after == generated_before, (
        "changed-doc validation must not mutate live generated docs sources. "
        "Generated API/CLI pages for validation belong in the temporary docs source tree."
    )


@pytest.mark.parametrize("generated_page", ["docs/api/cadrumo.rst", "docs/cli/index.rst"])
def test_single_page_rejects_generated_documentation_sources(generated_page: str) -> None:
    """Single-page canonical builds must not regenerate API or CLI source trees."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.docs.build",
            "--single-page",
            generated_page,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    assert result.returncode != 0
    assert "--single-page does not support generated API/CLI pages" in result.stderr


def test_tracked_sources_do_not_name_noncanonical_docs_build_roots() -> None:
    """Tracked code must not introduce preview/test output roots under ``docs/_build``."""
    git = shutil.which("git")
    assert git is not None, "git executable is required for docs build hygiene"
    result = subprocess.run(
        [git, "ls-files"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    assert result.returncode == 0, "git ls-files is required for docs build hygiene"

    violations: list[str] = []
    for raw_path in result.stdout.splitlines():
        normalised = raw_path.replace("\\", "/")
        if not (normalised in _BUILD_ROOT_SCAN_FILES or normalised.startswith(_BUILD_ROOT_SCAN_PREFIXES)):
            continue
        path = _REPO_ROOT / raw_path
        if not path.is_file() or "docs/_build" in normalised:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        roots = [*_DOCS_BUILD_LITERAL_RE.findall(text), *_PATH_BUILD_ROOT_RE.findall(text)]
        for root in roots:
            if root != _CANONICAL_BUILD_ROOT:
                violations.append(f"{raw_path}: docs/_build/{root}")

    assert not violations, (
        "Only docs/_build/html is an allowed repository-local docs build root. "
        "Use tmp_path or an OS temporary directory for validation/previews:\n  " + "\n  ".join(sorted(set(violations)))
    )


def _scope_config(scope: str, tmp_path: Path) -> dict[str, object]:
    """Evaluate the scope-conditional ``docs/conf.py`` config under one build scope.

    Runs ``docs/conf.py`` module-level code (never ``setup()``) in a subprocess
    with ``CADRUMO_DOCS_SCOPE`` set, and returns the switch-relevant config so the
    scope conditionals are asserted without a full Sphinx build.
    """
    conf = _DOCS / "conf.py"
    script = (
        "import json, runpy;"
        f"ns = runpy.run_path(r'{conf}');"
        "print('SCOPE_CONFIG=' + json.dumps({"
        "'user_scope': ns['_USER_SCOPE'],"
        "'has_autodoc': 'sphinx.ext.autodoc' in ns['extensions'],"
        "'has_viewcode': 'sphinx.ext.viewcode' in ns['extensions'],"
        "'has_typehints': 'sphinx_autodoc_typehints' in ns['extensions'],"
        "'has_myst': 'myst_parser' in ns['extensions'],"
        "'excludes_api': 'api/**' in ns['exclude_patterns'],"
        "'resolves_deferred': ns['_should_resolve_deferred_models']()}))"
    )
    env = {
        **os.environ,
        "CADRUMO_DOCS_SCOPE": scope,
        "CADRUMO_DOCS_PROJECT_ROOT": str(_REPO_ROOT),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / f"cadrumo-scope-store-{scope}"),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(row for row in result.stdout.splitlines() if row.startswith("SCOPE_CONFIG="))
    return json.loads(line[len("SCOPE_CONFIG=") :])


def test_docs_scope_config_switches_autodoc_and_api_exclusion(tmp_path: Path) -> None:
    """User scope drops the app-importing autodoc extensions and excludes docs/api.

    The whole point of the user scope is that the application is never imported to
    render docs: autodoc / viewcode / typehints (which import the app) are absent,
    the ``docs/api`` tree is excluded from the read set, and the deferred-model
    rebuild (an autodoc-only import) is skipped. Every narrative extension stays.
    Full scope keeps all of them, so the existing gates cover the API build.
    """
    user = _scope_config("user", tmp_path)
    assert user["user_scope"] is True
    assert user["has_autodoc"] is False
    assert user["has_viewcode"] is False
    assert user["has_typehints"] is False
    assert user["excludes_api"] is True
    assert user["resolves_deferred"] is False
    assert user["has_myst"] is True  # the narrative rendering surface is untouched

    full = _scope_config("full", tmp_path)
    assert full["user_scope"] is False
    assert full["has_autodoc"] is True
    assert full["has_viewcode"] is True
    assert full["has_typehints"] is True
    assert full["excludes_api"] is False
    assert full["resolves_deferred"] is True


def test_rendered_site_identity_and_static_marks_are_canonical(tmp_path: Path) -> None:
    """A real focused HTML build and shipped SVGs expose the canonical identity."""
    from bs4 import BeautifulSoup
    from defusedxml import ElementTree

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
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-docs-state"),
        # This gate reads the RENDERED index page's identity marks only; the
        # cli-sequence golden check and the cli-tree projection are enforced by
        # their dedicated gates and are not part of this page's assertions.
        "CADRUMO_DOCS_SKIP_SEQUENCE_CHECK": "1",
        "CADRUMO_DOCS_SKIP_CLI_TREE": "1",
    }
    result = subprocess.run(
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
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stdout + result.stderr

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
    from ..sequences._golden_store import GoldenFrame, SequenceGolden
    from ..sequences._schema import FrameKind

    golden = SequenceGolden(
        sequence_id=_SEQUENCE_ID,
        frames=(
            GoldenFrame(
                kind=FrameKind.SETUP,
                argv=("aeat", "app", "ledger", "import", "--file", "fixtures/x.csv"),
                exit_code=0,
                text="Imported 3 transactions.",
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
    result = subprocess.run(
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
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_S,
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
