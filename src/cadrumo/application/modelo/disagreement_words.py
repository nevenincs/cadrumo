"""How a source disagreement's sources and amounts read to a person, in each language.

A note or a resolution keeps what each source stated in language-neutral form:
the part the source plays, the kind of place it is, and the value in its own
type. This module words them when they are shown: the part or the cross-check as
a phrase, a figure with the marks of the reader's language, a date as that
language writes it. Nothing here names a payer, a document or a path, and no
role token, id or raw amount reaches a sentence.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.modelos.source_disagreement import (
    DisagreementBooleanValue,
    DisagreementDateValue,
    DisagreementDecimalValue,
    DisagreementEnumValue,
    DisagreementRelationValue,
    DisagreementRowsValue,
    DisagreementScalarValue,
    DisagreementTextValue,
    DisagreementValue,
    SourceDisagreementEntry,
    SourceDisagreementRole,
)
from .value_presentation import format_casilla_value

__all__ = [
    "CROSS_CHECK_LABEL_LOCALE_KEYS",
    "disagreement_value_text",
    "sources_facts",
    "sources_facts_words",
    "sources_words",
    "value_facts",
    "value_facts_words",
    "value_words",
]

CROSS_CHECK_LABEL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "retencion_soportada": "application.modelo.credit_cross_check_source.retencion_soportada",
        "borrador": "application.modelo.credit_cross_check_source.borrador",
        "ledger": "application.modelo.credit_cross_check_source.ledger",
        "filed_observation": "application.modelo.credit_cross_check_source.filed_observation",
    }
)
"""How a note names the source a credit was compared with, by its cross-check kind."""

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

_SOURCE_AMOUNT_LOCALE_KEY: Final = "application.modelo.credit_resolution.served_answer.source_amount"
_ROWS_KIND: Final = "rows"
_LIST_SEPARATOR: Final = "; "

type _ValueData = list[object]
"""One value as the facts keep it: ``[kind, text]``, or ``["rows", [[kind, text], ...]]``."""


def disagreement_value_text(value: DisagreementValue) -> str:
    """State one source's value as plain text, in its own type's canonical form."""
    match value:
        case DisagreementDecimalValue() | DisagreementRelationValue():
            return value.amount
        case DisagreementEnumValue():
            return value.token
        case DisagreementDateValue():
            return value.value.isoformat()
        case DisagreementBooleanValue():
            return "true" if value.value else "false"
        case DisagreementTextValue():
            return value.value
        case DisagreementRowsValue():
            return ",".join(disagreement_value_text(row) for row in value.rows)


def _scalar_data(value: DisagreementScalarValue) -> _ValueData:
    return [value.kind, disagreement_value_text(value)]


def _value_data(value: DisagreementValue) -> _ValueData:
    if isinstance(value, DisagreementRowsValue):
        return [_ROWS_KIND, [_scalar_data(row) for row in value.rows]]
    return [value.kind, disagreement_value_text(value)]


def value_facts(value: DisagreementValue) -> str:
    """Keep one value in a note's fact: its kind and canonical text, so any language can word it later."""
    return json.dumps(_value_data(value), separators=(",", ":"), ensure_ascii=False)


def sources_facts(sources: Iterable[SourceDisagreementEntry]) -> str:
    """Keep what every source stated in a note's fact: its part, its kind of place and its value."""
    return json.dumps(
        [[source.role.value, source.source_family, _value_data(source.value)] for source in sources],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _data_words(data: _ValueData, language: OutputLanguage) -> str:
    kind, payload = data
    if kind == _ROWS_KIND:
        if not isinstance(payload, list):
            raise ValueError("a row set keeps its rows as a list")
        return ", ".join(_data_words(row, language) for row in payload)
    if not isinstance(kind, str) or not isinstance(payload, str):
        raise ValueError("a kept value is a kind and its text")
    match kind:
        case "decimal" | "relation":
            return format_casilla_value(Decimal(payload), data_type="decimal", language=language)
        case "date":
            return format_casilla_value(date.fromisoformat(payload), data_type="date", language=language)
        case "boolean":
            return format_casilla_value(payload == "true", data_type="boolean", language=language)
        case _:
            return payload


def value_words(value: DisagreementValue, language: OutputLanguage) -> str:
    """One source's stated value as ``language`` writes it: a figure with its marks, a date, a yes or no."""
    return _data_words(_value_data(value), language)


def value_facts_words(facts: str, language: OutputLanguage) -> str:
    """Word a value kept by :func:`value_facts`."""
    return _data_words(json.loads(facts), language)


def _source_label(role: SourceDisagreementRole, family: str, language: OutputLanguage) -> str:
    """What the source is, in words: the kind of cross-check when it is one, else the part it plays."""
    label_key = CROSS_CHECK_LABEL_LOCALE_KEYS.get(family) if role is SourceDisagreementRole.CROSS_CHECK else None
    return tr(label_key or _ROLE_LOCALE_KEYS[role], locale=language.value)


def _source_words(role: SourceDisagreementRole, family: str, data: _ValueData, language: OutputLanguage) -> str:
    return tr(
        _SOURCE_AMOUNT_LOCALE_KEY,
        locale=language.value,
        source=_source_label(role, family, language),
        amount=_data_words(data, language),
    )


def sources_words(sources: Iterable[SourceDisagreementEntry], language: OutputLanguage) -> str:
    """What every source stated, each as the kind of source and its value."""
    return _LIST_SEPARATOR.join(
        _source_words(source.role, source.source_family, _value_data(source.value), language) for source in sources
    )


def sources_facts_words(facts: str, language: OutputLanguage) -> str:
    """Word what every source stated, kept by :func:`sources_facts`."""
    return _LIST_SEPARATOR.join(
        _source_words(SourceDisagreementRole(role), family, data, language) for role, family, data in json.loads(facts)
    )


def _require_total_tables() -> None:
    if set(_ROLE_LOCALE_KEYS) != set(SourceDisagreementRole):
        raise ValueError("every disagreement role needs its words")


_require_total_tables()
