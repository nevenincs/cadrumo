"""Deterministic grounding of statement movements a reader proposed.

A reader proposes the movements it believes a statement page prints. This
module decides which of them ARE printed, and it decides with no model in the
loop: every rule below is a comparison against the page's own text or an exact
sum over printed amounts.

**Anchoring.** A movement is accepted only when its printed booked date and its
printed amount appear together on one line of the page, and each line backs at
most one movement. The amount is the one the line prints: a proposal that
reformatted it is matched by its digits, and the line's printed form is what
gets parsed. Summary blocks and headings print an amount without a movement
date beside it; an invented movement prints nothing at all. Both are dropped
and reported, never imported. A dated line printing only a balance among lines
that print running balances is a balance line, kept as the opening or closing
balance rather than as a movement.

**Direction.** A printed sign decides which way money moved. For an amount
printed without one, as in separate debit and credit columns, the running
balances decide: the balance before plus or minus the amount must give the
line's balance. Only when no balance proves it does the reader's direction
apply. A reader direction that disagrees with a printed sign is reported and
ignored: the date and amount were anchored to the printed line, and the sign
printed on that line is the fact.

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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from .....application.ledger.invoice_label_vocabulary import CURRENCY_CODES
from .....application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementMovement,
    ProposedStatementPage,
)
from .....core.decimal.grammar import DecimalSeparatorValue
from .base import (
    FinancialProviderError,
    infer_day_first,
    infer_decimal_separator,
    parse_date_value,
    parse_statement_amount,
)

__all__ = [
    "GroundedMovement",
    "GroundedStatement",
    "ReconciliationOutcome",
    "StatementPageText",
    "ground_statement",
]

#: A word for the description check: a run of letters or digits.
_WORD_RE = re.compile(r"\w+", re.UNICODE)

#: Words shorter than this carry no evidence a reader could invent.
_MIN_CHECKED_WORD_LENGTH = 2

#: Currency symbols a statement may print instead of an ISO code. Only symbols
#: that name exactly one currency are listed; ``$`` names several.
_UNAMBIGUOUS_CURRENCY_SYMBOLS: Mapping[str, str] = {"€": "EUR", "£": "GBP"}

#: An amount printed with cents: an optional sign or accounting brackets, digit
#: groups and a two-digit decimal part. Requiring cents keeps reference numbers,
#: years and account numbers out; dates are masked before this runs.
_AMOUNT_TOKEN_RE = re.compile(
    r"(?<![\w.,])[+\-\u2212]?\(?(?:\d{1,3}(?:[.,\u00a0\u202f]\d{3})+|\d+)[.,]\d{2}\)?-?(?![.,]?\d)"
)

#: A currency code or symbol written as its own word, at most one space after an amount.
_CURRENCY_AFTER_RE = re.compile(r"^ ?([A-Z]{3}|[€£])(?![A-Za-z])")

#: The same immediately before an amount.
_CURRENCY_BEFORE_RE = re.compile(r"(?:^|[^A-Za-z])([A-Z]{3}|[€£]) ?$")

#: A numeric date, masked out of a line before its amounts are read.
_DATE_SPAN_RE = re.compile(r"(?<!\d)\d{1,4}[./-]\d{1,2}[./-]\d{2,4}(?!\d)")


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
        direction_source: ``printed_sign``, ``running_balance`` or ``reader``.
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
class _Token:
    """One amount printed on a line: its printed form, position and bare digits."""

    text: str
    start: int
    digits: str


@dataclass(frozen=True, slots=True)
class _Anchored:
    """A proposal anchored to one printed line and to the amount printed on it."""

    page: StatementPageText
    position: int
    line_index: int
    line: str
    tokens: tuple[_Token, ...]
    amount: _Token
    movement: ProposedStatementMovement


@dataclass(frozen=True, slots=True)
class _Draft:
    """An anchored movement parsed from its printed forms, direction not yet settled."""

    item: _Anchored
    magnitude: Decimal
    printed_sign: int | None
    balance: Decimal | None
    balance_text: str | None
    booked_date: date
    value_date: date | None
    value_text: str | None
    currency: str


def _present(value: str | None) -> str | None:
    """Return ``value`` unless it is absent or blank."""
    return value if value is not None and value.strip() else None


def _compact(text: str) -> str:
    """Remove every whitespace character, so spacing differences do not matter."""
    return "".join(text.split())


def _digits(text: str) -> str:
    """Return the bare digits of a printed amount, separators and marks removed."""
    return "".join(char for char in text if char.isdigit())


def _words(text: str) -> set[str]:
    """Return the casefolded evidence-bearing words of ``text``."""
    return {word.casefold() for word in _WORD_RE.findall(text) if len(word) >= _MIN_CHECKED_WORD_LENGTH}


def _page_lines(text: str) -> tuple[str, ...]:
    """Return the page's non-blank lines, stripped."""
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _amount_tokens(line: str) -> tuple[_Token, ...]:
    """Return every amount the line prints with cents, dates masked out first."""
    masked = _DATE_SPAN_RE.sub(lambda match: " " * len(match.group(0)), line)
    return tuple(
        _Token(text=match.group(0), start=match.start(), digits=_digits(match.group(0)))
        for match in _AMOUNT_TOKEN_RE.finditer(masked)
    )


