"""The sentence the evidence review serves for each reason a read draft cannot be confirmed yet.

A frontend shows these sentences as served and words no reason of its own. A
sentence is worded from its reason alone: it carries no party, amount or
document text.
"""

from __future__ import annotations

from typing import Final

from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ..operations.error_detail import served_words_language

_SERVED_LOCALE_KEYS: Final[dict[ConfirmationBlockReason, str]] = {
    reason: f"application.ledger.confirmation_block.served.{reason.value}" for reason in ConfirmationBlockReason
}


def served_block_reason_words(reason: ConfirmationBlockReason) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    language = served_words_language()
    return tr(_SERVED_LOCALE_KEYS[reason], locale=language.value), language


__all__ = ["served_block_reason_words"]
