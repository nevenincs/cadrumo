"""Closed sort axes for the ``aeat app ledger list`` surface.

The ledger-interface-contract ADR (D5) adds a stable, operator-selectable
sort to ``ledger list``. The two axes are declared here in ``core/`` — the
innermost hexagonal ring — so the Typer boundary can render the
accepted-value ``Choice([...])`` from the enum directly
(``aeat-architecture-boundaries``), production code routes on enum members,
and tests assert against members rather than raw strings.
"""

from __future__ import annotations

from enum import StrEnum


class LedgerSortField(StrEnum):
    """The closed set of fields a ``ledger list`` result may be sorted by.

    ``date`` is the effective value date (value_date or booked_date);
    ``value_date`` is the raw value date; ``amount`` is the non-negative
    magnitude; ``description``, ``lifecycle_state``, and ``classification``
    are the lexical / categorical axes; ``created_at`` / ``modified_at`` are
    the D6 persistence-record lifecycle timestamps; ``classified_at`` is the
    active-decision timestamp. A row missing the chosen key (a ``None``
    timestamp on a row authored before the axis existed) sorts deterministically
    last under both orders, never crashing the sort.
    """

    DATE = "date"
    VALUE_DATE = "value_date"
    AMOUNT = "amount"
    DESCRIPTION = "description"
    CREATED_AT = "created_at"
    MODIFIED_AT = "modified_at"
    CLASSIFIED_AT = "classified_at"
    LIFECYCLE_STATE = "lifecycle_state"
    CLASSIFICATION = "classification"


class LedgerSortOrder(StrEnum):
    """Ascending or descending order for a ``ledger list`` sort."""

    ASC = "asc"
    DESC = "desc"