def _token_sign(token: _Token) -> int | None:
    """Return the sign printed with an amount, or ``None`` when it prints none."""
    text = token.text.replace("\u2212", "-").strip()
    if text.startswith("-") or text.endswith("-") or (text.startswith("(") and text.endswith(")")):
        return -1
    if text.startswith("+"):
        return 1
    return None


def _label(page: StatementPageText, position: int) -> str:
    """Name a proposal without quoting any of its values."""
    return f"page {page.page_number} movement {position}"


def _amount_on_line(line: str, tokens: tuple[_Token, ...], printed: str) -> _Token | None:
    """Find the printed amount a proposal names on one line.

    The line's own printed form is the authority. A proposal that copied the
    form exactly, or that reformatted it (``5000,00`` for ``5.000,00``), is
    matched by its digits to the amount the line prints, and that printed form
    is what the movement is parsed from. An amount printed without cents is
    matched only by its exact printed form.
    """
    stripped = printed.strip()
    exact = next((token for token in tokens if token.text.strip() == stripped), None)
    if exact is not None:
        return exact
    digits = _digits(printed)
    if digits:
        by_digits = next((token for token in tokens if token.digits == digits), None)
        if by_digits is not None:
            return by_digits
    compact = _compact(stripped)
    if compact and compact in _compact(line):
        return _Token(text=stripped, start=line.find(stripped), digits=digits)
    return None


def _anchor_page(page: StatementPageText, warnings: list[str]) -> list[_Anchored]:
    """Anchor each proposal of one page to an unclaimed line printing its date and amount."""
    if not page.proposal.reply_usable:
        warnings.append(f"page {page.page_number}: the reader's reply could not be used")
    lines = _page_lines(page.text)
    compact_lines = tuple(_compact(line) for line in lines)
    line_tokens = tuple(_amount_tokens(line) for line in lines)
    claimed: set[int] = set()
    anchored: list[_Anchored] = []
    for position, movement in enumerate(page.proposal.movements, start=1):
        label = _label(page, position)
        printed_amount = _present(movement.amount)
        printed_booked = _present(movement.booked_date)
        if printed_amount is None or printed_booked is None:
            warnings.append(f"{label}: no printed date or amount was proposed; dropped")
            continue
        booked = _compact(printed_booked)
        found: tuple[int, _Token] | None = None
        for index, line in enumerate(lines):
            if index in claimed or booked not in compact_lines[index]:
                continue
            token = _amount_on_line(line, line_tokens[index], printed_amount)
            if token is not None:
                found = (index, token)
                break
        if found is None:
            warnings.append(f"{label}: its date and amount are not printed together on one line; dropped")
            continue
        index, token = found
        claimed.add(index)
        anchored.append(_Anchored(page, position, index, lines[index], line_tokens[index], token, movement))
    return anchored


