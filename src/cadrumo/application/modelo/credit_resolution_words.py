"""The sentences a frontend shows for the operator's resolutions of disputed figures, said by the application.

A refusal's sentence is served under keys written for frontends, apart from the
command line's messages, which tell the operator to copy an id from the check.
The sentence a stored resolution carries says which figure it answers and what
every source stated, in the reader's language: the box or boxes reached, what
kind of source each one is, and the amounts as that language writes them. Nothing
here names a payer, a document or a path.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.modelos.credit_resolution import CreditResolutionRecord, CreditResolutionState
from ..operations.error_detail import operation_catalogue_refusal_words
from .credit_resolution_repository import CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS, CreditResolutionRevokeRefusalReason
from .disagreement_words import sources_words, value_words

__all__ = [
    "credit_resolution_answer_words",
    "credit_resolution_current_words",
    "credit_resolution_revoke_refusal_words",
    "credit_resolution_state_words",
    "served_credit_resolution_refusal_words",
]

_SERVED_REFUSAL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "already_resolved": "application.modelo.credit_resolution.served.already_resolved",
        "not_resolved": "application.modelo.credit_resolution.served.not_resolved",
        "unknown_finding": "application.modelo.credit_resolution.served.unknown_finding",
        "calculation_not_current": "application.modelo.credit_resolution.served.calculation_not_current",
        "stale_revision": "application.modelo.credit_resolution.served.stale_revision",
    }
)
"""The sentence of each refusal reason, written for a frontend that shows it as served."""

_STATE_LOCALE_KEYS: Final[Mapping[CreditResolutionState, str]] = MappingProxyType(
    {
        CreditResolutionState.ACTIVE: "application.modelo.credit_resolution.served_row.state.active",
        CreditResolutionState.REVOKED: "application.modelo.credit_resolution.served_row.state.revoked",
    }
)
_CURRENT_LOCALE_KEYS: Final[Mapping[bool, str]] = MappingProxyType(
    {
        True: "application.modelo.credit_resolution.served_row.current.yes",
        False: "application.modelo.credit_resolution.served_row.current.no",
    }
)
_REVOKE_REFUSAL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "not_resolved": "application.modelo.credit_resolution.served_row.revoke_refusal.not_resolved",
        "unknown_finding": "application.modelo.credit_resolution.served_row.revoke_refusal.unreadable",
    }
)
_ANSWER_ONE_BOX_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.one_box"
_ANSWER_MANY_BOXES_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.many_boxes"
_ANSWER_NO_BOX_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.no_box"


def served_credit_resolution_refusal_words(reason: str, *, error_code: str) -> tuple[str, OutputLanguage]:
    """The finished sentence for a refusal ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])


def credit_resolution_answer_words(record: CreditResolutionRecord, language: OutputLanguage) -> str:
    """Say which figure an acceptance answers, the amount it accepted and what every source stated."""
    fact = record.disagreement
    accepted = next(source for source in fact.sources if source.role is record.accepted_role)
    sources = sources_words(fact.sources, language)
    boxes = fact.reached_casillas
    key = (
        _ANSWER_NO_BOX_LOCALE_KEY
        if not boxes
        else _ANSWER_ONE_BOX_LOCALE_KEY
        if len(boxes) == 1
        else _ANSWER_MANY_BOXES_LOCALE_KEY
    )
    return tr(
        key,
        locale=language.value,
        box=", ".join(str(box) for box in boxes),
        accepted=value_words(accepted.value, language),
        sources=sources,
    )


def credit_resolution_state_words(state: CreditResolutionState, language: OutputLanguage) -> str:
    """Say whether a stored resolution stands or has been taken back."""
    return tr(_STATE_LOCALE_KEYS[state], locale=language.value)


def credit_resolution_current_words(current: bool, language: OutputLanguage) -> str:
    """Say whether the declaration's current calculation still has the disagreement a resolution answers."""
    return tr(_CURRENT_LOCALE_KEYS[current], locale=language.value)


def credit_resolution_revoke_refusal_words(
    reason: CreditResolutionRevokeRefusalReason, language: OutputLanguage
) -> str:
    """Say why an acceptance cannot be taken back."""
    return tr(_REVOKE_REFUSAL_LOCALE_KEYS[reason], locale=language.value)


def _require_total_tables() -> None:
    if set(_SERVED_REFUSAL_LOCALE_KEYS) != set(CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS):
        raise ValueError("every credit resolution refusal reason needs its served words")


_require_total_tables()
