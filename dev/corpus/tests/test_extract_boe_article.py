"""Real-behaviour proof of the BOE article-slicing tool.

Two layers, both against real code paths:

* synthetic fixtures pin the boundary-finding logic itself (nested divs,
  absent/unclosed blocks, the version-selector strip, determinism, LF-only
  output) -- fast and independent of any specific corpus document;
* a real bundled whole-document page (``ley-37-1992.html``, the same fixture
  the production extractor's own test suite already trusts) proves the tool
  REPRODUCES grounded legal text: slicing several articles fresh out of the
  whole document and round-tripping them through the production extractor
  (``dev.docs.preprocess.normatives_html.build_outputs``) yields the identical unit
  text already committed for each article's standalone excerpt sidecar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ...docs.preprocess.normatives_html import build_outputs
from ...docs.preprocess.schema import PreprocessOutput
from ..extract_boe_article import (
    _DIV_OPEN_OR_CLOSE,
    ArticleExtractionError,
    extract_article,
    write_article_excerpt,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/corpus/tests/test_extract_boe_article.py -> parents[3] is repo root.
_REPO_ROOT = REPO_ROOT
_NORMATIVES_HTML = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "normatives" / "html"
_LIVA_DOCUMENT = _NORMATIVES_HTML / "ley-37-1992.html"
_LIVA_DOCUMENT_ID = "BOE-A-1992-28740"

_SIMPLE_DOCUMENT = """\
<div class="bloque" id="a1">
<p class="bloque">[Bloque 1: #a1]</p>
<h5 class="articulo">Artículo 1. Objeto.</h5>
<p class="parrafo">El impuesto grava las operaciones.</p>
<form class="lista formBOE" method="GET">
<fieldset><legend>Seleccionar redacción</legend></fieldset>
</form>
</div>
<p class="linkSubir"><a href="#top">Subir</a></p>
<hr class="bloque"/>
<div class="bloque" id="a2">
<p class="bloque">[Bloque 2: #a2]</p>
<h5 class="articulo">Artículo 2. Ámbito.</h5>
<p class="parrafo">El impuesto se aplica en todo el territorio.</p>
</div>
"""


def _is_balanced(markup: str) -> bool:
    """Every ``<div>`` in ``markup`` closes, and no ``</div>`` is unmatched."""
    depth = 0
    for tag in _DIV_OPEN_OR_CLOSE.finditer(markup):
        depth += 1 if tag.group(0).startswith("<div") else -1
        if depth < 0:
            return False
    return depth == 0


def test_extract_article_slices_only_the_named_block() -> None:
    excerpt = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-A-1992-28740", block="a1")

    assert "Artículo 1. Objeto." in excerpt
    assert "El impuesto grava las operaciones." in excerpt
    assert "Ámbito" not in excerpt, "the sibling block a2 must not leak into the a1 excerpt"
    assert "Subir" not in excerpt, "page-navigation chrome outside the block must never be included"
    assert _is_balanced(excerpt), "a correctly sliced excerpt is always tag-balanced"


def test_extract_article_strips_the_version_selector_form() -> None:
    excerpt = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-A-1992-28740", block="a1")

    assert "formBOE" not in excerpt
    assert "Seleccionar redacción" not in excerpt


def test_extract_article_header_names_the_document_and_permalink() -> None:
    excerpt = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-A-1992-28740", block="a1")

    assert "Document: BOE-A-1992-28740" in excerpt
    assert "Permalink: https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a1" in excerpt
    assert "Excerpt: Artículo 1. Objeto. only." in excerpt


def test_extract_article_tracks_nested_div_depth() -> None:
    """A block that itself nests a sub-``<div>`` must not fool the boundary.

    BOE's real corpus never nests one ``bloque`` inside another, but nothing
    enforces that -- this is the case that separates "find the true matching
    close" from the hand-curation defect this tool exists to retire: "assume
    the next ``</div>`` is the one you want".
    """
    nested = """\
<div class="bloque" id="a1">
<h5 class="articulo">Artículo 1.</h5>
<p class="parrafo">Texto principal.</p>
<div class="nota">
<p>Una nota anidada.</p>
</div>
<p class="parrafo">Texto tras la nota.</p>
</div>
<div class="bloque" id="a2">
<h5 class="articulo">Artículo 2.</h5>
</div>
"""
    excerpt = extract_article(nested, document_id="BOE-X", block="a1")

    assert "Una nota anidada." in excerpt, "content nested one level deep must survive"
    assert "Texto tras la nota." in excerpt, "content after the nested div must still be included"
    assert "Artículo 2." not in excerpt, "the boundary must resolve at a1's OWN close, not the nested one"
    assert _is_balanced(excerpt)


def test_extract_article_raises_when_block_is_absent() -> None:
    with pytest.raises(ArticleExtractionError, match="a999"):
        extract_article(_SIMPLE_DOCUMENT, document_id="BOE-X", block="a999")


def test_extract_article_raises_when_div_is_never_closed() -> None:
    unclosed = '<div class="bloque" id="a1"><h5 class="articulo">Sin cierre.</h5>'
    with pytest.raises(ArticleExtractionError, match="never closed"):
        extract_article(unclosed, document_id="BOE-X", block="a1")


def test_extract_article_raises_when_only_the_form_widget_remains() -> None:
    only_chrome = """\
<div class="bloque" id="a1">
<form class="lista formBOE"><fieldset></fieldset></form>
</div>
"""
    with pytest.raises(ArticleExtractionError, match="empty"):
        extract_article(only_chrome, document_id="BOE-X", block="a1")


def test_extract_article_falls_back_to_a_generic_excerpt_line_without_a_heading() -> None:
    headless = """\
<div class="bloque" id="daprimera">
<p class="parrafo">Texto de una disposición sin encabezado clasificado.</p>
</div>
"""
    excerpt = extract_article(headless, document_id="BOE-X", block="daprimera")

    assert "Excerpt: block daprimera only." in excerpt


def test_extract_article_output_uses_lf_only_line_endings() -> None:
    excerpt = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-X", block="a1")

    assert "\r" not in excerpt


def test_extract_article_is_deterministic() -> None:
    first = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-X", block="a1")
    second = extract_article(_SIMPLE_DOCUMENT, document_id="BOE-X", block="a1")

    assert first == second


def test_write_article_excerpt_writes_and_reads_back(tmp_path: Path) -> None:
    source = tmp_path / "whole-document.html"
    source.write_text(_SIMPLE_DOCUMENT, encoding="utf-8")
    destination_root = tmp_path / "corpus"

    written = write_article_excerpt(
        source=source,
        document_id="BOE-X",
        block="a1",
        destination_name="boe-x-art-1.html",
        destination_root=destination_root,
    )

    assert written == destination_root / "boe-x-art-1.html"
    assert "Artículo 1. Objeto." in written.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("block", "committed_filename"),
    [
        # Previously among the 46 syntax-broken hand-curated excerpts.
        ("a90", "ley-37-1992-art-90.html"),
        ("a91", "ley-37-1992-art-91.html"),
        ("a92", "ley-37-1992-art-92.html"),
        ("a161", "ley-37-1992-art-161.html"),
        ("a84", "ley-37-1992-art-84.html"),
        ("a163duovicies", "ley-37-1992-art-163-duovicies.html"),
        # Never broken -- widens the proof beyond "reproduces my own fix".
        # (Several never-broken siblings -- e.g. art-13, art-15, art-20 -- were
        # hand-trimmed without their amendment-history blockquote and are
        # deliberately excluded here: this tool's output is then a strict
        # superset of theirs rather than identical, which is a separate,
        # pre-existing completeness gap in that legacy corpus, not something
        # this test should assert equality against.)
        ("a1", "ley-37-1992-art-1.html"),
        ("a17", "ley-37-1992-art-17.html"),
    ],
)
def test_extract_article_reproduces_committed_liva_article_text(
    tmp_path: Path,
    block: str,
    committed_filename: str,
) -> None:
    """Slicing fresh from the whole document matches the committed excerpt's grounded text.

    This is the reproducibility proof the hand-curation process could never
    offer: given the SAME source (the bundled whole ``ley-37-1992.html``, a
    fixture the production extractor's own test suite already trusts) and
    the SAME block id, the tool's output round-trips through the production
    extractor to the identical unit text already committed for that
    article's standalone excerpt -- for articles this session fixed by hand
    AND for articles that were never broken.
    """
    committed_sidecar = _NORMATIVES_HTML / f"{committed_filename}.extracted.json"
    assert committed_sidecar.is_file(), f"fixture assumption broken: no committed sidecar for block {block!r}"
    committed = PreprocessOutput.model_validate_json(committed_sidecar.read_text(encoding="utf-8"))

    document_markup = _LIVA_DOCUMENT.read_text(encoding="utf-8")
    excerpt = extract_article(document_markup, document_id=_LIVA_DOCUMENT_ID, block=block)
    assert _is_balanced(excerpt)

    fresh_source = tmp_path / committed_filename
    fresh_source.write_text(excerpt, encoding="utf-8")
    fresh = build_outputs(fresh_source, repo_root=tmp_path)

    assert len(fresh) == 1
    assert [unit.text for unit in fresh[0].units] == [unit.text for unit in committed.units]
