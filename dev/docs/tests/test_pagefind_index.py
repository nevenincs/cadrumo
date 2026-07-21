"""Real-behaviour tests for the post-build Pagefind index pass.

Exercises the vendored Pagefind binary over a self-contained HTML fixture
(no mocks): the directory pass indexes pages, the per-language splits are
produced (es/ca/en - proving the extended binary's multi-language stemmers
are vendored), the custom-record injection seam works, and the search-page
template plus the pagefind.yml config reference the artifacts the pass
emits.

The index-pass tests are ``integration``-marked (they run the bundled
binary over real HTML); the config/template assertions are pure-file checks.
None mock Pagefind - the whole point is to prove the vendored binary runs
offline.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ..pagefind_index import (
    PagefindConfigurationError,
    SearchIndexResult,
    build_search_index,
)

# dev/docs/tests/test_pagefind_index.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"

_FIXTURE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <nav class="sidebar-tree"><a href="/x">nav noise</a></nav>
  <article role="main" id="furo-main-content">
    <h1>{title}</h1>
    <p>{body}</p>
  </article>
</body>
</html>
"""


def _write_fixture_site(root: Path) -> None:
    """Materialise a tiny built-HTML site with the pagefind.yml config."""
    (root / "index.html").write_text(
        _FIXTURE_PAGE.format(
            title="Prorrata",
            body="La prorrata determina el porcentaje de IVA deducible.",
        ),
        encoding="utf-8",
    )
    (root / "casilla.html").write_text(
        _FIXTURE_PAGE.format(
            title="Casilla",
            body="Posicion longitud tipo descripcion del campo del registro.",
        ),
        encoding="utf-8",
    )
    modules_page = root / "_modules" / "aeat" / "engine.html"
    modules_page.parent.mkdir(parents=True)
    modules_page.write_text(
        _FIXTURE_PAGE.format(
            title="Private source listing",
            body="This generated source listing must remain online but never enter search.",
        ),
        encoding="utf-8",
    )
    api_page = root / "api" / "engine.html"
    api_page.parent.mkdir(parents=True)
    api_page.write_text(
        _FIXTURE_PAGE.format(
            title="Generated API reference",
            body="This developer reference must remain online but never enter search.",
        ),
        encoding="utf-8",
    )
    # Use the real shipped pagefind.yml so the test covers the actual config.
    (root / "pagefind.yml").write_text(
        (_DOCS / "pagefind.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


@pytest.mark.integration
@pytest.mark.hex_core
def test_index_pass_indexes_built_html(tmp_path: Path) -> None:
    """The post-build pass indexes the fixture pages and writes the index.

    Proves the vendored binary runs offline and emits the chunked index plus
    the Pagefind UI bundle the search page loads.
    """
    _write_fixture_site(tmp_path)

    result = build_search_index(tmp_path)

    assert isinstance(result, SearchIndexResult)
    assert result.page_count == 2
    pf = tmp_path / "pagefind"
    assert pf.is_dir()
    files = {p.name for p in pf.rglob("*") if p.is_file()}
    # The UI bundle the search.html template references must be emitted.
    assert "pagefind-ui.js" in files
    assert "pagefind-ui.css" in files
    assert "pagefind.js" in files
    # Generated source and API pages stay deployable but are absent from the
    # ephemeral Pagefind input tree, so only human documentation pages count.
    assert result.page_count == 2
    assert (tmp_path / "_modules" / "aeat" / "engine.html").is_file()
    assert (tmp_path / "api" / "engine.html").is_file()


@pytest.mark.integration
@pytest.mark.hex_core
def test_custom_record_injection_seam_and_language_splits(tmp_path: Path) -> None:
    """The injection seam runs and per-language (es/ca/en) splits are produced.

    Confirms two contract points at once: the custom-record injection seam is
    callable (records injected via the ``inject`` callback), and the extended
    binary produces separate per-language index splits - es and ca splits
    prove the Spanish and Catalan stemmers are vendored (the standard binary
    would lack them).
    """
    _write_fixture_site(tmp_path)

    async def inject(index: object) -> None:
        # The custom-record step plugs in here; the seam must accept es/ca/en.
        await index.add_custom_record(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]  # reason: pagefind index is dynamically typed
            url="/glossary/#prorrata",
            content="La prorrata es la regla del porcentaje de IVA deducible.",
            language="es",
            meta={"title": "prorrata", "kind": "concept"},
        )
        await index.add_custom_record(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]  # reason: pagefind index is dynamically typed
            url="/glossary/#prorrata-ca",
            content="La prorrata determina el percentatge IVA deduible.",
            language="ca",
            meta={"title": "prorrata", "kind": "concept"},
        )

    result = build_search_index(tmp_path, inject=inject)
    assert result.page_count == 2

    pf = tmp_path / "pagefind"
    languages = {p.name.split("_")[0] for p in pf.rglob("*.pf_index")}
    assert {"es", "ca", "en"} <= languages, languages


@pytest.mark.unit
@pytest.mark.hex_core
def test_pagefind_yml_scopes_to_article_body() -> None:
    """The shipped pagefind.yml indexes the article body, excluding chrome."""
    text = (_DOCS / "pagefind.yml").read_text(encoding="utf-8")
    assert 'root_selector: "article[role=main]"' in text
    assert "exclude_selectors:" in text
    assert ".sidebar-tree" in text  # navigation chrome is excluded


@pytest.mark.integration
@pytest.mark.hex_core
def test_index_requires_a_valid_selector_config(tmp_path: Path) -> None:
    """The real indexer rejects a missing or malformed shipped config clearly."""
    _write_fixture_site(tmp_path)

    missing = tmp_path / "missing.yml"
    with pytest.raises(PagefindConfigurationError, match="config not found"):
        build_search_index(tmp_path, config_path=missing)

    invalid = tmp_path / "invalid.yml"
    invalid.write_text("root_selector: []\nexclude_selectors: [nav]\n", encoding="utf-8")
    with pytest.raises(PagefindConfigurationError, match="root_selector"):
        build_search_index(tmp_path, config_path=invalid)


@pytest.mark.unit
@pytest.mark.hex_core
def test_search_template_references_pagefind_bundle() -> None:
    """The Furo search override loads the Pagefind UI from the index output."""
    template = (_DOCS / "_templates" / "search.html").read_text(encoding="utf-8")
    assert "pagefind/pagefind-ui.js" in template
    assert "pagefind/pagefind-ui.css" in template
    assert "PagefindUI" in template


@pytest.mark.unit
@pytest.mark.hex_core
def test_unavailable_pagefind_is_a_named_error() -> None:
    """A real no-site process reports the vendor-absent boundary clearly."""
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(_REPO_ROOT)!r})\n"
        "from dev.docs.pagefind_index import PagefindUnavailableError, _require_pagefind\n"
        "try:\n"
        "    _require_pagefind()\n"
        "except PagefindUnavailableError:\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit('Pagefind unexpectedly imported without site-packages')\n"
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", script],
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
