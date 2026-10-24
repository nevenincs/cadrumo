"""Deterministic grounding of statement movements a reader proposed.

A reader proposes the movements it believes a statement page prints. This
module decides which of them ARE printed, and it decides with no model in the
loop: every rule below is a comparison against the page's own text or an exact
sum over printed amounts.

**Anchoring.** A movement is accepted only when its printed booked date and its
printed amount appear together on one line of the page, and each line backs at
most one movement. Summary blocks, balance lines and headings print an amount
without a movement date beside it; an invented movement prints nothing at all.
Both are dropped and reported, never imported.

**Direction.** A printed sign decides which way money moved. The reader's
direction is used only for an amount printed without a sign, and a reader
direction that contradicts a printed sign drops the movement: the reader has
then misread the line, and nothing else it said about that line is trusted.

**Closure.** Where the statement prints an opening and a closing balance, or a
running balance on its movement lines, the accepted movements must sum to them
exactly. A contradiction means a movement is missing, invented or misread, so
the statement is refused whole rather than imported short.

Every value that reaches a movement is parsed by the shared provider parsers
from its printed form. No warning produced here quotes a printed value: a
warning names the page and the position of the proposal it concerns.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from .....application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementMovement,
    ProposedStatementPage,
)
from .....core.decimal.grammar import DecimalSeparator, DecimalSeparatorValue, european_thousands_reading_is_ambiguous
from .....core.errors.hierarchy import CoreValidationError
from .....core.parsing.codes import normalise_iso_4217_currency
from .base import FinancialProviderError, parse_amount_value, parse_date_value

__all__ = [
    "GroundedMovement",
    "GroundedStatement",
    "ReconciliationOutcome",
    "StatementPageText",
    "ground_statement",
]

#: Day, month and year groups of a printed numeric date.
_NUMERIC_DATE_RE = re.compile(r"^\s*(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})")

#: A word for the description check: a run of letters or digits.
_WORD_RE = re.compile(r"\w+", re.UNICODE)

#: Words shorter than this carry no evidence a reader could invent.
_MIN_CHECKED_WORD_LENGTH = 2

#: Currency symbols a statement may print instead of an ISO code. Only symbols
#: that name exactly one currency are listed; ``$`` names several.
_UNAMBIGUOUS_CURRENCY_SYMBOLS: Mapping[str, str] = {"€": "EUR", "£": "GBP"}

#: An ISO 4217-shaped code printed inside an amount, such as ``+8,55EUR``.
_PRINTED_CODE_RE = re.compile(r"(?<![A-Za-z])([A-Z]{3})(?![A-Za-z])")

#: Sign markers the shared amount parser reads as a positive or negative sign.
_POSITIVE_SIGN_RE = re.compile(r"^[^\d]*\+")


class ReconciliationOutcome(StrEnum):
    """What the printed balances said about the accepted movements."""

    RECONCILED = "reconciled"
    """Every printed balance check that could run agreed exactly."""

    CONTRADICTED = "contradicted"
    """A printed balance disagrees with the accepted movements."""

    NOT_CHECKABLE = "not_checkable"
    """The statement prints no balance the movements could be checked against."""


@dataclass(frozen=True, slots=True)
class StatementPageText:
    """One transcribed page and what a reader proposed for it.

    Attributes:
        page_number: One-based page position in the source document.
        text: The page transcription. FINANCIAL: held in memory only.
        proposal: The reader's proposal for this page.
        transcribed_by: Name of the reader that produced ``text``.
    """

    page_number: int
    text: str
    proposal: ProposedStatementPage
    transcribed_by: str


@dataclass(frozen=True, slots=True)
class GroundedMovement:
    """One movement anchored to a printed line and parsed from its printed forms.

    Attributes:
        page_number: Page the anchoring line is printed on.
        line_number: One-based position of the anchoring line among the page's
            non-blank lines.
        booked_date: Parsed booking date.
        value_date: Parsed value date, when printed.
        signed_amount: Signed amount; negative for money leaving the account.
        currency: ISO 4217 code.
        description: Printed movement text.
        counterparty: Printed counterparty, when the reader named one the page prints.
        balance: Running balance printed on the anchoring line, if any.
        direction_source: ``printed_sign`` or ``reader``.
        printed: The printed forms the movement was parsed from, for audit.
    """

    page_number: int
    line_number: int
    booked_date: date
    value_date: date | None
    signed_amount: Decimal
    currency: str
    description: str
    counterparty: str | None
    balance: Decimal | None
    direction_source: str
    printed: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    """The accepted movements of a statement and everything that was not accepted.

    Attributes:
        movements: Accepted movements in document order.
        warnings: One entry per dropped proposal or noteworthy inference.
        refusals: Statement-level reasons the statement cannot be imported.
        reconciliation: The outcome of the printed-balance checks.
    """

    movements: tuple[GroundedMovement, ...]
    warnings: tuple[str, ...]
    refusals: tuple[str, ...]
    reconciliation: ReconciliationOutcome

    @property
    def importable(self) -> bool:
        """Whether at least one movement is accepted and nothing refuses the statement."""
        return bool(self.movements) and not self.refusals


@dataclass(frozen=True, slots=True)
class _Anchored:
    """A proposal anchored to one printed line, before parsing."""

    page: StatementPageText
    position: int
    line_index: int
    line: str
    movement: ProposedStatementMovement


def _present(value: str | None) -> str | None:
    """Return ``value`` unless it is absent or blank."""
    return value if value is not None and value.strip() else None


def _compact(text: str) -> str:
    """Remove every whitespace character, so spacing differences do not matter."""
    return "".join(text.split())


def _words(text: str) -> set[str]:
    """Return the casefolded evidence-bearing words of ``text``."""
    return {word.casefold() for word in _WORD_RE.findall(text) if len(word) >= _MIN_CHECKED_WORD_LENGTH}


def _page_lines(text: str) -> tuple[str, ...]:
    """Return the page's non-blank lines, stripped."""
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _label(page: StatementPageText, position: int) -> str:
    """Name a proposal without quoting any of its values."""
    return f"page {page.page_number} movement {position}"


def _anchor_page(page: StatementPageText, warnings: list[str]) -> list[_Anchored]:
    """Anchor each proposal of one page to an unclaimed line printing its date and amount."""
    if not page.proposal.reply_usable:
        warnings.append(f"page {page.page_number}: the reader's reply could not be used")
    lines = _page_lines(page.text)
    compact_lines = tuple(_compact(line) for line in lines)
    claimed: set[int] = set()
    anchored: list[_Anchored] = []
    for position, movement in enumerate(page.proposal.movements, start=1):
        label = _label(page, position)
        printed_amount = _present(movement.amount)
        printed_booked = _present(movement.booked_date)
        if printed_amount is None or printed_booked is None:
            warnings.append(f"{label}: no printed date or amount was proposed; dropped")
            continue
        amount = _compact(printed_amount)
        booked = _compact(printed_booked)
        line_index = next(
            (
                index
                for index, compact in enumerate(compact_lines)
                if index not in claimed and amount in compact and booked in compact
            ),
            None,
        )
        if line_index is None:
            warnings.append(f"{label}: its date and amount are not printed together on one line; dropped")
            continue
        claimed.add(line_index)
        anchored.append(_Anchored(page, position, line_index, lines[line_index], movement))
    return anchored


def _day_first(anchored: Sequence[_Anchored]) -> bool | None:
    """Infer the statement's day order from its printed dates, or ``None`` on conflict.

    A first group above 12 can only be a day and a second group above 12 can
    only be a day too, read the other way. A statement printing both is not one
    convention, and choosing either would misdate half its movements. With no
    evidence either way the European day-first reading applies.
    """
    day_first_votes = 0
    month_first_votes = 0
    for item in anchored:
        for printed in (item.movement.booked_date, item.movement.value_date):
            match = _NUMERIC_DATE_RE.match(printed or "")
            if match is None or len(match.group(1)) == 4:
                continue
            first, second = int(match.group(1)), int(match.group(2))
            if first > 12:
                day_first_votes += 1
            elif second > 12:
                month_first_votes += 1
    if day_first_votes and month_first_votes:
        return None
    return not month_first_votes


