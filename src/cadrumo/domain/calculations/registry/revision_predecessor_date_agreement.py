"""A declared predecessor agrees with the editions' validity dates.

An edition naming a sibling as its predecessor claims it follows that sibling.
Where the two editions could never be live at once, that claim has a direction
the dates can check: the named predecessor must take effect strictly before its
successor. A successor naming an edition that starts later, or on the same day,
is refused naming both editions and their windows.

A pair whose period selectors overlap is exempt. Overlapping editions are the
parallel-variant case, scheme variants sharing one validity window, and no date
order exists between them for a declaration to contradict.

Where it stops:

- Only named edges are judged. An edition declaring no predecessor, or omitting
  the key, claims no order, and the forest rule owns whether those declarations
  are well formed. Run that rule first: a named target that is not an edition
  here is refused, but not explained the way the forest rule explains it.
- Overlap is decided by the period selectors alone, exactly as every other
  revision-overlap check decides it; order is decided by ``valid_from`` alone.
  Whether an edition's ``valid_from`` and ``valid_to`` agree with its own
  selector is not judged here.
- Agreement is checked per edge. It does not require the named predecessor to
  be the nearest earlier edition, so a successor skipping an intermediate
  edition passes.

The input is plain edition ids and windows, so the typed modelo validator and
any caller holding raw manifests apply the same rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from .errors import RegistryValidationError
from .period_selector_overlap import period_selectors_overlap
from .schema_references import PeriodSelector

__all__ = ("EditionWindow", "validate_predecessor_date_agreement")


@dataclass(frozen=True, slots=True)
class EditionWindow:
    """The validity an edition declares: its dates and its period selector."""

    valid_from: date
    valid_to: date | None
    period_selector: PeriodSelector


def validate_predecessor_date_agreement(
    modelo_id: str,
    *,
    named: Mapping[str, str],
    windows: Mapping[str, EditionWindow],
) -> None:
    """Refuse a named predecessor that does not start before its non-overlapping successor.

    ``named`` maps each edition that names a sibling to that sibling's id;
    ``windows`` holds every edition's declared validity.

    Raises:
        RegistryValidationError: When a named edition or its target has no
            window, or when a successor and its named predecessor do not
            overlap and the predecessor does not take effect strictly earlier.
    """
    for edition, target in sorted(named.items()):
        successor = windows.get(edition)
        predecessor = windows.get(target)
        if successor is None or predecessor is None:
            missing = edition if successor is None else target
            raise RegistryValidationError(
                f"modelo {modelo_id!r} revision {missing!r} has no declared validity window "
                f"to check the predecessor edge {edition!r} -> {target!r} against",
            )
        if period_selectors_overlap(successor.period_selector, predecessor.period_selector):
            continue
        if predecessor.valid_from < successor.valid_from:
            continue
        raise RegistryValidationError(
            f"modelo {modelo_id!r} revision {edition!r} {_describe(successor)} declares predecessor "
            f"{target!r} {_describe(predecessor)}, which does not take effect before it; the two editions "
            "do not overlap, so the declared predecessor must be the earlier edition",
        )


def _describe(window: EditionWindow) -> str:
    valid_to = window.valid_to.isoformat() if window.valid_to is not None else "open"
    selector = window.period_selector
    if selector.years:
        years = ", ".join(str(year) for year in selector.years)
    elif selector.year_from is None:
        years = "any year"
    else:
        years = f"{selector.year_from} to {selector.year_to if selector.year_to is not None else 'open'}"
    periods = ", ".join(str(period) for period in selector.periods)
    return f"(valid {window.valid_from.isoformat()} to {valid_to}; years {years}; periods {periods})"