def _day_first(anchored: Sequence[_Anchored]) -> bool | None:
    """Infer the statement's day order from its printed dates, or ``None`` on conflict."""
    return infer_day_first(
        printed
        for item in anchored
        for printed in (item.movement.booked_date, item.movement.value_date)
        if printed is not None
    )


def _decimal_separator(anchored: Sequence[_Anchored], warnings: list[str]) -> DecimalSeparatorValue | None:
    """Infer the statement's decimal convention from every amount its anchored lines print."""
    separator, mixed = infer_decimal_separator(token.text for item in anchored for token in (item.amount, *item.tokens))
    if mixed:
        warnings.append(f"amounts print both decimal conventions; reading them as {separator!r}-decimal")
    return separator


def _parse_signed(printed: str, separator: DecimalSeparatorValue | None) -> Decimal | None:
    """Parse one printed amount, or ``None`` when it is unreadable or its separator stays ambiguous."""
    try:
        return parse_statement_amount(printed, decimal_separator=separator)
    except FinancialProviderError:
        return None


def _resolve_currency_code(candidate: str | None, page_text: str) -> str | None:
    """Return an ISO code for a printed currency mark the page actually prints."""
    if candidate is None or not candidate.strip():
        return None
    mark = candidate.strip()
    code = _UNAMBIGUOUS_CURRENCY_SYMBOLS.get(mark, mark.upper())
    if code not in CURRENCY_CODES or (mark not in page_text and code not in page_text):
        return None
    return code


def _currency_beside(line: str, token: _Token) -> str | None:
    """Return the currency printed immediately beside an amount, if any.

    Only a mark touching the amount, or one space from it, counts. A code
    elsewhere on the line -- a ``BIC`` label, an account name -- says nothing
    about this amount.
    """
    if token.start < 0:
        return None
    following = _CURRENCY_AFTER_RE.match(line[token.start + len(token.text) :])
    preceding = _CURRENCY_BEFORE_RE.search(line[: token.start])
    for match in (following, preceding):
        if match is None:
            continue
        mark = str(match.group(1))
        code = _UNAMBIGUOUS_CURRENCY_SYMBOLS.get(mark, mark)
        if code in CURRENCY_CODES:
            return code
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


def _line_balance(item: _Anchored, separator: DecimalSeparatorValue | None) -> tuple[Decimal | None, str | None]:
    """Return the running balance the anchoring line prints after the movement's amount.

    The balance the reader proposed is used when the line prints it after the
    amount; otherwise the last amount printed after the movement's amount is
    the line's running balance. A line printing nothing after the amount has
    none.
    """
    after = tuple(token for token in item.tokens if token.start > item.amount.start)
    if not after:
        return None, None
    proposed = _present(item.movement.balance)
    chosen = next((token for token in after if proposed is not None and token.digits == _digits(proposed)), after[-1])
    value = _parse_signed(chosen.text, separator)
    return (value, chosen.text) if value is not None else (None, None)


