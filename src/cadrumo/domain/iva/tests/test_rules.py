"""IVA citation schema invariants."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.citation_grounding import CitationGrounding
from ..schema import IvaCitation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_iva_citation_rejects_a_verified_claim_with_no_quotation() -> None:
    with pytest.raises(ValidationError, match="must carry its verbatim quotation"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "   ",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )


def test_iva_citation_rejects_an_unresolved_claim_with_no_reason() -> None:
    """Unresolved without a reason is indistinguishable from unchecked."""
    with pytest.raises(ValidationError, match="must record WHY"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "",
                "grounding": CitationGrounding.UNRESOLVED,
                "unresolved_reason": "   ",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )


def test_iva_citation_rejects_an_unresolved_claim_that_carries_a_quotation() -> None:
    """Text parked under unresolved grounding is never read against the corpus.

    A candidate quotation stored here would read as evidence to anyone printing
    the field while the record itself says it has none.
    """
    with pytest.raises(ValidationError, match="must not carry a quotation"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "El tipo impositivo sera el 21 por ciento",
                "grounding": CitationGrounding.UNRESOLVED,
                "unresolved_reason": "candidate text that did not match the bundled corpus",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )
