"""Ground a complete statement through printed movements, balance spans and coverage evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from .....core.decimal.grammar import DecimalSeparatorValue
from ._statement_grounding import (
    GroundedMovement,
    GroundedStatement,
    MovementDraft,
    PrintedBalances,
    ReconciliationOutcome,
    StatementConventions,
    StatementPageText,
    anchor_statement_page,
    currency_beside_amount,
    draft_anchored_movement,
    grounded_movement,
    proposed_statement_balance,
    reconcile_statement,
    resolve_statement_currency,
    separate_balance_lines,
    settle_statement_drafts,
    statement_day_first,
    statement_decimal_separator,
    unaccounted_statement_lines,
)


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
    anchored = [item for page in pages for item in anchor_statement_page(page, warnings)]
    day_first = statement_day_first(anchored)
    if day_first is None:
        return GroundedStatement(
            movements=(),
            warnings=tuple(warnings),
            refusals=("the statement prints dates in both day-month and month-day order",),
            reconciliation=ReconciliationOutcome.NOT_CHECKABLE,
        )
    separator = statement_decimal_separator(anchored, warnings)
    page_currency = {page.page_number: resolve_statement_currency(page.proposal.currency, page.text) for page in pages}
    conventions = StatementConventions(
        day_first=day_first,
        separator=separator,
        page_currency=page_currency,
        default_currency=default_currency,
    )
    drafts = [draft for item in anchored if (draft := draft_anchored_movement(item, conventions, warnings)) is not None]
    candidates, printed_balances = separate_balance_lines(drafts, warnings)
    opening, closing = _balance_bounds(pages, separator, printed_balances)
    movements = tuple(
        grounded_movement(draft, signed, source)
        for draft, signed, source in settle_statement_drafts(candidates, opening, warnings)
    )
    _warn_currency(movements, page_currency, candidates, default_currency, warnings)
    reconciliation, confirmed, complete = reconcile_statement(movements, opening, closing)
    contradictions: list[str] = []
    if reconciliation is ReconciliationOutcome.CONTRADICTED:
        contradictions.append("the printed balances do not follow from the accepted movements")
    movements = _confirmed_movements(movements, confirmed)
    _review_unconfirmed(movements, reconciliation, warnings, contradictions)
    _check_coverage(
        pages, movements, printed_balances, opening, closing, conventions, complete, warnings, contradictions
    )
    if not movements:
        contradictions.append("no movement proposed for this statement is printed on it")
    return GroundedStatement(
        movements=movements,
        warnings=tuple(warnings),
        refusals=tuple(contradictions),
        reconciliation=reconciliation,
    )


def _warn_currency(
    movements: Sequence[GroundedMovement],
    page_currency: Mapping[int, str | None],
    candidates: Sequence[MovementDraft],
    default_currency: str,
    warnings: list[str],
) -> None:
    """Warn only when accepted movements have neither a printed page nor amount currency."""
    printed_currency = any(page_currency.values()) or any(
        currency_beside_amount(movement_draft.item.line, movement_draft.item.amount) for movement_draft in candidates
    )
    if movements and not printed_currency:
        warnings.append(
            f"the statement prints no currency the reader could ground; reading amounts as {default_currency}",
        )


def _confirmed_movements(
    movements: tuple[GroundedMovement, ...], confirmed: frozenset[int]
) -> tuple[GroundedMovement, ...]:
    """Stamp balance-span confirmation while retaining every original printed field."""
    movements = tuple(
        replace(
            movement,
            confirmed=position in confirmed,
            printed={**movement.printed, "confirmed": str(position in confirmed).lower()},
        )
        for position, movement in enumerate(movements)
    )
    return movements


def _review_unconfirmed(
    movements: Sequence[GroundedMovement],
    reconciliation: ReconciliationOutcome,
    warnings: list[str],
    contradictions: list[str],
) -> None:
    """Retain review warnings and refuse reader-only direction outside confirmed spans."""
    unconfirmed = [movement for movement in movements if not movement.confirmed]
    if reconciliation is ReconciliationOutcome.NOT_CHECKABLE and movements:
        warnings.append(
            "the statement prints no balance the movements could be reconciled against; "
            "review every row before importing",
        )
    elif unconfirmed and reconciliation is ReconciliationOutcome.RECONCILED:
        warnings.append(f"{len(unconfirmed)} movement(s) are not spanned by a printed balance check; review them")
    guessed = sum(1 for movement in unconfirmed if movement.direction_source == "reader")
    if guessed:
        contradictions.append(
            f"{guessed} movement(s) print no sign and no printed balance confirms the reader's direction",
        )


def _check_coverage(
    pages: Sequence[StatementPageText],
    movements: Sequence[GroundedMovement],
    printed_balances: PrintedBalances,
    opening: Decimal | None,
    closing: Decimal | None,
    conventions: StatementConventions,
    complete: bool,
    warnings: list[str],
    contradictions: list[str],
) -> None:
    """Classify every unaccounted printed movement according to complete balance evidence."""
    accounted = (
        frozenset((movement.page_number, movement.line_number - 1) for movement in movements) | printed_balances.lines
    )
    known_balances = frozenset(
        value
        for value in (opening, closing, *(movement.balance for movement in movements), *printed_balances.values)
        if value is not None
    )
    for line in unaccounted_statement_lines(pages, accounted, known_balances, conventions):
        finding = f"{line} prints a date and an amount that no accepted movement accounts for"
        if complete:
            warnings.append(finding)
        else:
            contradictions.append(finding)


def _balance_bounds(
    pages: Sequence[StatementPageText], separator: DecimalSeparatorValue | None, printed_balances: PrintedBalances
) -> tuple[Decimal | None, Decimal | None]:
    """Prefer balances established by printed dated lines over page-level reader proposals."""
    opening = (
        printed_balances.opening
        if printed_balances.opening is not None
        else proposed_statement_balance(pages, separator, opening=True)
    )
    closing = (
        printed_balances.closing
        if printed_balances.closing is not None
        else proposed_statement_balance(pages, separator, opening=False)
    )
    return opening, closing