def _decimal_vote(printed: str) -> DecimalSeparatorValue | None:
    """Return which separator one printed amount proves is decimal, if any."""
    body = "".join(char for char in printed if char.isdigit() or char in ",.")
    has_comma = "," in body
    has_dot = "." in body
    if has_comma and has_dot:
        return DecimalSeparator.COMMA if body.rfind(",") > body.rfind(".") else DecimalSeparator.PERIOD
    if has_comma:
        return DecimalSeparator.COMMA
    if has_dot and not european_thousands_reading_is_ambiguous(body):
        return DecimalSeparator.PERIOD
    return None


def _decimal_separator(anchored: Sequence[_Anchored], warnings: list[str]) -> DecimalSeparatorValue | None:
    """Infer the statement's decimal convention from every printed amount and balance."""
    votes: Counter[DecimalSeparatorValue] = Counter()
    for item in anchored:
        for printed in (item.movement.amount, item.movement.balance):
            vote = _decimal_vote(printed or "")
            if vote is not None:
                votes[vote] += 1
    if not votes:
        return None
    ranked = votes.most_common()
    if len(ranked) > 1:
        warnings.append(
            f"amounts print both decimal conventions; reading them as {ranked[0][0]!r}-decimal",
        )
    return ranked[0][0]


def _parse_signed(printed: str, separator: DecimalSeparatorValue | None) -> Decimal | None:
    """Parse one printed amount, or ``None`` when it is not a readable amount."""
    body = "".join(char for char in printed if char.isdigit() or char in ",.")
    if separator is None and european_thousands_reading_is_ambiguous(body):
        return None
    try:
        return parse_amount_value(printed, decimal_separator=separator)
    except FinancialProviderError:
        return None


def _resolve_currency_code(candidate: str | None, page_text: str) -> str | None:
    """Return an ISO code for a printed currency mark the page actually prints."""
    if candidate is None or not candidate.strip():
        return None
    mark = candidate.strip()
    code = _UNAMBIGUOUS_CURRENCY_SYMBOLS.get(mark, mark.upper())
    if mark not in page_text and code not in page_text:
        return None
    try:
        return normalise_iso_4217_currency(code)
    except CoreValidationError:
        return None


def _amount_currency(printed_amount: str) -> str | None:
    """Return the ISO code printed inside an amount itself, if it carries one."""
    match = _PRINTED_CODE_RE.search(printed_amount)
    if match is None:
        for symbol, code in _UNAMBIGUOUS_CURRENCY_SYMBOLS.items():
            if symbol in printed_amount:
                return code
        return None
    try:
        return normalise_iso_4217_currency(match.group(1))
    except CoreValidationError:
        return None


def _grounded_text(candidate: str | None, page_words: set[str]) -> str | None:
    """Return ``candidate`` when every evidence-bearing word of it is printed on the page."""
    if candidate is None:
        return None
    collapsed = " ".join(candidate.split())
    if not collapsed or not _words(collapsed) <= page_words:
        return None
    return collapsed


def _line_remainder(line: str, printed: Sequence[str | None]) -> str:
    """Return the anchoring line with its date, amount and balance forms removed."""
    remainder = line
    for value in printed:
        present = _present(value)
        if present is not None:
            remainder = remainder.replace(present.strip(), " ")
    collapsed = " ".join(remainder.split())
    return collapsed or line


@dataclass(frozen=True, slots=True)
class _StatementConventions:
    """Statement-wide readings every movement is parsed under."""

    day_first: bool
    separator: DecimalSeparatorValue | None
    page_currency: Mapping[int, str | None]
    default_currency: str


def _sign_printed_beside(line: str, printed_amount: str) -> int | None:
    """Return the sign the line prints next to the amount, when the proposal left it out.

    A reader may copy ``63,04EUR`` where the line prints ``-63,04EUR``. The
    printed sign is still the authority, so it is read off the line itself:
    a minus or plus immediately before the amount, or a trailing minus.
    """
    compact_line = _compact(line).replace("−", "-")
    body = _compact(printed_amount).replace("−", "-").lstrip("+-")
    index = compact_line.find(body)
    if not body or index < 0:
        return None
    before = compact_line[index - 1] if index > 0 else ""
    end = index + len(body)
    after = compact_line[end] if end < len(compact_line) else ""
    if before == "-" or after == "-":
        return -1
    if before == "+":
        return 1
    return None


