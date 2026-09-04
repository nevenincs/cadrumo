"""BOE normatives HTML article-split extractor for the dev-side RAG index.

Extracts the tracked BOE/AEAT normatives HTML corpus - consolidated laws,
royal decrees, and ordenes, plus single-article slices - into
schema-conformant sidecars so a reader query like "pro rata" reaches the
actual BOE article text the code is grounded against, as clean prose rather
than raw markup. The normatives corpus is the legal-grounding surface
(``legal_refs`` resolve into it), so splitting it per article and stripping
the TOC link farms is what makes the article text usefully retrievable.

Splitting follows the BOE document structure:

* ``<h5 class="articulo">`` is the article boundary - one
  :class:`PreprocessUnit` per article, titled by the article heading.
* the ``[Bloque N: #aN]`` marker that precedes each article carries the
  article anchor (``#aN``); it is stamped on the unit so a hit deep-links to
  the specific article on the BOE permalink.
* the table-of-contents link farm (``<li><a href="#aN">`` boilerplate) and
  the per-article jurisprudence ``<form>`` controls live before the first
  article or between the marker and the heading; they are stripped so only
  article prose ships.
* the same structural treatment applies to BOE ``anexo`` headings.  A
  marker-backed annex is its own unit and keeps the literal BOE fragment;
  unmarked annex headings are still their own titled units, without inventing
  a fragment that the source does not supply.

Attribution is pulled from the canonical link embedded in a full BOE document,
composing the per-article permalink with the ``#aN`` anchor; single-article
slices with no canonical link fall back to the standing BOE/AEAT attribution.
Either way the reuse-with-attribution obligation is honoured.

This is the production normatives preprocessor. When the upstream
``vaultspec-rag`` preprocess-hook lands, this module re-targets the upstream
sink and the committed sidecars are retired; ``PreprocessOutput`` is the
forward-compatible precursor that makes that migration mechanical.
"""

from __future__ import annotations

import html as html_entities
import re
import unicodedata
from pathlib import Path
from typing import Final

from ..._paths import UTF_8
from ._parts import split_units_by_budget, write_part_sidecars
from .schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from .sidecar import sha256_of

#: Stable id of this extractor, recorded in every sidecar's provenance.
HTML_EXTRACTOR_ID = "normatives-html"

#: Version of this extractor; part of the cache identity. Bump when the
#: rendering changes so a regeneration is distinguishable from a no-op.
HTML_EXTRACTOR_VERSION = "1.3"
_UTF_8: Final[str] = UTF_8

#: Standing BOE/AEAT attribution used when no canonical link pins a permalink.
_BASE_ATTRIBUTION = (
    "Source: Boletin Oficial del Estado (BOE) / Agencia Estatal de Administracion Tributaria. Reused with attribution."
)

# The BOE legal text lives inside <div id="textoxslt">; the page footer
# (<div id="pie">) carries site chrome (Aviso legal, Mapa, the AEBOE postal
# address) that must never ride into the last article's body. The content is
# clipped to the textoxslt container before splitting.
_CONTENT_START = re.compile(r'<div[^>]*id="textoxslt"[^>]*>', re.IGNORECASE)

#: The legal-text container's own BOE fragment. Literal, not an extractor
#: alias: ``doc.php`` serves ``<div id="textoxslt">`` and the permalink
#: ``...doc.php?id=BOE-A-...#textoxslt`` deep-links to it, so this satisfies
#: the same "fragment the source supplies" rule the bloque markers do.
#:
#: It is stamped only on the whole-document fallback unit, and only when the
#: container was actually found. A BOE page with no article delimiter (a
#: correccion de errores, a single-provision norm) otherwise yields one unit
#: with no anchor at all, and ``resolve_anchored_extracted_unit`` returns the
#: sole unit of an anchorless single-unit sidecar for ANY requested anchor --
#: so every such citation's ``corpus_ref`` fragment is unfalsifiable. Carrying
#: the real container fragment makes the declared anchor checkable: the right
#: one matches exactly and a wrong one is refused.
_CONTAINER_ANCHOR: Final[str] = "#textoxslt"
_FOOTER_START = re.compile(r'<div[^>]*id="pie"[^>]*>', re.IGNORECASE)
_CANONICAL_LINK = re.compile(
    r"""<link\b(?=[^>]*\brel=["']canonical["'])(?=[^>]*\bhref=["'](?P<href>https://www\.boe\.es/[^"']+)["'])[^>]*>""",
    re.IGNORECASE,
)

