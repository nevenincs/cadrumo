"""Sizing for the co-location geometry question: can the pipeline segment a column?

The co-location ceiling is zero because a two-column invoice header reaches the
resolver as one line: the text extractor emits reading order, and the visual gap
between the issuer block and the recipient block leaves no character behind.
The obvious remedy is to preserve spatial information, which is a pipeline-shaped
change rather than a resolver-shaped one, so it is SIZED here before anyone
commits to it. **This module measures; it changes no pipeline.**

Every figure is re-derived from the corpus on demand rather than written down,
for the reason the rest of this package exists: a size quoted in prose goes stale
silently, and a stale size is worse than none because it is still actionable.

Three questions, and the third narrows the other two before they are asked.

**Can the extractors emit coordinates at all?** For the text-layer path, yes:
pdfplumber exposes a per-word box, and on a real two-column invoice the two
party labels sit at opposite ends of the page. For the vision path, no -- it
returns a model's text and has no coordinates to give. So geometry is available
for exactly one of the two prose transports.

**What would preserving it cost?** :func:`geometry_payload_ratio` measures the
serialized size of a minimal per-word box set against the text it accompanies.
Both the in-memory transcription and its cache entry forbid extra fields, and
the cache namespace is versioned and FINANCIAL, so preserving geometry is a
schema change on two strict models plus a namespace bump that invalidates every
cached transcription -- and re-reading is free on the text-layer path and a paid
model call on the vision path, which is the path the cache exists for.

**Is the scope smaller than it looks?** Yes, and this is the finding that should
be read first. Co-location is never consulted for a structured record, for two
independent reasons and the stronger one is structural: the draft path RETURNS
on a structured shape before grounding is reached, and the structured builder
calls neither the grounding entry point nor the co-location resolver nor the
stamp. There is nothing to co-locate against either, because a structured shape
is read exactly and never transcribed. The second reason is the guard that would
catch such an envelope if one arrived by another route --
``ATTRIBUTION_ESTABLISHING_ORIGINS`` in
``cadrumo.application.ledger.party_attribution``, which carries
``EXACT_STRUCTURED`` and clears the stamp by origin.

Naming the weaker one alone would misdescribe the mechanism: it governs whether
a value is STAMPED, which is a different question from whether co-location is
CONSULTED. Only prose is in scope, and within prose only the text-layer
transport can carry coordinates.

**And the geometry may not need to be preserved at all.**
:func:`column_aware_rendering_partitions` measures the alternative: consume the
coordinates at extraction time to emit a column-aware reading order, and discard
them. The resolver is unchanged, no model gains a field, no namespace is bumped
and no payload grows. The row asked whether the pipeline can PRESERVE geometry;
this measures whether it needs to.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from cadrumo.application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from cadrumo.application.ledger.evidence_draft import FieldProvenance, InvoiceDraft
from cadrumo.application.ledger.party_colocation import party_regions
from cadrumo.core import LOCAL_TRANSPORT_LABEL, FieldGroundingOutcome, FieldOrigin

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8

__all__ = [
    "ColumnSegmentationSize",
    "column_aware_rendering_partitions",
    "geometry_payload_ratio",
    "render_page_text",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

#: Words whose baselines fall within this many points are one visual row. Chosen
#: to exceed ordinary baseline jitter without merging adjacent printed lines; it
#: is a probe constant, never a tuned threshold, because the only two-column
#: documents available to tune against share one template.
_ROW_TOLERANCE_POINTS = 3.0


class ColumnSegmentationSize(BaseModel):
    """One document's before/after under column-aware rendering.

    Attributes:
        doc_id: The corpus document.
        partitions_in_reading_order: Whether the resolver partitions the text as
            the extractor emits it today.
        partitions_column_aware: Whether it partitions when the same words are
            rendered column by column.
    """

    model_config = _STRICT

    doc_id: str
    partitions_in_reading_order: bool
    partitions_column_aware: bool


def _transcription(text: str) -> DocumentTranscription:
    """Return a probe transcription naming its own source, never a real reader."""
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="0" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="geometry-sizing-probe",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )


def _draft(supplier: str, customer: str) -> InvoiceDraft:
    """Return the minimal draft carrying one role-evidence excerpt per identity."""

    def envelope(field: str, excerpt: str) -> FieldProvenance:
        return FieldProvenance(
            field=field,
            origin=FieldOrigin.TEXT_LAYER,
            grounding=FieldGroundingOutcome.UNANCHORED,
            anchor=excerpt,
            role_evidence=excerpt,
        )

    return InvoiceDraft(
        provenance=(envelope("supplier_tax_id", supplier), envelope("customer_tax_id", customer)),
    )


def render_page_text(words: Sequence[Mapping[str, Any]], *, split_x: float, column_aware: bool) -> str:
    """Render extracted words as page text, optionally column by column.

    ``column_aware=False`` reproduces what the pipeline emits today: words
    grouped by visual row and read left to right across the whole page, so a
    two-column header becomes one line carrying both parties.

    ``column_aware=True`` groups by row AND by side of ``split_x``, so each
    column's rows are emitted separately. Nothing about the words changes; only
    the order they are written out in.

    Args:
        words: Per-word boxes, each carrying ``text``, ``x0`` and ``top``.
        split_x: The page x-coordinate separating the two columns.
        column_aware: Whether to segment by column before rendering.

    Returns:
        The rendered page text, one visual row per line.
    """
    rows: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for word in words:
        row = round(float(word["top"]) / _ROW_TOLERANCE_POINTS)
        column = int(float(word["x0"]) >= split_x) if column_aware else 0
        rows.setdefault((row, column), []).append(word)
    return "\n".join(
        " ".join(str(word["text"]) for word in sorted(group, key=lambda w: float(w["x0"])))
        for _key, group in sorted(rows.items(), key=lambda item: (item[0][0], item[0][1]))
    )


def column_aware_rendering_partitions(
    *,
    doc_id: str,
    words: Sequence[Mapping[str, Any]],
    page_width: float,
    supplier_label: str,
    customer_label: str,
) -> ColumnSegmentationSize:
    """Return whether column-aware rendering alone lets the resolver partition.

    Drives the real :func:`~application.ledger.party_colocation.party_regions` in both renderings,
    so this cannot drift into its own idea of what partitioning means. The split
    is the page midpoint rather than a fitted boundary: a fitted one would be
    tuned on the only layout available and would report its own tuning.

    Args:
        doc_id: The corpus document, carried onto the result.
        words: Per-word boxes from the extractor.
        page_width: Page width in points, used for the midpoint split.
        supplier_label: The printed label anchoring the issuer side.
        customer_label: The printed label anchoring the recipient side.

    Returns:
        The before/after pair for this document.
    """
    draft = _draft(supplier_label, customer_label)
    split_x = page_width / 2
    return ColumnSegmentationSize(
        doc_id=doc_id,
        partitions_in_reading_order=bool(
            party_regions(
                draft=draft,
                transcription=_transcription(render_page_text(words, split_x=split_x, column_aware=False)),
            ),
        ),
        partitions_column_aware=bool(
            party_regions(
                draft=draft,
                transcription=_transcription(render_page_text(words, split_x=split_x, column_aware=True)),
            ),
        ),
    )


def geometry_payload_ratio(words: Sequence[Mapping[str, Any]], *, text: str) -> float:
    """Return serialized minimal-geometry bytes divided by text bytes.

    The cost of PRESERVING geometry rather than consuming it. Minimal on
    purpose -- three rounded numbers per word, no font, no page, no confidence --
    so the figure is a floor on the payload growth rather than an estimate of
    it. What it grows is a FINANCIAL record in encrypted storage.

    Args:
        words: Per-word boxes.
        text: The transcription text the geometry would accompany.

    Returns:
        The ratio, or ``0.0`` when there is no text to compare against.
    """
    payload = json.dumps(
        [[round(float(w["x0"]), 1), round(float(w["x1"]), 1), round(float(w["top"]), 1)] for w in words],
        separators=(",", ":"),
    )
    text_bytes = len(text.encode(_UTF_8))
    return len(payload.encode(_UTF_8)) / text_bytes if text_bytes else 0.0