def _direction(
    label: str,
    line: str,
    printed_amount: str,
    amount: Decimal,
    proposed: ProposedDirection | None,
    warnings: list[str],
) -> tuple[Decimal, str] | None:
    """Return the signed amount and where its direction came from, or ``None`` to drop."""
    printed_negative = amount < 0
    printed_positive = not printed_negative and _POSITIVE_SIGN_RE.match(printed_amount) is not None
    if not printed_negative and not printed_positive:
        beside = _sign_printed_beside(line, printed_amount)
        if beside is not None:
            amount = abs(amount) * beside
            printed_negative = beside < 0
            printed_positive = beside > 0
    if printed_negative or printed_positive:
        if proposed is not None and (proposed is ProposedDirection.OUT) != printed_negative:
            warnings.append(f"{label}: the reader's direction contradicts the printed sign; dropped")
            return None
        return amount, "printed_sign"
    if proposed is None:
        warnings.append(f"{label}: the amount prints no sign and no direction was proposed; dropped")
        return None
    return (amount if proposed is ProposedDirection.IN else -amount), "reader"


def _ground_movement(
    item: _Anchored,
    conventions: _StatementConventions,
    warnings: list[str],
) -> GroundedMovement | None:
    """Parse one anchored proposal into a movement, or report why it cannot be one."""
    movement = item.movement
    label = _label(item.page, item.position)
    printed_amount = movement.amount or ""
    printed_booked = movement.booked_date or ""
    amount = _parse_signed(printed_amount, conventions.separator)
    if amount is None:
        warnings.append(f"{label}: the printed amount is not a readable amount; dropped")
        return None
    if amount == 0:
        warnings.append(f"{label}: the printed amount is zero; dropped")
        return None
    directed = _direction(label, item.line, printed_amount, amount, movement.direction, warnings)
    if directed is None:
        return None
    signed_amount, direction_source = directed
    try:
        booked_date = parse_date_value(printed_booked, day_first=conventions.day_first, label="booked date")
    except FinancialProviderError:
        warnings.append(f"{label}: the printed booked date is not a complete date; dropped")
        return None
    page_compact = _compact(item.page.text)
    line_compact = _compact(item.line)
    value_date: date | None = None
    printed_value_date = _present(movement.value_date)
    if printed_value_date is not None and _compact(printed_value_date) in page_compact:
        try:
            value_date = parse_date_value(printed_value_date, day_first=conventions.day_first, label="value date")
        except FinancialProviderError:
            printed_value_date = None
    else:
        printed_value_date = None
    balance: Decimal | None = None
    printed_balance = _present(movement.balance)
    if printed_balance is not None and _compact(printed_balance) in line_compact:
        balance = _parse_signed(printed_balance, conventions.separator)
    if balance is None:
        printed_balance = None
    page_words = _words(item.page.text)
    description = _grounded_text(movement.description, page_words) or _line_remainder(
        item.line,
        (printed_booked, printed_amount, printed_value_date, printed_balance),
    )
    currency = (
        _amount_currency(printed_amount)
        or conventions.page_currency.get(item.page.page_number)
        or conventions.default_currency
    )
    printed = {
        "page_number": str(item.page.page_number),
        "line_number": str(item.line_index + 1),
        "booked_date_printed": printed_booked,
        "amount_printed": printed_amount,
        "value_date_printed": printed_value_date or "",
        "balance_printed": printed_balance or "",
        "direction_source": direction_source,
        "transcribed_by": item.page.transcribed_by,
    }
    return GroundedMovement(
        page_number=item.page.page_number,
        line_number=item.line_index + 1,
        booked_date=booked_date,
        value_date=value_date,
        signed_amount=signed_amount,
        currency=currency,
        description=description,
        counterparty=_grounded_text(movement.counterparty, page_words),
        balance=balance,
        direction_source=direction_source,
        printed=printed,
    )


