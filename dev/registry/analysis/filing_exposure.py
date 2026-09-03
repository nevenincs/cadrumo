"""How much of each screen's population sits in a revision that can be filed.

Every screen in this package reports a disagreement between declarations. Not
every disagreement costs the same. A revision below filing grade that cannot
state a deadline, or emits an amount at an undetermined magnitude, is declaring
incompletely about something it never does; the same gap in a filing-grade
revision is a defect a filer meets.

That question has been asked one screen at a time, by hand, four times in this
campaign - of the deadline conditions, the unscaled monetary fields, the
published trees and the grade findings - and each time it reordered what
mattered. This asks it of every condition at once.

This is not a screen. It reports about the screens rather than about the
registry, its unit is a condition rather than a modelo, and it therefore
declares no screen entry point and is enrolled in no runner table. What it
produces is a reading order: a condition whose population is entirely below
filing grade can wait behind one whose population is not.

It reports and gates nothing. Filing-grade exposure is a priority, not an
invariant, and a corpus may legitimately carry a great deal of it while every
gate holds.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .corpus import bundled_modelo_ids
from .screens import screen_findings

__all__ = [
    "ConditionExposure",
    "condition_exposure",
    "filing_grade_revisions",
]

_FILING = "filing"


def filing_grade_revisions(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> frozenset[tuple[str, str]]:
    """Return every ``(modelo, revision)`` declaring filing grade."""
    return frozenset(
        (modelo_id, str(revision_id))
        for modelo_id in modelo_ids
        for revision_id, revision in authority.modelo(modelo_id).revisions.items()
        if str(getattr(revision, "authority_grade", "")) == _FILING
    )


@dataclass(frozen=True, slots=True)
class ConditionExposure:
    """One screen condition, and how much of it a filer would meet."""

    screen: str
    kind: str
    findings: int
    #: Findings whose revision declares filing grade.
    filing_findings: int
    revisions: int
    filing_revisions: int
    #: Findings carrying no revision, which were never measured against grade.
    #: Kept separate from a measured zero: several screens report per modelo or
    #: per design because that is their unit - a continuity chain spans
    #: revisions and a design transcription belongs to none - and counting them
    #: as "not filing grade" would turn an unasked question into an answer.
    unmeasured: int = 0

    @property
    def wholly_below_filing(self) -> bool:
        """Whether this condition was measured and none of it can be filed.

        False when nothing was measurable, which is a refusal to claim rather
        than a claim of safety. Eleven conditions looked wholly below filing
        grade on the first run and eight of them had simply never been asked:
        their findings carry no revision at all.
        """
        return self.filing_findings == 0 and self.findings > self.unmeasured


def condition_exposure(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ConditionExposure, ...]:
    """Return every screen condition with its filing-grade exposure.

    Findings are read from each screen's own entry point, never from the runner
    table: a table entry may project onto a subset, and a projection's exposure
    is the exposure of what survived it rather than of the condition.

    A finding carrying no revision is counted in the total and not in the filing
    figure - a continuity chain spans revisions, so asking which one it sits in
    has no answer, and guessing would report an exposure nobody measured.
    """
    filing = filing_grade_revisions(authority, modelo_ids)
    totals: collections.Counter[tuple[str, str]] = collections.Counter()
    filing_totals: collections.Counter[tuple[str, str]] = collections.Counter()
    unmeasured: collections.Counter[tuple[str, str]] = collections.Counter()
    units: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    filing_units: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)

    for name, findings in screen_findings(authority, modelo_ids):
        for finding in findings:
            kind = getattr(finding, "kind", name)
            if not isinstance(kind, str):
                kind = name
            key = (name, kind)
            totals[key] += 1
            modelo = getattr(finding, "modelo", None)
            revision = getattr(finding, "revision", None)
            if modelo is None or revision is None:
                unmeasured[key] += 1
                continue
            unit = (str(modelo), str(revision))
            units[key].add(unit)
            if unit in filing:
                filing_totals[key] += 1
                filing_units[key].add(unit)

    return tuple(
        sorted(
            (
                ConditionExposure(
                    screen=screen,
                    kind=kind,
                    findings=count,
                    filing_findings=filing_totals[(screen, kind)],
                    revisions=len(units[(screen, kind)]),
                    filing_revisions=len(filing_units[(screen, kind)]),
                    unmeasured=unmeasured[(screen, kind)],
                )
                for (screen, kind), count in totals.items()
            ),
            key=lambda item: (-item.filing_findings, item.screen, item.kind),
        )
    )


def main() -> int:
    """Print one row per condition, most filing-exposed first; always exit 0."""
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    exposures = condition_exposure(authority, modelo_ids)
    for item in exposures:
        sys.stdout.write(
            f"filing_exposure screen={item.screen} kind={item.kind} findings={item.findings} "
            f"filing_findings={item.filing_findings} revisions={item.revisions} "
            f"filing_revisions={item.filing_revisions} unmeasured={item.unmeasured} "
            f"wholly_below_filing={str(item.wholly_below_filing).lower()}\n"
        )
    exposed = [item for item in exposures if item.filing_findings]
    sys.stdout.write(
        f"summary conditions={len(exposures)} with_filing_exposure={len(exposed)} "
        f"filing_findings={sum(item.filing_findings for item in exposures)} "
        f"wholly_below_filing={sum(1 for item in exposures if item.wholly_below_filing)} "
        f"unmeasurable={sum(1 for item in exposures if item.findings == item.unmeasured)} "
        f"filing_grade_revisions={len(filing_grade_revisions(authority, modelo_ids))}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
