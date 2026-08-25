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

from ..._paths import REPO_ROOT
from ..pagefind_index import PagefindUnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# dev/docs/tests/test_pagefind_config.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"


def test_pagefind_yml_scopes_to_article_body() -> None:
    """The shipped pagefind.yml indexes the article body, excluding chrome."""
    text = (_DOCS / "pagefind.yml").read_text(encoding="utf-8")
    assert 'root_selector: "article[role=main]"' in text
    assert "exclude_selectors:" in text
    assert ".sidebar-tree" in text  # navigation chrome is excluded


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
