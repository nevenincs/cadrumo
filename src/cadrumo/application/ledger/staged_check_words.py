"""The sentences the staged-work check serves for what holds a movement back and for a share it cannot read.

A frontend shows these sentences as served. They sit under keys written for no
surface in particular, so none names a command option, and each is worded from
its kind alone: it carries no field value, movement, amount or typed text.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, get_args

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from .staged_check_contracts import StagedBlockerKind

BLOCKER_WORDS_LOCALE_KEYS: Final[Mapping[StagedBlockerKind, str]] = MappingProxyType(
    {
        "cannot_clear": "application.ledger.staged_check.served.blocker.cannot_clear",
        "needs_classification": "application.ledger.staged_check.served.blocker.needs_classification",
        "mixed_needs_share": "application.ledger.staged_check.served.blocker.mixed_needs_share",
        "share_needs_mixed": "application.ledger.staged_check.served.blocker.share_needs_mixed",
        "transfer_with_tax": "application.ledger.staged_check.served.blocker.transfer_with_tax",
        "draft_incomplete": "application.ledger.staged_check.served.blocker.draft_incomplete",
        "amount_signed": "application.ledger.staged_check.served.blocker.amount_signed",
        "needs_withholding_category": "application.ledger.staged_check.served.blocker.needs_withholding_category",
    }
)
"""The sentence that explains each kind of blocker."""

BLOCKER_FIX_LOCALE_KEYS: Final[Mapping[StagedBlockerKind, str]] = MappingProxyType(
    {
        "cannot_clear": "application.ledger.staged_check.served.fix.cannot_clear",
        "needs_classification": "application.ledger.staged_check.served.fix.needs_classification",
        "mixed_needs_share": "application.ledger.staged_check.served.fix.mixed_needs_share",
        "share_needs_mixed": "application.ledger.staged_check.served.fix.share_needs_mixed",
        "transfer_with_tax": "application.ledger.staged_check.served.fix.transfer_with_tax",
        "draft_incomplete": "application.ledger.staged_check.served.fix.draft_incomplete",
        "amount_signed": "application.ledger.staged_check.served.fix.amount_signed",
        "needs_withholding_category": "application.ledger.staged_check.served.fix.needs_withholding_category",
    }
)
"""The sentence that says what puts each kind of blocker right."""

SHARE_REFUSAL_LOCALE_KEY: Final = "application.ledger.staged_check.served.share_refusal"
"""The sentence for a business share typed in a form no percentage reads as."""


def blocker_words(kind: StagedBlockerKind, language: OutputLanguage) -> tuple[str, str]:
    """The explanation and the fix of a blocker kind, said in ``language``."""
    return (
        tr(BLOCKER_WORDS_LOCALE_KEYS[kind], locale=language.value),
        tr(BLOCKER_FIX_LOCALE_KEYS[kind], locale=language.value),
    )


def share_refusal_words(language: OutputLanguage) -> str:
    """The sentence shown for a business share that could not be read as a percentage."""
    return tr(SHARE_REFUSAL_LOCALE_KEY, locale=language.value)


def _require_total_tables() -> None:
    kinds = set(get_args(StagedBlockerKind))
    if set(BLOCKER_WORDS_LOCALE_KEYS) != kinds or set(BLOCKER_FIX_LOCALE_KEYS) != kinds:
        raise ValueError("every staged blocker kind needs its explanation and its fix")


_require_total_tables()

__all__ = [
    "BLOCKER_FIX_LOCALE_KEYS",
    "BLOCKER_WORDS_LOCALE_KEYS",
    "SHARE_REFUSAL_LOCALE_KEY",
    "blocker_words",
    "share_refusal_words",
]
