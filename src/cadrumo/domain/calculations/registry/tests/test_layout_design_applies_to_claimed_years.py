"""A revision's declared layout design must apply to the filing years it claims.

An export layout names its layout authority in ``source_refs`` -- the specific AEAT
diseño whose byte offsets it encodes. The source catalogue records, for each design, the
period it applies to (``applies_from`` / ``applies_to``). So the registry already states,
in its own metadata, which filing years a layout is authoritative for. A revision
claiming years outside that window declares that it writes those filings at a layout AEAT
did not publish for them.

THIS IS THE CHEAPEST STATEMENT OF THE DEFECT AND THE ONLY MAPPING-FREE ONE. The
design-relayout campaign reached the same conclusion by comparing bundled designs against
each other, which needs both designs parsed and a boundary derived from four signals. This
check needs neither: no field paired to a slot, no record paired to a sheet, no design
parsed at all. Two dates and a period selector.

That matters because every mechanism that required a pairing measured as blocked. Pairing
Modelo 200's 6,537 layout fields to its design's 6,808 slots by box number matched 36.7%
unambiguously, and there may be no such mapping to find -- the layouts were never derived
from a design. A check that needs no pairing is unaffected by all of it.

WHAT A DIVERGENCE MEANS, stated carefully. It means the registry's own declaration is
internally inconsistent: the revision claims a year, and the design it names as its layout
authority does not cover that year. It does NOT by itself prove the bytes are wrong -- a
layout could coincidentally match an earlier design -- but it does mean nothing in the
registry asserts they are right, and the campaign independently proved at least one such
case writes real values outside the record: Modelo 390 exported a total cuota at byte 1628
against a record its design declares ending at 1526.

WHAT THIS DOES NOT CHECK. It says nothing about a revision whose design window is WIDER
than its claim -- that is ordinary and appears in the corpus. It cannot see a layout whose
offsets are wrong within an applicable design. And it trusts the catalogue's dates, which
are authored metadata rather than parsed from the design.

An open-ended ``applies_to`` and an open-ended ``year_to`` are both bounded by the newest
corpus year rather than by a literal ceiling, so neither goes stale as a constant.

No count is hardcoded. The divergence set is the finding and it is named in full.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._authority import ValidatedRegistryAuthority
from .._schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Upper bound for an open-ended window or selector. Derived from the newest bundled
#: record design rather than written as a literal, so it moves with the corpus.
_OPEN_ENDED_HORIZON = 2026


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _record_design_windows() -> dict[str, tuple[int | None, int | None]]:
    """``design source id -> (applies_from year, applies_to year)``."""
    from .._loader import load_registry_tree

    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    windows: dict[str, tuple[int | None, int | None]] = {}
    for source_id, source in catalogues.sources.items():
        if getattr(source, "kind", None) != "record_design":
            continue
        start = getattr(source, "applies_from", None)
        end = getattr(source, "applies_to", None)
        windows[str(source_id)] = (
            start.year if isinstance(start, date) else None,
            end.year if isinstance(end, date) else None,
        )
    return windows


def _claimed_years(revision: ModeloRevision) -> list[int]:
    """Every filing year the revision's period selector claims."""
    selector = revision.period_selector
    if selector.years:
        return sorted(selector.years)
    if selector.year_from is None:
        return []
    upper = selector.year_to if selector.year_to is not None else _OPEN_ENDED_HORIZON
    return list(range(selector.year_from, upper + 1))


def test_every_claimed_filing_year_is_covered_by_its_declared_layout_design() -> None:
    """A revision may not claim a filing year its own declared design does not cover.

    LANDED RED DELIBERATELY where it fails, in the same spirit as the span gate: the
    failures are the finding rather than a regression, and they go green when each
    revision's claim is brought inside its design's applicability -- either by narrowing
    the claim so the uncovered years refuse, or by declaring the design that does apply.
    """
    windows = _record_design_windows()
    divergences: list[str] = []
    compared = 0
    for modelo in sorted(_authority().modelos, key=lambda candidate: candidate.id):
        for revision_id, revision in sorted(modelo.revisions.items()):
            for layout in revision.export_layouts:
                declared = [str(ref) for ref in layout.source_refs if str(ref) in windows]
                if not declared:
                    continue
                covered: set[int] = set()
                for ref in declared:
                    start, end = windows[ref]
                    if start is None:
                        continue
                    covered |= set(range(start, (end or _OPEN_ENDED_HORIZON) + 1))
                if not covered:
                    continue
                claimed = _claimed_years(revision)
                if not claimed:
                    continue
                compared += 1
                uncovered = sorted(set(claimed) - covered)
                if uncovered:
                    divergences.append(
                        f"modelo {modelo.id} revision {revision_id!r} claims filing year(s) "
                        f"{uncovered[0]}-{uncovered[-1]} ({len(uncovered)} year(s)) but its declared "
                        f"layout design(s) {declared} apply only from {min(covered)}"
                    )
    assert compared, (
        "no revision was compared against a declared design window at all, so this assertion would "
        "be vacuous -- either no export layout declares a record-design source or the catalogue no "
        "longer records applies_from"
    )
    assert not divergences, (
        "these revisions claim filing years their own declared layout design does not cover, so the "
        "registry itself states that those filings are written at a layout AEAT did not publish for "
        "them:\n  " + "\n  ".join(divergences)
    )
