"""Config and template assertions for the Pagefind search surface.

Pure-file checks, split out of ``test_pagefind_index`` so each module carries a
single execution lane. The index-pass tests there run the vendored binary over
real HTML and are ``integration``; these read shipped files and assert their
content, so they belong in the fast lane. The original module's own docstring
already drew this boundary -- it just could not express it while both lanes
shared one file.
"""

from __future__ import annotations

import pytest

from dev._paths import REPO_ROOT

from ..pagefind_index import PAGE_EXCLUDED_SELECTORS, PagefindUnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# dev/docs/tests/test_pagefind_config.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"


def test_a_page_record_leaves_out_the_chrome_and_recorded_json() -> None:
    """The selectors the index is built with name the page's surroundings and machine output.

    That they take effect is proven on a built index in ``test_shared_search_index``;
    this pins what is asked for, so dropping one is a visible change.
    """
    assert {".sidebar-drawer", ".toc-drawer", ".announcement", "footer"} <= set(PAGE_EXCLUDED_SELECTORS)
    assert 'pre.cadrumo-frame-output[data-format="json"]' in PAGE_EXCLUDED_SELECTORS
    assert not (_DOCS / "pagefind.yml").exists(), "the index reads no configuration file; selectors live in code"


def test_search_template_hosts_the_shared_controller() -> None:
    """The search page is a bare mount for the shared controller.

    The stock ``PagefindUI`` drop was retired: the page no longer loads a
    per-page UI bundle. It exposes the ``#pagefind-search`` mount that the
    globally-loaded ``cadrumo-docs.js`` (``initSearchPage``, wired through
    ``html_js_files`` in ``conf.py``) renders the same search controller as the
    Ctrl-K palette into -- one implementation, two hosts. Asserting the retired
    bundle is absent keeps the divergent second surface from creeping back in.
    """
    template = (_DOCS / "_templates" / "search.html").read_text(encoding="utf-8")
    assert 'id="pagefind-search"' in template
    # The retired PagefindUI bundle path is gone, and the page loads no per-page
    # script/link at all -- the controller arrives via the global cadrumo-docs.js
    # (asserting the raw wiring, not the comment prose that names the retirement).
    assert "pagefind-ui" not in template
    assert "<script" not in template
    assert "<link" not in template


def test_unavailable_pagefind_is_a_named_error() -> None:
    """The vendor-absent boundary is a named, actionable error type."""
    assert issubclass(PagefindUnavailableError, RuntimeError)
