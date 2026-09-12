"""Temporal selection for registry-backed modelo revisions.

Selects exactly one :class:`ModeloRevision` from a :class:`ModeloDefinition`
given a filing year, period, and optional date constraint.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from .errors import (
    AmbiguousRevisionSelectionError,
    EjercicioOrdenNotYetPublishedError,
    NoRevisionForPeriodError,
)
from .ids import RevisionId
from .period_selector_match import selector_token_for_request
from .schema import ModeloDefinition, ModeloRevision, SupportedFilingYearsCatalogue


def _supported_filing_year(
    filing_year: int,
    support: SupportedFilingYearsCatalogue | None,
) -> int | None:
    """Project an admitted year through the shared support-envelope mechanics."""
    if support is None:
        return filing_year
    return support.projection_coordinate(filing_year)


def _project_reference_date(on: date | None, *, requested_year: int, selection_year: int) -> date | None:
    """Preserve a reference date's filing-year offset when support projects the year."""
    if on is None or requested_year == selection_year:
        return on
    projected_year = on.year - (requested_year - selection_year)
    projected_day = min(on.day, monthrange(projected_year, on.month)[1])
    return on.replace(year=projected_year, day=projected_day)


def _declared_filing_window_covers(
    revision: ModeloRevision,
    *,
    on: date,
    filing_year: int,
    period: str | None,
) -> bool:
    """Return whether ``on`` falls inside a filing window this revision declares.

    Scoped to the requested coordinate: a window admits ``on`` only for the
    ``filing_year`` it declares and, when the caller named one, the period it
    declares. A window opened for December's monthly filing must not admit a
    request for the fourth quarter merely because the two are filed together.
    """
    for window in revision.deadline_windows:
        if window.filing_year != filing_year:
            continue
        if period is not None and selector_token_for_request((window.period.registry_token,), period) is None:
            continue
        if window.opens_on <= on <= window.closes_on:
            return True
    return False


def _revision_governs_period_on(revision: ModeloRevision, on: date) -> bool:
    """Return whether ``on`` falls inside the tax periods a revision governs."""
    return revision.contains_date(on)


def _effective_candidates(
    matching: list[ModeloRevision],
    *,
    on: date | None,
    filing_year: int,
    period: str | None,
) -> list[ModeloRevision]:
    """Narrow selector-matched revisions to those applicable on ``on``, in tiers.

    ``valid_from``/``valid_to`` delimit the TAX PERIODS a revision governs, not
    the dates on which it may be filed: the corpus declares them at period
    granularity throughout, down to mid-period design boundaries (modelo 490's
    2022 first quarter closes at 31 March 2022, modelo 763's 2012 revision spans
    only its second and third quarters). Almost every filing is made after the
    period it declares has closed, so testing a filing date against that window
    alone refuses the revision at the very moment it is legally due -- modelo
    390's resumen anual is filed in the thirty first calendar days of the
    January FOLLOWING its ejercicio (Orden EHA/3111/2009, art. 8), which no
    ``valid_to`` of 31 December can contain.

    The filing reach is therefore read from the one place the registry grounds
    it -- the revision's own ``deadline_windows``, each carrying the legal and
    source references that establish it -- rather than by widening a period
    window past the law or inferring a deadline in code.

    The two tiers are ORDERED, not pooled, and the order is what keeps a design
    boundary readable. Across a boundary the outgoing revision's last filing
    window overlaps the incoming revision's first governed periods: on 15
    September 2024 modelo 303's ``2024-hasta-08-y-2t`` is still filable for
    August while ``2024-desde-09-y-3t`` already governs September. Pooling the
    two makes that date ambiguous and refuses a question that has an obvious
    answer. A revision whose governed periods are live is the design in force,
    so the window tier is consulted only once no candidate governs ``on`` --
    which is exactly the after-the-year-closes case the windows exist for.

    A revision declaring no window for the requested coordinate makes no claim
    about being filable outside its periods and is refused exactly as before.
    """
    if on is None:
        return matching
    governing = [revision for revision in matching if _revision_governs_period_on(revision, on)]
    if governing:
        return governing
    return [
        revision
        for revision in matching
        if _declared_filing_window_covers(revision, on=on, filing_year=filing_year, period=period)
    ]


def _year_revision_candidates(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    on: date | None,
) -> list[ModeloRevision]:
    """Return year-matching revisions applicable on ``on``, in the declared order.

    ``period`` is ``None`` here because the question is not period-scoped: the
    caller asked which revision governs a filing YEAR. Every window the modelo
    declares for that year is therefore admissible evidence, and the tier order
    above -- not a period filter this caller cannot supply -- is what keeps a
    design boundary unambiguous.
    """
    matching = [
        revision for revision in modelo.revisions.values() if revision.period_selector.includes_year(filing_year)
    ]
    return _effective_candidates(matching, on=on, filing_year=filing_year, period=None)


