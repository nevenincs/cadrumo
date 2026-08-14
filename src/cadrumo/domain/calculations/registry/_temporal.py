"""Temporal selection for registry-backed modelo revisions.

Selects exactly one :class:`ModeloRevision` from a :class:`ModeloDefinition`
given a filing year, period, and optional date constraint.
"""

from __future__ import annotations

from datetime import date

from ._errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError
from ._ids import RevisionId
from ._period_selector_match import selector_token_for_request
from ._schema import ModeloDefinition, ModeloRevision


def select_revision_for_year(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    on: date | None = None,
) -> ModeloRevision:
    """Select exactly one revision for a filing year and effective date.

    This is the year-only authority for read-only revision-wide surfaces such
    as bindings discovery.  Callers that already have its revision may
    materialise a snapshot with that explicit ``revision_id`` rather than
    independently selecting again.

    Args:
        modelo: The :class:`ModeloDefinition` whose declared revisions are
            searched for the one matching ``filing_year`` and ``on``.
        filing_year: AEAT filing year used to narrow revisions by their
            ``period_selector``.
        on: Optional reference date that must fall within the revision's
            ``valid_from`` / ``valid_to`` window.
    """
    candidates = [
        revision
        for revision in modelo.revisions.values()
        if revision.period_selector.includes_year(filing_year)
        and (on is None or (revision.valid_from <= on and (revision.valid_to is None or on <= revision.valid_to)))
    ]
    if not candidates:
        raise NoRevisionForPeriodError(
            modelo_id=modelo.id,
            filing_year=filing_year,
            period="year",
            revision_id=None,
        )
    if len(candidates) > 1:
        # A year-only answer for a year covered by more than one revision is wrong
        # in whichever direction it is given, so this refuses rather than picking.
        # The REMEDY is selected by naming a locale key of its own: the
        # period-scoped selector raises the same error, and telling that caller to
        # supply a period would send it to redo what it already did.
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo.id,
            candidate_ids=tuple(revision.id for revision in candidates),
            filing_year=filing_year,
            reason=(
                "this filing year carries a mid-year AEAT design boundary, so more than one "
                "revision covers it and no year-only answer is correct"
            ),
            translated_message="errors.snapshot.ambiguous_revision_selection_year_only",
        )
    return candidates[0]


def select_revision(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
) -> ModeloRevision:
    """Select exactly one :class:`ModeloRevision` for a filing period.

    Args:
        modelo: The :class:`ModeloDefinition` to select a revision from.
        filing_year: AEAT filing year used to narrow revisions by
            ``period_selector``.
        period: Period token (e.g. ``"1T"``, ``"0A"``, ``"ALTA"``);
            case-insensitive against the revision's declared periods.
        on: Optional reference date that must fall within the revision's
            ``valid_from`` / ``valid_to`` window.
        revision_id: Optional explicit revision id; restricts candidates to
            the matching revision when supplied.
    """
    candidates = [
        revision
        for revision in modelo.revisions.values()
        if _revision_matches_request(
            revision,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
        )
    ]
    return _select_single_revision(
        modelo,
        candidates,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )


def _revision_matches_request(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
    on: date | None,
    revision_id: RevisionId | None,
) -> bool:
    if revision_id is not None and revision.id != revision_id:
        return False
    if not revision.period_selector.includes_year(filing_year):
        return False
    # Case-insensitive comparison is intentional: _resolve_period() in the
    # declaracion parser calls .upper() on every period string before it reaches
    # the registry, producing "ALTA"/"MODIFICACION"/"BAJA" for M036 whose
    # canonical registry periods are lowercase. The shared matcher also lets
    # symbolic EVENT-N selectors cover concrete EVENT-1/EVENT-2 scopes.
    #
    # The caller's token remains unchanged; canonical normalisation happens at
    # the snapshot boundary, where relation consumers compare exact tokens.
    if selector_token_for_request(revision.period_selector.periods, period) is None:
        return False
    return on is None or (revision.valid_from <= on and (revision.valid_to is None or on <= revision.valid_to))


def _select_single_revision(
    modelo: ModeloDefinition,
    candidates: list[ModeloRevision],
    *,
    filing_year: int,
    period: str,
    revision_id: RevisionId | None,
) -> ModeloRevision:
    if not candidates:
        raise NoRevisionForPeriodError(
            modelo_id=modelo.id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        )
    if len(candidates) > 1:
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo.id,
            candidate_ids=tuple(revision.id for revision in candidates),
        )
    return candidates[0]
