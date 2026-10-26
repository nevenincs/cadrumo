"""Shared wording and typed parsing for the Records entry tools."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from textual.widgets import Select

from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.operations.public_period import PublicPeriod
from ....core.i18n.render import tr
from ....core.period import Period, PeriodError
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState

#: The AEAT period codes an operator can choose: quarters, the annual period and months.
PERIOD_CODES: Final[tuple[str, ...]] = ("1T", "2T", "3T", "4T", "0A", *(f"{month:02d}" for month in range(1, 13)))

DIRECTION_LOCALE_KEYS: Final[dict[TransactionDirection, str]] = {
    TransactionDirection.INCOMING: "tui.ledger.entry_tools.direction.incoming",
    TransactionDirection.OUTGOING: "tui.ledger.entry_tools.direction.outgoing",
    TransactionDirection.INTERNAL_TRANSFER: "tui.ledger.entry_tools.direction.internal_transfer",
}

CLASSIFICATION_LOCALE_KEYS: Final[dict[BusinessClassification, str]] = {
    BusinessClassification.BUSINESS: "tui.ledger.entry_tools.classification.business",
    BusinessClassification.PERSONAL: "tui.ledger.entry_tools.classification.personal",
    BusinessClassification.MIXED: "tui.ledger.entry_tools.classification.mixed",
    BusinessClassification.NOT_YET_PROCESSED: "tui.ledger.entry_tools.classification.not_yet_processed",
    BusinessClassification.PROCESSED_UNCLASSIFIED: "tui.ledger.entry_tools.classification.processed_unclassified",
    BusinessClassification.SKIPPED_BY_RULE: "tui.ledger.entry_tools.classification.skipped_by_rule",
    BusinessClassification.FAILED_VALIDATION: "tui.ledger.entry_tools.classification.failed_validation",
    BusinessClassification.REVIEWED_EXCLUDED: "tui.ledger.entry_tools.classification.reviewed_excluded",
}

LIFECYCLE_LOCALE_KEYS: Final[dict[TransactionLifecycleState, str]] = {
    TransactionLifecycleState.ACTIVE: "tui.ledger.entry_tools.lifecycle.active",
    TransactionLifecycleState.ARCHIVED: "tui.ledger.entry_tools.lifecycle.archived",
    TransactionLifecycleState.STASHED: "tui.ledger.entry_tools.lifecycle.stashed",
    TransactionLifecycleState.SPLIT: "tui.ledger.entry_tools.lifecycle.split",
}


def direction_label(token: str) -> str:
    """Name a stored direction in words; a token outside the closed set is shown as stored."""
    try:
        return tr(DIRECTION_LOCALE_KEYS[TransactionDirection(token)])
    except ValueError:
        return token


def classification_label(token: str) -> str:
    """Name a stored business classification in words; an unknown token is shown as stored."""
    try:
        return tr(CLASSIFICATION_LOCALE_KEYS[BusinessClassification(token)])
    except ValueError:
        return token


def lifecycle_label(token: str) -> str:
    """Name a stored lifecycle state in words; an unknown token is shown as stored."""
    try:
        return tr(LIFECYCLE_LOCALE_KEYS[TransactionLifecycleState(token)])
    except ValueError:
        return token


def entry_label(transaction: LedgerTransactionProjection) -> str:
    """Name one entry the way the operator recorded it: date, amount and description."""
    return tr(
        "tui.ledger.entry_tools.entry_label",
        date=transaction.date,
        amount=transaction.amount,
        currency=transaction.currency,
        description=transaction.description,
    )


def short_id(transaction_id: str) -> str:
    """The first twelve characters of an identifier, enough to tell entries apart."""
    return transaction_id[:12]


def period_options() -> tuple[tuple[str, str], ...]:
    """The period choices; AEAT codes are official tokens and stay untranslated."""
    return tuple((code, code) for code in PERIOD_CODES)


def selected_value(select: Select[str]) -> str | None:
    """The chosen value of a select, or ``None`` when it is blank."""
    return None if select.is_blank() else str(select.value)


def read_period(year_text: str, code: str | None, *, required: bool = False) -> PublicPeriod | None:
    """Parse a typed filing year and a chosen period code into the operation's period.

    Both or neither must be given; a required period refuses neither.

    Raises:
        ValueError: With operator copy when only one half is given, the year is
            not a number, or the pair names no period.
    """
    year_text = year_text.strip()
    if not year_text and code is None:
        if required:
            raise ValueError(tr("tui.ledger.entry_tools.period.required"))
        return None
    if not year_text or code is None:
        raise ValueError(tr("tui.ledger.entry_tools.period.pair"))
    if not year_text.isdigit() or len(year_text) != 4:
        raise ValueError(tr("tui.ledger.entry_tools.period.invalid"))
    try:
        return PublicPeriod.from_period(Period.from_year_and_code(int(year_text), code))
    except (PeriodError, ValueError):
        raise ValueError(tr("tui.ledger.entry_tools.period.invalid")) from None


def period_label(period: PublicPeriod | None) -> str:
    """Name a period, or say that every period is included."""
    if period is None:
        return tr("tui.ledger.entry_tools.period.all")
    return tr("tui.ledger.entry_tools.period.named", year=period.filing_year, code=period.code)


def joined(lines: Iterable[str]) -> str:
    """Join non-empty lines for one multi-line status."""
    return "\n".join(line for line in lines if line)


__all__ = [
    "CLASSIFICATION_LOCALE_KEYS",
    "DIRECTION_LOCALE_KEYS",
    "LIFECYCLE_LOCALE_KEYS",
    "PERIOD_CODES",
    "classification_label",
    "direction_label",
    "entry_label",
    "joined",
    "lifecycle_label",
    "period_label",
    "period_options",
    "read_period",
    "selected_value",
    "short_id",
]