def _absence_refusal(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    revision_id: RevisionId | None,
) -> NoRevisionForPeriodError:
    """Build the refusal for a year no revision covers, as specific as the corpus allows.

    A modelo that has declared the year awaits its approving Orden gets to say
    so: the request failed for a reason nobody can act on yet, which is a
    different fact from an unattended gap and leads an operator somewhere else.
    Absent a declaration the plain absence refusal stands, so a modelo that has
    simply not been authored cannot borrow the excuse.
    """
    available = tuple(str(declared) for declared in modelo.revisions)
    pending = modelo.pending_orden_for(filing_year)
    if pending is not None:
        return EjercicioOrdenNotYetPublishedError(
            modelo_id=modelo.id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            available_revision_ids=available,
            rests_on=str(pending.rests_on),
            expected_publication_year=pending.expected_publication_year,
        )
    return NoRevisionForPeriodError(
        modelo_id=modelo.id,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        available_revision_ids=available,
    )


def _select_single_year_revision(
    modelo: ModeloDefinition,
    candidates: list[ModeloRevision],
    *,
    filing_year: int,
) -> ModeloRevision:
    """Resolve year candidates, refusing both absence and mid-year ambiguity."""
    if not candidates:
        raise _absence_refusal(modelo, filing_year=filing_year, period="year", revision_id=None)
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


def select_revision_for_year(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    on: date | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
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
        on: Optional reference date at which the revision must be the
            applicable design: inside the tax periods it governs, or inside a
            filing window it declares for this coordinate.
        support: Optional registry envelope that hard-gates the request and
            carries a year beyond its authored horizon back to that horizon.
    """
    selection_year = _supported_filing_year(filing_year, support)
    selection_on = (
        None
        if selection_year is None
        else _project_reference_date(on, requested_year=filing_year, selection_year=selection_year)
    )
    return _select_single_year_revision(
        modelo,
        []
        if selection_year is None
        else _year_revision_candidates(modelo, filing_year=selection_year, on=selection_on),
        filing_year=filing_year,
    )


def select_revision(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
) -> ModeloRevision:
    """Select exactly one :class:`ModeloRevision` for a filing period.

    Args:
        modelo: The :class:`ModeloDefinition` to select a revision from.
        filing_year: AEAT filing year used to narrow revisions by
            ``period_selector``.
        period: Period token (e.g. ``"1T"``, ``"0A"``, ``"ALTA"``);
            case-insensitive against the revision's declared periods.
        on: Optional reference date at which the revision must be the
            applicable design: inside the tax periods it governs, or inside a
            filing window it declares for this coordinate.
        revision_id: Optional explicit revision id; restricts candidates to
            the matching revision when supplied.
        support: Optional registry envelope that hard-gates the request and
            carries a year beyond its authored horizon back to that horizon.
    """
    selection_year = _supported_filing_year(filing_year, support)
    matching = (
        []
        if selection_year is None
        else [
            revision
            for revision in modelo.revisions.values()
            if _revision_matches_request(
                revision,
                filing_year=selection_year,
                period=period,
                revision_id=revision_id,
            )
        ]
    )
    selection_on = (
        None
        if selection_year is None
        else _project_reference_date(on, requested_year=filing_year, selection_year=selection_year)
    )
    candidates = _effective_candidates(
        matching,
        on=selection_on,
        filing_year=filing_year if selection_year is None else selection_year,
        period=period,
    )
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
    revision_id: RevisionId | None,
) -> bool:
    """Return whether a revision matches the request's identity and selector.

    Deliberately date-free: ``on`` narrows the matched set in tiers via
    :func:`_effective_candidates`, which cannot be expressed as a per-revision
    predicate because the tier a revision lands in depends on whether any OTHER
    candidate governs the date.
    """
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
    return selector_token_for_request(revision.period_selector.periods_for_year(filing_year), period) is not None


def _select_single_revision(
    modelo: ModeloDefinition,
    candidates: list[ModeloRevision],
    *,
    filing_year: int,
    period: str,
    revision_id: RevisionId | None,
) -> ModeloRevision:
    if not candidates:
        raise _absence_refusal(modelo, filing_year=filing_year, period=period, revision_id=revision_id)
    if len(candidates) > 1:
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo.id,
            candidate_ids=tuple(revision.id for revision in candidates),
        )
    return candidates[0]
