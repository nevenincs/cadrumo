"""A grounded row may not be asserted beyond the provision it cites.

The IVA corpora carry no year-dated text at all -- every citation names a LIVA
article and quotes it verbatim -- so the anti-mirror check that bounds an
edition-dated citation by its own edition year has nothing to read here. What
these rows do carry is a provision id, and the registry legal catalogue records
when each provision took effect and, where it has been repealed, when it stopped.

That makes the permissible span DERIVABLE rather than asserted. A row claiming
2022 through 2026 for an article in force since 1993 is a checkable fact; the
same claim for an article that only took effect in 2024 is a fabrication, and it
is the exact shape a future author would produce by widening a window to turn
this corpus's year-coverage gate green.

The check fails closed in both directions: a provision effective after the
window opens, and a provision repealed before the window closes. Where a row
cites several provisions the permissible span is their INTERSECTION -- a rule
rests on all of the articles it reads, so the earliest-ending one bounds it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.core.validity_window import ValidityWindow
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from .._catalogue import bundled_iva_catalogue
from .._place_of_supply import load_place_of_supply_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _legal_catalogue() -> dict[str, LegalReference]:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return dict(catalogues.legal)


def _permitted_span(
    references: Iterable[str],
    catalogue: dict[str, LegalReference],
) -> tuple[date, date | None]:
    """Return the intersection of the cited provisions' effective spans.

    Returns:
        The latest ``effective_from`` and the earliest ``effective_to`` among the
        cited provisions, the latter ``None`` when none of them is repealed.
    """
    starts: list[date] = []
    ends: list[date] = []
    for reference in references:
        entry = catalogue[reference]
        starts.append(entry.effective_from)
        if entry.effective_to is not None:
            ends.append(entry.effective_to)
    return max(starts), (min(ends) if ends else None)


def _violation(
    window: ValidityWindow,
    permitted_start: date,
    permitted_end: date | None,
) -> str:
    if window.valid_from < permitted_start:
        return f"window opens {window.valid_from.isoformat()} before the provision took effect {permitted_start.isoformat()}"
    if permitted_end is not None and window.valid_to > permitted_end:
        return f"window closes {window.valid_to.isoformat()} after the provision was repealed {permitted_end.isoformat()}"
    return ""


def _catalogue_rows() -> list[tuple[str, tuple[str, ...], ValidityWindow]]:
    return [
        (f"{regulation.category.value}/{citation.legal_reference}", (citation.legal_reference,), citation.window)
        for regulation in bundled_iva_catalogue()
        for citation in regulation.citations
    ]


def _place_of_supply_rows() -> list[tuple[str, tuple[str, ...], ValidityWindow]]:
    return [
        (rule.rule_id, rule.legal_references, rule.window)
        for rule in load_place_of_supply_table().values()
        if rule.window is not None
    ]


def test_every_grounded_iva_row_stays_inside_its_provisions_effective_span() -> None:
    """The whole shipped surface, measured against the catalogue on every run.

    Property, not tally: the permitted span is re-derived from the legal
    catalogue each run, so amending a provision's effective date automatically
    re-judges every row that cites it.
    """
    catalogue = _legal_catalogue()
    rows = _catalogue_rows() + _place_of_supply_rows()
    assert rows, "no grounded IVA rows were measured; this gate would pass vacuously"

    violations = []
    for label, references, window in rows:
        permitted_start, permitted_end = _permitted_span(references, catalogue)
        problem = _violation(window, permitted_start, permitted_end)
        if problem:
            violations.append(f"{label}: {problem}")

    assert violations == [], (
        "these IVA rows are asserted beyond the provisions they cite:\n  "
        + "\n  ".join(sorted(violations))
        + "\nNarrow the window to what the provision supports, or cite the provision that actually "
        "covers the wider span. Never widen a window to admit a filing year."
    )


def test_a_window_opening_before_its_provision_took_effect_is_a_violation() -> None:
    """DISCRIMINATING: the shape a future author produces by widening backwards."""
    permitted_start, permitted_end = date(2021, 7, 1), None
    window = ValidityWindow(valid_from=date(2020, 1, 1), valid_to=date(2026, 12, 31))

    assert "before the provision took effect" in _violation(window, permitted_start, permitted_end)


def test_a_window_closing_after_its_provision_was_repealed_is_a_violation() -> None:
    """DISCRIMINATING: fails closed on a repeal, which a coverage count cannot see."""
    permitted_start, permitted_end = date(1993, 1, 1), date(2023, 12, 31)
    window = ValidityWindow(valid_from=date(2022, 1, 1), valid_to=date(2026, 12, 31))

    assert "after the provision was repealed" in _violation(window, permitted_start, permitted_end)


def test_a_window_inside_the_span_is_not_a_violation() -> None:
    assert not _violation(
        ValidityWindow(valid_from=date(2022, 1, 1), valid_to=date(2026, 12, 31)),
        date(1993, 1, 1),
        None,
    )


def test_the_permitted_span_of_several_provisions_is_their_intersection() -> None:
    """A rule rests on every article it reads, so the narrowest one bounds it."""
    catalogue = _legal_catalogue()
    early = "ley-37-1992:art-68"
    late = "ley-37-1992:art-13"

    start_alone, _ = _permitted_span([early], catalogue)
    start_together, _ = _permitted_span([early, late], catalogue)

    assert catalogue[late].effective_from > catalogue[early].effective_from, (
        "the fixture provisions no longer differ in effective date; pick two that do, or this "
        "assertion proves nothing about intersection"
    )
    assert start_alone == catalogue[early].effective_from
    assert start_together == catalogue[late].effective_from


def test_every_cited_provision_resolves_in_the_legal_catalogue() -> None:
    """Anchor: an unresolvable id would make the span check silently skip a row."""
    catalogue = _legal_catalogue()
    cited = {
        reference for _label, references, _window in _catalogue_rows() + _place_of_supply_rows() for reference in references
    }

    assert cited, "no provisions were cited at all; the gate above would be vacuous"
    assert sorted(reference for reference in cited if reference not in catalogue) == []
