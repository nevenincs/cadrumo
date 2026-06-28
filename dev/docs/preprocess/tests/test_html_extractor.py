"""Real-behaviour proof of the BOE normatives HTML article-split extractor.

Exercises real corpus HTML through the production extractor (no mocks):

* a real multi-article consolidated law splits into one unit per article,
  each titled and anchored to its ``#aN`` BOE permalink fragment;
* the TOC link farm and per-article jurisprudence forms are stripped - known
  boilerplate is ABSENT and known article prose is PRESENT;
* attribution resolves from the sibling manifest's BOE permalink for a law,
  and falls back to the standing attribution for a manifest-less slice;
* the written text sidecar carries a walker-supported extension and the
  installed walker's own filter accepts it (real installed package, no mock);
* anti-tautology: a tampered provenance sidecar is rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._html import (
    HTML_EXTRACTOR_ID,
    build_outputs,
    extract_html,
)
from .._schema import (
    ExtractionStatus,
    PreprocessOutput,
    SourceDocumentKind,
)
from .._sidecar import (
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sidecar_paths_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_html_extractor.py -> parents[4] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_NORMATIVES = _REPO_ROOT / "src" / "aeat" / "_data" / "corpus" / "normatives"

# A real multi-article consolidated law (IVA) with a TOC link farm, bloque
# anchors, and a sibling manifest carrying the BOE permalink.
_LAW_HTML = _NORMATIVES / "html" / "ley-37-1992.html"
# A real single-article slice with no manifest (base-attribution fallback).
_SLICE_HTML = _NORMATIVES / "html" / "orden-hap-2250-2015-art-4.html"


def test_worked_example_files_exist() -> None:
    """Both real corpus HTML files are present (guards the whole proof)."""
    assert _LAW_HTML.is_file(), _LAW_HTML
    assert _SLICE_HTML.is_file(), _SLICE_HTML


def test_law_splits_into_anchored_articles() -> None:
    """The consolidated law splits one unit per article with a BOE anchor.

    Asserts the legal-grounding surface a query needs: Articulo 1 is its own
    unit, titled, anchored to ``#a1``, carrying its real prose.
    """
    outputs = build_outputs(_LAW_HTML, repo_root=_REPO_ROOT)

    assert len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, PreprocessOutput)
    assert output.source_kind is SourceDocumentKind.NORMATIVES_HTML
    assert output.status is ExtractionStatus.OK
    assert output.preprocessor_id == HTML_EXTRACTOR_ID
    # Many articles, one unit each (the IVA law has 100+ articles).
    assert len(output.units) > 100

    article_one = next(u for u in output.units if u.title and u.title.startswith("Artículo 1."))
    assert article_one.anchor == "#a1"
    assert "Impuesto sobre el Valor Añadido" in article_one.text
    assert "tributo de naturaleza indirecta" in article_one.text


def test_toc_and_form_boilerplate_is_stripped() -> None:
    """Known TOC/markup boilerplate is ABSENT; known article prose is PRESENT.

    The F4 audit flagged TOC link farms polluting the index; this is the
    proof they no longer ship. Asserts across every unit's text.
    """
    output = build_outputs(_LAW_HTML, repo_root=_REPO_ROOT)[0]
    body = "\n".join(u.text for u in output.units)
    titles = "\n".join(u.title or "" for u in output.units)

    # Boilerplate absent: no residual tags, TOC list items, links, or the
    # per-article jurisprudence control label.
    assert "<li>" not in body
    assert "href=" not in body
    assert "<a " not in body
    assert "Jurisprudencia" not in body
    assert "[Bloque" not in body  # the anchor marker is consumed, not shipped
    assert "Subir" not in body  # the back-to-top nav is stripped
    # Page footer chrome (clipped at <div id="pie">) must not ride into the
    # last article body.
    assert "Aviso legal" not in body
    assert "Avda. de Manoteras" not in body
    # HTML entities are decoded to real characters, not left encoded.
    assert "&iacute;" not in body and "&oacute;" not in body
    assert "&aacute;" not in body and "&uacute;" not in body

    # Real article prose present (heading rides as the unit title).
    assert "Artículo 1. Naturaleza del impuesto." in titles
    assert "tributo de naturaleza indirecta" in body


def test_attribution_resolves_from_manifest_and_falls_back() -> None:
    """A law pins its BOE permalink; a manifest-less slice uses the fallback."""
    law = build_outputs(_LAW_HTML, repo_root=_REPO_ROOT)[0]
    assert "BOE" in law.attribution
    assert "boe.es" in law.attribution  # the manifest permalink

    slice_out = build_outputs(_SLICE_HTML, repo_root=_REPO_ROOT)[0]
    assert "BOE" in slice_out.attribution
    # The slice has no manifest, so only the standing attribution (no URL).
    assert "Official source:" not in slice_out.attribution


def test_single_article_slice_extracts_one_unit() -> None:
    """A bare single-article slice yields one readable unit, no anchor."""
    output = build_outputs(_SLICE_HTML, repo_root=_REPO_ROOT)[0]
    assert output.status is ExtractionStatus.OK
    assert len(output.units) == 1
    unit = output.units[0]
    assert unit.title is not None and unit.title.startswith("Artículo 4.")
    assert "modelo 184" in unit.text
    assert "<" not in unit.text and ">" not in unit.text


def test_sidecar_round_trips_and_is_walker_indexable(tmp_path: Path) -> None:
    """Written sidecar reloads equal and the .md is accepted by the walker.

    Copies the slice into tmp so no sidecar lands in the corpus tree.
    Inspects the real installed walker (no mock): the rendered .md must pass
    the extension, size-cap, and binary filters.
    """
    from vaultspec_rag.indexer._chunking import (
        _MAX_FILE_SIZE,
        SUPPORTED_EXTENSIONS,
        _is_binary,
    )

    source_copy = tmp_path / _SLICE_HTML.name
    source_copy.write_bytes(_SLICE_HTML.read_bytes())

    written = extract_html(source_copy, repo_root=tmp_path)
    assert len(written) == 1
    text_path = written[0]
    assert text_path.name == source_copy.name + EXTRACTED_TEXT_SUFFIX

    reloaded = load_sidecar(source_copy)
    assert reloaded.source_kind is SourceDocumentKind.NORMATIVES_HTML
    assert reloaded.status is ExtractionStatus.OK
    assert reloaded.units

    assert text_path.suffix.lower() in SUPPORTED_EXTENSIONS
    assert text_path.stat().st_size <= _MAX_FILE_SIZE
    assert not _is_binary(text_path)


def test_tampered_sidecar_is_rejected(tmp_path: Path) -> None:
    """Anti-tautology: a corrupt provenance sidecar fails to load.

    If this passed with a broken payload the round-trip assertions would be
    vacuous. A truncated sha256 violates the field constraint.
    """
    source_copy = tmp_path / _SLICE_HTML.name
    source_copy.write_bytes(_SLICE_HTML.read_bytes())
    extract_html(source_copy, repo_root=tmp_path)

    _, json_path = sidecar_paths_for(source_copy)
    good = json_path.read_text(encoding="utf-8")
    output = load_sidecar(source_copy)
    json_path.write_text(good.replace(output.source_sha256, "deadbeef"), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)
