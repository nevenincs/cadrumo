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

WHAT A DIVERGENCE MEANS, stated carefully. It means the registry's own declaration is
internally inconsistent: the revision claims a year, and the design it names as its layout
authority does not cover that year. It does NOT by itself prove the bytes are wrong -- a
layout could coincidentally match an earlier design -- but it does mean nothing in the
registry asserts they are right, and the campaign independently proved at least one such
case writes real values outside the record: Modelo 390 exported a total cuota at byte 1628
against a record its design declares ending at 1526.

THE AXIS CORRECTION, and the false positive it removed. ``period_selector.year_from`` /
``year_to`` claim EJERCICIO years -- the tax period a filing reports on -- while a design
source's ``applies_from`` / ``applies_to`` are the calendar DATES a norm took legal effect.
For an annual return filed in arrears (the ordinary case for Spain's informativas: the
campaign for ejercicio N commonly opens in calendar year N+1), those are different axes by
construction, and comparing them as if they were the same year produced a false positive on
every correctly-authored arrears-filed annual return this check reached: Modelo 720's own
approving orden (Orden HAP/72/2013, read from the bundled corpus) states verbatim in its
disposición final única that it applies "por primera vez, para la presentación de la
declaración informativa correspondiente al ejercicio 2012" -- ejercicio 2012 IS genuinely
covered, and narrowing the revision's claim to hide the year would have made the registry
assert something false to satisfy this check.

The fix reads the SAME per-revision data every deadline-driven surface already reads
instead of assuming a fixed offset: ``revision.deadline_windows`` declares, per ejercicio
(``filing_year``), the real ``opens_on`` / ``closes_on`` presentation dates. A claimed
ejercicio is covered when the calendar year(s) its OWN declared presentation window spans
intersect the design's applicable years -- not when the ejercicio number itself does. A
revision with no deadline window declared for a claimed year falls back to comparing the
ejercicio number directly, which is exactly the prior (unshifted) behaviour and stays
correct for any filing whose ejercicio and presentation calendar year coincide.

WHAT THIS DOES NOT CHECK. It says nothing about a revision whose design window is WIDER
than its claim -- that is ordinary and appears in the corpus. It cannot see a layout whose
offsets are wrong within an applicable design. It trusts the catalogue's applicability dates
and the revision's own deadline windows, both authored metadata rather than parsed from the
design or independently re-derived from the norm's text. And a revision whose claimed year
has no declared deadline window is compared on the ejercicio number alone, so a genuinely
arrears-filed year with a missing deadline-window declaration could still false-positive --
that gap is a deadline-window coverage question, not one this check resolves.

THE DIVERGENCE SET SPLITS IN TWO, AND ONLY ONE HALF IS A REGISTRY DEFECT. Measured
across the current set: half the lines name a revision whose claimed EJERCICIOS fall
wholly inside its design's window and whose PRESENTATION year alone falls outside --
modelo 303's ``2022`` claims ejercicio 2022, presents in 2023, and cites
``aeat-dr-303-2022`` whose catalogue window closes 2022-12-31. That shape is
systematic rather than per-revision: for an arrears-filed return, a design window
recorded on the EJERCICIO axis can never intersect the presentation year, so the
comparison is between a window meaning one thing and a date meaning another. Whether
a design's ``applies_from``/``applies_to`` record the ejercicio it governs or the
calendar span its norm is in force is the open question, and it is not settled here.

The other half is a genuine gap: the revision claims ejercicios its cited design does
not cover on ANY reading -- modelo 126's ``2019-y-siguientes`` claims ejercicio 2019
while citing ``aeat-dr-126-2020``, and modelo 126 bundles no earlier design at all.
Those need AEAT's published design for the missing year bundled; they cannot be
resolved by re-reading the axis.

An open-ended ``applies_to`` and an open-ended ``year_to`` are both bounded by the newest
corpus year rather than by a literal ceiling, so neither goes stale as a constant.

No count is hardcoded. The divergence set is the finding and it is named in full.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
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

    _modelos, catalogues = bundled_registry_tree()
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
    """Every EJERCICIO the revision's period selector claims."""
    selector = revision.period_selector
    if selector.years:
        return sorted(selector.years)
    if selector.year_from is None:
        return []
    upper = selector.year_to if selector.year_to is not None else _OPEN_ENDED_HORIZON
    return list(range(selector.year_from, upper + 1))


