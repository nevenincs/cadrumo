"""The workbench's words for a declaration: its modelo's name, its period and its dates.

A filer reads "1st quarter 2026" and "Modelo 130 · Income tax instalment", never
the transport tokens ``1T`` or ``0A``. A period kind without words of its own is
shown as its official code rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from .....core.external_constants import OutputLanguage
from .....core.i18n.render import lookup_translation, tr
from .....core.period import Period, PeriodKind

_NOT_APPLYING_LOCALE_KEYS: Final[Mapping[PeriodKind, str]] = MappingProxyType(
    {
        PeriodKind.QUARTERLY: "tui.modelo.workbench.applicability.quarter",
        PeriodKind.MONTHLY: "tui.modelo.workbench.applicability.month",
        PeriodKind.ANNUAL: "tui.modelo.workbench.applicability.year",
    }
)
_NOT_APPLYING_PERIOD_LOCALE_KEY: Final[str] = "tui.modelo.workbench.applicability.period"


def does_not_apply_text(period: Period) -> str:
    """Say that a page does not apply, naming the period the way the filer counts it: this quarter, month or year."""
    return tr(_NOT_APPLYING_LOCALE_KEYS.get(period.kind, _NOT_APPLYING_PERIOD_LOCALE_KEY))


def modelo_number(modelo: str) -> str:
    """Name a modelo by its number alone, for narrow terminals."""
    return tr("tui.modelo.workbench.modelo_number", modelo=modelo)


def modelo_title(modelo: str, language: OutputLanguage) -> str:
    """Return the modelo's own title in the filer's language, or its number alone."""
    for locale in (language.value, OutputLanguage.ES.value):
        title = lookup_translation(f"modelo.schema.{modelo}.field.title", locale=locale)
        if title is not None and title:
            return tr("tui.modelo.workbench.modelo_title", modelo=modelo, title=title)
    return modelo_number(modelo)


__all__ = [
    "does_not_apply_text",
    "modelo_number",
    "modelo_title",
]
