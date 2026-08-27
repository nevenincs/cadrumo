"""Advisory checks on a revision's own temporal declaration.

A revision states when it applies twice over: once as a validity window
(``valid_from`` / ``valid_to``) and once as a period selector. The two can
disagree, and nothing else in registry validation compares them, so a revision
can declare a bounded selector while claiming an open-ended validity, or claim
to start in a year its selector never reaches.

These findings are ADVISORY and this module never raises. An incoherent
temporal declaration does not make a filing wrong on its own -- revision
selection still resolves through the window gate -- so refusing the whole
registry load over one would take the corpus offline for a defect that harms
nothing today. What it does do is make the next revision harder to reason
about, which is what an advisory is for.

Supersession is defined by OVERLAP, not by date order. Modelo 369 ships three
revisions that all begin on the same day and partition the period axis between
them -- the OSS esquema exterior, importación and unión -- and none supersedes
any other. A check that read "a later sibling exists" as supersession would
report two of those three on every run, and an advisory that fires on correct
data is one operators learn to ignore.
"""

from __future__ import annotations

from collections.abc import Iterable

from .schema import ModeloDefinition, ModeloRevision

__all__ = [
    "temporal_coherence_advisories",
]


def _selector_periods(revision: ModeloRevision) -> frozenset[str]:
    """Return the period tokens ``revision`` declares, as plain strings."""
    return frozenset(str(period) for period in (getattr(revision.period_selector, "periods", None) or ()))


def _selector_year_from(revision: ModeloRevision) -> int | None:
    """Return the selector's declared first year, when it declares one."""
    year_from = getattr(revision.period_selector, "year_from", None)
    return int(year_from) if year_from is not None else None


def _selector_year_to(revision: ModeloRevision) -> int | None:
    """Return the selector's declared last year, when it declares one."""
    year_to = getattr(revision.period_selector, "year_to", None)
    return int(year_to) if year_to is not None else None


def _superseding_revisions(
    revision: ModeloRevision,
    siblings: Iterable[ModeloRevision],
) -> tuple[ModeloRevision, ...]:
    """Return the siblings that genuinely supersede ``revision``.

    A sibling supersedes only when it starts strictly later AND competes for at
    least one of the same periods. Parallel regimes that partition the period
    axis never supersede one another however their start dates compare.
    """
    own_periods = _selector_periods(revision)
    return tuple(
        sibling
        for sibling in siblings
        if sibling is not revision
        and sibling.valid_from > revision.valid_from
        and (_selector_periods(sibling) & own_periods)
    )


def temporal_coherence_advisories(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Return one advisory line per incoherent temporal declaration.

    Three conditions are reported:

    - a revision that a later overlapping sibling supersedes while declaring no
      validity terminus, so the corpus states two revisions govern the same
      period from the successor's start onward;
    - a revision whose selector is bounded by a declared last year while its
      validity end is left open, so the two declarations disagree about when it
      stops;
    - a revision whose selector first year is not the year its declared validity
      starts in.

    Args:
        modelos: The compiled modelo definitions to inspect.

    Returns:
        Advisory lines, sorted and stable. Empty when every revision's two
        temporal declarations agree.
    """
    advisories: list[str] = []
    for modelo in modelos:
        revisions = tuple(modelo.revisions.values())
        for revision in revisions:
            validity_end = getattr(revision, "valid_to", None)
            superseding = _superseding_revisions(revision, revisions)
            if validity_end is None and superseding:
                names = ", ".join(sorted(str(sibling.id) for sibling in superseding))
                advisories.append(
                    f"modelo {modelo.id} revision {revision.id}: superseded by {names} but declares no "
                    "validity terminus, so the corpus states both govern the same periods from the "
                    "successor's start onward",
                )
            year_to = _selector_year_to(revision)
            if validity_end is None and year_to is not None:
                advisories.append(
                    f"modelo {modelo.id} revision {revision.id}: selector is bounded at year {year_to} "
                    "but the declared validity end is open, so the two declarations disagree about when "
                    "this revision stops applying",
                )
            year_from = _selector_year_from(revision)
            if year_from is not None and year_from != revision.valid_from.year:
                advisories.append(
                    f"modelo {modelo.id} revision {revision.id}: selector starts at year {year_from} but "
                    f"declared validity starts {revision.valid_from.isoformat()}; one of the two is wrong "
                    "about when this revision begins",
                )
    return tuple(sorted(advisories))
