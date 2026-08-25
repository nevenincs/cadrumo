"""Real-behaviour tests for the post-build Pagefind index pass.

Exercises the vendored Pagefind binary over a self-contained HTML fixture
(no mocks): the directory pass indexes pages, the per-language splits are
produced (es/ca/en - proving the extended binary's multi-language stemmers
are vendored), the custom-record injection seam works, and the search-page
template plus the pagefind.yml config reference the artifacts the pass
emits.

Every test here runs the bundled binary over real HTML, so the module is
``integration`` throughout. The config and template assertions that used to
share this file are pure-file checks and now live in ``test_pagefind_config``,
one execution lane per module. None mock Pagefind - the whole point is to prove
the vendored binary runs offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import DirectoryEntryKind, scan_directory

from ..._paths import REPO_ROOT
from ..pagefind_index import SearchIndexResult, build_search_index

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/tests/test_pagefind_index.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
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
    # Use the real shipped pagefind.yml so the test covers the actual config.
    (root / "pagefind.yml").write_text(
        (_DOCS / "pagefind.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


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
    files = {p.name for p in scan_directory(pf, recursive=True, select=DirectoryEntryKind.FILES)}
    # The UI bundle the search.html template references must be emitted.
    assert "pagefind-ui.js" in files
    assert "pagefind-ui.css" in files
    assert "pagefind.js" in files


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
    languages = {p.name.split("_")[0] for p in scan_directory(pf, pattern="*.pf_index", recursive=True)}
    assert {"es", "ca", "en"} <= languages, languages