# Block-level noise stripped before article splitting: jurisprudence forms,
# scripts, styles, and the per-article "Subir" (back-to-top) nav paragraph.
_FORM = re.compile(r"<form\b.*?</form>", re.IGNORECASE | re.DOTALL)
_SCRIPT = re.compile(r"<script\b.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE = re.compile(r"<style\b.*?</style>", re.IGNORECASE | re.DOTALL)
_SUBIR = re.compile(r'<p[^>]*class="linkSubir"[^>]*>.*?</p>', re.IGNORECASE | re.DOTALL)

# The unit-heading delimiter and the bloque markers. The anchor matcher
# preserves every BOE fragment assigned to an extracted unit, including
# dispositions and annexes; the marker matcher strips every
# "[Bloque N: #...]" navigation marker from the body text - none are article
# prose.
_UNIT_HEADING_SPLIT = re.compile(
    r"""<h[1-6]\b(?=[^>]*\bclass=["'][^"']*\b(?:articulo|anexo|anexo_num)\b[^"']*["'])[^>]*>""",
    re.IGNORECASE,
)
_ORDINAL_WORD = r"(?:Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[eé]ptimo|Octavo|Noveno|D[eé]cimo)"
_APARTADO_ORDINAL_HEADING = re.compile(
    rf"""(?P<section><section\b(?=[^>]*\bclass=["'][^"']*\bapartado\b[^"']*["'])[^>]*>\s*)
    (?P<opening><h(?P<level>[1-6])\b(?![^>]*\bclass=)[^>]*>)
    (?P<ordinal>\s*{_ORDINAL_WORD}\.\s*)</h(?P=level)\s*>""",
    re.IGNORECASE | re.VERBOSE,
)
_ORDINAL_PROVISION_PARAGRAPH = re.compile(
    rf"""<p\b(?=[^>]*\bclass=["'][^"']*\bparrafo(?:_2)?\b[^"']*["'])[^>]*>
    \s*(?P<content>{_ORDINAL_WORD}\..*?)</p>""",
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)
_ORDINAL_TITLE_BODY = re.compile(r"^(?P<title>.+?\.)\s*–\s*(?P<body>.+)$", re.DOTALL)
_BLOQUE_ANCHOR = re.compile(r"\[Bloque\s+\d+:\s*(#[\w-]+)\]", re.IGNORECASE)
_BLOQUE_MARKER = re.compile(r"\[Bloque\s+\d+:[^\]]*\]", re.IGNORECASE)
_ARTICLE_HEADING_ANCHOR = re.compile(r"^art[ií]culo\s+(\d+(?:\s*(?:bis|ter|quater|quinquies))?)\b", re.IGNORECASE)
_HEADING_CLOSE = re.compile(r"</h[1-6]\s*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")

# BOE's annual estimacion-objetiva orders express the reviewed calculation
# instructions as paragraph headings inside ANEXO I/II, rather than as HTML
# heading elements.  The parent annex remains a useful search unit, but an
# exact legal citation must resolve only the stated instruction fragment.  A
# derived fragment therefore carries a stable corpus-local anchor and stops at
# the next source-stated peer heading; it never borrows ``required_text`` as a
# selector and never widens to the whole annex at citation time.
_ANNEX_FRAGMENT_SPECS: Final[dict[str, tuple[tuple[str, str, str], ...]]] = {
    "ANEXO I": (
        ("#anexo-i-instruccion-2-1", "2.1 fase 1:", "2.2 fase 2:"),
        ("#anexo-i-instruccion-2-2", "2.2 fase 2:", "2.3 fase 3:"),
        ("#anexo-i-instruccion-2-3", "2.3 fase 3:", "3. los agricultores jovenes"),
        ("#anexo-i-instruccion-3", "3. los agricultores jovenes", "pagos fraccionados"),
    ),
    "ANEXO II": (
        ("#anexo-ii-instruccion-2-2-a", "2.2 fase 2:", "b) minoracion por incentivos a la inversion"),
        ("#anexo-ii-instruccion-2-2-b", "b) minoracion por incentivos a la inversion", "2.3 fase 3:"),
        (
            "#anexo-ii-instruccion-2-3-incompatibilidades",
            "incompatibilidades entre los indices correctores:",
            "a) indices correctores especiales.",
        ),
        (
            "#anexo-ii-instruccion-2-3-b-1",
            "b.1) indice corrector para empresas de pequena dimension:",
            "b.2) indice corrector de temporada:",
        ),
        (
            "#anexo-ii-instruccion-2-3-b-2",
            "b.2) indice corrector de temporada:",
            "b.3) indice corrector de exceso:",
        ),
        (
            "#anexo-ii-instruccion-2-3-b-3",
            "b.3) indice corrector de exceso:",
            "b.4) indice corrector por inicio de nuevas actividades.",
        ),
        (
            "#anexo-ii-instruccion-2-3-b-4",
            "b.4) indice corrector por inicio de nuevas actividades.",
            "pagos fraccionados",
        ),
    ),
}

_IVA_ANNUAL_INSTRUCTION_FRAGMENT_SPEC: Final[tuple[str, str, str]] = (
    "#anexo-i-instrucciones-iva",
    "instrucciones para la aplicacion de los indices y modulos en el impuesto sobre el valor anadido",
    "cuotas trimestrales",
)

_M303_ANNUAL_ORDEN_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "orden-hfp-1335-2021.html",
        "orden-hfp-1172-2022.html",
        "orden-hfp-1359-2023.html",
        "orden-hac-1347-2024.html",
        "orden-hac-1425-2025.html",
    },
)


