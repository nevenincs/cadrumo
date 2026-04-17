"""Temporary compatibility shims for issue ``#20`` i18n primitives."""

from __future__ import annotations

import re
from typing import Protocol

from ._errors import LLMConfigError

_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2}$")


class LanguageLike(Protocol):
    """Protocol matching the expected future ``aeat.i18n.Language`` surface."""

    value: str


class TranslatableLike(Protocol):
    """Protocol matching the future translatable container from issue ``#20``."""

    def get(self, language: str, /) -> str | None:
        """Return the translation for a language, if present."""


def normalize_language_code(language: str | LanguageLike) -> str:
    """Normalize and validate a language code.

    TODO #20: replace this shim with ``from aeat.i18n import Language`` once
    the trilingual i18n branch lands.
    """

    value = language if isinstance(language, str) else language.value
    normalized = value.strip().lower()
    if not _LANGUAGE_CODE_PATTERN.fullmatch(normalized):
        msg = f"Language must be a two-letter ISO 639-1 code, got {value!r}"
        raise LLMConfigError(msg)
    return normalized
