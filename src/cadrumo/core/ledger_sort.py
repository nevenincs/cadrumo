"""Closed sort axes for the ``aeat app ledger list`` surface.

``ledger list`` exposes a stable, operator-selectable sort. The two axes are
declared here in ``core/`` — the innermost hexagonal ring — so the authored
command specification can project the accepted values from the enum directly,
production code routes on enum members, and tests assert against members rather
than raw strings.

:class:`LedgerSortField` selects the projection axis and
:class:`LedgerSortOrder` selects the direction. The CLI parser and the
ledger projection service both use these enum members rather than raw
string tokens, threading them through
:data:`cadrumo.entrypoints.cli._app_ledger_command_specs.LEDGER_COMMAND_SPECS`,
:func:`cadrumo.entrypoints.cli._ledger_read_cli.ledger_list`,
:func:`cadrumo.entrypoints.cli._ledger_list.project_ledger_list`, and the stable
:func:`cadrumo.entrypoints.cli._ledger_list._sort_results` helper.

This module deliberately declares tokens only. It does not project
transactions, compare rows, page results, or decide missing-key ordering; those
rules stay in the ledger-list projection helpers so the CLI and tests exercise
one implementation.
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

    The value set is consumed by the command-spec runtime and by
    :func:`cadrumo.entrypoints.cli._ledger_list._sort_field_value`, so any new
    member must be added with a projection over
    :class:`~cadrumo.domain.transactions.Transaction` and covered by the real
    repository sort tests.

    Attributes:
        DATE: Effective value date, falling back to booked date.
        VALUE_DATE: Raw value date from the imported/manual transaction.
        AMOUNT: Non-negative transaction magnitude.
        DESCRIPTION: Operator-facing transaction description.
        CREATED_AT: Persistence-record creation timestamp.
        MODIFIED_AT: Persistence-record modification timestamp.
        CLASSIFIED_AT: Timestamp for the active classification decision.
        LIFECYCLE_STATE: Transaction lifecycle state token.
        CLASSIFICATION: Business classification token.
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
    """Ascending or descending order for a ``ledger list`` sort.

    :class:`LedgerSortOrder` controls only the primary axis selected by
    :class:`LedgerSortField`; the final content-addressed ``transaction_id``
    tie-break remains ascending in
    :func:`cadrumo.entrypoints.cli._ledger_list._sort_results`.

    Attributes:
        ASC: Sort the primary axis ascending.
        DESC: Sort the primary axis descending.
    """

    ASC = "asc"
    DESC = "desc"