def _printed_balance(
    pages: Sequence[StatementPageText],
    separator: DecimalSeparatorValue | None,
    *,
    opening: bool,
) -> Decimal | None:
    """Return the first printed opening or last printed closing balance a page prints."""
    ordered = pages if opening else tuple(reversed(pages))
    for page in ordered:
        printed = _present(page.proposal.opening_balance if opening else page.proposal.closing_balance)
        if printed is not None and _compact(printed) in _compact(page.text):
            value = _parse_signed(printed, separator)
            if value is not None:
                return value
    return None


def _running_balance_findings(movements: Sequence[GroundedMovement]) -> tuple[int, list[str]]:
    """Check consecutive running balances in whichever order the statement lists them.

    A statement may list oldest first or newest first. Each order makes a
    different claim about consecutive lines, so the check passes when every pair
    agrees under one order; a statement that agrees under neither is
    contradicted.
    """
    checks = 0
    ascending = True
    descending = True
    for previous, current in pairwise(movements):
        if previous.balance is None or current.balance is None:
            continue
        checks += 1
        ascending = ascending and previous.balance + current.signed_amount == current.balance
        descending = descending and current.balance + previous.signed_amount == previous.balance
    if not checks or ascending or descending:
        return checks, []
    return checks, ["the printed running balances do not follow from the movements"]


def _reconcile(
    pages: Sequence[StatementPageText],
    movements: Sequence[GroundedMovement],
    separator: DecimalSeparatorValue | None,
) -> tuple[ReconciliationOutcome, list[str]]:
    """Check the accepted movements against every printed balance."""
    checks, contradictions = _running_balance_findings(movements)
    opening = _printed_balance(pages, separator, opening=True)
    closing = _printed_balance(pages, separator, opening=False)
    if opening is not None and closing is not None:
        checks += 1
        if opening + sum((movement.signed_amount for movement in movements), Decimal(0)) != closing:
            contradictions.append("the movements do not sum from the printed opening balance to the closing balance")
    if contradictions:
        return ReconciliationOutcome.CONTRADICTED, contradictions
    if checks:
        return ReconciliationOutcome.RECONCILED, []
    return ReconciliationOutcome.NOT_CHECKABLE, []


def ground_statement(pages: Sequence[StatementPageText], *, default_currency: str) -> GroundedStatement:
    """Decide which proposed movements a statement prints, and whether it reconciles.

    Args:
        pages: Every page of the statement in document order, transcribed and
            read.
        default_currency: The ISO code a movement takes when neither its amount
            nor its page prints a currency.

    Returns:
        The accepted movements, every dropped proposal as a warning, any
        statement-level refusal, and the reconciliation outcome.
    """
    warnings: list[str] = []
    anchored = [item for page in pages for item in _anchor_page(page, warnings)]
    day_first = _day_first(anchored)
    if day_first is None:
        return GroundedStatement(
            movements=(),
            warnings=tuple(warnings),
            refusals=("the statement prints dates in both day-month and month-day order",),
            reconciliation=ReconciliationOutcome.NOT_CHECKABLE,
        )
    separator = _decimal_separator(anchored, warnings)
    page_currency = {page.page_number: _resolve_currency_code(page.proposal.currency, page.text) for page in pages}
    conventions = _StatementConventions(
        day_first=day_first,
        separator=separator,
        page_currency=page_currency,
        default_currency=default_currency,
    )
    movements = tuple(
        grounded for item in anchored if (grounded := _ground_movement(item, conventions, warnings)) is not None
    )
    printed_currency = any(page_currency.values()) or any(
        _amount_currency(movement.printed["amount_printed"]) for movement in movements
    )
    if movements and not printed_currency:
        warnings.append(
            f"the statement prints no currency the reader could ground; reading amounts as {default_currency}",
        )
    reconciliation, contradictions = _reconcile(pages, movements, separator)
    if reconciliation is ReconciliationOutcome.NOT_CHECKABLE and movements:
        warnings.append(
            "the statement prints no balance the movements could be reconciled against; "
            "review every row before importing",
        )
    if not movements:
        contradictions.append("no movement proposed for this statement is printed on it")
    return GroundedStatement(
        movements=movements,
        warnings=tuple(warnings),
        refusals=tuple(contradictions),
        reconciliation=reconciliation,
    )
