"""The workbench's words for a page that does not apply, naming the period the way the filer counts it.

A filer reads "does not apply this quarter", never the transport tokens ``1T``
or ``0A``. A period kind without words of its own is said as "this period".
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from .....core.i18n.render import tr
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


__all__ = [
    "does_not_apply_text",
]
