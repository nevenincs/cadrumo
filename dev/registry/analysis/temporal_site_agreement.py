"""Screen: whether a revision's several temporal declaration sites agree with each other.

A revision states its temporal facts in more than one place. ``valid_from`` and
``valid_to`` carry the window. The period selector carries ``year_from`` and
``year_to``, and separately an explicit ``years`` tuple that says the same kind
of thing a different way. The deadline windows each carry a ``filing_year``,
which is a third statement of which years the revision serves. Nothing compares
them, so they can disagree and the registry validates.

This screen compares the sites that the revision-name screen does not cover.
The name-against-window comparison lives there; duplicating it here would give
one condition two owners.

Four disagreements are reported:

- ``deadline_year_outside_window`` - a deadline window is declared for a filing
  year the revision's own window excludes. One of the two is wrong and the
  registry cannot tell which.
- ``window_year_without_deadline`` - a year inside a CLOSED declared window has
  no deadline window. Open-ended windows are skipped here rather than assumed
  to run to some horizon, because inventing an end date to measure against
  would manufacture findings that the declaration does not support.
- ``selector_dual_form`` - the selector carries both an explicit ``years``
  tuple and a ``year_from``/``year_to`` bound. Both describe the served years,
  and a reader has no rule for which wins.
- ``no_deadline_windows`` - a revision declares no deadline window at all,
  reported so that a silent absence is distinguishable from a year-by-year gap.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus import bundled_modelo_ids

__all__ = [
    "YEAR_LEVEL_TEMPORAL_SITES",
    "TemporalSiteFinding",
    "screen_authority",
    "site_agreement_findings",
    "undated_window_years",
    "unserved_interior_years",
]

#: Every declared field that states which YEARS a revision serves, as a dotted
#: path from the revision. Data rather than prose, because the number of places
#: one temporal fact is restated is the measurement this whole package exists to
#: support, and a figure carried only in a sentence cannot be re-derived.
#:
#: The boundary is year-level claims. A deadline window also carries `opens_on`,
#: `closes_on` and `payment_cutoff_on`, which say WHEN within a year a filing is
#: due rather than WHICH years the revision serves; they are dates, not another
#: statement of the window, and folding them in would inflate the count with
#: facts that cannot disagree with it.
#:
#: The revision's directory name is a further site and is deliberately absent:
#: it is not a declared field, and the name-against-window comparison is owned
#: by the sibling screen. Counting it here would give one condition two owners.
YEAR_LEVEL_TEMPORAL_SITES: tuple[str, ...] = (
    "valid_from",
    "valid_to",
    "period_selector.year_from",
    "period_selector.year_to",
    "period_selector.years",
    "deadline_windows.filing_year",
)


@dataclass(frozen=True, slots=True)
class TemporalSiteFinding:
    """One disagreement between two of a revision's temporal declaration sites."""

    modelo: str
    revision: str
    kind: str
    detail: str


def unserved_interior_years(spans: tuple[tuple[int, int | None], ...]) -> tuple[int, ...]:
    """Return years inside a modelo's own span that none of its revisions serves.

    ``spans`` is one ``(first_year, last_year)`` pair per revision, with ``None``
    for a revision that never closes. The interior is measured from the earliest
    year any revision serves, never from a fixed year: the corpus's modelos begin
    anywhere from 2003 to 2026, and years before a modelo's first revision are
    outside the registry's reach rather than missing from it. Modelo 322 carries
    a revision directory named `2008-2022` that serves 2022 alone, which reads
    like a fourteen-year hole and is not one.

    Open-ended revisions are closed at the latest year any revision mentions, so
    the newest revision running open-ended contributes no gap to a horizon
    nobody declared.

    Separated from the gate that uses it so a constructed gap can be shown to be
    caught. A gate over a corpus with no instance of its condition proves the
    corpus clean and says nothing about the gate.
    """
    closed = [(start, end) for start, end in spans if end is not None]
    if not closed:
        return ()
    open_starts = [start for start, end in spans if end is None]
    horizon = max(max(end for _, end in closed), *(open_starts or [0]))
    served: set[int] = set()
    for start, end in closed:
        served |= set(range(start, end + 1))
    for start in open_starts:
        served |= set(range(start, horizon + 1))
    return tuple(year for year in range(min(served), max(served) + 1) if year not in served)


def undated_window_years(revision: ModeloRevision) -> tuple[int, ...]:
    """Return years inside a revision's CLOSED window that no deadline window covers.

    The one home for this computation. The capability screen needs the same
    years to say that a filing-grade revision cannot date some of the years it
    serves, and its first version read them back out of this screen's finding
    prose - which is a second implementation wearing a disguise, and one that
    would return nothing at all if this wording were reworded.

    An open window yields nothing: a revision that never closes has no last year
    to enumerate to, and demanding a deadline for every year to come would be
    asking it to predict them.
    """
    opening = revision.valid_from.year
    closing = None if revision.valid_to is None else revision.valid_to.year
    if closing is None:
        return ()
    declared = {window.filing_year for window in revision.deadline_windows}
    return tuple(year for year in range(opening, closing + 1) if year not in declared)


def site_agreement_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[TemporalSiteFinding, ...]:
    """Compare one revision's window, period selector and deadline windows."""
    findings: list[TemporalSiteFinding] = []
    selector = revision.period_selector
    opening = revision.valid_from.year
    closing = revision.valid_to.year if revision.valid_to is not None else selector.year_to

    if selector.years and selector.year_from is not None:
        findings.append(
            TemporalSiteFinding(
                modelo=modelo_id,
                revision=str(revision.id),
                kind="selector_dual_form",
                detail=f"years={list(selector.years)} and year_from={selector.year_from}",
            )
        )

    deadline_years = sorted({window.filing_year for window in revision.deadline_windows})
    if not deadline_years:
        findings.append(
            TemporalSiteFinding(
                modelo=modelo_id,
                revision=str(revision.id),
                kind="no_deadline_windows",
                detail=f"window opens {opening} and declares no deadline window",
            )
        )
        return tuple(findings)

    for year in deadline_years:
        if year < opening or (closing is not None and year > closing):
            findings.append(
                TemporalSiteFinding(
                    modelo=modelo_id,
                    revision=str(revision.id),
                    kind="deadline_year_outside_window",
                    detail=f"deadline filing_year={year} outside window {opening}..{closing}",
                )
            )

    if closing is not None:
        missing = list(undated_window_years(revision))
        if missing:
            findings.append(
                TemporalSiteFinding(
                    modelo=modelo_id,
                    revision=str(revision.id),
                    kind="window_year_without_deadline",
                    detail=f"closed window {opening}..{closing} has no deadline window for {missing}",
                )
            )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[TemporalSiteFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[TemporalSiteFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            findings.extend(site_agreement_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    census: collections.Counter[str] = collections.Counter(finding.kind for finding in findings)
    for finding in findings:
        sys.stdout.write(
            f"temporal_site modelo={finding.modelo} revision={finding.revision} "
            f"kind={finding.kind} detail={finding.detail!r}\n"
        )
    tally = " ".join(f"{kind}={count}" for kind, count in sorted(census.items()))
    sys.stdout.write(f"summary findings={len(findings)} {tally}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
