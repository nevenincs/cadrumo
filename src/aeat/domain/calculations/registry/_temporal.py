"""Temporal selection for registry-backed modelo revisions.

Selects exactly one :class:`ModeloRevision` from a :class:`ModeloDefinition`
given a filing year, period, and optional date constraint.
"""

from __future__ import annotations

from datetime import date

from ._errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError
from ._schema import ModeloDefinition, ModeloRevision


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
        # formats ("0A", "1T".."4T", "01".."12") are case-invariant, so the
        # normalisation is harmless for them.  Downstream consumers receive the
        # caller-supplied period (the RegistrySnapshot stores it verbatim), not
        # the registry's canonical form, so no case-sensitive downstream
        # regression is possible from this comparison.
        if period.lower() not in {p.lower() for p in revision.period_selector.periods}:
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
