"""The workbench's words for a declaration: its modelo's name, its period and its dates.

A filer reads "1st quarter 2026" and "Modelo 130 · Income tax instalment", never
the transport tokens ``1T`` or ``0A``. A period kind without words of its own is
shown as its official code rather than guessed at.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from types import MappingProxyType
from typing import Final

from rich.cells import cell_len

from .....application.modelo.value_presentation import format_casilla_value
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import lookup_translation, tr
from .....core.period import Period, PeriodKind

PERIOD_WORD_NAMES: Final[tuple[str, ...]] = (
    *(f"quarter_{quarter}" for quarter in range(1, 5)),
    *(f"month_{month:02d}" for month in range(1, 13)),
    "annual",
)
"""Every period the workbench names in words; any other period reads as its code and year."""

_NOT_APPLYING_LOCALE_KEYS: Final[Mapping[PeriodKind, str]] = MappingProxyType(
    {
        PeriodKind.QUARTERLY: "tui.modelo.workbench.applicability.quarter",
        PeriodKind.MONTHLY: "tui.modelo.workbench.applicability.month",
        PeriodKind.ANNUAL: "tui.modelo.workbench.applicability.year",
    }
)
_NOT_APPLYING_PERIOD_LOCALE_KEY: Final[str] = "tui.modelo.workbench.applicability.period"
_BREAKABLE_SPACE: Final[re.Pattern[str]] = re.compile(r"[^\S\u00a0]+")
"""Where words may break: any space except a no-break space, which holds "art. 71" or "1 000" together."""


def period_words(period: Period) -> str:
    """Name a filing period in the filer's language."""
    code = str(period.code)
    year = period.filing_year
    if period.kind is PeriodKind.QUARTERLY and code[:1].isdigit():
        name = f"quarter_{code[0]}"
    elif period.kind is PeriodKind.MONTHLY and code.isdigit():
        name = f"month_{int(code):02d}"
    elif period.kind is PeriodKind.ANNUAL:
        name = "annual"
    else:
        return f"{code} {year}"
    return tr(f"tui.modelo.workbench.period.{name}", year=year)


def does_not_apply_text(period: Period) -> str:
    """Say that a page does not apply, naming the period the way the filer counts it: this quarter, month or year."""
    return tr(_NOT_APPLYING_LOCALE_KEYS.get(period.kind, _NOT_APPLYING_PERIOD_LOCALE_KEY))


def wrap_words(text: str, width: int) -> tuple[str, ...]:
    """Break ``text`` into lines of at most ``width`` cells, only where a space other than a no-break one stands.

    A single word wider than the line is cut where it must be, so no line
    ever runs past ``width``.
    """
    width = max(width, 1)
    lines: list[str] = []
    line = ""
    for word in _BREAKABLE_SPACE.split(text.strip()):
        candidate = f"{line} {word}" if line else word
        if cell_len(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        while cell_len(line) > width:
            cut = 1
            while cell_len(line[: cut + 1]) <= width:
                cut += 1
            lines.append(line[:cut])
            line = line[cut:]
    lines.append(line)
    return tuple(lines)


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


def date_text(value: date, language: OutputLanguage) -> str:
    """A date in the order the filer's language writes it, as the rows write one."""
    return format_casilla_value(value, data_type="date", language=language)


def day_text(moment: datetime, language: OutputLanguage) -> str:
    """The day of a moment, in the filer's own time zone, written as :func:`date_text` writes a date."""
    local = moment.astimezone() if moment.tzinfo is not None else moment
    return date_text(local.date(), language)


__all__ = [
    "PERIOD_WORD_NAMES",
    "date_text",
    "day_text",
    "does_not_apply_text",
    "modelo_number",
    "modelo_title",
    "period_words",
    "wrap_words",
]
