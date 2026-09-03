"""Report screen conditions whose populations coincide, as candidate duplicates.

This package's subject is the same fact declared twice. Its instruments have the
same problem: eighteen screens report about one corpus, and two of them can
describe one condition in two vocabularies without either author noticing.

One such pair has already been found and retired by hand.
``modelo_capability.layout_without_filing_grade`` reported exactly the revisions
that ``grade_earned.under_declared`` already reported with prerequisite
``export_layout`` - not similar populations, the same set. Finding it took
exporting both and comparing them by hand. This does that comparison for every
pair.

Two relations are reported, and every row names one of them:

- ``identical`` - two conditions name exactly the same revisions. The strongest
  candidate: whatever one says, the other says about the same population.
- ``contained`` - one condition's revisions are a proper subset of another's.
  Weaker and still worth a look, because a condition that fires only where
  another already fires may be the second's special case wearing its own name.
  The precedence guard on ``files_here_for_years_it_cannot_date`` exists because
  two deadline conditions were found in exactly this relation.

Partial overlap is NOT reported. Two conditions sharing some revisions is the
normal state of a corpus where a few modelos carry most of the defects, and
reporting it would bury the two relations above in hundreds of rows that mean
nothing.

**Coincidence is not duplication, and this reports the first.** The corpus has
128 revisions and several conditions fire on one or two of them; two unrelated
conditions both firing on modelo 165's stub are identical by this measure and
share nothing but a subject. That is why this reports and does not gate, and why
each row carries its population size - a one-revision identity is a coincidence
to glance at, and a twenty-revision identity is a duplicate to investigate.

This is not a screen. It reports about the screens rather than about the
registry, its unit is a pair of conditions rather than a modelo, and it
therefore declares no screen entry point and is enrolled in no runner table.

Empty populations are excluded rather than compared. Several screens report per
modelo or per design and carry no revision to compare, so their populations are
empty and every pair of them would read as identical - which would be this
report inventing the exact defect it exists to find.

Comparison happens at the finest unit BOTH conditions carry, and the row says
which. Comparing at the revision when both conditions speak about fields
manufactures relationships out of aggregation: the first version of this report
put ``money_split_representation`` inside ``money_without_scale`` at the top of
its output, and the two are an ``if``/``elif`` on one field - mutually exclusive
by construction, and merely landing in the same five revisions. That is the same
error as measuring revision overlap by calendar year instead of by year and
period, arriving in a different package on the same afternoon.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .corpus import bundled_modelo_ids
from .screens import screen_findings

__all__ = [
    "RELATIONS",
    "UNITS",
    "ConditionPopulation",
    "ConditionRelation",
    "condition_populations",
    "overlapping_conditions",
]

#: Every relation this report can assign, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
RELATIONS: Final[tuple[str, ...]] = ("identical", "contained")

#: Every unit a comparison can be made at, coarsest last. A pair is compared at
#: the first of these that both sides carry.
UNITS: Final[tuple[str, ...]] = ("field", "casilla", "revision")

#: The finding attribute that identifies each unit beyond the revision, in the
#: same order. Declared beside the unit names so a unit cannot be added without
#: saying how to read it.
_UNIT_ATTRIBUTES: Final[dict[str, str]] = {"field": "field_id", "casilla": "casilla_id"}


@dataclass(frozen=True, slots=True)
class ConditionPopulation:
    """One condition's findings, keyed at every unit they can be read at.

    A condition carries a finer unit only when EVERY one of its findings does.
    A partial one would make two conditions look disjoint because half their
    rows were keyed differently, which is a false negative and the worse of the
    two errors this report can make.
    """

    units: dict[str, frozenset[tuple[str, ...]]]

    def finest_shared(self, other: ConditionPopulation) -> str:
        """Return the finest unit both populations carry."""
        return next(unit for unit in UNITS if unit in self.units and unit in other.units)


@dataclass(frozen=True, slots=True)
class ConditionRelation:
    """Two conditions whose revision populations coincide."""

    left: str
    right: str
    relation: str
    #: The unit the two populations were compared at, which is the finest both
    #: carry. A revision-level row about two conditions that both speak of
    #: fields would be an artifact of aggregation rather than a finding.
    unit: str
    #: How many revisions the smaller population holds. A one-revision identity
    #: is a coincidence; a large one is a candidate duplicate. Carried so the
    #: distinction is the reader's to make rather than this module's.
    shared: int
    left_size: int
    right_size: int

    @property
    def density(self) -> float:
        """What fraction of the larger population the smaller one occupies.

        Containment in a big population is nearly free and says almost nothing.
        The provenance condition names 88 of the corpus's 128 revisions, so
        nine of the nineteen pairs found are containments in it - a condition
        firing anywhere is likely inside it, and that is a fact about its size
        rather than a relationship between the two.

        The rows that carried a real relationship stood out by this figure:
        ``files_here_for_years_it_cannot_date`` occupies two thirds of
        ``window_year_without_deadline``, and the provenance containments
        occupy under a tenth. Reported rather than filtered, because where the
        threshold sits is a reader's judgement and a cutoff written here would
        silently drop the next real pair that falls beneath it.
        """
        larger = max(self.left_size, self.right_size)
        return self.shared / larger if larger else 0.0


def condition_populations(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> dict[str, ConditionPopulation]:
    """Return each condition's findings keyed at every unit they can be read at.

    Census screens are excluded: their rows are transitions examined rather than
    findings, so their population is every revision with fields and would
    contain almost every other condition. Screens declaring a source they derive
    from are excluded for the opposite reason - they re-describe that source's
    findings, so the pair is identical BY CONSTRUCTION and reporting it as a
    candidate duplicate would be reporting a declared relationship as a
    discovery.

    A finer unit is kept only when every finding of the condition carries it.
    """
    from .screens import CORPUS_SCREENS, SCREENS

    excluded = {
        entry.name
        for entry in (*SCREENS, *CORPUS_SCREENS)
        if entry.entry_returns == "census" or getattr(entry, "derives_from", None) is not None
    }
    rows: dict[str, list[tuple[str, str, object]]] = collections.defaultdict(list)
    for name, findings in screen_findings(authority, modelo_ids):
        if name in excluded:
            continue
        for finding in findings:
            kind = getattr(finding, "kind", name)
            modelo = getattr(finding, "modelo", None)
            revision = getattr(finding, "revision", None)
            if modelo is None or revision is None:
                continue
            label = f"{name}.{kind if isinstance(kind, str) else name}"
            rows[label].append((str(modelo), str(revision), finding))

    populations: dict[str, ConditionPopulation] = {}
    for label, findings in rows.items():
        if not findings:
            continue
        units: dict[str, frozenset[tuple[str, ...]]] = {
            "revision": frozenset((modelo, revision) for modelo, revision, _ in findings)
        }
        for unit, attribute in _UNIT_ATTRIBUTES.items():
            keyed = [(modelo, revision, getattr(finding, attribute, None)) for modelo, revision, finding in findings]
            if any(value is None for _, _, value in keyed):
                continue
            units[unit] = frozenset((modelo, revision, str(value)) for modelo, revision, value in keyed)
        populations[label] = ConditionPopulation(units=units)
    return populations


def overlapping_conditions(
    populations: dict[str, ConditionPopulation],
) -> tuple[ConditionRelation, ...]:
    """Return every identical or properly contained pair, at their finest unit.

    Separated from the walk so both relations can be shown to be reported from
    input written in a test. A report whose relations have no constructed proof
    stops distinguishing them the moment the corpus stops containing one.

    Each unordered pair yields at most one row: ``identical`` is symmetric and
    would otherwise be reported twice, and ``contained`` names the smaller side
    on the left so the row reads in one direction.
    """
    relations: list[ConditionRelation] = []
    names = sorted(populations)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            unit = populations[left].finest_shared(populations[right])
            first, second = populations[left].units[unit], populations[right].units[unit]
            if first == second:
                smaller, larger, low, high = left, right, first, second
                relation = "identical"
            elif first < second:
                smaller, larger, low, high = left, right, first, second
                relation = "contained"
            elif second < first:
                smaller, larger, low, high = right, left, second, first
                relation = "contained"
            else:
                continue
            relations.append(
                ConditionRelation(
                    left=smaller,
                    right=larger,
                    relation=relation,
                    unit=unit,
                    shared=len(low),
                    left_size=len(low),
                    right_size=len(high),
                )
            )
    return tuple(sorted(relations, key=lambda item: (-item.density, -item.shared, item.left, item.right)))


def main() -> int:
    """Print one row per coinciding pair, largest population first; always exit 0."""
    authority = bundled_authority()
    populations = condition_populations(authority, bundled_modelo_ids())
    relations = overlapping_conditions(populations)
    for item in relations:
        sys.stdout.write(
            f"condition_overlap relation={item.relation} left={item.left} right={item.right} "
            f"unit={item.unit} shared={item.shared} left_size={item.left_size} "
            f"right_size={item.right_size} "
            f"density={item.density:.2f}\n"
        )
    tally: collections.Counter[str] = collections.Counter(item.relation for item in relations)
    census = " ".join(f"{relation}={tally[relation]}" for relation in RELATIONS)
    sys.stdout.write(f"summary conditions={len(populations)} pairs={len(relations)} {census}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
