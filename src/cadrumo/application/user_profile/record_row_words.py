"""The words that name one row of a record section, and one row reference between sections.

A row of a repeatable record section is identified by its row key, which tells an
operator nothing. Every surface that lists such rows -- the grouped profile read, a
ledger picker -- shows the sentence served here instead, in the output language,
so no surface composes a label from stored facts.

A section whose rows have no summary here is not served as a record group or as a
picker; adding one is how a section becomes listable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from ...core.i18n.render import tr
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ...domain.user_profile.labels import profile_choice_label

_KEY_ROOT: Final = "application.user_profile.record_groups"
_PROPERTY_SUMMARY_LOCALE_KEY: Final = f"{_KEY_ROOT}.{INMUEBLE_SECTION}.summary"
_LEASE_OPEN_SUMMARY_LOCALE_KEY: Final = f"{_KEY_ROOT}.{ARRENDAMIENTO_SECTION}.summary_open"
_LEASE_ENDED_SUMMARY_LOCALE_KEY: Final = f"{_KEY_ROOT}.{ARRENDAMIENTO_SECTION}.summary_ended"
_RELATION_KEY_ROOT: Final = f"{_KEY_ROOT}.relation"

type RowValues = Mapping[str, str]


def _property_place(row: RowValues, locale: str | None) -> str:
    """Return a property's address, else its cadastral reference, else the words of its location code.

    A stored row holds only stated facts, so a leaf it does not state is absent rather than empty.
    """
    for leaf in ("direccion", "referencia_catastral"):
        stated = row.get(leaf)
        if stated is not None:
            return stated
    situacion = row.get("situacion")
    return "" if situacion is None else profile_choice_label(INMUEBLE_SECTION, "situacion", situacion, locale=locale)


def _property_words(row_key: int, row: RowValues, locale: str | None) -> str:
    """Name a property by where it is."""
    return tr(_PROPERTY_SUMMARY_LOCALE_KEY, row=row_key, place=_property_place(row, locale), locale=locale)


def _lease_words(row_key: int, row: RowValues, locale: str | None) -> str:
    """Name a lease by the days it runs; a lease with no end date continues."""
    start = row.get("fecha_inicio", "")
    end = row.get("fecha_fin")
    if end is None:
        return tr(_LEASE_OPEN_SUMMARY_LOCALE_KEY, row=row_key, start=start, locale=locale)
    return tr(_LEASE_ENDED_SUMMARY_LOCALE_KEY, row=row_key, start=start, end=end, locale=locale)


_SUMMARIES: Final[Mapping[str, Callable[[int, RowValues, str | None], str]]] = {
    INMUEBLE_SECTION: _property_words,
    ARRENDAMIENTO_SECTION: _lease_words,
}


def summarised_sections() -> frozenset[str]:
    """Return the record sections whose rows have served words."""
    return frozenset(_SUMMARIES)


def record_row_summary_words(section_key: str, row_key: int, row: RowValues, *, locale: str | None = None) -> str:
    """Return the sentence that names one stored row of ``section_key`` in ``locale``, else the output language.

    Raises:
        KeyError: When the section's rows have no served words.
    """
    return _SUMMARIES[section_key](row_key, row, locale)


def record_summary_words_keys() -> frozenset[str]:
    """Return every locale key the row summaries of the summarised sections say their sentences with."""
    return frozenset({_PROPERTY_SUMMARY_LOCALE_KEY, _LEASE_OPEN_SUMMARY_LOCALE_KEY, _LEASE_ENDED_SUMMARY_LOCALE_KEY})


def record_relation_words_key(section_key: str, field_key: str) -> str:
    """Return the locale key of the words that name a row reference declared at ``section_key.field_key``."""
    return f"{_RELATION_KEY_ROOT}.{section_key}.{field_key}"


def record_relation_words(section_key: str, field_key: str) -> str:
    """Return what a row naming another through ``section_key.field_key`` is to the row it names."""
    return tr(record_relation_words_key(section_key, field_key))


__all__ = [
    "record_relation_words",
    "record_relation_words_key",
    "record_row_summary_words",
    "record_summary_words_keys",
    "summarised_sections",
]
