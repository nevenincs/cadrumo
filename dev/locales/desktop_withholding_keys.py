"""Declared desktop shell keys for the Withholding page.

The page words each certificate, income class, origin, amount column and statement from what the ledger
serves with it, so these keys are only its chrome: the page's title and headings, the column heads that
the served rows do not carry, and the page's own states.
"""

from typing import Final

DESKTOP_WITHHOLDING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.withholding.absences.empty",
        "desktop.withholding.absences.history",
        "desktop.withholding.absences.title",
        "desktop.withholding.change",
        "desktop.withholding.column.class",
        "desktop.withholding.column.note",
        "desktop.withholding.column.origin",
        "desktop.withholding.column.payer",
        "desktop.withholding.column.state",
        "desktop.withholding.column.stated_on",
        "desktop.withholding.column.withdrawn_on",
        "desktop.withholding.ejercicio",
        "desktop.withholding.empty",
        "desktop.withholding.failed",
        "desktop.withholding.loading",
        "desktop.withholding.read_again",
        "desktop.withholding.records.empty",
        "desktop.withholding.records.title",
        "desktop.withholding.refresh",
        "desktop.withholding.signed_out",
        "desktop.withholding.title",
        "desktop.withholding.what",
    }
)
