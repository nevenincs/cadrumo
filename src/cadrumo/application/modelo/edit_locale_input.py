"""Locale-specific marks and boolean words accepted by the edit entry grammar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ...core.external_constants import OutputLanguage


@dataclass(frozen=True, slots=True)
class ModeloEditLocaleMarks:
    """Decimal/grouping marks and boolean words for one entry locale."""

    decimal: str
    groups: frozenset[str]
    booleans: dict[str, bool]


SPACE_GROUPS: Final = frozenset({" ", chr(0x00A0), chr(0x202F)})
_LOCALE_MARKS: Final[dict[OutputLanguage, ModeloEditLocaleMarks]] = {
    OutputLanguage.ES: ModeloEditLocaleMarks(
        decimal=",", groups=frozenset({"."}), booleans={"sí": True, "si": True, "no": False}
    ),
    OutputLanguage.CA: ModeloEditLocaleMarks(
        decimal=",", groups=frozenset({"."}), booleans={"sí": True, "si": True, "no": False}
    ),
    OutputLanguage.HU: ModeloEditLocaleMarks(decimal=",", groups=SPACE_GROUPS, booleans={"igen": True, "nem": False}),
    OutputLanguage.EN: ModeloEditLocaleMarks(decimal=".", groups=frozenset({","}), booleans={"yes": True, "no": False}),
}


def locale_marks(locale: OutputLanguage) -> ModeloEditLocaleMarks:
    """Return the entry marks and boolean words of a supported locale."""
    return _LOCALE_MARKS[locale]


__all__ = ["SPACE_GROUPS", "ModeloEditLocaleMarks", "locale_marks"]