def _clip_to_content(markup: str) -> tuple[str, str]:
    """Clip markup to the BOE legal-text container, dropping page chrome.

    A full BOE page wraps its legal text in ``<div id="textoxslt">`` and ends
    with a ``<div id="pie">`` footer (site navigation and the AEBOE postal
    address). The footer must never ride into the last article, so the markup
    is clipped from the content-start marker (when present) up to the footer
    marker. A single-article slice has neither marker and is returned whole.

    Returns the clipped markup plus the container's own BOE fragment when the
    content marker was present, else the empty string. The fragment is what
    lets an unsegmented full BOE page still carry a falsifiable anchor: see
    :data:`_CONTAINER_ANCHOR`.
    """
    container_anchor = ""
    start = _CONTENT_START.search(markup)
    if start is not None:
        markup = markup[start.end() :]
        container_anchor = _CONTAINER_ANCHOR
    footer = _FOOTER_START.search(markup)
    if footer is not None:
        markup = markup[: footer.start()]
    return markup, container_anchor


def render_normative_prose(markup: str) -> str:
    """Strip remaining tags and collapse whitespace into readable prose.

    Runs after the block-level noise removal: drops every residual tag,
    collapses runs of spaces/tabs, and squeezes three-or-more blank lines to
    a paragraph break so the article reads as clean text.

    Public because it is the project's one BOE-markup-to-prose rendering, and
    a second consumer now needs it: the excerpt-versus-current screen compares
    an extracted sidecar's prose against a redaction sliced out of raw
    article-endpoint markup, and a comparison rendered two different ways
    measures the renderer rather than the law.
    """
    text = _TAG.sub("", markup)
    text = _BLOQUE_MARKER.sub("", text)
    # Decode HTML entities (&iacute; -> i-acute) so the article reads as real
    # Spanish text rather than entity-encoded markup.
    text = html_entities.unescape(text)
    text = _WS.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return _BLANKS.sub("\n\n", text).strip()


def _segments(markup: str) -> list[tuple[str, str]]:
    """Split markup into ``(anchor, unit_markup)`` pairs per legal heading.

    The text before the first article or annex heading (document metadata and
    the TOC link farm) is discarded. Each unit's anchor is read from the
    ``[Bloque N: #... ]`` marker in the tail of the preceding segment when
    present, else the empty string.  This deliberately does not mint a
    fragment for an unmarked annex: ``PreprocessUnit.anchor`` is a literal
    BOE deep-link fragment, not an extractor alias.
    """
    parts = _UNIT_HEADING_SPLIT.split(markup)
    if len(parts) <= 1:
        return []
    segments: list[tuple[str, str]] = []
    # parts[0] is the preamble (metadata + TOC); the anchor for article i is
    # carried in the tail of parts[i] (the bloque marker precedes its h5).
    for index in range(1, len(parts)):
        preceding = parts[index - 1]
        # The anchor is the last bloque marker before this heading (an
        # article may be preceded by several markers; the nearest wins).
        anchor_matches = _BLOQUE_ANCHOR.findall(preceding)
        anchor = anchor_matches[-1] if anchor_matches else ""
        segments.append((anchor, parts[index]))
    return segments


