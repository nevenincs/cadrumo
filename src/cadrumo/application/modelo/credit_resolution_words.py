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
from ...domain.modelos.credit_resolution import CreditResolutionRecord
from ...domain.modelos.source_disagreement import (
    DisagreementBooleanValue,
    DisagreementDateValue,
    DisagreementDecimalValue,
    DisagreementEnumValue,
    DisagreementRelationValue,
    DisagreementRowsValue,
    DisagreementTextValue,
    DisagreementValue,
    SourceDisagreementEntry,
    SourceDisagreementRole,
)
from ..operations.error_detail import operation_catalogue_refusal_words
from .calculation_notes import CROSS_CHECK_LABEL_LOCALE_KEYS
from .credit_resolution_repository import CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS
from .value_presentation import format_casilla_value

__all__ = ["credit_resolution_answer_words", "served_credit_resolution_refusal_words"]

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

_ROLE_LOCALE_KEYS: Final[Mapping[SourceDisagreementRole, str]] = MappingProxyType(
    {
        SourceDisagreementRole.VALUE_SOURCE: "application.modelo.credit_resolution.served_source.value_source",
        SourceDisagreementRole.CROSS_CHECK: "application.modelo.credit_resolution.served_source.cross_check",
        SourceDisagreementRole.PROFILE: "application.modelo.credit_resolution.served_source.profile",
        SourceDisagreementRole.BACKEND: "application.modelo.credit_resolution.served_source.backend",
        SourceDisagreementRole.BORRADOR: "application.modelo.credit_resolution.served_source.borrador",
        SourceDisagreementRole.CALLER: "application.modelo.credit_resolution.served_source.caller",
    }
)
"""How each part a source plays in a disagreement is named."""

_ANSWER_ONE_BOX_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.one_box"
_ANSWER_MANY_BOXES_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.many_boxes"
_ANSWER_NO_BOX_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.no_box"
_SOURCE_AMOUNT_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.source_amount"
_LIST_SEPARATOR: Final = "; "


def served_credit_resolution_refusal_words(reason: str, *, error_code: str) -> tuple[str, OutputLanguage]:
    """The finished sentence for a refusal ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])


def _value_words(value: DisagreementValue, language: OutputLanguage) -> str:
    """One source's stated value as ``language`` writes it: a figure with that language's marks, a date, a yes or no."""
    match value:
        case DisagreementDecimalValue() | DisagreementRelationValue():
            return format_casilla_value(value.decimal, data_type="decimal", language=language)
        case DisagreementDateValue():
            return format_casilla_value(value.value, data_type="date", language=language)
        case DisagreementBooleanValue():
            return format_casilla_value(value.value, data_type="boolean", language=language)
        case DisagreementEnumValue():
            return value.token
        case DisagreementTextValue():
            return value.value
        case DisagreementRowsValue():
            return ", ".join(_value_words(row, language) for row in value.rows)


def _source_words(source: SourceDisagreementEntry, language: OutputLanguage) -> str:
    """What the source is, in words: the kind of cross-check when it is one, else the part it plays."""
    label_key = (
        CROSS_CHECK_LABEL_LOCALE_KEYS.get(source.source_family)
        if source.role is SourceDisagreementRole.CROSS_CHECK
        else None
    )
    return tr(label_key or _ROLE_LOCALE_KEYS[source.role], locale=language.value)


def credit_resolution_answer_words(record: CreditResolutionRecord, language: OutputLanguage) -> str:
    """Say which figure an acceptance answers, the amount it accepted and what every source stated."""
    fact = record.disagreement
    accepted = next(source for source in fact.sources if source.role is record.accepted_role)
    sources = _LIST_SEPARATOR.join(
        tr(
            _SOURCE_AMOUNT_LOCALE_KEY,
            locale=language.value,
            source=_source_words(source, language),
            amount=_value_words(source.value, language),
        )
        for source in fact.sources
    )
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
        accepted=_value_words(accepted.value, language),
        sources=sources,
    )


def _require_total_tables() -> None:
    if set(_SERVED_REFUSAL_LOCALE_KEYS) != set(CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS):
        raise ValueError("every credit resolution refusal reason needs its served words")
    if set(_ROLE_LOCALE_KEYS) != set(SourceDisagreementRole):
        raise ValueError("every disagreement role needs its words")


_require_total_tables()