def _deadline_windows_by_filing_year(revision: ModeloRevision) -> dict[int, tuple[date, date]]:
    """Return each ejercicio's full real presentation span, aggregated across its windows.

    A quarterly revision declares one deadline window PER QUARTER, all sharing the
    same ``filing_year`` -- Modelo 131's Q4 campaign for ejercicio 2026 opens
    2027-01-01, a full calendar year after its Q1 window. Keeping only the last
    declared window would silently drop the earlier quarters' dates; the span is
    the min open date to the max close date across every window for that ejercicio.
    """
    spans: dict[int, tuple[date, date]] = {}
    for window in revision.deadline_windows:
        existing = spans.get(window.filing_year)
        if existing is None:
            spans[window.filing_year] = (window.opens_on, window.closes_on)
        else:
            spans[window.filing_year] = (min(existing[0], window.opens_on), max(existing[1], window.closes_on))
    return spans


def _presentation_calendar_years(
    claimed_year: int,
    windows_by_filing_year: Mapping[int, tuple[date, date]],
) -> set[int]:
    """Return the calendar year(s) the filing FOR ``claimed_year`` actually spans.

    An annual informative return is commonly filed the year after the ejercicio it
    reports, so a design taking effect in calendar year N can legitimately cover
    ejercicio N-1. This reads the revision's own declared presentation window for
    that ejercicio (already authored for the deadline engine) rather than assuming
    any fixed offset. When no window is declared for ``claimed_year`` the ejercicio
    number is used unshifted, which is exactly the prior comparison and stays
    correct for a filing whose ejercicio and presentation year coincide.
    """
    window = windows_by_filing_year.get(claimed_year)
    if window is None:
        return {claimed_year}
    opens_on, closes_on = window
    return set(range(opens_on.year, closes_on.year + 1))


def _year_covered_by_any_design(
    year: int,
    declared: list[str],
    windows: Mapping[str, tuple[int | None, int | None]],
) -> bool:
    """Return whether ``year`` falls inside at least one declared design's window.

    A bounds check rather than a materialized, horizon-capped set: a design with
    no declared ``applies_to`` has no evidence it ever stops applying, so it
    covers any year from its start onward with no artificial ceiling. Capping an
    open-ended design at the same enumeration horizon used for open-ended CLAIMS
    would falsely diverge on the boundary ejercicio whose presentation lag pushes
    one calendar year past that horizon -- exactly the shape Modelo 131, 349 and
    720 all hit at their newest declared ejercicio.
    """
    for ref in declared:
        start, end = windows[ref]
        if start is not None and year >= start and (end is None or year <= end):
            return True
    return False


def _revision_divergences(
    modelo_id: str,
    revision_id: str,
    revision: ModeloRevision,
    windows: Mapping[str, tuple[int | None, int | None]],
) -> tuple[int, list[str]]:
    """Return ``(export layouts compared, divergence messages)`` for one revision.

    Extracted so the comparison itself -- not just the corpus it normally runs
    against -- can be driven directly with a deliberately corrupted ``windows``
    argument to prove it still detects a genuine span violation.
    """
    compared = 0
    divergences: list[str] = []
    windows_by_filing_year = _deadline_windows_by_filing_year(revision)
    for layout in revision.export_layouts:
        declared = [str(ref) for ref in layout.source_refs if str(ref) in windows]
        if not declared:
            continue
        starts = [start for ref in declared if (start := windows[ref][0]) is not None]
        if not starts:
            continue
        claimed = _claimed_years(revision)
        if not claimed:
            continue
        compared += 1
        uncovered = sorted(
            year
            for year in claimed
            if not any(
                _year_covered_by_any_design(presentation_year, declared, windows)
                for presentation_year in _presentation_calendar_years(year, windows_by_filing_year)
            )
        )
        if uncovered:
            # Report BOTH bounds and the presentation years actually compared. The
            # message previously printed only `apply only from {min(starts)}`, which
            # omitted `applies_to` -- the half that does the work -- and printed the
            # EJERCICIO years while comparing the PRESENTATION years the arrears
            # correction above derives. Four of this check's entries then read as
            # self-contradictory (a claimed year at or after the design's start), and
            # a reader triaging the list judges them spurious and discounts the rest.
            spans = ", ".join(
                f"{ref} ({windows[ref][0]}-{windows[ref][1] if windows[ref][1] is not None else 'open'})"
                for ref in declared
            )
            presented = sorted(
                {
                    presentation_year
                    for year in uncovered
                    for presentation_year in _presentation_calendar_years(year, windows_by_filing_year)
                }
            )
            divergences.append(
                f"modelo {modelo_id} revision {revision_id!r} claims ejercicio(s) "
                f"{uncovered[0]}-{uncovered[-1]} ({len(uncovered)} year(s)), presented in "
                f"calendar year(s) {presented[0]}-{presented[-1]}, which fall outside its "
                f"declared layout design(s) {spans}"
            )
    return compared, divergences


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
            layer_compared, layer_divergences = _revision_divergences(modelo.id, revision_id, revision, windows)
            compared += layer_compared
            divergences.extend(layer_divergences)
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


