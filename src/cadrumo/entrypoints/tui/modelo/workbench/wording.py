"""The workbench's words for a declaration: its modelo's name and its period.

A filer reads "1st quarter 2026" and "Modelo 130 · Income tax instalment", never
the transport tokens ``1T`` or ``0A``. A period kind without words of its own is
shown as its official code rather than guessed at.
"""

from __future__ import annotations

from .....core.external_constants import OutputLanguage
from .....core.i18n.render import lookup_translation, tr
from .....core.period import Period, PeriodKind


def period_words(period: Period) -> str:
    """Name a filing period in the filer's language."""
    code = str(period.code)
    year = period.filing_year
    if period.kind is PeriodKind.QUARTERLY and code[:1].isdigit():
        return tr(f"tui.modelo.workbench.period.quarter_{code[0]}", year=year)
    if period.kind is PeriodKind.MONTHLY and code.isdigit():
        return tr(f"tui.modelo.workbench.period.month_{int(code):02d}", year=year)
    if period.kind is PeriodKind.ANNUAL:
        return tr("tui.modelo.workbench.period.annual", year=year)
    return f"{code} {year}"


def modelo_number(modelo: str) -> str:
    """Name a modelo by its number alone, for narrow terminals."""
    return tr("tui.modelo.workbench.modelo_number", modelo=modelo)


def modelo_title(modelo: str, language: OutputLanguage) -> str:
    """Return the modelo's own title in the filer's language, or its number alone."""
    for locale in (language.value, OutputLanguage.ES.value):
        title = lookup_translation(f"modelo.schema.{modelo}.field.title", locale=locale)
        if title:
            return tr("tui.modelo.workbench.modelo_title", modelo=modelo, title=title)
    return modelo_number(modelo)


__all__ = ["modelo_number", "modelo_title", "period_words"]