def _promote_ordinal_legal_boundaries(markup: str) -> str:
    """Promote two BOE ordinal-provision encodings to legal headings.

    BOE normally uses classed heading tags for legal-unit boundaries.  A small
    legacy subset instead encodes an ordinal provision as either an unclassed
    heading directly inside ``section.apartado``, or as a run of ordinal
    ``parrafo`` elements before the first regular legal heading.  Both forms
    state a legal boundary in their source text but carry no BOE fragment, so
    this only promotes their internal segmentation: it never assigns one.
    """

    markup = _APARTADO_ORDINAL_HEADING.sub(
        lambda match: (
            f'{match.group("section")}{match.group("opening")[:-1]} class="articulo">'
            f"{match.group('ordinal')}</h{match.group('level')}>"
        ),
        markup,
    )

    first_heading = _UNIT_HEADING_SPLIT.search(markup)
    preamble_end = first_heading.start() if first_heading is not None else len(markup)
    preamble = markup[:preamble_end]
    matches = list(_ORDINAL_PROVISION_PARAGRAPH.finditer(preamble))
    if len(matches) < 2:
        return markup

    def replace_ordinal_paragraph(match: re.Match[str]) -> str:
        content = match.group("content").strip()
        title_and_body = _ORDINAL_TITLE_BODY.match(content)
        if title_and_body is None:
            return f'<h5 class="articulo">{content}</h5>'
        return (
            f'<h5 class="articulo">{title_and_body.group("title").strip()}</h5>'
            f'<p class="parrafo">{title_and_body.group("body").strip()}</p>'
        )

    return _ORDINAL_PROVISION_PARAGRAPH.sub(replace_ordinal_paragraph, preamble) + markup[preamble_end:]


def _heading_and_body(unit_markup: str) -> tuple[str, str]:
    """Split one legal-unit segment into ``(heading, body)`` clean text.

    The segment begins immediately after its opening heading tag, so the
    heading runs up to its closing ``</hN>`` and the body is everything after,
    with block-level noise already removed by the caller.
    """
    closing = _HEADING_CLOSE.search(unit_markup)
    if closing is None:
        return "", render_normative_prose(unit_markup)
    heading = render_normative_prose(unit_markup[: closing.start()])
    body = render_normative_prose(unit_markup[closing.end() :])
    return heading, body


def _anchor_from_heading(heading: str) -> str:
    """Derive BOE's article fragment when legacy source markup lacks a bloque marker."""
    match = _ARTICLE_HEADING_ANCHOR.match(heading.strip())
    if match is None:
        return ""
    return "#a" + re.sub(r"\s+", "", match.group(1)).lower()


def _fold_fragment_heading(text: str) -> str:
    """Fold a source heading for stable boundary recognition."""
    decomposed = unicodedata.normalize("NFKD", text.replace("\xa0", " "))
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks).strip().casefold()


def _derived_annex_fragment_units(
    unit: PreprocessUnit,
    *,
    include_iva_annual_fragments: bool,
) -> list[PreprocessUnit]:
    """Derive citation-sized units from source-stated annex instruction headings."""
    if unit.title not in _ANNEX_FRAGMENT_SPECS:
        return []
    lines = unit.text.splitlines()
    folded = tuple(_fold_fragment_heading(line) for line in lines)
    derived: list[PreprocessUnit] = []
    fragment_specs = _ANNEX_FRAGMENT_SPECS[unit.title]
    if include_iva_annual_fragments and unit.title == "ANEXO II":
        fragment_specs = (_IVA_ANNUAL_INSTRUCTION_FRAGMENT_SPEC, *fragment_specs)
    for anchor, start_prefix, end_prefix in fragment_specs:
        starts = [index for index, line in enumerate(folded) if line.startswith(start_prefix)]
        ends = [index for index, line in enumerate(folded) if line.startswith(end_prefix)]
        if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0] + 1:
            continue
        start = starts[0]
        end = ends[0]
        title = lines[start].strip()
        body = "\n".join(lines[start + 1 : end]).strip()
        if not title or not body:
            continue
        derived.append(
            PreprocessUnit(
                text=body,
                title=title,
                section=f"{unit.title}: {title}",
                anchor=anchor,
            ),
        )
    return derived


def _with_derived_annex_fragments(
    units: list[PreprocessUnit],
    *,
    include_iva_annual_fragments: bool,
) -> list[PreprocessUnit]:
    """Append citation-sized derived fragments in parent-annex order."""
    derived = [
        fragment
        for unit in units
        for fragment in _derived_annex_fragment_units(
            unit,
            include_iva_annual_fragments=include_iva_annual_fragments,
        )
    ]
    return [*units, *derived]


