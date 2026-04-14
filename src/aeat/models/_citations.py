"""Strict pydantic model for a single legal citation.

A :class:`LegalCitation` ties a modelo to a concrete article of a
normative corpus entry, with a curated Spanish quotation preserved
verbatim from the research doc. The model is strict/frozen/extra=forbid
per the modelo-inventory ADR.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from aeat.models._categories import LegalCitationSource


class LegalCitation(BaseModel):
    """A single legal citation backing a :class:`ModeloMetadata` entry.

    Attributes:
        source: The :class:`LegalCitationSource` describing the
            provenance of the citation (ley, real decreto, ...).
        article: The article identifier within the source (e.g.
            ``"30"``, ``"primero"``). Never empty.
        url: Optional BOE / Manual práctico URL pointing at the
            article. Stored for display only.
        quoted_text_es: Verbatim Spanish quotation of the article
            summary. Must be non-empty after stripping whitespace.
        retrieval_date: The date on which ``quoted_text_es`` was
            captured from the source corpus.
        is_curated_summary: Whether ``quoted_text_es`` is a
            project-curated summary rather than the literal BOE
            article body. Set to ``True`` for every v1 citation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source: LegalCitationSource
    article: str = Field(min_length=1)
    url: HttpUrl | None = None
    quoted_text_es: str
    retrieval_date: date
    is_curated_summary: bool

    @field_validator("quoted_text_es")
    @classmethod
    def _quoted_text_not_blank(cls, value: str) -> str:
        """Reject empty / whitespace-only ``quoted_text_es`` values."""
        if not value.strip():
            raise ValueError("quoted_text_es must not be empty or whitespace-only")
        return value