def _draft(item: _Anchored, conventions: _StatementConventions, warnings: list[str]) -> _Draft | None:
    """Parse one anchored proposal's printed forms, or report why it cannot be a movement."""
    label = _label(item.page, item.position)
    movement = item.movement
    amount = _parse_signed(item.amount.text, conventions.separator)
    if amount is None:
        warnings.append(f"{label}: the printed amount is not a readable amount; dropped")
        return None
    if amount == 0:
        warnings.append(f"{label}: the printed amount is zero; dropped")
        return None
    sign = -1 if amount < 0 else _token_sign(item.amount)
    if (
        sign is not None
        and movement.direction is not None
        and (movement.direction is ProposedDirection.OUT) != (sign < 0)
    ):
        warnings.append(f"{label}: the reader's direction disagrees with the printed sign; the printed sign is used")
    try:
        booked_date = parse_date_value(movement.booked_date or "", day_first=conventions.day_first, label="booked date")
    except FinancialProviderError:
        warnings.append(f"{label}: the printed booked date is not a complete date; dropped")
        return None
    value_text = _present(movement.value_date)
    value_date: date | None = None
    if value_text is not None and _compact(value_text) in _compact(item.page.text):
        try:
            value_date = parse_date_value(value_text, day_first=conventions.day_first, label="value date")
        except FinancialProviderError:
            value_text = None
    else:
        value_text = None
    balance, balance_text = _line_balance(item, conventions.separator)
    currency = (
        _currency_beside(item.line, item.amount)
        or conventions.page_currency.get(item.page.page_number)
        or conventions.default_currency
    )
    return _Draft(
        item=item,
        magnitude=abs(amount),
        printed_sign=sign,
        balance=balance,
        balance_text=balance_text,
        booked_date=booked_date,
        value_date=value_date,
        value_text=value_text,
        currency=currency,
    )


@dataclass(frozen=True, slots=True)
class _PrintedBalances:
    """Opening and closing balances read off dated balance lines, before any reader claim."""

    opening: Decimal | None
    closing: Decimal | None


def _signed_value(draft: _Draft) -> Decimal:
    """Return the draft's printed value, signed only where the line prints a sign."""
    return -draft.magnitude if draft.printed_sign == -1 else draft.magnitude


def _balance_line_role(index: int, drafts: Sequence[_Draft]) -> str | None:
    """Classify a dated line that prints only a balance among lines that print one.

    A ``brought forward`` or ``carried forward`` line prints a date and one
    amount, which is the running balance itself rather than a movement. It is
    recognised arithmetically: next to a movement line printing a running
    balance, its value either equals that balance (the balance carried on) or
    is the balance before that movement (the balance brought in).
    """
    draft = drafts[index]
    if draft.balance is not None:
        return None
    value = _signed_value(draft)
    for neighbour_index in (index - 1, index + 1):
        if not 0 <= neighbour_index < len(drafts):
            continue
        neighbour = drafts[neighbour_index]
        if neighbour.balance is None:
            continue
        signs = (neighbour.printed_sign,) if neighbour.printed_sign is not None else (1, -1)
        if any(value + sign * neighbour.magnitude == neighbour.balance for sign in signs):
            return "opening"
        if value == neighbour.balance:
            return "closing"
    return None


def _separate_balance_lines(drafts: Sequence[_Draft], warnings: list[str]) -> tuple[list[_Draft], _PrintedBalances]:
    """Drop dated balance lines from the movements and keep their values as printed balances."""
    movements: list[_Draft] = []
    opening: Decimal | None = None
    closing: Decimal | None = None
    for index, draft in enumerate(drafts):
        role = _balance_line_role(index, drafts)
        if role is None:
            movements.append(draft)
            continue
        warnings.append(f"{_label(draft.item.page, draft.item.position)}: prints a balance, not a movement; dropped")
        if role == "opening" and opening is None:
            opening = _signed_value(draft)
        elif role == "closing":
            closing = _signed_value(draft)
    return movements, _PrintedBalances(opening=opening, closing=closing)


def _balance_sign(index: int, movements: Sequence[_Draft], opening: Decimal | None) -> int | None:
    """Return the direction the running balances prove for an unsigned amount, if they prove one.

    The balance printed before this movement -- the previous line's in an
    oldest-first statement, the next line's in a newest-first one, the opening
    balance at either end -- plus or minus the amount must give this line's
    balance. Exactly one of the two can hold for a non-zero amount.
    """
    draft = movements[index]
    if draft.balance is None:
        return None
    previous = movements[index - 1].balance if index > 0 else opening
    following = movements[index + 1].balance if index + 1 < len(movements) else opening
    for before in (previous, following):
        if before is None:
            continue
        if before + draft.magnitude == draft.balance:
            return 1
        if before - draft.magnitude == draft.balance:
            return -1
    return None


