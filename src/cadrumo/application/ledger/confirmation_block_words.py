"""The sentence the evidence review serves for each reason a read draft cannot be confirmed yet.

A frontend shows these sentences as served and words no reason of its own. A
reason's sentence is worded from its reason alone: it carries no party, amount
or document text. A finding's sentence quotes the figures and printed text its
check names, from the values the finding carries.
"""

from __future__ import annotations

from typing import Final

from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.draft_discrepancy import DraftFindingWording
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ..operations.error_detail import served_words_language
from .invoice_draft_records import FindingWords

_SERVED_LOCALE_KEYS: Final[dict[ConfirmationBlockReason, str]] = {
    reason: f"application.ledger.confirmation_block.served.{reason.value}" for reason in ConfirmationBlockReason
}

_FINDING_LOCALE_KEYS: Final[dict[DraftFindingWording, str]] = {
    wording: f"application.ledger.draft_finding.{wording.value}" for wording in DraftFindingWording
}


def served_block_reason_words(reason: ConfirmationBlockReason) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    language = served_words_language()
    return tr(_SERVED_LOCALE_KEYS[reason], locale=language.value), language


def served_finding_words(words: FindingWords | None) -> tuple[str | None, OutputLanguage | None]:
    """The finished sentence explaining a finding and its language, or nothing for a finding without words."""
    if words is None:
        return None, None
    language = served_words_language()
    return tr(_FINDING_LOCALE_KEYS[words.wording], locale=language.value, **dict(words.params)), language


__all__ = ["served_block_reason_words", "served_finding_words"]
