"""Shared record projection for the Pagefind injection tests.

Underscore-prefixed so it is never collected as a test module. Holds the one
helper both lanes need: the concept-card subset projected into search records.
The lane-specific fixtures stay with their own modules.
"""

from __future__ import annotations

from ..pagefind_inject import _Materialised
from ..terminology._concept_cards import project_concept_cards
from ..terminology.unified_record import to_search_record


def concept_records() -> _Materialised:
    """Project the concept-card subset into materialised search records."""
    cards, _ = project_concept_cards()
    records = [to_search_record(card) for card in cards]
    return _Materialised(records=records, concepts=len(cards))
