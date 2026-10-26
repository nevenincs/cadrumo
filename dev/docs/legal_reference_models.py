"""Typed legal catalogue rows, rendered pages, and generation inventories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class LegalReferenceError(RuntimeError):
    """Raised when the legal reference surface cannot be rendered safely."""


@dataclass(frozen=True)
class LegalProvisionRecord:
    """One authored ``[legal.<id>]`` catalogue row.

    The record keeps catalogue values typed and unchanged.  Optional fields
    remain absent rather than being filled with generated or inferred prose.
    """

    legal_id: str
    kind: str
    document_id: str
    corpus_ref: str
    permalink: str
    authority: str | None = None
    evidence_tier: str | None = None
    article: str | None = None
    section: str | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: str | None = None
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    required_text: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegalPage:
    """One generated document page and its target/grounding inventory."""

    document_id: str
    #: The reader-facing designation of the instrument this page renders.
    instrument: str
    output_relpath: str
    rst: str
    #: Anchors actually emitted; law-level rows without a fragment have none.
    anchors: tuple[str, ...]
    #: ``legal_id -> site-relative page or page+anchor target``.
    targets: dict[str, str]
    #: ``legal_id -> emitted anchor``; ``None`` means page-level target only.
    anchor_by_id: dict[str, str | None]
    #: ``legal_id -> authored BOE permalink`` rendered on the destination.
    grounding_by_id: dict[str, str]


@dataclass(frozen=True)
class LegalReferenceResult:
    """Summary of one deterministic legal-reference generation pass."""

    pages: tuple[LegalPage, ...]
    index_relpath: str
    page_count: int
    provision_count: int
    grounding_count: int
    #: ``legal_id -> the exact target rendered for that provision``.
    targets: dict[str, str]
    #: ``legal_id -> anchor`` or ``None`` for a page-level law entry.
    anchors: dict[str, str | None]

    @property
    def document_count(self) -> int:
        """Alias for the number of document pages, useful to later gates."""
        return self.page_count

    @property
    def legal_links(self) -> int:
        """Alias matching the sibling reference-generator summaries."""
        return self.grounding_count
