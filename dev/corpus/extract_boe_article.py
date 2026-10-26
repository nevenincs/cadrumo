"""Slice one BOE consolidated article out of a fetched whole-document page.

``fetch_boe_normative.py`` acquires two shapes: the whole consolidated
document (``fetch_normative``) and a single article via the open-data XML
endpoint (``fetch_article``). Neither produces the THIRD shape this corpus
actually ships in bulk -- roughly 180 files under ``corpus/normatives/html/``
are single-article HTML *excerpts*, header-commented with their BOE
permalink, sliced out of a whole-document ``act.php`` page.

That shape had no acquisition tool at all. Every excerpt was hand-sliced by
copying one ``<div class="bloque" id="aXX">...</div>`` block out of a fetched
page, and the hand process had one systematic defect: it is easy to copy up
to the WRONG closing ``</div>`` when scanning thousands of lines of BOE
markup by eye, because a full page nests one ``<div class="bloque">`` per
block with no visual distinction between "this article's own close" and "the
next block's open". A ``just audit-all`` security sweep found the result: 46
of ~180 excerpts carried a dangling ``</div>`` plus leaked-in boilerplate
(the version-selector ``<form>``, the "Subir" link, and the START of the next
block) trailing past the article's real end -- syntactically invalid HTML,
and in a handful of cases the next section's own heading had bled into the
CURRENT article's extracted grounding text as a result.

This module is the missing tool. Given an already-fetched, already-validated
whole-document page (``fetch_normative``'s output, or any bundled page that
carries the same ``act.php`` shape) and a block anchor, it finds the block's
TRUE matching close tag by tracking ``<div>`` nesting depth -- not by
pattern-matching a "looks like the end" marker -- so the boundary is correct
by construction rather than by careful copying. It is a pure function of the
source bytes and the block id: re-running it against the same source and
block always yields byte-identical output, so a re-extraction is a
reproducibility check rather than a fresh judgment call.

Composes with the whole-document fetcher rather than duplicating it:
``extract_article`` trusts that its caller already ran ``fetch_normative``'s
per-fieldset "serves the text in force" invariant over the WHOLE document
(which covers every block, including the one being sliced), so it does not
re-derive version selection here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_ROOT))

_CORPUS: Final[Path] = _ROOT / "src/cadrumo/_data/corpus/normatives/html"

#: Every div open/close tag, in document order, so a block's true nesting
#: depth can be tracked from its own opening tag to its own matching close.
_DIV_OPEN_OR_CLOSE = re.compile(r"<div\b|</div\s*>", re.IGNORECASE)

#: The per-block version-selector widget (radio buttons choosing a historical
#: redaction). Extraction-irrelevant BOE UI chrome: the production extractor
#: (``dev.docs.preprocess.normatives_html``) strips it with the identical pattern before
#: splitting articles, so dropping it here changes nothing about what a
#: reader or a grounding citation ever sees -- it only keeps the raw excerpt
#: file itself clean and free of the exact boilerplate that caused the
#: original defect.
_VERSION_SELECTOR_FORM = re.compile(
    r"""<form\b(?=[^>]*\bclass=["']lista\ formBOE["'])[^>]*>.*?</form>""",
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

#: The article/annex heading, matching the same class set the production
#: extractor splits on, so the derived "Excerpt: ..." header line always
#: names the same unit the extractor will later carve out.
_UNIT_HEADING = re.compile(
    r"""<h[1-6]\b(?=[^>]*\bclass=["'][^"']*\b(?:articulo|anexo|anexo_num)\b[^"']*["'])[^>]*>
        (?P<title>.*?)
        </h[1-6]\s*>""",
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)
_TAG = re.compile(r"<[^>]+>")
_UTF_8: Final[str] = "utf-8"


class ArticleExtractionError(RuntimeError):
    """A block cannot be shown to slice into a clean, self-contained excerpt."""


def _block_open_tag(markup: str, *, block: str) -> re.Match[str]:
    pattern = re.compile(
        rf"""<div\b(?=[^>]*\bclass=["']bloque["'])(?=[^>]*\bid=["']{re.escape(block)}["'])[^>]*>""",
        re.IGNORECASE,
    )
    match = pattern.search(markup)
    if match is None:
        raise ArticleExtractionError(f'no <div class="bloque" id="{block}"> found in the source document')
    return match


def _matching_close_tag(markup: str, *, start: int) -> re.Match[str]:
    """Return the ``</div>`` match that closes the div opened just before ``start``.

    Tracks nesting depth from 1 (the block's own opening tag, already
    consumed by the caller) rather than returning the very next ``</div>``:
    a block that itself nests a sub-``<div>`` -- BOE's structure never does
    this for a ``bloque``, but nothing enforces that it never will -- must not
    fool the boundary the way the hand-curated files were fooled by trusting
    "the next closing tag looks about right".
    """
    depth = 1
    for tag in _DIV_OPEN_OR_CLOSE.finditer(markup, start):
        if tag.group(0).startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return tag
    raise ArticleExtractionError("the block's opening <div> is never closed in the source document")


def _excerpt_heading_line(body: str, *, block: str) -> str:
    """Derive the header comment's ``Excerpt: ...`` line from the block's own heading."""
    heading_match = _UNIT_HEADING.search(body)
    if heading_match is None:
        return f"Excerpt: block {block} only."
    title = _TAG.sub("", heading_match.group("title")).strip()
    return f"Excerpt: {title} only." if title else f"Excerpt: block {block} only."


def extract_article(document_markup: str, *, document_id: str, block: str) -> str:
    """Slice one block's own HTML out of a whole consolidated-document page.

    Args:
        document_markup: The full ``act.php`` page, as ``fetch_normative`` wrote it.
        document_id: The BOE identifier the page belongs to, e.g. ``BOE-A-1992-28740``.
        block: The block anchor to slice out, e.g. ``a90`` or ``a163octovicies``.

    Returns:
        The canonical excerpt: a header comment naming the document and its
        permalink, followed by the block's own content with the
        version-selector widget stripped and LF-only line endings. Byte-for-
        byte deterministic given the same inputs.

    Raises:
        ArticleExtractionError: If the block is absent, its opening ``<div>``
            is never closed, or it is empty once the version-selector widget
            is stripped.
    """
    opening = _block_open_tag(document_markup, block=block)
    closing = _matching_close_tag(document_markup, start=opening.end())
    body = document_markup[opening.end() : closing.start()]
    body = _VERSION_SELECTOR_FORM.sub("", body)
    body = body.strip("\n")
    if not body.strip():
        raise ArticleExtractionError(f"block {block!r} is empty once the version-selector widget is stripped")

    permalink = f"https://www.boe.es/buscar/act.php?id={document_id}#{block}"
    header = (
        "<!--\n"
        "Official BOE consolidated source excerpt.\n"
        f"Document: {document_id}\n"
        f"Permalink: {permalink}\n"
        f"{_excerpt_heading_line(body, block=block)}\n"
        "-->\n"
    )
    return header + body + "\n"


def write_article_excerpt(
    *,
    source: Path,
    document_id: str,
    block: str,
    destination_name: str,
    destination_root: Path = _CORPUS,
) -> Path:
    """Slice one article from an already-fetched whole document and write it.

    ``source`` must already be a validated ``fetch_normative`` payload (or a
    bundled whole-document page of the same shape): this function trusts the
    whole-document per-fieldset "serves the text in force" invariant was
    already enforced upstream, and does not re-derive version selection per
    block. The bytes are written and read back before the path is returned,
    matching ``fetch_normative``'s own read-back-verify convention.

    Args:
        source: Path to the whole consolidated document.
        document_id: The BOE identifier the page belongs to.
        block: The block anchor to slice out.
        destination_name: Filename under ``corpus/normatives/html/``.
        destination_root: Injected so tests can write to a scratch directory
            instead of the real bundled corpus; defaults to it for real use.

    Returns:
        The written path.

    Raises:
        ArticleExtractionError: If the block cannot be sliced cleanly, or the
            read-back does not match what was written.
    """
    markup = source.read_text(encoding=_UTF_8)
    excerpt = extract_article(markup, document_id=document_id, block=block)
    destination = destination_root / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = excerpt.encode(_UTF_8)
    destination.write_bytes(data)
    if destination.read_bytes() != data:
        raise ArticleExtractionError(f"read-back of {destination} does not match the sliced bytes")
    return destination