def _m303_annual_orden_table_units(source: Path) -> list[PreprocessUnit]:
    """Project the canonical annual-Orden parser into exact legal-corpus units."""
    if source.name not in _M303_ANNUAL_ORDEN_SOURCES:
        return []
    from cadrumo.core.orden_anual_html import (
        extract_orden_anual_iva_authority,
        orden_anual_iva_authority_units,
    )

    authority = extract_orden_anual_iva_authority(source.read_bytes(), source_label=source.name)
    return [
        PreprocessUnit(
            text=unit.text,
            title=unit.title,
            section=unit.section,
            anchor=unit.anchor,
        )
        for unit in orden_anual_iva_authority_units(authority)
    ]


def _document_boe_url(markup: str) -> str:
    """Return the authoritative BOE permalink embedded in ``markup``."""
    match = _CANONICAL_LINK.search(markup)
    if match is None:
        return ""
    return html_entities.unescape(match.group("href")).strip()


def _attribution_for(boe_url: str) -> str:
    """Compose the attribution string for a normatives document."""
    if boe_url:
        return f"{_BASE_ATTRIBUTION} Official source: {boe_url}"
    return _BASE_ATTRIBUTION


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Extract a BOE normatives HTML file into one or more records.

    One :class:`PreprocessUnit` per article or annex heading, titled by that
    heading and anchored to its literal BOE fragment when present. A file with
    no supported legal-heading delimiter (a stray fragment) extracts to a
    single whole-document unit. When the combined text would exceed the
    per-sidecar byte budget the units are grouped so each
    :class:`PreprocessOutput` renders under the walker's file cap.

    Args:
        source: Path to the ``.html`` file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        A list of validated records (one per sidecar pair to write).
    """
    markup = source.read_text(encoding=_UTF_8)
    boe_url = _document_boe_url(markup)
    markup, container_anchor = _clip_to_content(markup)
    markup = _SCRIPT.sub(" ", markup)
    markup = _STYLE.sub(" ", markup)
    markup = _FORM.sub(" ", markup)
    markup = _SUBIR.sub(" ", markup)
    markup = _promote_ordinal_legal_boundaries(markup)

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)
    attribution = _attribution_for(boe_url)

    units: list[PreprocessUnit] = []
    for anchor, article_markup in _segments(markup):
        heading, body = _heading_and_body(article_markup)
        if not body and not heading:
            continue
        # The heading rides as the unit title (which render_text emits as the
        # "# heading" line), so the unit text is the article body alone. When
        # an article has a heading but no body, the heading is the only text.
        text = body or heading
        if not text:
            continue
        anchor = anchor or _anchor_from_heading(heading)
        units.append(
            PreprocessUnit(
                text=text,
                title=heading or None,
                section=heading or None,
                anchor=anchor or None,
            ),
        )

    # A file with no <h5 class="articulo"> (a single-article slice whose body
    # is bare parrafos, or an atypical fragment) still yields one unit from
    # the whole stripped document so nothing is silently dropped. A full BOE
    # page reaching here was clipped to its legal-text container, so that
    # container's fragment anchors the unit; a bare slice supplies none.
    if not units:
        whole = render_normative_prose(markup)
        if whole:
            units.append(PreprocessUnit(text=whole, anchor=container_anchor or None))

    units = _with_derived_annex_fragments(
        units,
        include_iva_annual_fragments=source.name == "orden-hac-1347-2024.html",
    )
    units.extend(_m303_annual_orden_table_units(source))

    if not units:
        return [
            PreprocessOutput(
                source_kind=SourceDocumentKind.NORMATIVES_HTML,
                status=ExtractionStatus.EMPTY,
                source_relpath=relpath,
                source_sha256=digest,
                preprocessor_id=HTML_EXTRACTOR_ID,
                preprocessor_version=HTML_EXTRACTOR_VERSION,
                attribution=attribution,
                units=(),
            ),
        ]

    groups = split_units_by_budget(units)
    return [
        PreprocessOutput(
            source_kind=SourceDocumentKind.NORMATIVES_HTML,
            status=ExtractionStatus.OK,
            source_relpath=relpath,
            source_sha256=digest,
            preprocessor_id=HTML_EXTRACTOR_ID,
            preprocessor_version=HTML_EXTRACTOR_VERSION,
            attribution=attribution,
            units=tuple(group),
        )
        for group in groups
    ]


def extract_html(source: Path, *, repo_root: Path) -> list[Path]:
    """Extract a normatives HTML file and write its committed sidecar pair(s).

    Args:
        source: Path to the ``.html`` file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        The list of ``*.extracted.md`` text-sidecar paths written (one per
        part), in part order.

    Raises:
        PreprocessSidecarError: If a sidecar cannot be written.
    """
    outputs = build_outputs(source, repo_root=repo_root)
    return write_part_sidecars(source, outputs)
