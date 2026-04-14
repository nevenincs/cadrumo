"""Unit tests for :class:`aeat.models._citations.LegalCitation`."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from aeat.models._categories import LegalCitationSource
from aeat.models._citations import LegalCitation

pytestmark = pytest.mark.unit


def _make(**overrides: object) -> LegalCitation:
    base: dict[str, object] = {
        "source": LegalCitationSource.LEY,
        "article": "29",
        "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
        "quoted_text_es": "Enumera las obligaciones tributarias formales.",
        "retrieval_date": date(2026, 4, 13),
        "is_curated_summary": True,
    }
    base.update(overrides)
    return LegalCitation.model_validate(base)


def test_happy_path_construction() -> None:
    """A well-formed citation validates cleanly."""
    citation = _make()
    assert citation.source is LegalCitationSource.LEY
    assert citation.article == "29"
    assert citation.is_curated_summary is True


def test_rejects_empty_quoted_text_es() -> None:
    """Empty ``quoted_text_es`` raises :class:`ValidationError`."""
    with pytest.raises(ValidationError):
        _make(quoted_text_es="")


def test_rejects_whitespace_only_quoted_text_es() -> None:
    """Whitespace-only ``quoted_text_es`` raises :class:`ValidationError`."""
    with pytest.raises(ValidationError):
        _make(quoted_text_es="   \n\t")


def test_accepts_is_curated_summary_true() -> None:
    """`is_curated_summary=True` is the v1 default and must pass."""
    assert _make(is_curated_summary=True).is_curated_summary is True


def test_http_url_is_accepted() -> None:
    """HTTP(S) URLs are coerced to :class:`pydantic.HttpUrl`."""
    citation = _make(url="https://www.boe.es/buscar/doc.php?id=BOE-A-2003-23186")
    assert str(citation.url).startswith("https://www.boe.es/")


def test_extra_forbid() -> None:
    """Unknown keys are rejected."""
    with pytest.raises(ValidationError):
        LegalCitation.model_validate(
            {
                "source": LegalCitationSource.LEY,
                "article": "29",
                "url": None,
                "quoted_text_es": "texto",
                "retrieval_date": date(2026, 4, 13),
                "is_curated_summary": True,
                "unexpected": "boom",
            }
        )