def _settle(
    movements: Sequence[_Draft],
    opening: Decimal | None,
    warnings: list[str],
) -> list[tuple[_Draft, Decimal, str]]:
    """Give every movement its signed amount: printed sign, then running balance, then reader."""
    settled: list[tuple[_Draft, Decimal, str]] = []
    for index, draft in enumerate(movements):
        if draft.printed_sign is not None:
            settled.append((draft, draft.magnitude * draft.printed_sign, "printed_sign"))
            continue
        proven = _balance_sign(index, movements, opening)
        if proven is not None:
            settled.append((draft, draft.magnitude * proven, "running_balance"))
            continue
        proposed = draft.item.movement.direction
        if proposed is None:
            warnings.append(
                f"{_label(draft.item.page, draft.item.position)}: the amount prints no sign, no running balance "
                "proves its direction and no direction was proposed; dropped",
            )
            continue
        settled.append((draft, draft.magnitude if proposed is ProposedDirection.IN else -draft.magnitude, "reader"))
    return settled


def _movement(draft: _Draft, signed_amount: Decimal, direction_source: str) -> GroundedMovement:
    """Build the accepted movement and the printed forms it was parsed from."""
    item = draft.item
    movement = item.movement
    page_words = _words(item.page.text)
    description = _grounded_text(movement.description, page_words) or _line_remainder(
        item.line,
        (movement.booked_date, item.amount.text, draft.value_text, draft.balance_text),
    )
    printed = {
        "page_number": str(item.page.page_number),
        "line_number": str(item.line_index + 1),
        "booked_date_printed": movement.booked_date or "",
        "amount_printed": item.amount.text,
        "value_date_printed": draft.value_text or "",
        "balance_printed": draft.balance_text or "",
        "direction_source": direction_source,
        "transcribed_by": item.page.transcribed_by,
    }
    return GroundedMovement(
        page_number=item.page.page_number,
        line_number=item.line_index + 1,
        booked_date=draft.booked_date,
        value_date=draft.value_date,
        signed_amount=signed_amount,
        currency=draft.currency,
        description=description,
        counterparty=_grounded_text(movement.counterparty, page_words),
        balance=draft.balance,
        direction_source=direction_source,
        printed=printed,
    )


def _proposed_balance(
    pages: Sequence[StatementPageText],
    separator: DecimalSeparatorValue | None,
    *,
    opening: bool,
) -> Decimal | None:
    """Return the first opening or last closing balance a reader proposed that its page prints."""
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
    movements: Sequence[GroundedMovement],
    opening: Decimal | None,
    closing: Decimal | None,
) -> tuple[ReconciliationOutcome, list[str]]:
    """Check the accepted movements against every printed balance."""
    checks, contradictions = _running_balance_findings(movements)
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
    drafts = [draft for item in anchored if (draft := _draft(item, conventions, warnings)) is not None]
    candidates, printed_balances = _separate_balance_lines(drafts, warnings)
    opening = (
        printed_balances.opening
        if printed_balances.opening is not None
        else _proposed_balance(pages, separator, opening=True)
    )
    closing = (
        printed_balances.closing
        if printed_balances.closing is not None
        else _proposed_balance(pages, separator, opening=False)
    )
    movements = tuple(
        _movement(draft, signed, source) for draft, signed, source in _settle(candidates, opening, warnings)
    )
    printed_currency = any(page_currency.values()) or any(
        _currency_beside(movement_draft.item.line, movement_draft.item.amount) for movement_draft in candidates
    )
    if movements and not printed_currency:
        warnings.append(
            f"the statement prints no currency the reader could ground; reading amounts as {default_currency}",
        )
    reconciliation, contradictions = _reconcile(movements, opening, closing)
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
