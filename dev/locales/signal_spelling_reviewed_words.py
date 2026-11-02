"""Reviewed exact dictionary gaps used by the locale spelling audit."""

from __future__ import annotations

from .signal_spelling_reviewed_words_ca import REVIEWED_CATALAN_SPELLINGS
from .signal_spelling_reviewed_words_en import REVIEWED_ENGLISH_SPELLINGS
from .signal_spelling_reviewed_words_es import REVIEWED_SPANISH_SPELLINGS
from .signal_spelling_reviewed_words_hu import REVIEWED_HUNGARIAN_SPELLINGS

REVIEWED_LOCALE_SPELLINGS: dict[str, frozenset[str]] = {
    "en": REVIEWED_ENGLISH_SPELLINGS,
    "es": REVIEWED_SPANISH_SPELLINGS,
    "ca": REVIEWED_CATALAN_SPELLINGS,
    "hu": REVIEWED_HUNGARIAN_SPELLINGS,
}
