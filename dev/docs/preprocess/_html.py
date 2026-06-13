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

Attribution is pulled from the sibling normatives ``manifest.json``
(``boe_url`` / ``boe_id``) where one exists, composing the per-article
permalink with the ``#aN`` anchor; single-article slices with no manifest
fall back to the standing BOE/AEAT attribution. Either way the
reuse-with-attribution obligation is honoured.

This is the production normatives preprocessor; the ``_example.py`` HTML stub
remains a worked example only. When the upstream ``vaultspec-rag``
preprocess-hook lands, this module re-targets the upstream sink and the
committed sidecars are retired; ``PreprocessOutput`` is the
forward-compatible precursor that makes that migration mechanical.
"""

from __future__ import annotations

import html as html_entities
import json
import re
from pathlib import Path
from typing import Final

from ._parts import split_units_by_budget, write_part_sidecars
from ._schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from ._sidecar import sha256_of

#: Stable id of this extractor, recorded in every sidecar's provenance.
HTML_EXTRACTOR_ID = "normatives-html"

#: Version of this extractor; part of the cache identity. Bump when the
#: rendering changes so a regeneration is distinguishable from a no-op.
HTML_EXTRACTOR_VERSION = "1.0"
_UTF_8: Final[str] = "utf-8"

#: Standing BOE/AEAT attribution used when no manifest pins a permalink.
_BASE_ATTRIBUTION = (
    "Source: Boletin Oficial del Estado (BOE) / Agencia Estatal de Administracion Tributaria. Reused with attribution."
)

# The BOE legal text lives inside <div id="textoxslt">; the page footer
# (<div id="pie">) carries site chrome (Aviso legal, Mapa, the AEBOE postal
# address) that must never ride into the last article's body. The content is
# clipped to the textoxslt container before splitting.
_CONTENT_START = re.compile(r'<div[^>]*id="textoxslt"[^>]*>', re.IGNORECASE)
_FOOTER_START = re.compile(r'<div[^>]*id="pie"[^>]*>', re.IGNORECASE)

# Block-level noise stripped before article splitting: jurisprudence forms,
# scripts, styles, and the per-article "Subir" (back-to-top) nav paragraph.
_FORM = re.compile(r"<form\b.*?</form>", re.IGNORECASE | re.DOTALL)
_SCRIPT = re.compile(r"<script\b.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE = re.compile(r"<style\b.*?</style>", re.IGNORECASE | re.DOTALL)
_SUBIR = re.compile(r'<p[^>]*class="linkSubir"[^>]*>.*?</p>', re.IGNORECASE | re.DOTALL)

# The article heading delimiter and the bloque markers. The anchor matcher
# keeps only article (#aN) anchors for the unit anchor; the marker matcher
# strips every "[Bloque N: #...]" navigation marker (article, titulo,
# capitulo, etc.) from the body text - none of them are article prose.
_ARTICULO_SPLIT = re.compile(r'<h5[^>]*class="articulo"[^>]*>', re.IGNORECASE)
_BLOQUE_ANCHOR = re.compile(r"\[Bloque\s+\d+:\s*(#a[\w-]+)\]", re.IGNORECASE)
_BLOQUE_MARKER = re.compile(r"\[Bloque\s+\d+:[^\]]*\]", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def _clip_to_content(markup: str) -> str:
    """Clip markup to the BOE legal-text container, dropping page chrome.

    A full BOE page wraps its legal text in ``<div id="textoxslt">`` and ends
    with a ``<div id="pie">`` footer (site navigation and the AEBOE postal
    address). The footer must never ride into the last article, so the markup
    is clipped from the content-start marker (when present) up to the footer
    marker. A single-article slice has neither marker and is returned whole.
    """
    start = _CONTENT_START.search(markup)
    if start is not None:
        markup = markup[start.end() :]
    footer = _FOOTER_START.search(markup)
    if footer is not None:
        markup = markup[: footer.start()]
    return markup


def _strip_tags(markup: str) -> str:
    """Strip remaining tags and collapse whitespace into readable prose.

    Runs after the block-level noise removal: drops every residual tag,
    collapses runs of spaces/tabs, and squeezes three-or-more blank lines to
    a paragraph break so the article reads as clean text.
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
    """Split markup into ``(anchor, article_markup)`` pairs per article.

    The text before the first ``<h5 class="articulo">`` (document metadata
    and the TOC link farm) is discarded. Each article's anchor is read from
    the ``[Bloque N: #aN]`` marker in the tail of the preceding segment when
    present, else the empty string.
    """
    parts = _ARTICULO_SPLIT.split(markup)
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


def _heading_and_body(article_markup: str) -> tuple[str, str]:
    """Split one article segment into ``(heading, body)`` clean text.

    The segment begins immediately after the opening ``<h5 ...>`` tag, so the
    heading runs up to the closing ``</h5>`` and the body is everything
    after, with block-level noise already removed by the caller.
    """
    head_end = article_markup.lower().find("</h5>")
    if head_end == -1:
        return "", _strip_tags(article_markup)
    heading = _strip_tags(article_markup[:head_end])
    body = _strip_tags(article_markup[head_end + len("</h5>") :])
    return heading, body


def _document_boe_url(source: Path) -> str:
    """Return the document BOE permalink base from the sibling manifest.

    The manifest is ``<stem>.json`` one directory above the ``html/`` folder
    (``normatives/<stem>.json`` for ``normatives/html/<stem>.html``). Returns
    the empty string when no manifest or ``boe_url`` is present.
    """
    manifest_path = source.parent.parent / f"{source.stem}.json"
    if not manifest_path.is_file():
        return ""
    try:
        manifest = json.loads(manifest_path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(manifest, dict):
        return ""
    url = manifest.get("boe_url")
    return url.strip() if isinstance(url, str) else ""


def _attribution_for(source: Path, boe_url: str) -> str:
    """Compose the attribution string for a normatives document."""
    if boe_url:
        return f"{_BASE_ATTRIBUTION} Official source: {boe_url}"
    return _BASE_ATTRIBUTION


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Extract a BOE normatives HTML file into one or more records.

    One :class:`PreprocessUnit` per article (split on ``<h5
    class="articulo">``), titled by the article heading and anchored to its
    ``#aN`` permalink fragment. A file with no article delimiter (a stray
    fragment) extracts to a single whole-document unit. When the combined
    text would exceed the per-sidecar byte budget the units are grouped so
    each :class:`PreprocessOutput` renders under the walker's file cap.

    Args:
        source: Path to the ``.html`` file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        A list of validated records (one per sidecar pair to write).
    """
    markup = source.read_text(encoding=_UTF_8)
    markup = _clip_to_content(markup)
    markup = _SCRIPT.sub(" ", markup)
    markup = _STYLE.sub(" ", markup)
    markup = _FORM.sub(" ", markup)
    markup = _SUBIR.sub(" ", markup)

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)
    boe_url = _document_boe_url(source)
    attribution = _attribution_for(source, boe_url)

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
    # the whole stripped document so nothing is silently dropped.
    if not units:
        whole = _strip_tags(markup)
        if whole:
            units.append(PreprocessUnit(text=whole))

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
