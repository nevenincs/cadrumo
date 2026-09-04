"""Real-behaviour proof of the BOE normatives HTML article-split extractor.

Exercises real corpus HTML through the production extractor (no mocks):

* a real multi-article consolidated law splits into one unit per article,
  each titled and anchored to its ``#aN`` BOE permalink fragment;
* real marker-backed and unmarked annex headings become distinct legal units,
  while only source-supplied fragments are recorded as unit anchors;
* the TOC link farm and per-article jurisprudence forms are stripped - known
  boilerplate is ABSENT and known article prose is PRESENT;
* attribution resolves from the HTML's canonical BOE permalink for a law,
  and falls back to the standing attribution for a canonical-less slice;
* the written text sidecar carries a walker-supported extension and the
  installed walker's own filter accepts it (real installed package, no mock);
* anti-tautology: a tampered provenance sidecar is rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...._paths import REPO_ROOT
from ..normatives_html import (
    HTML_EXTRACTOR_ID,
    build_outputs,
    extract_html,
)
from ..schema import (
    ExtractionStatus,
    PreprocessOutput,
    SourceDocumentKind,
)
from ..sidecar import (
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sidecar_paths_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_html_extractor.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT
_NORMATIVES = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "normatives"

# A real multi-article consolidated law (IVA) with a TOC link farm, bloque
# anchors, and an embedded canonical BOE permalink.
_LAW_HTML = _NORMATIVES / "html" / "ley-37-1992.html"
# A real single-article slice with no canonical link (base-attribution fallback).
_SLICE_HTML = _NORMATIVES / "html" / "orden-hap-2250-2015-art-4.html"
# A BOE consolidated order whose annexes have literal ``[Bloque ...]``
# fragments, and a BOE daily-document order whose structural annex headings
# have no literal fragment to claim.
_MARKED_ANNEX_HTML = _NORMATIVES / "html" / "orden-eha-3435-2007.html"
_UNMARKED_ANNEX_HTML = _NORMATIVES / "html" / "orden-hfp-1359-2023.html"
_MODULES_2025_HTML = _NORMATIVES / "html" / "orden-hac-1347-2024.html"
_MODULES_2022_HTML = _NORMATIVES / "html" / "orden-hfp-1335-2021.html"
_APARTADO_ORDINAL_HTML = _NORMATIVES / "html" / "orden-hac-3625-2003-art-3.html"
_ORDINAL_PARAGRAPH_HTML = _NORMATIVES / "html" / "boe-a-2011-208-modelo-145.html"


def test_worked_example_files_exist() -> None:
    """The real corpus HTML documents used by this proof are present."""
    assert _LAW_HTML.is_file(), _LAW_HTML
    assert _SLICE_HTML.is_file(), _SLICE_HTML
    assert _MARKED_ANNEX_HTML.is_file(), _MARKED_ANNEX_HTML
    assert _UNMARKED_ANNEX_HTML.is_file(), _UNMARKED_ANNEX_HTML
    assert _MODULES_2025_HTML.is_file(), _MODULES_2025_HTML
    assert _MODULES_2022_HTML.is_file(), _MODULES_2022_HTML
    assert _APARTADO_ORDINAL_HTML.is_file(), _APARTADO_ORDINAL_HTML
    assert _ORDINAL_PARAGRAPH_HTML.is_file(), _ORDINAL_PARAGRAPH_HTML


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


def test_law_retains_non_article_boe_anchor() -> None:
    """A BOE disposition retains its own fragment rather than an article-only fallback."""
    output = build_outputs(_LAW_HTML, repo_root=_REPO_ROOT)[0]

    disposition = next(
        unit for unit in output.units if unit.title and unit.title.startswith("Disposición adicional primera.")
    )

    assert disposition.anchor == "#daprimera"
    assert "entidades locales" in disposition.text


def test_annex_headings_become_distinct_units_without_inventing_fragments() -> None:
    """Real BOE annex headings retain literal fragments, or no fragment at all.

    ``orden-eha-3435-2007`` exposes its annex ids in real ``Bloque`` markers;
    the extractor must preserve those ids rather than attach an annex to the
    preceding article.  ``orden-hfp-1359-2023`` has equally explicit annex
    headings but no source fragment, so its unit must stay unanchored instead
    of reusing the preceding article's anchor.
    """
    marked = build_outputs(_MARKED_ANNEX_HTML, repo_root=_REPO_ROOT)[0]
    annex_one = next(unit for unit in marked.units if unit.title == "ANEXO I")
    annex_two = next(unit for unit in marked.units if unit.title == "ANEXO II")
    assert annex_one.anchor == "#ai"
    assert annex_two.anchor == "#ai-2"
    assert "Ref. BOE-A-2018-17997" in annex_one.text

    unmarked = build_outputs(_UNMARKED_ANNEX_HTML, repo_root=_REPO_ROOT)[0]
    unmarked_annex = next(unit for unit in unmarked.units if unit.title == "ANEXO I")
    assert unmarked_annex.anchor is None
    assert "Actividades agrícolas, ganaderas y forestales" in unmarked_annex.text


def test_ordinal_legal_boundaries_are_titled_units_without_invented_anchors() -> None:
    """Legacy BOE ordinal forms remain discrete, structurally matchable units.

    The model-309 slice exposes its provision as an unclassed heading inside
    ``section.apartado``.  The Modelo 145 resolution encodes its operative
    provisions as ordinal paragraphs.  Both lack source-supplied fragments,
    so their titles, rather than a fabricated anchor, give the resolver its
    unique structural target.
    """
    apartado = build_outputs(_APARTADO_ORDINAL_HTML, repo_root=_REPO_ROOT)[0]
    tercero_units = [unit for unit in apartado.units if unit.title == "Tercero."]
    assert len(tercero_units) == 1
    tercero = tercero_units[0]
    assert tercero.anchor is None
    assert tercero.section == tercero.title
    assert "Plazo de presentación del modelo 309" in tercero.text
    assert "veinte primeros días naturales" in tercero.text
    assert "Disposición adicional única." not in tercero.text

    modelo_145 = build_outputs(_ORDINAL_PARAGRAPH_HTML, repo_root=_REPO_ROOT)[0]
    primero_title = (
        "Primero. Aprobación del modelo 145, de comunicación de datos del perceptor de rentas del trabajo a su pagador."
    )
    primero_units = [unit for unit in modelo_145.units if unit.title == primero_title]
    assert len(primero_units) == 1
    primero = primero_units[0]
    segundo_units = [unit for unit in modelo_145.units if unit.title and unit.title.startswith("Segundo.")]
    assert len(segundo_units) == 1
    segundo = segundo_units[0]
    assert primero.anchor is None
    assert primero.section == primero.title
    assert "Se aprueba el modelo 145" in primero.text
    assert "ejemplar para la empresa o entidad pagadora" in primero.text
    assert "Serán válidos también" in primero.text
    assert "Contenido de la comunicación de los datos relativos a hijos" not in primero.text
    assert segundo.anchor is None
    assert segundo.section == segundo.title
    assert "hijos y otros descendientes" in segundo.text


def test_annex_instructions_become_atomic_citation_units() -> None:
    """Real BOE paragraph headings bound one local citation unit each."""
    output = build_outputs(_UNMARKED_ANNEX_HTML, repo_root=_REPO_ROOT)[0]
    fragments = {unit.anchor: unit for unit in output.units if unit.anchor and "instruccion" in unit.anchor}

    employment = fragments["#anexo-ii-instruccion-2-2-a"]
    assert employment.title == "2.2\u2003Fase\xa02: Rendimiento neto minorado."
    assert "a)\u2003Minoración por incentivos al empleo." in employment.text
    assert "Si la diferencia resultase positiva" in employment.text
    assert "b)\u2003Minoración por incentivos a la inversión." not in employment.text

    excess = fragments["#anexo-ii-instruccion-2-3-b-3"]
    assert "al exceso sobre dichas cuantías se le aplicará el índice\xa01,30" in excess.text
    assert "b.4)\u2003Índice corrector por inicio de nuevas actividades." not in excess.text

    modules_2025 = build_outputs(_MODULES_2025_HTML, repo_root=_REPO_ROOT)[0]
    annex_one_point_three = next(unit for unit in modules_2025.units if unit.anchor == "#anexo-i-instruccion-3")
    assert "agricultores jóvenes o asalariados agrarios" in annex_one_point_three.title
    assert "pagos fraccionados" in annex_one_point_three.text
    assert "A efectos del pago fraccionado" not in annex_one_point_three.text


def test_iva_instructions_and_activity_tables_become_atomic_citation_units() -> None:
    """Real 2025 IVA source boundaries exclude adjacent instruction and activity units."""
    output = build_outputs(_MODULES_2025_HTML, repo_root=_REPO_ROOT)[0]
    fragments = {unit.anchor: unit for unit in output.units if unit.anchor}

    instructions = fragments["#anexo-i-instrucciones-iva"]
    assert "La cuota devengada por operaciones corrientes será la suma" in instructions.text
    assert "será deducible el\xa01 por ciento" in instructions.text
    assert "La cuota derivada del régimen simplificado será la mayor" in instructions.text
    assert "Cuotas trimestrales" not in instructions.text

    iva_table_anchors = tuple(
        unit.anchor
        for unit in output.units
        if unit.anchor
        and unit.anchor.startswith("#m303-anexo-ii-iva-")
        and unit.anchor != "#m303-anexo-ii-iva-ingreso-a-cuenta"
    )
    assert len(iva_table_anchors) == 49
    assert len(set(iva_table_anchors)) == len(iva_table_anchors)
    agricultural_anchors = tuple(
        unit.anchor
        for unit in output.units
        if unit.anchor
        and unit.anchor.startswith("#m303-anexo-i-iva-")
        and unit.anchor != "#m303-anexo-i-iva-ingreso-a-cuenta"
    )
    assert len(agricultural_anchors) == 17
    assert len(set(agricultural_anchors)) == len(agricultural_anchors)
    assert "#m303-anexo-i-iva-ingreso-a-cuenta" in fragments
    assert "#m303-iva-indices-correctores-temporada" in fragments
    assert "#m303-iva-cuotas-soportadas-dificil-justificacion" in fragments

    autotaxis = fragments["#m303-anexo-ii-iva-721-2-transporte-por-autotaxis"]
    assert autotaxis.title == "Transporte por autotaxis"
    assert "\n721.2\n" in autotaxis.text
    assert "Cuota mínima por operaciones corrientes: 10 %" in autotaxis.text
    assert "Transporte de mercancías por carretera" not in autotaxis.text

    freight = fragments["#m303-anexo-ii-iva-722-transporte-de-mercancias-por-carretera-excepto-residuos"]
    assert "\n722\n" in freight.text
    assert "Cuota mínima por operaciones corrientes: 10 %" in freight.text
    assert "Transporte de residuos por carretera" not in freight.text

    hairdressing = fragments["#m303-anexo-ii-iva-972-1-servicios-de-peluqueria-de-senora-y-caballero"]
    assert "\n972.1\n" in hairdressing.text
    assert "Cuota mínima por operaciones corrientes: 13 %" in hairdressing.text
    assert "Salones e institutos de belleza" not in hairdressing.text


def test_2022_iva_units_preserve_the_legacy_table_shape_and_lorca_reduction() -> None:
    """The source-neutral annual parser keeps 2022's multi-value table rows exact."""
    output = build_outputs(_MODULES_2022_HTML, repo_root=_REPO_ROOT)[0]
    fragments = {unit.anchor: unit for unit in output.units if unit.anchor}

    iva_table_anchors = tuple(
        unit.anchor
        for unit in output.units
        if unit.anchor
        and unit.anchor.startswith("#m303-anexo-ii-iva-")
        and unit.anchor != "#m303-anexo-ii-iva-ingreso-a-cuenta"
    )
    assert len(iva_table_anchors) == 49
    bread = fragments["#m303-anexo-ii-iva-419-1-industrias-del-pan-y-de-la-bolleria"]
    assert "1 Personal empleado. Persona. 1.693,54" in bread.text
    assert "3 Superficie del horno. 100 ddecímetros cuadrados. 30,47" in bread.text

    lorca = fragments["#m303-da-4-lorca-2022-reduction"]
    assert "anexo II de esta Orden" in lorca.text
    assert "20 por ciento" in lorca.text
    assert "cuota trimestral" in lorca.text
    assert "cuota anual" in lorca.text


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


def test_attribution_resolves_from_canonical_link_and_falls_back() -> None:
    """A law pins its BOE permalink; a canonical-less slice uses the fallback."""
    law = build_outputs(_LAW_HTML, repo_root=_REPO_ROOT)[0]
    assert "BOE" in law.attribution
    assert "Official source: https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740" in law.attribution

    slice_out = build_outputs(_SLICE_HTML, repo_root=_REPO_ROOT)[0]
    assert "BOE" in slice_out.attribution
    # The slice has no canonical link, so only the standing attribution (no URL).
    assert "Official source:" not in slice_out.attribution


def test_single_article_slice_derives_its_anchor_from_the_article_heading() -> None:
    """A legacy slice without a bloque marker still exposes its BOE article anchor."""
    output = build_outputs(_SLICE_HTML, repo_root=_REPO_ROOT)[0]
    assert output.status is ExtractionStatus.OK
    assert len(output.units) == 1
    unit = output.units[0]
    assert unit.title is not None and unit.title.startswith("Artículo 4.")
    assert unit.anchor == "#a4"
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