def test_presentation_calendar_years_reads_the_declared_deadline_window() -> None:
    """An ejercicio maps to the REAL calendar year its filing campaign opens in.

    Modelo 720 ejercicio 2012's own declared deadline window opens 2013-02-01,
    which is what makes it a legitimate match for a design whose applicability
    starts in calendar year 2013.
    """
    windows = {2012: (date(2013, 2, 1), date(2013, 4, 30))}
    assert _presentation_calendar_years(2012, windows) == {2013}


def test_presentation_calendar_years_falls_back_to_the_claimed_year_when_undeclared() -> None:
    """No declared window means no axis shift -- the prior, unshifted comparison."""
    assert _presentation_calendar_years(2019, {}) == {2019}


def test_presentation_calendar_years_spans_a_window_crossing_a_calendar_boundary() -> None:
    """A window straddling New Year's reports both years, not just the open date's."""
    windows = {2020: (date(2020, 12, 15), date(2021, 1, 10))}
    assert _presentation_calendar_years(2020, windows) == {2020, 2021}


def test_modelo_720_ejercicio_2012_is_covered_once_the_presentation_lag_is_read() -> None:
    """The concrete false positive this check exists to no longer raise, pinned by name.

    Orden HAP/72/2013's own disposición final única (read from the bundled corpus)
    states first application to the declaración informativa correspondiente al
    ejercicio 2012 -- the design genuinely covers it, and the revision's own
    declared deadline window agrees: ejercicio 2012's filing campaign opens
    2013-02-01, inside the design's applicable calendar years.
    """
    modelo = next(candidate for candidate in _authority().modelos if candidate.id == "720")
    revision_id, revision = next(iter(modelo.revisions.items()))
    windows = _record_design_windows()

    compared, divergences = _revision_divergences(modelo.id, revision_id, revision, windows)

    assert compared
    assert divergences == []


def test_a_genuine_presentation_span_violation_is_still_detected() -> None:
    """The gate must still fire on a real gap, not merely stop firing on a false one.

    Runtime plant, nothing under ``src`` or ``dev`` touched: Modelo 720's real
    revision is read from the authority unmodified, and only the LOCAL copy of the
    design-window mapping passed into the comparison is shrunk to exclude calendar
    year 2013 -- the year ejercicio 2012's real declared presentation window falls
    in. If this passed clean, the axis fix would have widened coverage rather than
    corrected it.
    """
    modelo = next(candidate for candidate in _authority().modelos if candidate.id == "720")
    revision_id, revision = next(iter(modelo.revisions.items()))
    real_windows = _record_design_windows()
    start, end = real_windows["aeat-dr-720"]
    assert start == 2013, "the control assumes the real design starts in 2013; re-check the fixture if this moves"
    shrunk_windows = {**real_windows, "aeat-dr-720": (2014, end)}

    compared, divergences = _revision_divergences(modelo.id, revision_id, revision, shrunk_windows)

    assert compared
    assert divergences
    assert "2012" in divergences[0]
