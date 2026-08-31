"""Registry-build gate: a layout-authority claim must be backed by a layout.

``evidence_tier = "layout_authority"`` asserts that the cited document is where
the record layout comes from. Nothing verified that. The tier was a typed field
whose truth condition lived only in the author's head, so a document that
established a modelo and scheduled it -- and said nothing whatsoever about its
layout -- could carry the claim, at ``review_status = "reviewed"``, indefinitely.

The population that exposed it: a family of hand-transcribed BOE excerpts under
``corpus/normatives/html/``, each two articles long (approval plus filing
deadline), each declaring layout authority, and each closing with its own
sentence "Pending operator re-verification." Several of them *point at* the
layout without containing it -- Modelo 490's reads "que figura en el anexo de
esta orden", naming the annex it omits. A reader following the tier to that file
learns that the modelo exists and when it is due, and nothing about how to
render a record.

What is checked, and why it is the annex
----------------------------------------

An orden approving a modelo carries its layout in the ANNEX; the articles carry
the obligation, the deadline and the presentation channel. So the honest minimum
for a layout-authority claim over a norm-text HTML is that the file contains the
annex SECTION, or names record-layout structure directly -- not that it merely
mentions the word "anexo" in a cross-reference to a part it does not include.

Three acceptance signals, any one of which satisfies the claim:

* an annex HEADING -- ``<h*>ANEXO ...`` in BOE's own markup, or a standalone
  ``ANEXO`` block;
* the phrase "diseño de registro(s)", which is the instrument naming the layout
  it publishes;
* positional-table vocabulary -- a "Posiciones" column header or a "Tipo de
  registro" record discriminator.

The negative lookbehind on ``posiciones`` is load-bearing: every BOE document
opens with "I. DISPOSICIONES GENERALES", so a bare substring match would accept
every stub in the corpus and the gate would pass vacuously while reporting
nothing. That is the exact shape of a check that looks like it works.

Scope, and why it is narrow
---------------------------

Only HTML under ``corpus/normatives/`` is examined. A design workbook, manual
PDF, XSD or ``.properties`` dictionary under ``corpus/aeat_official/`` IS the
layout by construction and carries no prose to scan; asserting a text predicate
over a binary would refuse honest sources for being unreadable rather than for
being wrong.

Size is corroboration, never the test. Measured over this corpus on 2026-08-15,
the partition this predicate produces is also cleanly separated by size --
every refused file is at most 2308 bytes, every accepted one at least 32119 --
which is the same order-of-magnitude gap ``_corpus_catalogue.py``'s
``_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR`` records from an independent
measurement. Two signals, one partition, nothing in between. The gate still
refuses on content, because size alone would misclassify a genuine layout that
happens to be terse and would accept a long document that says nothing.

See Also:
    :func:`cadrumo.domain.calculations.registry.corpus_catalogue._validate_source_corpus_tier_declaration`
        The sibling check that verifies a declared ``corpus_tier`` against the
        bundled file rather than trusting the declaration.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ._source_file_text import read_source_file_text
from .schema_references import SourceReference

#: The norm-text tree whose files are prose an author can under-transcribe. A
#: layout artefact outside it is the layout itself and is not scanned.
_NORMATIVES_HTML_PREFIX: Final = "corpus/normatives/"

#: An annex heading in BOE's own markup, where the layout lives.
_ANNEX_HEADING: Final = re.compile(r"<h[1-6][^>]*>\s*(?:<[^>]+>\s*)*anexos?\b", re.IGNORECASE)

#: A standalone ANEXO block, for dumps that do not wrap it in a heading tag.
_ANNEX_BLOCK: Final = re.compile(r"(?:^|>)\s*ANEXOS?\b[^<\n]{0,80}\s*(?:<|$)", re.MULTILINE)

#: The instrument naming the layout it publishes, or positional-table
#: vocabulary. ``(?<!dis)`` keeps "DISPOSICIONES GENERALES" -- present in every
#: BOE document, including every stub -- from satisfying the check.
_LAYOUT_VOCABULARY: Final = re.compile(
    r"dise\w*\s+de\s+registros?|(?<!dis)posiciones\b|tipo\s+de\s+registro",
    re.IGNORECASE,
)


def _carries_layout_content(raw: str) -> bool:
    if _ANNEX_HEADING.search(raw) or _ANNEX_BLOCK.search(raw):
        return True
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return bool(_LAYOUT_VOCABULARY.search(text))


def validate_layout_authority_content(
    sources: Mapping[str, SourceReference],
    *,
    source_root: Path | None,
) -> list[str]:
    """Return one failure per layout-authority claim its own file cannot support.

    Keyed per source ID rather than per file: the claim belongs to the
    declaration, so two IDs citing one under-transcribed excerpt are two
    unbacked claims and both are named. A file that cannot be read from this
    root is skipped rather than reported -- an unreachable corpus is an
    installation question that :func:`verify_source_file` already owns, and
    reporting it here would put a second count into circulation for it.

    Args:
        sources: The registry source catalogue, keyed by source ID.
        source_root: Repository root for resolving ``corpus_path``; when None,
            no file is reachable and the check yields nothing.

    Returns:
        Accumulated diagnostics; empty when every layout-authority claim over a
        norm-text HTML is backed by annex or layout content.
    """
    if source_root is None:
        return []
    failures: list[str] = []
    for source_id, source in sorted(sources.items()):
        if source.evidence_tier != "layout_authority":
            continue
        corpus_path = source.corpus_path
        if not corpus_path.startswith(_NORMATIVES_HTML_PREFIX) or not corpus_path.endswith(".html"):
            continue
        raw = read_source_file_text(source_root, source)
        if raw is None or _carries_layout_content(raw):
            continue
        failures.append(
            f"source {source_id!r} declares evidence_tier='layout_authority' but its bundled file "
            f"{corpus_path!r} ({source.bytes} bytes) carries no annex section and no record-layout "
            "vocabulary, so it cannot be where this modelo's layout comes from. An orden publishes "
            "its layout in the ANNEX; the articles carry the obligation, the deadline and the "
            "presentation channel. A file that only names the annex -- 'que figura en el anexo de "
            "esta orden' -- points at the layout instead of containing it. Either bundle the "
            "instrument's full text including its annex, or retier this source to the evidence it "
            "actually is (official_source_guidance for an approval-and-deadline excerpt) and cite a "
            "real layout authority for the layout",
        )
    return failures


__all__ = ["validate_layout_authority_content"]
