"""Temporal selection for registry-backed modelo revisions.

Selects exactly one :class:`ModeloRevision` from a :class:`ModeloDefinition`
given a filing year, period, and optional date constraint.
"""

from __future__ import annotations

from datetime import date

from ._errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError
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
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo.id,
            candidate_ids=tuple(revision.id for revision in candidates),
        )
    return candidates[0]


def select_revision(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
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
    candidates = []
    for revision in modelo.revisions.values():
        if revision_id is not None and revision.id != revision_id:
            continue
        if not revision.period_selector.includes_year(filing_year):
            continue
        # Case-insensitive comparison is intentional: _resolve_period() in the
        # declaracion parser calls .upper() on every period string before it
        # reaches the registry, producing "ALTA"/"MODIFICACION"/"BAJA" for M036
        # whose canonical registry periods are lowercase.  All other period
        # literal formats are case-invariant, and the shared matcher also lets
        # symbolic EVENT-N selectors cover concrete EVENT-1/EVENT-2 operator
        # scopes.
        #
        # This function still returns the caller's token unchanged; the
        # canonical form is resolved once at the snapshot boundary
        # (_build_validated_snapshot routes through registry_period_for_request).
        # That normalisation is what keeps a case-insensitive match here from
        # becoming a downstream regression: consumers such as
        # relation_source_requirements compare the snapshot's period with exact
        # membership against each relation's target_periods, so a raw "0a" would
        # select this revision while activating none of its relations. Do not
        # drop the snapshot-side normalisation on the strength of this
        # comparison being case-insensitive.
        if selector_token_for_request(revision.period_selector.periods, period) is None:
            continue
        if on is not None and (revision.valid_from > on or (revision.valid_to is not None and revision.valid_to < on)):
            continue
        candidates.append(revision)
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
